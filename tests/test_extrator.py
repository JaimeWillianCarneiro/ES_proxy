from datetime import date

import pandas as pd

from fakes import FonteFake, carregar_fixture
from pipeline_proxy.dominio import ModoExtracao, RequisicaoExtracao
from pipeline_proxy.extracao.estado import RepositorioEstadoMemoria
from pipeline_proxy.extracao.extrator import EtapaExtracao


def criar_etapa(estado=None):
    fonte = FonteFake(carregar_fixture("daily_ibm.json"))
    return EtapaExtracao(fonte, estado or RepositorioEstadoMemoria()), fonte


def test_extrai_todos_os_simbolos():
    etapa, fonte = criar_etapa()

    lotes = etapa.executar(RequisicaoExtracao(simbolos=("IBM", "MSFT")))

    assert [l.simbolo for l in lotes] == ["IBM", "MSFT"]
    assert fonte.chamadas == 2


def test_modo_completo_traz_tudo_mesmo_com_watermark():
    estado = RepositorioEstadoMemoria()
    estado.salvar("IBM", date(2100, 1, 1))
    etapa, _ = criar_etapa(estado)

    (lote,) = etapa.executar(RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.COMPLETA))

    assert len(lote.dados) == 100


def test_incremental_sem_watermark_traz_tudo():
    """Sem watermark prévia, o modo incremental deve trazer todos os dados disponíveis."""
    estado = RepositorioEstadoMemoria()
    etapa, _ = criar_etapa(estado)

    (lote,) = etapa.executar(RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.INCREMENTAL))

    assert len(lote.dados) == 100
    # A verificação de gravação foi movida para os testes da EtapaCarga


def test_incremental_traz_so_datas_posteriores_a_watermark():
    """Valida o filtro do extrator respeitando a watermark configurada no repositório."""
    estado = RepositorioEstadoMemoria()
    etapa, _ = criar_etapa(estado)
    req_completa = RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.COMPLETA)
    (completo,) = etapa.executar(req_completa)

    corte = completo.dados["data"].iloc[-4].date()  # deixa 3 datas depois do corte
    estado.salvar("IBM", corte)

    req_incremental = RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.INCREMENTAL)
    (lote,) = etapa.executar(req_incremental)

    assert len(lote.dados) == 3
    assert (lote.dados["data"] > pd.Timestamp(corte)).all()


def test_incremental_com_watermark_na_data_maxima_nao_traz_nada():
    """Se a watermark já estiver na última data existente, nada deve ser retornado."""
    estado = RepositorioEstadoMemoria()
    etapa, _ = criar_etapa(estado)
    (completo,) = etapa.executar(RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.COMPLETA))

    # Simula o estado gravado pela carga com a data mais recente
    estado.salvar("IBM", completo.dados["data"].max().date())

    (lote,) = etapa.executar(RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.INCREMENTAL))
    assert lote.vazio