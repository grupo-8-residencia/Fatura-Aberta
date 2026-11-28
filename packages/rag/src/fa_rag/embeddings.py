"""Extratores de embeddings configuráveis, com fallback determinístico e offline."""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request
from collections.abc import Sequence
from typing import Protocol

from fa_rag.texto import sem_acentos, tokenizar

DIM_PADRAO = 384
OLLAMA_URL_PADRAO = "http://localhost:11434"

_CONCEITOS_PTBR: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tarifa_social", ("baixa", "renda", "cadun", "bpc", "salari", "social", "idoso", "defic")),
    ("custo_disponibilidade", ("dispo", "minim", "consu", "baixo", "conve", "compe")),
    (
        "fatura_informacoes",
        ("fatur", "grand", "tarif", "histo", "impos", "codig", "posto", "branc"),
    ),
    ("bandeira_tarifaria", ("bande", "amare", "verme", "verde", "patam", "adici", "propo")),
    (
        "calendario_leitura",
        ("leitu", "medic", "inter", "calen", "reman", "repro", "27", "33", "47"),
    ),
    ("impedimento_media", ("imped", "acess", "media", "aritm", "estim", "12", "ciclo", "deman")),
    ("faturamento_mensal", ("mensa", "frequ", "civil", "dupli")),
    ("faturamento_suspensao", ("duran", "suspe", "relig", "ciclo")),
    ("devolucao_dobro", ("devol", "dobro", "indev", "repet", "indeb", "maior", "menor", "dolo")),
    ("erro_consumidor", ("atrib", "motiv", "consu", "falsa", "decla", "36")),
    ("pagamento_duplicidade", ("dupli", "pagam", "credi", "subse", "corren", "chequ")),
    ("encargos_atraso", ("multa", "atras", "juros", "mora", "ipca", "feria", "sabad", "doming")),
    ("vencimento_prazos", ("venci", "apres", "uteis", "orgao", "publi", "datas", "escol")),
    ("prazo_cobranca_atraso", ("60", "meses", "atras", "cinco", "anos")),
    ("notificacao_corte", ("notif", "antec", "15", "suspe", "inadi", "desta")),
    ("suspensao_indevida", ("indev", "pix", "execu", "limit", "obser", "suspe", "notif")),
    ("prazo_maximo_corte", ("90", "dias", "venci", "imped", "judic")),
    ("vital_saude", ("vital", "equip", "apare", "saude", "vida", "compr", "essen")),
    ("cip_cosip_direitos", ("cip", "ilumi", "publi", "7888", "distr", "revis", "resti", "impug")),
    (
        "cdc_direitos_basicos",
        ("onus", "prova", "inver", "veros", "hipos", "dano", "moral", "repar"),
    ),
    ("cdc_praticas_abusivas", ("abusi", "vanta", "exces", "orcam", "autor", "ridic", "const")),
    ("qualidade_prodist", ("prodi", "modul", "dic", "fic", "dmic", "dicri", "contin", "compe")),
    ("tarifa_homologada_reh", ("homol", "reh", "3614", "3542", "tusd", "neoen", "aplic")),
)


class Embedder(Protocol):
    """Contrato mínimo: vetores L2-normalizados de dimensão fixa."""

    dim: int

    def embed(self, textos: Sequence[str]) -> list[list[float]]: ...


