from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

from pipeline_proxy.nucleo.etapa import Etapa


class EtapaVisualizacao(Etapa[pd.DataFrame, pd.DataFrame]):
    def __init__(self, dir_saida: Path | str) -> None:
        self.dir_saida = Path(dir_saida)
        self.arquivos_gerados: list[Path] = []

    @property
    def nome(self) -> str:
        return "visualizacao"

    def executar(self, entrada: pd.DataFrame) -> pd.DataFrame:
        if entrada.empty:
            return entrada

        self.dir_saida.mkdir(parents=True, exist_ok=True)
        self.arquivos_gerados.clear()

        df = entrada.copy()
        df["data"] = pd.to_datetime(df["data"])

        # 1. Exporta CSV consolidado com dados reais e previsões
        caminho_csv = self.dir_saida / "previsoes.csv"
        df.to_csv(caminho_csv, index=False)
        self.arquivos_gerados.append(caminho_csv)

        # 2. Gera gráficos por símbolo
        for simbolo, grupo in df.groupby("simbolo"):
            g = grupo.sort_values("data").dropna(subset=["pred_media_movel"])
            if g.empty:
                continue

            fig, ax = plt.subplots(figsize=(12, 6))

            # Preço Real
            ax.plot(g["data"], g["close"], label="Real (Close)", color="#1f77b4", linewidth=1.8)

            # Random Walk
            ax.plot(
                g["data"],
                g["pred_random_walk"],
                label="Prev. Random Walk (Naive)",
                color="#ff7f0e",
                linestyle="--",
                alpha=0.8,
            )

            # Média Móvel
            ax.plot(
                g["data"],
                g["pred_media_movel"],
                label="Prev. Média Móvel (k=5)",
                color="#2ca02c",
                linestyle="-.",
                alpha=0.8,
            )

            # Destaque para outliers se houver
            outliers = g[g["outlier"] == 1]
            if not outliers.empty:
                ax.scatter(
                    outliers["data"],
                    outliers["close"],
                    color="#d62728",
                    s=50,
                    zorder=5,
                    label="Outlier identificado",
                )

            ax.set_title(f"Cotações Reais × Previstas — {simbolo}", fontsize=14, fontweight="bold")
            ax.set_xlabel("Data", fontsize=11)
            ax.set_ylabel("Preço de Fechamento", fontsize=11)
            ax.legend(loc="best")

            fig.tight_layout()

            caminho_png = self.dir_saida / f"grafico_{simbolo.replace('.', '_')}.png"
            fig.savefig(caminho_png, dpi=150)
            plt.close(fig)

            self.arquivos_gerados.append(caminho_png)

        return entrada