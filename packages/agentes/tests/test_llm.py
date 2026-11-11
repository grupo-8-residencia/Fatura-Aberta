"""Testes do cliente de LLM, do cliente falso e do verificador RF-15 (sem rede)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import request

import pytest

from fa_agentes import llm
from fa_agentes.linguagem import linguagem_permitida, verificar_linguagem


def _resposta_ollama(texto: str = '{"ok": true}') -> bytes:
    return json.dumps(
        {"message": {"content": texto}, "prompt_eval_count": 11, "eval_count": 7}
    ).encode("utf-8")


class _OllamaSimulado:
    """Substitui `llm._abrir`: responde /api/tags e /api/chat e guarda os corpos enviados."""

    def __init__(self) -> None:
        self.chat: list[dict[str, Any]] = []

    def __call__(self, req: request.Request, timeout: float) -> bytes:
        if req.full_url.endswith("/api/tags"):
            return json.dumps(
                {"models": [{"name": "gpt-oss:20b", "digest": "17052f91a42e97930aa6e28a6c6c06a9"}]}
            ).encode("utf-8")
        assert isinstance(req.data, bytes)
        self.chat.append(json.loads(req.data))
        return _resposta_ollama()


def test_cliente_falso_e_deterministico_e_registra_chamadas() -> None:
    c = llm.ClienteFalso(resposta=lambda s, p: json.dumps({"eco": p}))
    r = c.gerar(sistema="s", prompt="olá")
    assert r.json() == {"eco": "olá"} and r.digest == "falso" and c.versao() == "falso"
    assert c.chamadas == [("s", "olá")]


def test_criar_cliente_padrao_e_falso_e_nao_usa_rede() -> None:
    assert isinstance(llm.criar_cliente(env={}), llm.ClienteFalso)
    with pytest.raises(ValueError, match="desconhecido"):
        llm.criar_cliente(env={"FA_LLM_PROVEDOR": "nuvem"})


def test_criar_cliente_ollama_usa_modelos_diferentes_para_gerador_e_juiz() -> None:
    env = {"FA_LLM_PROVEDOR": "ollama"}
    g = llm.criar_cliente("gerador", env)
    j = llm.criar_cliente("juiz", env)
    assert isinstance(g, llm.ClienteOllama) and isinstance(j, llm.ClienteOllama)
    assert g.modelo == "gpt-oss:20b" and j.modelo == "qwen3:14b"
    assert g.temperatura == 0.0 and g.semente == 42
    assert g.pensar == "low" and j.pensar is False


def test_ollama_envia_temperatura_zero_semente_e_esquema(monkeypatch: pytest.MonkeyPatch) -> None:
    falso = _OllamaSimulado()
    monkeypatch.setattr(llm, "_abrir", falso)
    c = llm.ClienteOllama(pensar="low")
    esquema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    r = c.gerar(sistema="regras", prompt="pergunta", esquema=esquema)
    corpo = falso.chat[0]
    assert corpo["options"]["temperature"] == 0.0 and corpo["options"]["seed"] == 42
    assert corpo["format"] == esquema and corpo["think"] == "low" and corpo["stream"] is False
    assert r.json() == {"ok": True} and r.tokens_entrada == 11 and r.tokens_saida == 7
    assert r.digest == "17052f91a42e" and c.versao() == "17052f91a42e"


def test_ollama_cache_evita_chamada_repetida(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    falso = _OllamaSimulado()
    monkeypatch.setattr(llm, "_abrir", falso)
    c = llm.ClienteOllama(cache_dir=tmp_path)
    a = c.gerar(sistema="s", prompt="p")
    b = c.gerar(sistema="s", prompt="p")
    assert len(falso.chat) == 1 and not a.do_cache and b.do_cache and a.texto == b.texto
    c.gerar(sistema="s", prompt="outro")
    assert len(falso.chat) == 2


def test_modelo_ausente_levanta_erro_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_abrir", _OllamaSimulado())
    with pytest.raises(RuntimeError, match="não está instalado"):
        llm.ClienteOllama(modelo="inexistente:1b").versao()


def test_metadados_da_rodada_gravam_modelo_versao_e_hash_do_golden_set(tmp_path: Path) -> None:
    sums = tmp_path / "checksums.sha256"
    sums.write_text("abc  perguntas.jsonl\n", encoding="utf-8")
    meta = llm.metadados_rodada({"gerador": llm.ClienteFalso()}, checksums=sums, raiz=tmp_path)
    assert meta["temperatura"] == 0.0 and meta["semente"] == 42
    assert meta["modelos"]["gerador"] == {
        "provedor": "falso",
        "modelo": "falso-1",
        "versao": "falso",
    }
    assert len(meta["sha256_checksums_golden_set"]) == 64
    assert meta["data_utc"].endswith("Z") and meta["commit"]


def test_nenhuma_credencial_no_codigo_do_cliente() -> None:
    fonte = Path(llm.__file__).read_text(encoding="utf-8")
    assert "API_KEY" not in fonte and "Bearer" not in fonte


@pytest.mark.parametrize(
    "texto",
    [
        "Esta cobrança é ilegal.",
        "Há ILEGALIDADE na fatura.",
        "Você tem direito à restituição em dobro.",
        "Procure uma ação judicial.",
        "Isso configura fraude.",
        "Peça indenização por danos morais.",
    ],
)
def test_rf15_bloqueia_expressoes_proibidas(texto: str) -> None:
    assert verificar_linguagem(texto)
    assert not linguagem_permitida(texto)


def test_rf15_aceita_linguagem_de_evidencia() -> None:
    texto = (
        "O consumo faturado não corresponde à diferença entre as leituras. "
        "Recomenda-se solicitar a memória de cálculo à distribuidora."
    )
    assert verificar_linguagem(texto) == []
    assert linguagem_permitida("A tarifa diverge da tabela oficial que conseguimos obter.")
