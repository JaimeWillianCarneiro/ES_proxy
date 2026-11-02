import pytest
import requests
import responses

from fakes import carregar_fixture
from pipeline_proxy.dominio import COLUNAS, Tamanho
from pipeline_proxy.erros import (
    ErroAutenticacao,
    ErroCotaEsgotada,
    ErroLimiteRequisicoes,
    ErroPermanente,
    ErroTransitorio,
)
from pipeline_proxy.extracao.alpha_vantage import URL_BASE, AlphaVantageClient


@pytest.fixture
def cliente():
    return AlphaVantageClient("chave-teste")


@responses.activate
def test_busca_e_converte_para_o_schema(cliente):
    responses.get(URL_BASE, json=carregar_fixture("daily_ibm.json"))

    lote = cliente.buscar_diario("IBM")

    assert list(lote.dados.columns) == COLUNAS
    assert len(lote.dados) == 100
    assert lote.dados["data"].is_monotonic_increasing
    assert (lote.dados["simbolo"] == "IBM").all()
    assert str(lote.dados["volume"].dtype) == "int64"
    assert lote.fonte == "alpha_vantage"
    assert cliente.chamadas_reais == 1


@responses.activate
def test_envia_parametros_esperados(cliente):
    responses.get(URL_BASE, json=carregar_fixture("daily_ibm.json"))

    cliente.buscar_diario("IBM", Tamanho.FULL)

    params = responses.calls[0].request.params
    assert params == {
        "function": "TIME_SERIES_DAILY",
        "symbol": "IBM",
        "outputsize": "full",
        "apikey": "chave-teste",
    }


@responses.activate
def test_compact_nao_envia_outputsize(cliente):
    responses.get(URL_BASE, json=carregar_fixture("daily_ibm.json"))

    cliente.buscar_diario("IBM", Tamanho.COMPACT)

    assert "outputsize" not in responses.calls[0].request.params


@responses.activate
def test_cada_chamada_vai_a_api(cliente):
    responses.get(URL_BASE, json=carregar_fixture("daily_ibm.json"))

    cliente.buscar_diario("IBM")
    cliente.buscar_diario("IBM")

    assert cliente.chamadas_reais == 2
    assert len(responses.calls) == 2


@pytest.mark.parametrize(
    ("fixture", "erro"),
    [
        ("erro_simbolo_invalido.json", ErroPermanente),
        ("erro_apikey.json", ErroAutenticacao),
        ("limite_por_segundo.json", ErroLimiteRequisicoes),
        ("limite_diario.json", ErroCotaEsgotada),
    ],
)
@responses.activate
def test_classifica_erros_no_corpo_da_resposta(cliente, fixture, erro):
    responses.get(URL_BASE, json=carregar_fixture(fixture), status=200)

    with pytest.raises(erro):
        cliente.buscar_diario("IBM")


def test_limite_por_segundo_e_transitorio_e_cota_diaria_nao():
    assert issubclass(ErroLimiteRequisicoes, ErroTransitorio)
    assert issubclass(ErroCotaEsgotada, ErroPermanente)


@pytest.mark.parametrize(("status", "erro"), [(500, ErroTransitorio), (503, ErroTransitorio), (429, ErroTransitorio), (404, ErroPermanente)])
@responses.activate
def test_classifica_erros_http(cliente, status, erro):
    responses.get(URL_BASE, status=status)

    with pytest.raises(erro):
        cliente.buscar_diario("IBM")


@responses.activate
def test_timeout_e_transitorio(cliente):
    responses.get(URL_BASE, body=requests.Timeout("lento demais"))

    with pytest.raises(ErroTransitorio):
        cliente.buscar_diario("IBM")


@responses.activate
def test_resposta_sem_serie_e_permanente(cliente):
    responses.get(URL_BASE, json={"Meta Data": {}})

    with pytest.raises(ErroPermanente):
        cliente.buscar_diario("IBM")
