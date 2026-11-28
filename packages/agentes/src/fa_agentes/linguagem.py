"""Verificador de linguagem (RF-15): bloqueia a conclusão inadequada, não a palavra isolada.

As regras vêm de `docs/conformidade/recomendacoes-juridico-regulatorias.md` (seção 6) e de
`docs/conformidade/fronteira-juridica.md`. O produto usa linguagem de evidência: nunca declara
cobrança "ilegal", nunca estima restituição e nunca orienta ação judicial.

Três casos, nesta ordem:
- ``TERMOS_SEMPRE_VEDADOS``: instrução ao consumidor (ex.: "não pague a fatura"), sem exceção.
- ``REGRAS``: conclusão. Um termo só é aceito quando o trecho em que aparece nega a função da
  ferramenta ("a ferramenta não calcula restituição"). Fora disso, bloqueia.
- Não há nível "exige revisão" no código; o relatório o prevê, mas a decisão fica para a F1.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

REGRAS: dict[str, tuple[str, ...]] = {
    "qualificacao_juridica": (
        "ilegal",
        "ilegais",
        "ilegalidade",
        "ilegalmente",
        "ilicito",
        "crime",
        "criminoso",
        "criminosa",
        "fraude",
        "golpe",
        "estelionato",
        "roubo",
        "extorsao",
    ),  # fmt: skip
    "reparacao_financeira": (
        "restituicao",
        "ressarcimento",
        "ressarcido",
        "repeticao de indebito",
        "danos morais",
        "dano material",
        "indenizacao",
        "devolucao em dobro",
        "enriquecimento ilicito",
        "obrigacao de indenizar",
    ),  # fmt: skip
    "aconselhamento_processual": (
        "acao judicial",
        "juizado especial",
        "peticao inicial",
        "causa ganha",
        "processar",
    ),  # fmt: skip
    "conclusao_contextual": (
        "cobranca abusiva",
        "abuso",
        "ma-fe",
        "ma fe",
        "valor devido",
        "debito inexistente",
    ),  # fmt: skip
}

TERMOS_SEMPRE_VEDADOS: dict[str, tuple[str, ...]] = {
    "instrucao_ao_consumidor": (
        "nao pague",
        "deixe de pagar",
        "suspenda o pagamento",
    ),  # fmt: skip
}

# Verbos que descrevem o que a ferramenta faz. "Não calcula restituição" é escopo; "tem direito à
# restituição" é conclusão.
_VERBOS_DE_ESCOPO = (
    "calcula",
    "calculamos",
    "estima",
    "estimamos",
    "determina",
    "determinamos",
    "afirma",
    "afirmamos",
    "indica",
    "indicamos",
    "avalia",
    "avaliamos",
    "analisa",
    "analisamos",
    "orienta",
    "orientamos",
    "conclui",
    "concluimos",
    "garante",
    "garantimos",
    "substitui",
    "substituimos",
    "define",
    "definimos",
    "faz",
    "fazemos",
    "preve",
    "prevemos",
)
_ESCOPO_NEGATIVO = re.compile(
    r"\bnao\s+(?:" + "|".join(_VERBOS_DE_ESCOPO) + r")\b|\bnao\s+e\s+possivel\b|\bnao\s+ha\s+como\b"
)
# Vírgula e conjunções fecham o trecho: "não calcula restituição, mas você tem direito a" não
# pode liberar a segunda menção.
_FRONTEIRA = re.compile(r"[.;:!?,]|\b(?:mas|porem|contudo|todavia|entretanto|pois)\b")
_CITACAO_LITERAL = re.compile(r"“[^”]*”")


@dataclass(frozen=True, slots=True)
class Violacao:
    regra: str
    termo: str


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return sem_acento.lower()


def _em_escopo_negado(base: str, inicio_termo: int) -> bool:
    """Verdadeiro quando o trecho antes do termo, dentro da mesma oração, nega uma função."""
    inicio = 0
    for marca in _FRONTEIRA.finditer(base, 0, inicio_termo):
        inicio = marca.end()
    return _ESCOPO_NEGATIVO.search(base[inicio:inicio_termo]) is not None


def _ocorre_como_conclusao(base: str, termo: str) -> bool:
    for ocorrencia in re.finditer(rf"\b{re.escape(termo)}s?\b", base):
        if not _em_escopo_negado(base, ocorrencia.start()):
            return True
    return False


def verificar_linguagem(texto: str, *, permitir_citacao_literal: bool = False) -> list[Violacao]:
    """Lista as violações do RF-15 encontradas no texto (vazia = texto permitido).

    Com ``permitir_citacao_literal``, o trecho transcrito da norma entre aspas curvas (“…”) não
    conta: é a exceção decidida em 18/11/2026 para a citação literal com referência canônica (ato,
    dispositivo e vigência), a validar com o docente de Direito (#4). Só quem garante que o trecho
    entre aspas é texto da norma, com a citação ao lado, pode ligar a exceção; texto redigido pelo
    sistema continua bloqueado.
    """
    if permitir_citacao_literal:
        texto = _CITACAO_LITERAL.sub(" ", texto)
    base = _normalizar(texto)
    achadas: list[Violacao] = []
    for regra, termos in TERMOS_SEMPRE_VEDADOS.items():
        for termo in termos:
            if re.search(rf"\b{re.escape(termo)}\b", base):
                achadas.append(Violacao(regra, termo))
    for regra, termos in REGRAS.items():
        for termo in termos:
            if _ocorre_como_conclusao(base, termo):
                achadas.append(Violacao(regra, termo))
    return achadas


def linguagem_permitida(texto: str) -> bool:
    return not verificar_linguagem(texto)
