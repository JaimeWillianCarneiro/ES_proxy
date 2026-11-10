import pandas as pd
import numpy as np
from pipeline_proxy.modelagem.etapa import EtapaModelagem, calcular_mae, calcular_rmse


def test_metricas_mae_e_rmse():
    y_real = np.array([10.0, 20.0, 30.0])
    y_pred = np.array([12.0, 19.0, 32.0])

    # Erros: [2, -1, 2] -> Absolutos: [2, 1, 2] -> MAE = 5/3 = 1.666...
    # Quadrados: [4, 1, 4] -> Média = 9/3 = 3 -> RMSE = sqrt(3) ~ 1.732...
    assert np.isclose(calcular_mae(y_real, y_pred), 5 / 3)
    assert np.isclose(calcular_rmse(y_real, y_pred), np.sqrt(3))


def test_etapa_modelagem_previsoes_e_metricas():
    # 7 dias para testar janela de 5 dias
    df = pd.DataFrame({
        "simbolo": ["IBM"] * 7,
        "data": pd.date_range("2026-01-01", periods=7),
        "close": [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0],
        "valida": [1] * 7,
    })

    etapa = EtapaModelagem(janela_media_movel=5)
    resultado_df = etapa.executar(df)

    # Verifica colunas criadas
    assert "pred_random_walk" in resultado_df.columns
    assert "pred_media_movel" in resultado_df.columns

    # Random walk no dia 1 deve ser o close do dia 0 (100.0)
    assert resultado_df.loc[1, "pred_random_walk"] == 100.0

    # Média móvel dos 5 primeiros dias (índices 0 a 4: média de 100, 102, 101, 103, 105 = 102.2)
    # Essa média vira a previsão para o índice 5:
    assert np.isclose(resultado_df.loc[5, "pred_media_movel"], 102.2)

    # Métricas calculadas para IBM
    assert "IBM" in etapa.resultado.metricas
    m_rw = etapa.resultado.metricas["IBM"]["random_walk"]
    m_ma = etapa.resultado.metricas["IBM"]["media_movel"]

    assert m_rw.mae >= 0
    assert m_ma.rmse >= 0


def test_etapa_modelagem_dataframe_vazio():
    etapa = EtapaModelagem()
    res = etapa.executar(pd.DataFrame())
    assert res.empty