class EmbedderHash:
    """Hashing de unigramas, bigramas e trigramas de caracteres (determinístico, sem rede).

    Usa blake2b (estável entre execuções, ao contrário de ``hash()``) e pesos não negativos,
    de modo que o cosseno fica em [0, 1]. Não é semântico: captura sobreposição lexical e
    morfológica. É o padrão do CI; um modelo multilíngue pt-BR entra pelo mesmo contrato.
    """

    nome = "hash-ngramas-blake2b"
    versao = "1"

    def __init__(self, dim: int = DIM_PADRAO) -> None:
        if dim < 8:
            raise ValueError("dim deve ser >= 8")
        self.dim = dim

    def _indice(self, caracteristica: str) -> int:
        digest = hashlib.blake2b(caracteristica.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dim

    def _vetor(self, texto: str) -> list[float]:
        vetor = [0.0] * self.dim
        tokens = tokenizar(texto)
        for token in tokens:
            vetor[self._indice(f"u:{token}")] += 1.0
        for a, b in zip(tokens, tokens[1:], strict=False):
            vetor[self._indice(f"b:{a}_{b}")] += 0.7
        limpo = " ".join(sem_acentos(texto).lower().split())
        for i in range(len(limpo) - 2):
            trecho = limpo[i : i + 3]
            if trecho.strip() and " " not in trecho:
                vetor[self._indice(f"c:{trecho}")] += 0.2
        norma = math.sqrt(sum(x * x for x in vetor))
        return [x / norma for x in vetor] if norma > 0 else vetor

    def embed(self, textos: Sequence[str]) -> list[list[float]]:
        return [self._vetor(t) for t in textos]


class EmbedderSemanticoPtBr:
    """Embedder híbrido léxico-conceitual para português regulatório (determinístico e offline).

    Combina projeção em 23 eixos conceituais do domínio elétrico/consumerista pt-BR com
    n-gramas morfológicos normalizados, sem exigir download de pesos em rede no CI.
    """

    nome = "semantico-conceitual-ptbr"
    versao = "1"

    def __init__(self, dim: int = DIM_PADRAO) -> None:
        if dim < 32:
            raise ValueError("dim deve ser >= 32")
        self.dim = dim
        self._hash = EmbedderHash(dim=dim)

    def _indice(self, caracteristica: str) -> int:
        digest = hashlib.blake2b(caracteristica.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.dim

    def _vetor(self, texto: str) -> list[float]:
        base = list(self._hash._vetor(texto))
        tokens = set(tokenizar(texto))
        for nome_conceito, radicais in _CONCEITOS_PTBR:
            aderencia = sum(1 for r in radicais if r in tokens)
            if aderencia >= 2:
                peso = 0.16 * math.log1p(aderencia)
                base[self._indice(f"sem:{nome_conceito}:0")] += peso
                base[self._indice(f"sem:{nome_conceito}:1")] += peso * 0.75
        norma = math.sqrt(sum(x * x for x in base))
        return [x / norma for x in base] if norma > 0 else base

    def embed(self, textos: Sequence[str]) -> list[list[float]]:
        return [self._vetor(t) for t in textos]


class EmbedderOllama:
    """Extrator de embeddings semânticos via servidor Ollama local (``/api/embed``).

    Permite usar modelos multilíngues/pt-BR com licença permissiva (ex.: ``bge-m3`` MIT ou
    ``qwen3-embedding:0.6b`` Apache-2.0) pelo protocolo ``Embedder``, sem adicionar
    dependências pesadas nem tráfego de rede ao CI padrão.
    """

    def __init__(
        self,
        modelo: str = "bge-m3",
        *,
        url_base: str | None = None,
        digest: str = "",
        dim: int | None = None,
    ) -> None:
        self.modelo = modelo
        self.url_base = (
            url_base or os.environ.get("FA_RAG_OLLAMA_URL") or OLLAMA_URL_PADRAO
        ).rstrip("/")
        self.nome = f"ollama:{modelo}"
        self.versao = digest or "local"
        self.dim = dim if dim is not None else len(self.embed(["dimensão"])[0])

    def embed(self, textos: Sequence[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for i in range(0, len(textos), 16):
            corpo = json.dumps({"model": self.modelo, "input": list(textos[i : i + 16])})
            req = urllib.request.Request(
                f"{self.url_base}/api/embed",
                data=corpo.encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resposta:  # noqa: S310
                bruto = json.loads(resposta.read())["embeddings"]
            for v in bruto:
                norma = math.sqrt(sum(x * x for x in v)) or 1.0
                vetores.append([x / norma for x in v])
        return vetores


def criar_embedder(nome: str | None = None) -> Embedder:
    """Escolhe o extrator por ``FA_RAG_EMBEDDER`` (padrão ``hash``).

    Opções:
    - ``hash``: ``EmbedderHash`` (padrão determinístico e offline do CI);
    - ``semantico`` / ``ptbr``: ``EmbedderSemanticoPtBr`` (projeção conceitual pt-BR offline);
    - ``ollama:<modelo>``: ``EmbedderOllama`` conectado ao servidor Ollama local.
    """
    escolhido = (nome or os.environ.get("FA_RAG_EMBEDDER") or "hash").strip().lower()
    if escolhido == "hash":
        return EmbedderHash()
    if escolhido in {"semantico", "ptbr", "semantico-ptbr"}:
        return EmbedderSemanticoPtBr()
    if escolhido.startswith("ollama:"):
        modelo = escolhido.split(":", 1)[1].strip() or "bge-m3"
        return EmbedderOllama(modelo=modelo)
    raise ValueError(
        f"Embedder desconhecido: {escolhido!r} (disponíveis: hash, semantico, ollama:<modelo>)"
    )
