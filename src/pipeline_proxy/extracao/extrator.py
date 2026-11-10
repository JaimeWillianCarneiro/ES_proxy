"""Etapa de extração do pipeline.

Depende apenas da interface FonteDados: não sabe (nem precisa saber) se está
falando com o cliente real ou com um proxy.
"""

from __future__ import annotations

import logging
from dataclasses import replace

import pandas as pd

from pipeline_proxy.dominio import LoteExtracao, ModoExtracao, RequisicaoExtracao
from pipeline_proxy.extracao.estado import RepositorioEstado
from pipeline_proxy.extracao.fonte import FonteDados

log = logging.getLogger(__name__)


class EtapaExtracao:
    nome = "extracao"

    def __init__(self, fonte: FonteDados, estado: RepositorioEstado):
        self._fonte = fonte
        self._estado = estado

    def executar(self, entrada: RequisicaoExtracao) -> list[LoteExtracao]:
        return [self._extrair(simbolo, entrada) for simbolo in entrada.simbolos]

    def _extrair(self, simbolo: str, req: RequisicaoExtracao) -> LoteExtracao:
        lote = self._fonte.buscar_diario(simbolo, req.tamanho)
        if lote.vazio:
            return lote

        ultima_extraida = self._estado.obter(simbolo)
        if req.modo is ModoExtracao.INCREMENTAL and ultima_extraida is not None:
            novos = lote.dados[lote.dados["data"] > pd.Timestamp(ultima_extraida)]
            lote = replace(lote, dados=novos.reset_index(drop=True))

        log.info("%s: %d linhas (%s)", simbolo, len(lote.dados), req.modo)
        return lote
