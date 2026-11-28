"""Descarte de dados pessoais (nome, endereço, número da instalação, CPF/CNPJ).

Defesa em duas camadas: o parser só lê campos de uma lista explícita (e o contrato `Fatura`
não tem onde guardar dados pessoais), e `anonimizar` limpa qualquer texto que precise ser
registrado ou exibido.
"""

import re

MARCA = "[removido]"

# Linhas que começam com um rótulo de dado pessoal. O separador é opcional: o texto extraído de
# PDF pode vir como "Nome: Maria", "Nome Maria" ou com o valor na linha seguinte. A linha seguinte
# só é descartada quando o rótulo está sozinho na linha.
# Rótulos reais confirmados a partir do mapeamento de layouts (issue #9, docs/frentes/f4.md),
# cobrindo também segunda via (código da instalação/cliente) e bloco do boleto (pagador).
_ROTULOS_PESSOAIS = (
    r"(?:nome|cliente|titular|endere[cç]o|instala[cç][aã]o|unidade consumidora|cpf|cnpj|cep|"
    r"pagador|c[oó]digo\s+(?:da\s+instala[cç][aã]o|do\s+cliente))"
)
_LINHA_ROTULADA = re.compile(
    rf"(?im)^(?P<rotulo>[ \t]*(?:n[ºo°]\.?[ \t]*(?:da|do)[ \t]+)?{_ROTULOS_PESSOAIS}\b)"
    r"(?:[ \t:-]*\n[ \t]*[^\n]+|[^\n]*)"
)

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


def anonimizar(texto: str) -> str:
    """Remove dados pessoais do texto: linhas rotuladas, CPF, CNPJ e e-mail.

    Prefere remover a mais: uma linha que comece com rótulo pessoal perde todo o conteúdo.
    """
    texto = _LINHA_ROTULADA.sub(rf"\g<rotulo>: {MARCA}", texto)
    for padrao in (_CNPJ, _CPF, _EMAIL):
        texto = padrao.sub(MARCA, texto)
    return texto
