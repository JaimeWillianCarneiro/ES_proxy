"""Contrato de dados compartilhado entre as etapas do pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

import pandas as pd

# Schema da série diária bruta. A chave natural de cada linha é (simbolo, data):
# é ela que a deduplicação (Transformação) e o upsert (Carga) vão usar.
COLUNAS = ["simbolo", "data", "open", "high", "low", "close", "volume"]
CHAVE = ["simbolo", "data"]
DTYPES = {
    "simbolo": "string",
    "data": "datetime64[ns]",
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "int64",
}


class ModoExtracao(StrEnum):
    COMPLETA = "completa"
    INCREMENTAL = "incremental"


class Tamanho(StrEnum):
    """Parâmetro `outputsize` da Alpha Vantage."""

    COMPACT = "compact"  # últimos ~100 pregões (plano gratuito)
    FULL = "full"  # série inteira (plano premium)


def dataframe_vazio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in DTYPES.items()})


def aplicar_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas, ordem e tipos do schema. Não limpa nem valida conteúdo."""
    if df.empty:
        return dataframe_vazio()
    df = df[COLUNAS].astype(DTYPES)
    return df.sort_values("data", kind="stable").reset_index(drop=True)


@dataclass(frozen=True)
class RequisicaoExtracao:
    """Entrada da etapa de extração."""

    simbolos: tuple[str, ...]
    modo: ModoExtracao = ModoExtracao.COMPLETA
    tamanho: Tamanho = Tamanho.COMPACT


@dataclass(frozen=True)
class LoteExtracao:
    """Dados brutos de um símbolo, como vieram da fonte, mais metadados."""

    simbolo: str
    dados: pd.DataFrame
    fonte: str
    tamanho: Tamanho
    extraido_em: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def vazio(self) -> bool:
        return self.dados.empty

    def to_dict(self) -> dict:
        """Forma serializável em JSON (usada, por exemplo, por um cache)."""
        registros = self.dados.assign(data=self.dados["data"].dt.strftime("%Y-%m-%d"))
        return {
            "simbolo": self.simbolo,
            "fonte": self.fonte,
            "tamanho": str(self.tamanho),
            "extraido_em": self.extraido_em.isoformat(),
            "dados": registros.to_dict(orient="records"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> LoteExtracao:
        df = pd.DataFrame(d["dados"], columns=COLUNAS)
        df["data"] = pd.to_datetime(df["data"])
        return cls(
            simbolo=d["simbolo"],
            dados=aplicar_schema(df),
            fonte=d["fonte"],
            tamanho=Tamanho(d["tamanho"]),
            extraido_em=datetime.fromisoformat(d["extraido_em"]),
        )
