"""Ponto de entrada do pipeline.

É aqui que as dependências de cada etapa são escolhidas:
- `criar_fonte()` decide a FonteDados (é onde o proxy bom vai entrar);
- `EtapaTransformacao(escala_volume=...)` recebe o escalador (é onde o proxy
  ruim vai entrar).
"""

from __future__ import annotations

import logging

import pandas as pd

from pipeline_proxy.config import Config, carregar_config
from pipeline_proxy.dominio import RequisicaoExtracao
from pipeline_proxy.extracao.alpha_vantage import AlphaVantageClient
from pipeline_proxy.extracao.estado import RepositorioEstadoJson
from pipeline_proxy.extracao.extrator import EtapaExtracao
from pipeline_proxy.extracao.fonte import FonteDados
from pipeline_proxy.nucleo.etapa import Pipeline
from pipeline_proxy.transformacao.escala import EscalaLog
from pipeline_proxy.transformacao.etapa import EtapaTransformacao, ResumoTransformacao


def criar_fonte(config: Config) -> FonteDados:
    return AlphaVantageClient(config.api_key, timeout_s=config.timeout_s)


def imprimir_resumo(
    simbolos: tuple[str, ...], dados: pd.DataFrame, limpeza: ResumoTransformacao
) -> None:
    for simbolo in simbolos:
        datas = dados.loc[dados["simbolo"] == simbolo, "data"]
        if datas.empty:
            print(f"{simbolo:>10}: 0 linhas novas")
            continue
        print(
            f"{simbolo:>10}: {len(datas):4d} linhas "
            f"de {datas.min():%Y-%m-%d} a {datas.max():%Y-%m-%d}"
        )
    print(
        f"limpeza: {limpeza.duplicadas_removidas} duplicadas removidas, "
        f"{limpeza.valores_imputados} valores imputados, "
        f"{limpeza.invalidas} linhas inválidas, {limpeza.outliers} outliers"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = carregar_config()

    fonte = criar_fonte(config)
    estado = RepositorioEstadoJson(config.dir_dados / "estado.json")
    transformacao = EtapaTransformacao(escala_volume=EscalaLog())
    pipeline = Pipeline([EtapaExtracao(fonte, estado), transformacao])

    dados = pipeline.executar(
        RequisicaoExtracao(simbolos=config.simbolos, modo=config.modo, tamanho=config.tamanho)
    )

    imprimir_resumo(config.simbolos, dados, transformacao.resumo)
    if isinstance(fonte, AlphaVantageClient):
        print(f"chamadas_reais={fonte.chamadas_reais}")
    for nome, segundos in pipeline.tempos_s.items():
        print(f"tempo[{nome}]={segundos:.3f}s")


if __name__ == "__main__":
    main()
