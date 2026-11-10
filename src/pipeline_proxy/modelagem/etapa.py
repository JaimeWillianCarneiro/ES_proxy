from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from pipeline_proxy.nucleo.etapa import Etapa


@dataclass(frozen=True)
class MetricasModelo:
    mae: float
    rmse: float


@dataclass
class ResultadoModelagem:
    metricas: dict[str, dict[str, MetricasModelo]] = field(default_factory=dict)
    # Exemplo: {"IBM": {"random_walk": MetricasModelo(...), "media_movel": MetricasModelo(...)}}


def calcular_mae(y_real: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_real - y_pred)))


def calcular_rmse(y_real: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_real - y_pred) ** 2)))


class EtapaModelagem(Etapa[pd.DataFrame, pd.DataFrame]):
    def __init__(self, janela_media_movel: int = 5) -> None:
        self.janela = janela_media_movel
        self.resultado = ResultadoModelagem()

    @property
    def nome(self) -> str:
        return "modelagem"

    def executar(self, entrada: pd.DataFrame) -> pd.DataFrame:
        if entrada.empty:
            return entrada

        df = entrada.copy()
        df["data"] = pd.to_datetime(df["data"])
        # Garante ordenação temporal crescente por símbolo para que o lag/shift faça sentido
        df = df.sort_values(by=["simbolo", "data"]).reset_index(drop=True)

        dfs_simbolos = []
        self.resultado = ResultadoModelagem()

        for simbolo, grupo in df.groupby("simbolo", sort=False):
            g = grupo.copy()

            # Random Walk: a previsão para amanhã é o fechamento de hoje (shift de 1 dia)
            g["pred_random_walk"] = g["close"].shift(1)

            # Média Móvel: média dos últimos k dias deslocada em 1 dia para não vazar o dado atual
            g["pred_media_movel"] = (
                g["close"].rolling(window=self.janela).mean().shift(1)
            )

            # Filtra apenas dados com valida == 1 e onde as previsões não são nulas (NaN pelo rolling/shift)
            mascara_valida = (g["valida"] == 1) & g["pred_media_movel"].notna()
            dados_teste = g[mascara_valida]

            if not dados_teste.empty:
                y_real = dados_teste["close"].to_numpy()
                y_rw = dados_teste["pred_random_walk"].to_numpy()
                y_ma = dados_teste["pred_media_movel"].to_numpy()

                self.resultado.metricas[simbolo] = {
                    "random_walk": MetricasModelo(
                        mae=calcular_mae(y_real, y_rw),
                        rmse=calcular_rmse(y_real, y_rw),
                    ),
                    "media_movel": MetricasModelo(
                        mae=calcular_mae(y_real, y_ma),
                        rmse=calcular_rmse(y_real, y_ma),
                    ),
                }

            dfs_simbolos.append(g)

        return pd.concat(dfs_simbolos, ignore_index=True)