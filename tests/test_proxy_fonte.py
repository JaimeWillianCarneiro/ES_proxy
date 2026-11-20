"""Testes do FonteDadosProxy (Parte 3). Offline: o "cliente real" é um FonteFake."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from fakes import FonteFake, carregar_fixture
from pipeline_proxy.config import PoliticaRetry
from pipeline_proxy.dominio import LoteExtracao, Tamanho
from pipeline_proxy.erros import (
    ErroAutenticacao,
    ErroCotaEsgotada,
    ErroLimiteRequisicoes,
    ErroTransitorio,
)
from pipeline_proxy.extracao.fonte import FonteDados
from pipeline_proxy.extracao.proxy_fonte import FonteDadosProxy

CHAVE = "ABCD1234EFGH5678"
POLITICA = PoliticaRetry(tentativas=3, backoff_base_s=1.0, backoff_max_s=30.0)


class FonteInstavel(FonteFake):
    """FonteFake que lança os erros dados, um por chamada, antes de funcionar."""

    def __init__(self, payload: dict, erros: list[Exception]):
        super().__init__(payload)
        self._erros = list(erros)

    def buscar_diario(self, simbolo, tamanho=Tamanho.COMPACT):
        if self._erros:
            self.chamadas += 1
            raise self._erros.pop(0)
        return super().buscar_diario(simbolo, tamanho)


class Fabrica:
    """Fábrica do cliente que conta quantas vezes o cliente foi criado."""

    def __init__(self, cliente: FonteDados):
        self.cliente = cliente
        self.criacoes = 0

    def __call__(self) -> FonteDados:
        self.criacoes += 1
        return self.cliente


class Relogio:
    """Relógio controlável: permite "passar" horas sem esperar."""

    def __init__(self):
        self._agora = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self._agora

    def avancar(self, horas: float) -> None:
        self._agora += timedelta(hours=horas)


@pytest.fixture
def payload():
    return carregar_fixture("daily_ibm.json")


def criar_proxy(fabrica, tmp_path, *, api_key=CHAVE, relogio=None, esperas=None, **kwargs):
    return FonteDadosProxy(
        fabrica,
        api_key=api_key,
        dir_cache=tmp_path / "cache",
        politica_retry=POLITICA,
        dormir=(esperas.append if esperas is not None else (lambda s: None)),
        agora=relogio or Relogio(),
        **kwargs,
    )


# --- cache -------------------------------------------------------------------


def test_segunda_chamada_sai_do_cache(payload, tmp_path):
    cliente = FonteFake(payload)
    proxy = criar_proxy(Fabrica(cliente), tmp_path)

    proxy.buscar_diario("IBM")
    proxy.buscar_diario("IBM")

    assert cliente.chamadas == 1


def test_cache_vencido_chama_de_novo(payload, tmp_path):
    cliente = FonteFake(payload)
    relogio = Relogio()
    proxy = criar_proxy(Fabrica(cliente), tmp_path, relogio=relogio, validade=timedelta(hours=12))

    proxy.buscar_diario("IBM")
    relogio.avancar(13)
    proxy.buscar_diario("IBM")

    assert cliente.chamadas == 2


def test_cache_ainda_valido_nao_chama_de_novo(payload, tmp_path):
    cliente = FonteFake(payload)
    relogio = Relogio()
    proxy = criar_proxy(Fabrica(cliente), tmp_path, relogio=relogio, validade=timedelta(hours=12))

    proxy.buscar_diario("IBM")
    relogio.avancar(11)
    proxy.buscar_diario("IBM")

    assert cliente.chamadas == 1


def test_chave_do_cache_e_simbolo_e_tamanho(payload, tmp_path):
    cliente = FonteFake(payload)
    proxy = criar_proxy(Fabrica(cliente), tmp_path)

    proxy.buscar_diario("IBM", Tamanho.COMPACT)
    proxy.buscar_diario("IBM", Tamanho.FULL)  # tamanho diferente: não reaproveita
    proxy.buscar_diario("MSFT", Tamanho.COMPACT)  # símbolo diferente: idem

    assert cliente.chamadas == 3


def test_cache_corrompido_e_tratado_como_miss(payload, tmp_path):
    cliente = FonteFake(payload)
    proxy = criar_proxy(Fabrica(cliente), tmp_path)
    proxy.buscar_diario("IBM")
    (arquivo,) = (tmp_path / "cache").glob("IBM_*.json")
    arquivo.write_text("{ isto não é json")

    proxy.buscar_diario("IBM")

    assert cliente.chamadas == 2


def test_lote_do_cache_e_igual_ao_da_fonte(payload, tmp_path):
    """Comportamento preservado: o consumidor recebe os mesmos dados com ou sem cache."""
    proxy = criar_proxy(Fabrica(FonteFake(payload)), tmp_path)

    da_fonte = proxy.buscar_diario("IBM")
    do_cache = proxy.buscar_diario("IBM")

    pd.testing.assert_frame_equal(da_fonte.dados, do_cache.dados)
    assert isinstance(do_cache, LoteExtracao)
    assert do_cache.tamanho == da_fonte.tamanho


# --- virtual (lazy) ----------------------------------------------------------


def test_cliente_nao_e_criado_ao_construir_o_proxy(payload, tmp_path):
    fabrica = Fabrica(FonteFake(payload))

    proxy = criar_proxy(fabrica, tmp_path)

    assert fabrica.criacoes == 0
    assert not proxy.cliente_criado


def test_cliente_e_criado_so_no_primeiro_miss(payload, tmp_path):
    fabrica = Fabrica(FonteFake(payload))
    proxy = criar_proxy(fabrica, tmp_path)

    proxy.buscar_diario("IBM")
    proxy.buscar_diario("IBM")
    proxy.buscar_diario("MSFT")

    assert fabrica.criacoes == 1  # criado uma vez e reaproveitado


def test_cliente_nao_e_criado_se_tudo_vier_do_cache(payload, tmp_path):
    # Um primeiro proxy popula o cache em disco...
    criar_proxy(Fabrica(FonteFake(payload)), tmp_path).buscar_diario("IBM")

    # ...e um segundo (como numa nova execução) atende tudo sem criar o cliente.
    fabrica = Fabrica(FonteFake(payload))
    proxy = criar_proxy(fabrica, tmp_path)
    proxy.buscar_diario("IBM")

    assert fabrica.criacoes == 0
    assert proxy.chamadas_reais == 0


# --- proteção ----------------------------------------------------------------


@pytest.mark.parametrize("chave", ["", "abc", "chave com espaço", "ab/../cd12"])
def test_chave_vazia_ou_invalida_e_barrada(payload, tmp_path, chave):
    cliente = FonteFake(payload)
    fabrica = Fabrica(cliente)
    proxy = criar_proxy(fabrica, tmp_path, api_key=chave)

    with pytest.raises(ErroAutenticacao):
        proxy.buscar_diario("IBM")

    assert fabrica.criacoes == 0  # nem o cliente foi criado
    assert cliente.chamadas == 0  # e nenhuma cota foi gasta


def test_chave_demo_e_aceita(payload, tmp_path):
    proxy = criar_proxy(Fabrica(FonteFake(payload)), tmp_path, api_key="demo")

    assert not proxy.buscar_diario("IBM").vazio


# --- retry -------------------------------------------------------------------


def test_retry_recupera_de_falha_transitoria(payload, tmp_path):
    cliente = FonteInstavel(payload, [ErroLimiteRequisicoes("1 por segundo")] * 2)
    esperas: list[float] = []
    proxy = criar_proxy(Fabrica(cliente), tmp_path, esperas=esperas)

    lote = proxy.buscar_diario("IBM")

    assert not lote.vazio
    assert cliente.chamadas == 3  # 2 falhas + 1 sucesso
    assert esperas == [POLITICA.espera(0), POLITICA.espera(1)]  # backoff 1s, 2s


def test_retry_desiste_depois_de_esgotar_as_tentativas(payload, tmp_path):
    cliente = FonteInstavel(payload, [ErroTransitorio("rede")] * 10)
    esperas: list[float] = []
    proxy = criar_proxy(Fabrica(cliente), tmp_path, esperas=esperas)

    with pytest.raises(ErroTransitorio):
        proxy.buscar_diario("IBM")

    assert cliente.chamadas == POLITICA.tentativas
    assert len(esperas) == POLITICA.tentativas - 1  # não espera depois da última


def test_erro_permanente_nao_e_repetido(payload, tmp_path):
    cliente = FonteInstavel(payload, [ErroCotaEsgotada("25 por dia")])
    esperas: list[float] = []
    proxy = criar_proxy(Fabrica(cliente), tmp_path, esperas=esperas)

    with pytest.raises(ErroCotaEsgotada):
        proxy.buscar_diario("IBM")

    assert cliente.chamadas == 1
    assert esperas == []


def test_falha_nao_deixa_lixo_no_cache(payload, tmp_path):
    cliente = FonteInstavel(payload, [ErroCotaEsgotada("25 por dia")])
    proxy = criar_proxy(Fabrica(cliente), tmp_path)

    with pytest.raises(ErroCotaEsgotada):
        proxy.buscar_diario("IBM")

    assert not list((tmp_path / "cache").glob("*")) if (tmp_path / "cache").exists() else True
