"""Configuração do pipeline, lida de variáveis de ambiente / arquivo .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from pipeline_proxy.dominio import ModoExtracao, Tamanho


@dataclass(frozen=True)
class PoliticaRetry:
    """Política de novas tentativas da extração (aplicada pelo proxy).

    Espera antes da tentativa i (começando em 0): min(base * 2**i, maximo).
    """

    tentativas: int = 3
    backoff_base_s: float = 1.0
    backoff_max_s: float = 30.0

    def espera(self, tentativa: int) -> float:
        return min(self.backoff_base_s * 2**tentativa, self.backoff_max_s)


@dataclass(frozen=True)
class Config:
    api_key: str
    simbolos: tuple[str, ...]
    modo: ModoExtracao
    tamanho: Tamanho
    timeout_s: float
    dir_dados: Path
    retry: PoliticaRetry


def carregar_config() -> Config:
    load_dotenv()
    simbolos = tuple(
        s.strip().upper() for s in os.getenv("SIMBOLOS", "IBM").split(",") if s.strip()
    )
    return Config(
        api_key=os.getenv("ALPHAVANTAGE_API_KEY", ""),
        simbolos=simbolos,
        modo=ModoExtracao(os.getenv("MODO", "completa").lower()),
        tamanho=Tamanho(os.getenv("TAMANHO", "compact").lower()),
        timeout_s=float(os.getenv("TIMEOUT_S", "10")),
        dir_dados=Path(os.getenv("DIR_DADOS", "dados")),
        retry=PoliticaRetry(
            tentativas=int(os.getenv("RETRY_TENTATIVAS", "3")),
            backoff_base_s=float(os.getenv("RETRY_BACKOFF_BASE_S", "1")),
            backoff_max_s=float(os.getenv("RETRY_BACKOFF_MAX_S", "30")),
        ),
    )
