from datetime import date

import pandas as pd

from fakes import FonteFake, carregar_fixture
from pipeline_proxy.dominio import ModoExtracao, RequisicaoExtracao
from pipeline_proxy.extracao.estado import RepositorioEstadoJson, RepositorioEstadoMemoria
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


def test_incremental_sem_watermark_traz_tudo_e_grava_watermark():
    estado = RepositorioEstadoMemoria()
    etapa, _ = criar_etapa(estado)

    (lote,) = etapa.executar(RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.INCREMENTAL))

    assert len(lote.dados) == 100
    assert estado.obter("IBM") == lote.dados["data"].max().date()


def test_incremental_traz_so_datas_posteriores_a_watermark():
    estado = RepositorioEstadoMemoria()
    etapa, _ = criar_etapa(estado)
    req = RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.INCREMENTAL)
    (completo,) = etapa.executar(req)

    corte = completo.dados["data"].iloc[-4].date()  # deixa 3 datas depois do corte
    estado.salvar("IBM", corte)
    (lote,) = etapa.executar(req)

    assert len(lote.dados) == 3
    assert (lote.dados["data"] > pd.Timestamp(corte)).all()


def test_segunda_execucao_incremental_nao_traz_nada():
    etapa, _ = criar_etapa()
    req = RequisicaoExtracao(simbolos=("IBM",), modo=ModoExtracao.INCREMENTAL)

    etapa.executar(req)
    (lote,) = etapa.executar(req)

    assert lote.vazio


def test_watermark_persiste_em_json(tmp_path):
    caminho = tmp_path / "estado.json"
    etapa, _ = criar_etapa(RepositorioEstadoJson(caminho))

    (lote,) = etapa.executar(RequisicaoExtracao(simbolos=("IBM",)))

    assert RepositorioEstadoJson(caminho).obter("IBM") == lote.dados["data"].max().date()
