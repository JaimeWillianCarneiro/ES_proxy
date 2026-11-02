"""Implementações de teste da interface FonteDados."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline_proxy.dominio import LoteExtracao, Tamanho
from pipeline_proxy.extracao.alpha_vantage import parse_serie_diaria
from pipeline_proxy.extracao.fonte import FonteDados

FIXTURES = Path(__file__).parent / "fixtures"


def carregar_fixture(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text())


class FonteFake(FonteDados):
    """Serve um payload fixo, sem rede, e conta as chamadas recebidas."""

    def __init__(self, payload: dict):
        self._payload = payload
        self.chamadas = 0

    def buscar_diario(self, simbolo: str, tamanho: Tamanho = Tamanho.COMPACT) -> LoteExtracao:
        self.chamadas += 1
        return LoteExtracao(
            simbolo=simbolo,
            dados=parse_serie_diaria(self._payload, simbolo),
            fonte="fake",
            tamanho=tamanho,
        )
