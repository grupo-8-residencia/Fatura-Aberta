"""Erros da extração.

As mensagens nunca incluem trechos do texto da fatura, para que dados pessoais não vazem
por exceções, logs ou tracebacks.
"""


class ErroExtracao(ValueError):
    """A fatura não pôde ser convertida em `Fatura`."""
