"""Ponto de entrada do pipeline.

`criar_fonte()` é o único lugar que sabe qual implementação de FonteDados está
em uso. É aqui que o proxy vai entrar no lugar do cliente real.
"""

from __future__ import annotations

import logging

from pipeline_proxy.config import Config, carregar_config
from pipeline_proxy.dominio import LoteExtracao, RequisicaoExtracao
from pipeline_proxy.extracao.alpha_vantage import AlphaVantageClient
from pipeline_proxy.extracao.estado import RepositorioEstadoJson
from pipeline_proxy.extracao.extrator import EtapaExtracao
from pipeline_proxy.extracao.fonte import FonteDados
from pipeline_proxy.nucleo.etapa import Pipeline


def criar_fonte(config: Config) -> FonteDados:
    return AlphaVantageClient(config.api_key, timeout_s=config.timeout_s)


def imprimir_resumo(lotes: list[LoteExtracao]) -> None:
    for lote in lotes:
        if lote.vazio:
            print(f"{lote.simbolo:>10}: 0 linhas novas")
            continue
        datas = lote.dados["data"]
        print(
            f"{lote.simbolo:>10}: {len(lote.dados):4d} linhas "
            f"de {datas.min():%Y-%m-%d} a {datas.max():%Y-%m-%d}"
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = carregar_config()

    fonte = criar_fonte(config)
    estado = RepositorioEstadoJson(config.dir_dados / "estado.json")
    pipeline = Pipeline([EtapaExtracao(fonte, estado)])

    lotes = pipeline.executar(
        RequisicaoExtracao(simbolos=config.simbolos, modo=config.modo, tamanho=config.tamanho)
    )

    imprimir_resumo(lotes)
    if isinstance(fonte, AlphaVantageClient):
        print(f"chamadas_reais={fonte.chamadas_reais}")
    for nome, segundos in pipeline.tempos_s.items():
        print(f"tempo[{nome}]={segundos:.3f}s")


if __name__ == "__main__":
    main()
