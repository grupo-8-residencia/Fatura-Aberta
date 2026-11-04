"""Descarte de dados pessoais (nome, endereço, número da instalação, CPF/CNPJ).

Defesa em duas camadas: o parser só lê campos de uma lista explícita (e o contrato `Fatura`
não tem onde guardar dados pessoais), e `anonimizar` limpa qualquer texto que precise ser
registrado ou exibido.
"""

import re

MARCA = "[removido]"

# Linhas rotuladas com dados pessoais: o valor depois do rótulo é descartado.
# TODO: confirmar os rótulos reais com o mapa dos layouts (#9).
_ROTULOS_PESSOAIS = (
    r"(?:nome|cliente|titular|endere[cç]o|instala[cç][aã]o|unidade consumidora|cpf|cnpj|cep)"
)
_LINHA_ROTULADA = re.compile(rf"(?im)^(\s*{_ROTULOS_PESSOAIS}\b[^:\n]*:).*$")

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


def anonimizar(texto: str) -> str:
    """Remove dados pessoais do texto: linhas rotuladas, CPF, CNPJ e e-mail."""
    texto = _LINHA_ROTULADA.sub(rf"\1 {MARCA}", texto)
    for padrao in (_CNPJ, _CPF, _EMAIL):
        texto = padrao.sub(MARCA, texto)
    return texto
