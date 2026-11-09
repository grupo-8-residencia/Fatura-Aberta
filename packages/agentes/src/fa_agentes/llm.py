"""Cliente de LLM do experimento (F5): Ollama local, cliente falso para o CI e metadados de rodada.

Só biblioteca padrão. Nada de credencial no repositório: o que for sensível vem de variável de
ambiente. O provedor padrão é o ``falso``, então o CI roda sem rede e sem modelo.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib import request

TEMPERATURA = 0.0
SEMENTE = 42
URL_PADRAO = "http://localhost:11434"
MODELO_GERADOR_PADRAO = "gpt-oss:20b"
MODELO_JUIZ_PADRAO = "qwen3:14b"


@dataclass(frozen=True, slots=True)
class RespostaLLM:
    """Resposta de uma chamada, com o que é preciso para reproduzir a rodada."""

    texto: str
    modelo: str
    digest: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    duracao_s: float = 0.0
    do_cache: bool = False

    def json(self) -> Any:
        """Interpreta ``texto`` como JSON (levanta ``ValueError`` se não for)."""
        return json.loads(self.texto)


class ClienteLLM(Protocol):
    """Contrato mínimo que os baselines e o juiz usam."""

    provedor: str
    modelo: str

    def versao(self) -> str: ...

    def gerar(
        self, *, sistema: str, prompt: str, esquema: Mapping[str, Any] | None = None
    ) -> RespostaLLM: ...


def _abrir(req: request.Request, timeout: float) -> bytes:
    with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL é do ambiente local)
        data: bytes = resp.read()
    return data


def _chave_cache(partes: Mapping[str, Any]) -> str:
    bruto = json.dumps(partes, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ClienteOllama:
    """Chamadas ao Ollama com temperatura 0, semente fixa e saída estruturada opcional."""

    modelo: str = MODELO_GERADOR_PADRAO
    url: str = URL_PADRAO
    temperatura: float = TEMPERATURA
    semente: int = SEMENTE
    timeout_s: float = 600.0
    contexto: int = 8192
    pensar: bool | str | None = None
    cache_dir: Path | None = None
    provedor: str = field(default="ollama", init=False)
    _digest: str | None = field(default=None, init=False, repr=False)

    def versao(self) -> str:
        """Digest do modelo local: é a versão fixa da rodada."""
        if self._digest is None:
            req = request.Request(f"{self.url}/api/tags", method="GET")
            dados = json.loads(_abrir(req, 15.0))
            achados = [m for m in dados.get("models", []) if m.get("name") == self.modelo]
            if not achados:
                raise RuntimeError(f"Modelo {self.modelo!r} não está instalado no Ollama")
            self._digest = str(achados[0]["digest"])[:12]
        return self._digest

    def _payload(
        self, sistema: str, prompt: str, esquema: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        corpo: dict[str, Any] = {
            "model": self.modelo,
            "stream": False,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": self.temperatura,
                "seed": self.semente,
                "num_ctx": self.contexto,
            },
        }
        if esquema is not None:
            corpo["format"] = dict(esquema)
        if self.pensar is not None:
            corpo["think"] = self.pensar
        return corpo

    def gerar(
        self, *, sistema: str, prompt: str, esquema: Mapping[str, Any] | None = None
    ) -> RespostaLLM:
        corpo = self._payload(sistema, prompt, esquema)
        chave = _chave_cache({"digest": self.versao(), "corpo": corpo})
        arquivo = self.cache_dir / f"{chave}.json" if self.cache_dir else None
        if arquivo is not None and arquivo.exists():
            guardado = json.loads(arquivo.read_text(encoding="utf-8"))
            return RespostaLLM(**{**guardado, "do_cache": True})
        req = request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        inicio = time.perf_counter()
        dados = json.loads(_abrir(req, self.timeout_s))
        resposta = RespostaLLM(
            texto=str(dados.get("message", {}).get("content", "")),
            modelo=self.modelo,
            digest=self.versao(),
            tokens_entrada=int(dados.get("prompt_eval_count", 0)),
            tokens_saida=int(dados.get("eval_count", 0)),
            duracao_s=round(time.perf_counter() - inicio, 3),
        )
        if arquivo is not None:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            guardado = {k: getattr(resposta, k) for k in resposta.__slots__ if k != "do_cache"}
            arquivo.write_text(json.dumps(guardado, ensure_ascii=False), encoding="utf-8")
        return resposta


@dataclass(slots=True)
class ClienteFalso:
    """Cliente determinístico para testes e CI: sem rede, sem modelo, sem chave."""

    resposta: str | Callable[[str, str], str] = '{"resposta": "falso"}'
    modelo: str = "falso-1"
    provedor: str = field(default="falso", init=False)
    chamadas: list[tuple[str, str]] = field(default_factory=list, init=False)

    def versao(self) -> str:
        return "falso"

    def gerar(
        self, *, sistema: str, prompt: str, esquema: Mapping[str, Any] | None = None
    ) -> RespostaLLM:
        self.chamadas.append((sistema, prompt))
        texto = self.resposta(sistema, prompt) if callable(self.resposta) else self.resposta
        return RespostaLLM(texto=texto, modelo=self.modelo, digest="falso")


def criar_cliente(
    papel: str = "gerador",
    env: Mapping[str, str] | None = None,
    *,
    cache_dir: Path | None = None,
) -> ClienteLLM:
    """Escolhe o cliente por variáveis de ambiente (padrão: ``falso``).

    ``FA_LLM_PROVEDOR`` (``falso`` ou ``ollama``), ``FA_LLM_MODELO`` (gerador),
    ``FA_LLM_JUIZ_MODELO`` (juiz), ``FA_LLM_URL``. O juiz usa, por padrão, um modelo de outra
    família que o gerador, para reduzir o viés de autoavaliação.
    """
    ambiente = os.environ if env is None else env
    provedor = ambiente.get("FA_LLM_PROVEDOR", "falso").lower()
    if provedor == "falso":
        return ClienteFalso()
    if provedor == "ollama":
        if papel == "juiz":
            modelo = ambiente.get("FA_LLM_JUIZ_MODELO", MODELO_JUIZ_PADRAO)
            pensar: bool | str | None = False
        else:
            modelo = ambiente.get("FA_LLM_MODELO", MODELO_GERADOR_PADRAO)
            pensar = "low" if modelo.startswith("gpt-oss") else False
        return ClienteOllama(
            modelo=modelo, url=ambiente.get("FA_LLM_URL", URL_PADRAO), pensar=pensar,
            cache_dir=cache_dir,
        )  # fmt: skip
    raise ValueError(f"Provedor desconhecido: {provedor!r} (disponíveis: falso, ollama)")


def _commit_git(raiz: Path) -> str:
    try:
        saida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=raiz, capture_output=True, text=True, check=True, timeout=10,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"
    return saida.stdout.strip() or "desconhecido"


def metadados_rodada(
    clientes: Mapping[str, ClienteLLM],
    *,
    checksums: Path | None = None,
    raiz: Path | None = None,
) -> dict[str, Any]:
    """Cabeçalho de toda rodada: modelos, versões, temperatura, semente e hash do golden set."""
    hash_golden = (
        hashlib.sha256(checksums.read_bytes()).hexdigest()
        if checksums is not None and checksums.exists()
        else None
    )
    return {
        "data_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit_git(raiz or Path.cwd()),
        "temperatura": TEMPERATURA,
        "semente": SEMENTE,
        "sha256_checksums_golden_set": hash_golden,
        "modelos": {
            papel: {"provedor": c.provedor, "modelo": c.modelo, "versao": c.versao()}
            for papel, c in clientes.items()
        },
    }
