import sqlite3
import pandas as pd
from pipeline_proxy.carga.etapa import EtapaCarga
from pipeline_proxy.extracao.estado import RepositorioEstadoJson


def test_carga_persiste_watermark_em_json(tmp_path):
    caminho_db = tmp_path / "test.db"
    caminho_json = tmp_path / "estado.json"
    estado = RepositorioEstadoJson(caminho_json)

    etapa = EtapaCarga(caminho_db, estado=estado)

    df = pd.DataFrame([
        {
            "simbolo": "IBM",
            "data": "2026-11-09",
            "open": 200.0,
            "high": 205.0,
            "low": 199.0,
            "close": 204.0,
            "volume": 1000.0,
            "valida": 1,
            "retorno": 0.01,
            "outlier": 0,
            "volume_escalado": 6.9,
        }
    ])
    etapa.executar(df)

    assert RepositorioEstadoJson(caminho_json).obter("IBM") == pd.Timestamp("2026-11-09").date()


class FakeEstado:
    def __init__(self):
        self.datas = {}

    def obter(self, simbolo: str):
        return self.datas.get(simbolo)

    def salvar(self, simbolo: str, data):
        self.datas[simbolo] = data


def test_carga_atualiza_watermark_no_estado(tmp_path):
    caminho_db = tmp_path / "test.db"
    estado = FakeEstado()
    etapa = EtapaCarga(caminho_db, estado=estado)

    df = pd.DataFrame([
        {
            "simbolo": "IBM",
            "data": "2026-11-09",
            "open": 200.0,
            "high": 205.0,
            "low": 199.0,
            "close": 204.0,
            "volume": 1000.0,
            "valida": 1,
            "retorno": 0.01,
            "outlier": 0,
            "volume_escalado": 6.9,
        }
    ])

    etapa.executar(df)

    # Verifica se a watermark do símbolo foi gravada
    assert estado.obter("IBM") is not None
    assert str(estado.obter("IBM")) == "2026-11-09"
    
    
    
def test_carga_cria_tabela_e_insere_dados(tmp_path):
    caminho_db = tmp_path / "test.db"
    etapa = EtapaCarga(caminho_db)

    df = pd.DataFrame([
        {
            "simbolo": "IBM",
            "data": "2026-11-09",
            "open": 200.0,
            "high": 205.0,
            "low": 199.0,
            "close": 204.0,
            "volume": 1000.0,
            "valida": 1,
            "retorno": 0.015,
            "outlier": 0,
            "volume_escalado": 6.90,
        }
    ])

    retorno = etapa.executar(df)

    assert not retorno.empty
    assert etapa.linhas_afetadas == 1

    with sqlite3.connect(caminho_db) as conn:
        linhas = conn.execute("SELECT * FROM cotacoes").fetchall()
        assert len(linhas) == 1
        assert linhas[0][0] == "IBM"
        assert linhas[0][1] == "2026-11-09"
        assert linhas[0][5] == 204.0
        assert linhas[0][8] == 0.015


def test_carga_upsert_atualiza_registro_existente(tmp_path):
    caminho_db = tmp_path / "test.db"
    etapa = EtapaCarga(caminho_db)

    df_inicial = pd.DataFrame([
        {
            "simbolo": "IBM",
            "data": "2026-11-09",
            "open": 200.0,
            "high": 205.0,
            "low": 199.0,
            "close": 204.0,
            "volume": 1000.0,
            "valida": 1,
            "retorno": 0.01,
            "outlier": 0,
            "volume_escalado": 6.90,
        }
    ])
    etapa.executar(df_inicial)

    # Reexecuta com a mesma chave primária (simbolo, data), mas com close e retorno atualizados
    df_atualizado = pd.DataFrame([
        {
            "simbolo": "IBM",
            "data": "2026-11-09",
            "open": 200.0,
            "high": 205.0,
            "low": 199.0,
            "close": 210.0,
            "volume": 1000.0,
            "valida": 1,
            "retorno": 0.03,
            "outlier": 0,
            "volume_escalado": 6.90,
        }
    ])
    etapa.executar(df_atualizado)

    with sqlite3.connect(caminho_db) as conn:
        linhas = conn.execute("SELECT simbolo, data, close, retorno FROM cotacoes").fetchall()
        assert len(linhas) == 1
        assert linhas[0][2] == 210.0
        assert linhas[0][3] == 0.03


def test_carga_dataframe_vazio(tmp_path):
    caminho_db = tmp_path / "test.db"
    etapa = EtapaCarga(caminho_db)

    retorno = etapa.executar(pd.DataFrame())

    assert retorno.empty
    assert etapa.linhas_afetadas == 0