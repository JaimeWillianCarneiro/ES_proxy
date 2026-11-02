"""Estado da extração incremental: a última data já extraída por símbolo."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path


class RepositorioEstado(ABC):
    @abstractmethod
    def obter(self, simbolo: str) -> date | None: ...

    @abstractmethod
    def salvar(self, simbolo: str, ultima_data: date) -> None: ...


class RepositorioEstadoJson(RepositorioEstado):
    """Guarda a última data de cada símbolo num arquivo JSON.

    Quando a etapa de Carga existir, ela pode oferecer outra implementação
    (por exemplo, MAX(data) no banco) sem mudar o extrator.
    """

    def __init__(self, caminho: Path):
        self._caminho = caminho

    def obter(self, simbolo: str) -> date | None:
        valor = self._ler().get(simbolo)
        return date.fromisoformat(valor) if valor else None

    def salvar(self, simbolo: str, ultima_data: date) -> None:
        estado = self._ler()
        estado[simbolo] = ultima_data.isoformat()
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._caminho.write_text(json.dumps(estado, indent=2, sort_keys=True))

    def _ler(self) -> dict[str, str]:
        if not self._caminho.exists():
            return {}
        return json.loads(self._caminho.read_text())


class RepositorioEstadoMemoria(RepositorioEstado):
    def __init__(self):
        self._estado: dict[str, date] = {}

    def obter(self, simbolo: str) -> date | None:
        return self._estado.get(simbolo)

    def salvar(self, simbolo: str, ultima_data: date) -> None:
        self._estado[simbolo] = ultima_data
