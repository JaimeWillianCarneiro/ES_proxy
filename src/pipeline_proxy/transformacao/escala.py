"""Escaladores usados pela Transformação.

A etapa recebe o escalador pronto no construtor, então trocar a técnica é só
passar outra implementação de `Escala` (isso é o padrão Strategy).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Escala(ABC):
    @abstractmethod
    def transformar(self, serie: pd.Series) -> pd.Series: ...


class EscalaLog(Escala):
    """log(1 + x): comprime a cauda longa do volume."""

    def transformar(self, serie: pd.Series) -> pd.Series:
        return np.log1p(serie.astype("float64"))


class EscalaMinMax(Escala):
    """Leva a série para o intervalo [0, 1]."""

    def transformar(self, serie: pd.Series) -> pd.Series:
        serie = serie.astype("float64")
        amplitude = serie.max() - serie.min()
        if amplitude == 0 or pd.isna(amplitude):
            return serie * 0.0
        return (serie - serie.min()) / amplitude
