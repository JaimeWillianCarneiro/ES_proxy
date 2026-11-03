"""Passos de limpeza, como funções puras sobre o DataFrame do schema OHLCV.

Cada função recebe um DataFrame e devolve um novo, sem alterar a entrada.
"""

from __future__ import annotations

import pandas as pd

from pipeline_proxy.dominio import CHAVE

PRECOS = ["open", "high", "low", "close"]


def deduplicar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas repetidas por (simbolo, data), mantendo a última."""
    return (
        df.drop_duplicates(subset=CHAVE, keep="last")
        .sort_values(CHAVE, kind="stable")
        .reset_index(drop=True)
    )


def imputar_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill de preços faltantes (NaN), por símbolo.

    Não cria linhas para dias sem pregão e não interpola preço.
    """
    df = df.copy()
    df[PRECOS] = df.groupby("simbolo", observed=True)[PRECOS].ffill()
    return df


def marcar_invalidas(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona `valida`: False quando os valores do dia são inconsistentes."""
    valida = (
        (df["high"] >= df[["open", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "close"]].min(axis=1))
        & (df["volume"] >= 0)
        & df[PRECOS].notna().all(axis=1)
    )
    return df.assign(valida=valida)


def marcar_outliers(df: pd.DataFrame, limiar_z: float = 3.0) -> pd.DataFrame:
    """Adiciona `retorno` (variação diária do close) e `outlier` (|z| > limiar).

    O z-score é calculado por símbolo. Marca, não remove.
    """
    retorno = df.groupby("simbolo", observed=True)["close"].pct_change()
    por_simbolo = retorno.groupby(df["simbolo"], observed=True)
    z = (retorno - por_simbolo.transform("mean")) / por_simbolo.transform("std")
    return df.assign(retorno=retorno, outlier=(z.abs() > limiar_z).fillna(False))
