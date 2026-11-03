import numpy as np
import pandas as pd
import pytest

from fakes import FonteFake, carregar_fixture
from pipeline_proxy.dominio import LoteExtracao, Tamanho, aplicar_schema
from pipeline_proxy.transformacao.escala import EscalaLog, EscalaMinMax
from pipeline_proxy.transformacao.etapa import COLUNAS_LIMPAS, EtapaTransformacao
from pipeline_proxy.transformacao.limpeza import (
    deduplicar,
    imputar_faltantes,
    marcar_invalidas,
    marcar_outliers,
)


def criar_lote(simbolo, linhas):
    """linhas: lista de (data, open, high, low, close, volume)."""
    df = pd.DataFrame(linhas, columns=["data", "open", "high", "low", "close", "volume"])
    df["data"] = pd.to_datetime(df["data"])
    df["simbolo"] = simbolo
    return LoteExtracao(simbolo=simbolo, dados=aplicar_schema(df), fonte="teste", tamanho=Tamanho.COMPACT)


def linhas_estaveis(n, preco=10.0, inicio="2026-01-01"):
    datas = pd.bdate_range(inicio, periods=n)
    return [(d, preco, preco + 1, preco - 1, preco + 0.01 * (i % 3), 1000) for i, d in enumerate(datas)]


@pytest.fixture
def ibm():
    return FonteFake(carregar_fixture("daily_ibm.json")).buscar_diario("IBM")


# --- passos isolados -------------------------------------------------------


def test_deduplicar_mantem_a_ultima_ocorrencia():
    lote = criar_lote("X", [("2026-01-02", 10, 11, 9, 10, 100), ("2026-01-02", 10, 11, 9, 10.5, 200)])

    df = deduplicar(lote.dados)

    assert len(df) == 1
    assert df["close"].iloc[0] == 10.5


def test_imputar_preenche_com_o_valor_anterior_do_mesmo_simbolo():
    a = criar_lote("A", [("2026-01-02", 10, 11, 9, 10, 100), ("2026-01-05", 10, 11, 9, np.nan, 100)])
    b = criar_lote("B", [("2026-01-02", 50, 51, 49, np.nan, 100)])
    df = pd.concat([a.dados, b.dados], ignore_index=True)

    df = imputar_faltantes(df)

    assert df.loc[df["simbolo"] == "A", "close"].tolist() == [10, 10]
    assert df.loc[df["simbolo"] == "B", "close"].isna().all()  # não vaza entre símbolos


def test_imputar_nao_cria_dias_sem_pregao():
    lote = criar_lote("A", [("2026-01-02", 10, 11, 9, 10, 100), ("2026-01-05", 10, 11, 9, 10, 100)])

    assert len(imputar_faltantes(lote.dados)) == 2


@pytest.mark.parametrize(
    "linha",
    [
        ("2026-01-02", 10, 9, 8, 10, 100),  # high < open
        ("2026-01-02", 10, 11, 10.5, 10, 100),  # low > close
        ("2026-01-02", 10, 11, 9, 10, -1),  # volume negativo
        ("2026-01-02", 10, 11, 9, np.nan, 100),  # preço faltando
    ],
)
def test_marcar_invalidas(linha):
    df = marcar_invalidas(criar_lote("X", [linha]).dados)

    assert not df["valida"].iloc[0]


def test_linha_consistente_e_valida():
    df = marcar_invalidas(criar_lote("X", [("2026-01-02", 10, 11, 9, 10.5, 100)]).dados)

    assert df["valida"].iloc[0]


def test_marcar_outliers_detecta_salto_e_nao_remove():
    linhas = linhas_estaveis(40)
    d, o, h, l, c, v = linhas[30]
    linhas[30] = (d, o, 20, l, 19.5, v)  # salto de ~95% no fechamento
    df = marcar_outliers(criar_lote("X", linhas).dados)

    assert len(df) == 40
    assert df["outlier"].iloc[30]
    assert df["outlier"].sum() <= 2  # o salto e, no máximo, a volta
    assert pd.isna(df["retorno"].iloc[0])


def test_outlier_com_uma_linha_so_nao_quebra():
    df = marcar_outliers(criar_lote("X", [("2026-01-02", 10, 11, 9, 10, 100)]).dados)

    assert not df["outlier"].iloc[0]


# --- escalas ---------------------------------------------------------------


def test_escala_log():
    assert EscalaLog().transformar(pd.Series([0, np.e - 1])).tolist() == pytest.approx([0, 1])


def test_escala_min_max():
    assert EscalaMinMax().transformar(pd.Series([2, 4, 6])).tolist() == [0, 0.5, 1]
    assert EscalaMinMax().transformar(pd.Series([5, 5])).tolist() == [0, 0]


# --- etapa completa --------------------------------------------------------


def test_etapa_com_dados_reais_limpos(ibm):
    etapa = EtapaTransformacao(EscalaLog())

    df = etapa.executar([ibm])

    assert list(df.columns) == COLUNAS_LIMPAS
    assert len(df) == 100
    assert df["valida"].all()
    assert etapa.resumo.duplicadas_removidas == 0
    assert etapa.resumo.valores_imputados == 0
    np.testing.assert_allclose(df["volume_escalado"], np.log1p(df["volume"]))


def test_etapa_com_dados_sujos():
    sujo = criar_lote(
        "X",
        [
            ("2026-01-02", 10, 11, 9, 10, 100),
            ("2026-01-05", 10, 11, 9, np.nan, 100),  # faltante
            ("2026-01-06", 10, 9, 8, 10, 100),  # inválida (high < open)
        ],
    )
    repetido = criar_lote("X", [("2026-01-02", 10, 11, 9, 10, 100)])  # duplicada
    etapa = EtapaTransformacao(EscalaLog())

    df = etapa.executar([sujo, repetido])

    assert len(df) == 3
    assert etapa.resumo.linhas_entrada == 4
    assert etapa.resumo.duplicadas_removidas == 1
    assert etapa.resumo.valores_imputados == 1
    assert etapa.resumo.invalidas == 1


def test_etapa_junta_varios_simbolos_ordenados(ibm):
    outro = criar_lote("X", linhas_estaveis(5))

    df = EtapaTransformacao(EscalaLog()).executar([outro, ibm])

    assert sorted(df["simbolo"].unique()) == ["IBM", "X"]
    assert df.groupby("simbolo")["data"].apply(lambda s: s.is_monotonic_increasing).all()


def test_etapa_sem_dados_devolve_dataframe_vazio_com_schema(ibm):
    vazio = LoteExtracao(simbolo="IBM", dados=ibm.dados.iloc[0:0], fonte="teste", tamanho=Tamanho.COMPACT)

    df = EtapaTransformacao(EscalaLog()).executar([vazio])

    assert df.empty
    assert list(df.columns) == COLUNAS_LIMPAS


def test_etapa_aceita_qualquer_escala(ibm):
    df = EtapaTransformacao(EscalaMinMax()).executar([ibm])

    assert df["volume_escalado"].between(0, 1).all()
