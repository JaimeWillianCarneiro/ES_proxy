"""Etapa de transformação e limpeza do pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from pipeline_proxy.dominio import COLUNAS, LoteExtracao, aplicar_schema, dataframe_vazio
from pipeline_proxy.transformacao.escala import Escala
from pipeline_proxy.transformacao.limpeza import (
    PRECOS,
    deduplicar,
    imputar_faltantes,
    marcar_invalidas,
    marcar_outliers,
)

log = logging.getLogger(__name__)

# Schema da saída: colunas brutas + colunas derivadas pela limpeza.
COLUNAS_LIMPAS = COLUNAS + ["valida", "retorno", "outlier", "volume_escalado"]


@dataclass(frozen=True)
class ResumoTransformacao:
    linhas_entrada: int = 0
    duplicadas_removidas: int = 0
    valores_imputados: int = 0
    invalidas: int = 0
    outliers: int = 0


class EtapaTransformacao:
    nome = "transformacao"

    def __init__(self, escala_volume: Escala, limiar_outlier_z: float = 3.0):
        self._escala_volume = escala_volume
        self._limiar_outlier_z = limiar_outlier_z
        self.resumo = ResumoTransformacao()

    def executar(self, entrada: list[LoteExtracao]) -> pd.DataFrame:
        brutos = juntar_lotes(entrada)

        sem_duplicadas = deduplicar(brutos)
        faltantes_antes = int(sem_duplicadas[PRECOS].isna().sum().sum())
        imputados = imputar_faltantes(sem_duplicadas)
        faltantes_depois = int(imputados[PRECOS].isna().sum().sum())

        df = marcar_invalidas(imputados)
        df = marcar_outliers(df, self._limiar_outlier_z)
        df = df.assign(volume_escalado=self._escala_volume.transformar(df["volume"]))
        df = df[COLUNAS_LIMPAS]

        self.resumo = ResumoTransformacao(
            linhas_entrada=len(brutos),
            duplicadas_removidas=len(brutos) - len(sem_duplicadas),
            valores_imputados=faltantes_antes - faltantes_depois,
            invalidas=int((~df["valida"]).sum()),
            outliers=int(df["outlier"].sum()),
        )
        log.info("limpeza: %s", self.resumo)
        return df


def juntar_lotes(lotes: list[LoteExtracao]) -> pd.DataFrame:
    """Concatena os DataFrames dos lotes num só, no schema bruto."""
    dados = [lote.dados for lote in lotes if not lote.vazio]
    if not dados:
        return dataframe_vazio()
    return aplicar_schema(pd.concat(dados, ignore_index=True))
