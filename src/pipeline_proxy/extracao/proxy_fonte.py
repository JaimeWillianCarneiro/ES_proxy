"""Proxy da fonte de dados

`FonteDadosProxy` implementa a mesma interface `FonteDados` do cliente real
(`AlphaVantageClient`, o *RealSubject*). Por isso a `EtapaExtracao` não percebe
a troca: ela continua chamando `buscar_diario(...)` sem saber se quem responde
é o cliente real ou este intermediário.

Cada responsabilidade abaixo resolve um problema do código original:

- Proteção: barra chave vazia ou com formato inválido antes de qualquer chamada.
  Problema original: o erro de chave só aparecia depois de gastar uma requisição.
- Cache: guarda o lote bruto em disco, com validade.
  Problema original: toda execução ia à rede e gastava a cota diária (25/dia).
- Virtual (lazy): só cria o cliente real (e a sessão HTTP) no primeiro cache miss.
  Problema original: o cliente era criado sempre, mesmo sem precisar dele.
- Retry: repete só falhas transitórias, com espera crescente.
  Problema original: um erro de rede ou de limite por segundo derrubava o pipeline.

Ordem de uma chamada: proteção -> cache -> (miss) cliente real com retry ->
grava no cache.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline_proxy.config import PoliticaRetry
from pipeline_proxy.dominio import LoteExtracao, Tamanho
from pipeline_proxy.erros import ErroAutenticacao, ErroTransitorio
from pipeline_proxy.extracao.fonte import FonteDados

log = logging.getLogger(__name__)

# Chaves da Alpha Vantage são alfanuméricas (a "demo" tem 4 caracteres).
# Só checamos o formato: quem diz se a chave é válida de verdade é o servidor.
FORMATO_CHAVE = re.compile(r"[A-Za-z0-9]{4,64}")

VALIDADE_PADRAO = timedelta(hours=12)


class FonteDadosProxy(FonteDados):
    def __init__(
        self,
        fabrica_cliente: Callable[[], FonteDados],
        api_key: str,
        dir_cache: Path,
        validade: timedelta = VALIDADE_PADRAO,
        politica_retry: PoliticaRetry | None = None,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        # Recebemos uma *fábrica* e não o cliente pronto: assim o cliente real
        # (e a sessão HTTP dele) só passa a existir se alguém precisar dele.
        self._fabrica_cliente = fabrica_cliente
        self._cliente: FonteDados | None = None

        self._api_key = api_key
        self._dir_cache = dir_cache
        self._validade = validade
        self._retry = politica_retry or PoliticaRetry()
        # `dormir` e `agora` são injetados para os testes não esperarem de
        # verdade nem dependerem do relógio.
        self._dormir = dormir
        self._agora = agora

    # --- interface FonteDados -------------------------------------------------

    def buscar_diario(self, simbolo: str, tamanho: Tamanho = Tamanho.COMPACT) -> LoteExtracao:
        # 1. Proteção: falha cedo, sem gastar cota nem abrir rede.
        self._validar_chave()

        # 2. Cache: se há um lote ainda válido, o cliente real nem é tocado.
        lote = self._ler_cache(simbolo, tamanho)
        if lote is not None:
            log.info("[PROXY] cache hit: %s (%s)", simbolo, tamanho)
            return lote

        # 3. Miss: delega ao cliente real, agora com retry.
        log.info("[PROXY] cache miss: %s (%s)", simbolo, tamanho)
        lote = self._buscar_com_retry(simbolo, tamanho)

        # 4. Guarda para as próximas chamadas.
        self._gravar_cache(lote)
        return lote

    # --- consulta para a demo e os testes -------------------------------------

    @property
    def cliente_criado(self) -> bool:
        """Diz se o cliente real já foi criado (prova do lazy loading)."""
        return self._cliente is not None

    @property
    def chamadas_reais(self) -> int:
        """Chamadas que realmente chegaram à API (0 enquanto só há cache hit).

        Existe para a demo continuar mostrando `chamadas_reais` com o proxy
        ligado, já que o `main` não consegue mais ler o contador do cliente.
        """
        return getattr(self._cliente, "chamadas_reais", 0)

    # --- proteção -------------------------------------------------------------

    def _validar_chave(self) -> None:
        if not self._api_key or not FORMATO_CHAVE.fullmatch(self._api_key):
            raise ErroAutenticacao("[PROXY] API key ausente ou com formato inválido")

    # --- virtual (lazy) -------------------------------------------------------

    def _obter_cliente(self) -> FonteDados:
        if self._cliente is None:
            log.info("[PROXY] criando o cliente real (primeiro cache miss)")
            self._cliente = self._fabrica_cliente()
        return self._cliente

    # --- retry ----------------------------------------------------------------

    def _buscar_com_retry(self, simbolo: str, tamanho: Tamanho) -> LoteExtracao:
        cliente = self._obter_cliente()
        for tentativa in range(self._retry.tentativas):
            try:
                return cliente.buscar_diario(simbolo, tamanho)
            except ErroTransitorio as e:
                # Última tentativa: desiste e deixa o erro subir.
                if tentativa == self._retry.tentativas - 1:
                    raise
                espera = self._retry.espera(tentativa)
                log.warning(
                    "[PROXY] falha transitória (%s); tentativa %d/%d, esperando %.1fs",
                    e, tentativa + 1, self._retry.tentativas, espera,
                )
                self._dormir(espera)
            # ErroPermanente não é capturado de propósito: repetir não adianta,
            # então ele sobe direto para quem chamou.
        raise AssertionError("inalcançável: tentativas deve ser >= 1")

    # --- cache ----------------------------------------------------------------

    def _caminho_cache(self, simbolo: str, tamanho: Tamanho) -> Path:
        # Chave do cache = (simbolo, tamanho). Trocamos caracteres estranhos
        # para o símbolo nunca virar um caminho fora do diretório do cache.
        seguro = re.sub(r"[^A-Za-z0-9._-]", "_", simbolo)
        return self._dir_cache / f"{seguro}_{tamanho}.json"

    def _ler_cache(self, simbolo: str, tamanho: Tamanho) -> LoteExtracao | None:
        caminho = self._caminho_cache(simbolo, tamanho)
        if not caminho.exists():
            return None
        try:
            lote = LoteExtracao.from_dict(json.loads(caminho.read_text()))
        except (ValueError, KeyError, TypeError) as e:
            # Arquivo corrompido não pode derrubar o pipeline: tratamos como miss.
            log.warning("[PROXY] cache ilegível em %s (%s); ignorando", caminho.name, e)
            return None

        if self._agora() - lote.extraido_em >= self._validade:
            log.info("[PROXY] cache vencido: %s (%s)", simbolo, tamanho)
            return None
        return lote

    def _gravar_cache(self, lote: LoteExtracao) -> None:
        # Lote vazio costuma indicar um problema na fonte; não vale cachear.
        if lote.vazio:
            return
        self._dir_cache.mkdir(parents=True, exist_ok=True)
        caminho = self._caminho_cache(lote.simbolo, lote.tamanho)
        # Escreve num temporário e renomeia, para nunca deixar um JSON pela metade.
        temporario = caminho.with_suffix(".tmp")
        temporario.write_text(json.dumps(lote.to_dict()))
        temporario.replace(caminho)
