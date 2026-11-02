"""Cliente da Alpha Vantage — o *RealSubject* do padrão Proxy.

Propositalmente "burro": monta a URL, faz a chamada HTTP, interpreta o JSON e
classifica os erros. Cache, novas tentativas e validação da chave ficam de fora
(são responsabilidade do proxy).
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

from pipeline_proxy.dominio import LoteExtracao, Tamanho, aplicar_schema, dataframe_vazio
from pipeline_proxy.erros import (
    ErroAutenticacao,
    ErroCotaEsgotada,
    ErroLimiteRequisicoes,
    ErroPermanente,
    ErroTransitorio,
)
from pipeline_proxy.extracao.fonte import FonteDados

log = logging.getLogger(__name__)

URL_BASE = "https://www.alphavantage.co/query"
CHAVE_SERIE = "Time Series (Daily)"
CAMPOS = {
    "1. open": "open",
    "2. high": "high",
    "3. low": "low",
    "4. close": "close",
    "5. volume": "volume",
}


class AlphaVantageClient(FonteDados):
    fonte = "alpha_vantage"

    def __init__(
        self,
        api_key: str,
        timeout_s: float = 10.0,
        url_base: str = URL_BASE,
        session: requests.Session | None = None,
    ):
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._url_base = url_base
        # Abrir a sessão HTTP é o custo de criar este objeto (e o que um
        # proxy virtual consegue adiar).
        self._session = session or requests.Session()
        self.chamadas_reais = 0

    def buscar_diario(self, simbolo: str, tamanho: Tamanho = Tamanho.COMPACT) -> LoteExtracao:
        params = {"function": "TIME_SERIES_DAILY", "symbol": simbolo, "apikey": self._api_key}
        # "compact" já é o padrão da API; enviar só quando for "full" mantém a
        # URL idêntica à da documentação, única aceita pela chave "demo".
        if tamanho is Tamanho.FULL:
            params["outputsize"] = str(tamanho)
        payload = self._requisitar(params)
        return LoteExtracao(
            simbolo=simbolo,
            dados=parse_serie_diaria(payload, simbolo),
            fonte=self.fonte,
            tamanho=tamanho,
        )

    def _requisitar(self, params: dict[str, str]) -> dict:
        self.chamadas_reais += 1
        log.info("[API] %s %s (chamada real nº %d)", params["function"], params["symbol"], self.chamadas_reais)
        try:
            resposta = self._session.get(self._url_base, params=params, timeout=self._timeout_s)
        except (requests.Timeout, requests.ConnectionError) as e:
            raise ErroTransitorio(f"falha de rede: {e}") from e

        if resposta.status_code == 429 or resposta.status_code >= 500:
            raise ErroTransitorio(f"HTTP {resposta.status_code}")
        if resposta.status_code >= 400:
            raise ErroPermanente(f"HTTP {resposta.status_code}")

        try:
            payload = resposta.json()
        except ValueError as e:
            raise ErroPermanente("resposta não é JSON") from e

        verificar_erro_na_resposta(payload)
        return payload


def verificar_erro_na_resposta(payload: dict) -> None:
    """A Alpha Vantage responde HTTP 200 mesmo em erro; o erro vem no corpo."""
    if "Error Message" in payload:
        msg = payload["Error Message"]
        if "apikey" in msg.lower():
            raise ErroAutenticacao(msg)
        raise ErroPermanente(msg)

    msg = payload.get("Note") or payload.get("Information")
    if msg is None:
        return
    texto = msg.lower()
    # A mensagem de limite por segundo também cita o limite diário, então a
    # ordem dos testes importa.
    if "per second" in texto or "per minute" in texto or "sparingly" in texto:
        raise ErroLimiteRequisicoes(msg)
    if "per day" in texto:
        raise ErroCotaEsgotada(msg)
    if "api key" in texto:
        raise ErroAutenticacao(msg)
    raise ErroPermanente(msg)


def parse_serie_diaria(payload: dict, simbolo: str) -> pd.DataFrame:
    """Converte o JSON da TIME_SERIES_DAILY para o schema do domínio.

    Só converte tipos e ordena por data: não remove duplicatas, não preenche
    faltantes e não valida valores — isso é trabalho da Transformação.
    """
    if CHAVE_SERIE not in payload:
        raise ErroPermanente(f"resposta sem '{CHAVE_SERIE}': chaves {list(payload)}")

    serie = payload[CHAVE_SERIE]
    if not serie:
        return dataframe_vazio()

    df = pd.DataFrame.from_dict(serie, orient="index").rename(columns=CAMPOS)
    df.index = pd.to_datetime(df.index)
    df = df.rename_axis("data").reset_index().assign(simbolo=simbolo)
    return aplicar_schema(df)
