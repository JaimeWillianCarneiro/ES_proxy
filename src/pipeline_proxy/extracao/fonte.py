"""Interface da fonte de dados — o *Subject* do padrão Proxy.

Quem consome dados (a EtapaExtracao) depende só desta interface. Hoje ela é
implementada pelo AlphaVantageClient (RealSubject); depois, um proxy vai
implementá-la também, e a troca acontece apenas em `criar_fonte()` no main.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pipeline_proxy.dominio import LoteExtracao, Tamanho


class FonteDados(ABC):
    @abstractmethod
    def buscar_diario(self, simbolo: str, tamanho: Tamanho = Tamanho.COMPACT) -> LoteExtracao:
        """Retorna a série diária bruta (OHLCV) do símbolo.

        Lança ErroTransitorio quando repetir pode resolver e ErroPermanente
        quando não pode (ver pipeline_proxy.erros).
        """
