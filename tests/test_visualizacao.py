import pandas as pd
from pipeline_proxy.visualizacao.etapa import EtapaVisualizacao


def test_visualizacao_gera_csv_e_png(tmp_path):
    etapa = EtapaVisualizacao(tmp_path)

    df = pd.DataFrame({
        "simbolo": ["IBM"] * 6,
        "data": pd.date_range("2026-01-01", periods=6),
        "open": [100.0] * 6,
        "high": [105.0] * 6,
        "low": [99.0] * 6,
        "close": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
        "volume": [1000.0] * 6,
        "valida": [1] * 6,
        "retorno": [0.01] * 6,
        "outlier": [0, 0, 0, 0, 1, 0],
        "volume_escalado": [6.9] * 6,
        "pred_random_walk": [None, 101.0, 102.0, 103.0, 104.0, 105.0],
        "pred_media_movel": [None, None, None, None, None, 103.0],
    })

    retorno = etapa.executar(df)

    assert not retorno.empty
    assert (tmp_path / "previsoes.csv").exists()
    assert (tmp_path / "grafico_IBM.png").exists()
    assert len(etapa.arquivos_gerados) == 2


def test_visualizacao_dataframe_vazio(tmp_path):
    etapa = EtapaVisualizacao(tmp_path)
    retorno = etapa.executar(pd.DataFrame())

    assert retorno.empty
    assert len(etapa.arquivos_gerados) == 0