from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd

from pipeline_proxy.extracao.estado import RepositorioEstado
from pipeline_proxy.nucleo.etapa import Etapa


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cotacoes (
    simbolo TEXT NOT NULL,
    data TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    valida INTEGER,
    retorno REAL,
    outlier INTEGER,
    volume_escalado REAL,
    PRIMARY KEY (simbolo, data)
);
"""

UPSERT_SQL = """
INSERT INTO cotacoes (
    simbolo, data, open, high, low, close, volume, valida, retorno, outlier, volume_escalado
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(simbolo, data) DO UPDATE SET
    open = excluded.open,
    high = excluded.high,
    low = excluded.low,
    close = excluded.close,
    volume = excluded.volume,
    valida = excluded.valida,
    retorno = excluded.retorno,
    outlier = excluded.outlier,
    volume_escalado = excluded.volume_escalado;
"""


class EtapaCarga(Etapa[pd.DataFrame, pd.DataFrame]):
    def __init__(
        self,
        caminho_banco: Path | str,
        estado: RepositorioEstado | None = None,
    ) -> None:
        self.caminho_banco = Path(caminho_banco)
        self.estado = estado
        self.linhas_afetadas: int = 0
        self._inicializar_banco()

    @property
    def nome(self) -> str:
        return "carga"

    def _inicializar_banco(self) -> None:
        self.caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.caminho_banco) as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()

    def executar(self, entrada: pd.DataFrame) -> pd.DataFrame:
        if entrada.empty:
            self.linhas_afetadas = 0
            return entrada

        df = entrada.copy()
        datas_dt = pd.to_datetime(df["data"])
        df["data"] = datas_dt.dt.strftime("%Y-%m-%d")

        colunas = [
            "simbolo",
            "data",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "valida",
            "retorno",
            "outlier",
            "volume_escalado",
        ]

        for col_bool in ("valida", "outlier"):
            if col_bool in df.columns:
                df[col_bool] = df[col_bool].astype(int)

        registros = [
            tuple(linha) for linha in df[colunas].itertuples(index=False, name=None)
        ]

        with sqlite3.connect(self.caminho_banco) as conn:
            cursor = conn.cursor()
            cursor.executemany(UPSERT_SQL, registros)
            conn.commit()
            self.linhas_afetadas = cursor.rowcount

        # Só atualiza a watermark SE a transação do banco foi concluída com sucesso
        if self.estado is not None:
            # Agrupa por símbolo e pega a maior data
            for simbolo, max_data in datas_dt.groupby(df["simbolo"]).max().items():
                self.estado.salvar(str(simbolo), max_data.date())

        return entrada