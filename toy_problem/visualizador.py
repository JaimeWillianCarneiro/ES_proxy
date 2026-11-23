"""Implementação do padrão Proxy usando um Visualizador de Imagens Pesadas.

Papéis do padrão (GoF):
- Subject: `Imagem`
- RealSubject: `ImagemReal`
- Proxy: `ImagemProxy`
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable


class ErroAcessoImagem(PermissionError):
    """Lançada pelo Proxy de Proteção quando o usuário não tem permissão."""


class Imagem(ABC):
    """Subject: interface comum entre o objeto real e o proxy."""

    @abstractmethod
    def exibir(self) -> str:
        """Renderiza e retorna a representação visual da imagem."""


class ImagemReal(Imagem):
    """RealSubject: objeto pesado cujo carregamento em disco/rede é custoso."""

    def __init__(
        self,
        caminho_arquivo: str,
        tempo_carregamento_s: float = 1.5,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.caminho_arquivo = caminho_arquivo
        self.exibicoes = 0
        # Simula o custo de ler e decodificar uma imagem de alta resolução
        dormir(tempo_carregamento_s)
        self._conteudo_decodificado = f"<Pixels 8K de '{caminho_arquivo}'>"

    def exibir(self) -> str:
        self.exibicoes += 1
        return f"Exibindo {self._conteudo_decodificado}"


class ImagemProxy(Imagem):
    """Proxy (Virtual + Proteção): controla acesso e adia a criação do RealSubject."""

    PERFIS_AUTORIZADOS = frozenset({"admin", "editor"})

    def __init__(
        self,
        caminho_arquivo: str,
        perfil_usuario: str,
        tempo_carregamento_s: float = 1.5,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self._caminho_arquivo = caminho_arquivo
        self._perfil_usuario = perfil_usuario
        self._tempo_carregamento_s = tempo_carregamento_s
        self._dormir = dormir
        self._imagem_real: ImagemReal | None = None

    @property
    def carregada(self) -> bool:
        """Indica se o RealSubject já foi instanciado na memória."""
        return self._imagem_real is not None

    def exibir(self) -> str:
        # 1. Proxy de Proteção: bloqueia acesso não autorizado antes de gastar recursos
        if self._perfil_usuario not in self.PERFIS_AUTORIZADOS:
            raise ErroAcessoImagem(
                f"Perfil '{self._perfil_usuario}' não tem permissão para abrir '{self._caminho_arquivo}'."
            )

        # 2. Proxy Virtual (Lazy Loading): instancia o objeto pesado apenas na 1ª necessidade
        if self._imagem_real is None:
            self._imagem_real = ImagemReal(
                caminho_arquivo=self._caminho_arquivo,
                tempo_carregamento_s=self._tempo_carregamento_s,
                dormir=self._dormir,
            )

        # 3. Delegação: repassa a chamada ao RealSubject mantendo a mesma interface
        return self._imagem_real.exibir()