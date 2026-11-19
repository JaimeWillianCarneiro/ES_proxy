import matplotlib.pyplot as plt
import pandas as pd
import pytest

from pipeline_proxy.visualizacao.etapa import EtapaVisualizacao


def _df_exemplo(simbolo: str = "IBM", com_outlier: bool = True) -> pd.DataFrame:
    outliers = [0, 0, 0, 0, 1, 0] if com_outlier else [0] * 6
    return pd.DataFrame({
        "simbolo": [simbolo] * 6,
        "data": pd.date_range("2026-01-01", periods=6),
        "open": [100.0] * 6,
        "high": [105.0] * 6,
        "low": [99.0] * 6,
        "close": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
        "volume": [1000.0] * 6,
        "valida": [1] * 6,
        "retorno": [0.01] * 6,
        "outlier": outliers,
        "volume_escalado": [6.9] * 6,
        "pred_random_walk": [None, 101.0, 102.0, 103.0, 104.0, 105.0],
        "pred_media_movel": [None, None, None, None, None, 103.0],
    })


def test_visualizacao_gera_csv_e_png(tmp_path):
    etapa = EtapaVisualizacao(tmp_path)

    retorno = etapa.executar(_df_exemplo("IBM"))

    assert not retorno.empty
    assert (tmp_path / "previsoes.csv").exists()
    assert (tmp_path / "grafico_IBM.png").exists()
    assert len(etapa.arquivos_gerados) == 2


def test_visualizacao_dataframe_vazio_limpa_arquivos(tmp_path):
    etapa = EtapaVisualizacao(tmp_path)
    etapa.executar(_df_exemplo("IBM"))
    assert len(etapa.arquivos_gerados) == 2

    retorno = etapa.executar(pd.DataFrame())

    assert retorno.empty
    assert len(etapa.arquivos_gerados) == 0


def test_visualizacao_moeda_e_janela_dinamica(tmp_path, monkeypatch):
    capturas: dict[str, object] = {}
    fig_original, ax_original = plt.subplots()

    def _subplots_mock(*args, **kwargs):
        capturas["subplots_chamado"] = True
        return fig_original, ax_original

    def _set_ylabel_mock(label, *args, **kwargs):
        capturas["ylabel"] = label

    def _plot_mock(*args, **kwargs):
        labels = capturas.setdefault("plot_labels", [])
        if "label" in kwargs:
            labels.append(kwargs["label"])

    monkeypatch.setattr(plt, "subplots", _subplots_mock)
    monkeypatch.setattr(ax_original, "set_ylabel", _set_ylabel_mock)
    monkeypatch.setattr(ax_original, "plot", _plot_mock)
    monkeypatch.setattr(fig_original, "savefig", lambda *a, **kw: None)
    monkeypatch.setattr(plt, "close", lambda *a, **kw: None)

    etapa_b3 = EtapaVisualizacao(tmp_path, janela_media_movel=10)
    etapa_b3.executar(_df_exemplo("PETR4.SAO", com_outlier=False))

    assert capturas["subplots_chamado"] is True
    assert capturas["ylabel"] == "Preço de Fechamento (R$)"
    assert "Prev. Média Móvel (k=10)" in capturas["plot_labels"]
    assert (tmp_path / "grafico_PETR4_SAO.png").parent == tmp_path

    capturas.clear()
    etapa_us = EtapaVisualizacao(tmp_path, janela_media_movel=3)
    etapa_us.executar(_df_exemplo("IBM", com_outlier=False))

    assert capturas["ylabel"] == "Preço de Fechamento (US$)"
    assert "Prev. Média Móvel (k=3)" in capturas["plot_labels"]

    plt.close(fig_original)


@pytest.mark.parametrize("simbolo_entrada,arquivo_esperado", [("IBM", "grafico_IBM.png"), ("PETR4.SAO", "grafico_PETR4_SAO.png")])
def test_nome_arquivo_grafico_por_simbolo(tmp_path, simbolo_entrada, arquivo_esperado):
    etapa = EtapaVisualizacao(tmp_path)
    etapa.executar(_df_exemplo(simbolo_entrada))

    assert (tmp_path / arquivo_esperado).exists()