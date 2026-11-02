"""Contrato comum das etapas e o orquestrador do pipeline."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger(__name__)


class Etapa[E, S](Protocol):
    """Toda etapa tem um nome e transforma uma entrada E numa saída S."""

    nome: str

    def executar(self, entrada: E) -> S: ...


@dataclass
class Pipeline:
    """Executa as etapas em sequência: a saída de uma é a entrada da próxima."""

    etapas: list[Etapa[Any, Any]]
    tempos_s: dict[str, float] = field(default_factory=dict, init=False)

    def executar(self, entrada: Any) -> Any:
        dado = entrada
        for etapa in self.etapas:
            inicio = time.perf_counter()
            dado = etapa.executar(dado)
            self.tempos_s[etapa.nome] = time.perf_counter() - inicio
            log.info("etapa %s concluída em %.3fs", etapa.nome, self.tempos_s[etapa.nome])
        return dado
