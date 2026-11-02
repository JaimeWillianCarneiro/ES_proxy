"""Hierarquia de erros da extração.

A separação entre erro transitório e permanente existe para que quem está em
volta da fonte (o futuro proxy) saiba se vale a pena tentar de novo:

- ErroTransitorio: repetir pode resolver (timeout, 5xx, limite por segundo).
- ErroPermanente: repetir não adianta (símbolo inválido, chave inválida,
  cota diária esgotada).
"""


class ErroExtracao(Exception):
    """Base de todos os erros da etapa de extração."""


class ErroTransitorio(ErroExtracao):
    """Falha temporária: uma nova tentativa pode ter sucesso."""


class ErroLimiteRequisicoes(ErroTransitorio):
    """Limite de requisições por segundo/minuto atingido; esperar e repetir resolve."""


class ErroPermanente(ErroExtracao):
    """Falha definitiva: repetir a mesma chamada não vai resolver."""


class ErroAutenticacao(ErroPermanente):
    """API key ausente ou inválida."""


class ErroCotaEsgotada(ErroPermanente):
    """Cota diária do plano esgotada; só volta no dia seguinte."""
