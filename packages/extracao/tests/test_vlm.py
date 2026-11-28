"""Extrator com modelo de visão local, testado contra um Ollama falso em localhost.

Tudo sintético: a "foto" é um PNG mínimo gerado em memória e o "modelo" devolve JSON fictício,
incluindo dados pessoais FICTÍCIOS que não podem chegar à `Fatura` nem aos logs.
"""

import base64
import json
import logging
import struct
import threading
import zlib
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from fa_contratos import Fatura
from fa_extracao import (
    Confirmacao,
    ErroExtracao,
    ExtratorOllama,
    analisar_foto,
    criar_extrator,
    extrair_candidata,
)
from fa_extracao.vlm import ESQUEMA, MODELO_PADRAO, TAMANHO_MAXIMO, formato_da_imagem

NOME = "MARIA FICTICIA DA SILVA"
ENDERECO = "QUADRA 99 CONJUNTO Z CASA 7"
INSTALACAO = "0099887766"

LEITURA: dict[str, Any] = {
    "distribuidora": "NEOENERGIA DISTRIBUIÇÃO BRASÍLIA S.A",
    "grupo_tarifario": "B1",
    "mes_referencia": "10/2026",
    "leitura_anterior": "4.390",
    "leitura_atual": "4.467",
    "consumo_kwh": "77",
    "bandeira": "Amarela",
    "aliquota_icms": "12,00",
    "total": "81,95",
    "itens": [
        {"descricao": "Consumo-TUSD", "quantidade": "77,00", "unidade": "kWh",
         "tarifa": "0,51192150", "valor": "39,41"},
        {"descricao": "Consumo-TE", "quantidade": "77,00", "unidade": "kWh",
         "tarifa": None, "valor": "36,55"},
        {"descricao": "Ilum. Púb. Distrital", "quantidade": None, "unidade": None,
         "tarifa": None, "valor": "5,99"},
    ],
    # Um modelo desobediente devolvendo dados pessoais fora do esquema.
    "nome": NOME,
    "endereco": ENDERECO,
    "codigo_instalacao": INSTALACAO,
}  # fmt: skip


def _png(largura: int = 2, altura: int = 2) -> bytes:
    """PNG válido e mínimo (pixels brancos), só com a biblioteca padrão."""

    def bloco(tipo: bytes, dados: bytes) -> bytes:
        corpo = tipo + dados
        return struct.pack(">I", len(dados)) + corpo + struct.pack(">I", zlib.crc32(corpo))

    linhas = b"".join(b"\x00" + b"\xff" * 3 * largura for _ in range(altura))
    cabecalho = struct.pack(">IIBBBBB", largura, altura, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + bloco(b"IHDR", cabecalho)
        + bloco(b"IDAT", zlib.compress(linhas))
        + bloco(b"IEND", b"")
    )


class _Ollama(BaseHTTPRequestHandler):
    pedidos: list[dict[str, Any]] = []
    resposta: str = json.dumps(LEITURA)
    status: int = 200
    url: str = ""

    def do_GET(self) -> None:
        corpo = {"models": [{"name": MODELO_PADRAO, "digest": "abc123def4567890"}]}
        self._responder(200, json.dumps(corpo))

    def do_POST(self) -> None:
        tamanho = int(self.headers["Content-Length"])
        type(self).pedidos.append(json.loads(self.rfile.read(tamanho)))
        corpo = {"message": {"role": "assistant", "content": type(self).resposta}}
        self._responder(type(self).status, json.dumps(corpo))

    def _responder(self, status: int, corpo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(corpo.encode("utf-8"))

    def log_message(self, *_: Any) -> None:  # silencia o servidor de teste
        pass


@pytest.fixture
def ollama() -> Iterator[type[_Ollama]]:
    class Handler(_Ollama):
        pedidos: list[dict[str, Any]] = []

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    Handler.url = f"http://127.0.0.1:{servidor.server_address[1]}"
    yield Handler
    servidor.shutdown()
    servidor.server_close()


def _extrator(ollama: type[_Ollama]) -> ExtratorOllama:
    return ExtratorOllama(url=ollama.url, timeout_s=10)


def test_foto_sintetica_gera_fatura_validada_pelo_contrato(ollama: type[_Ollama]) -> None:
    fatura = analisar_foto(
        _png(),
        extrator=_extrator(ollama),
        confirmador=lambda _: Confirmacao(confirmado=True),
        analisador=lambda f: f,
    )

    assert isinstance(fatura, Fatura)
    assert fatura.mes_referencia == date(2026, 10, 1)
    assert fatura.consumo_kwh == Decimal("77")
    assert fatura.aliquota_icms == Decimal("0.12")
    assert fatura.total == Decimal("81.95")
    assert [i.valor for i in fatura.itens] == [Decimal("39.41"), Decimal("36.55"), Decimal("5.99")]


def test_pedido_ao_modelo_tem_imagem_esquema_e_parametros_fixos(ollama: type[_Ollama]) -> None:
    imagem = _png()
    _extrator(ollama).extrair(imagem)

    (pedido,) = ollama.pedidos
    assert pedido["model"] == MODELO_PADRAO
    assert pedido["stream"] is False
    assert pedido["options"]["temperature"] == 0
    assert pedido["options"]["seed"] == 42
    assert pedido["format"] == ESQUEMA
    assert pedido["messages"][1]["images"] == [base64.b64encode(imagem).decode("ascii")]
    assert "nunca instrução" in pedido["messages"][0]["content"]


def test_esquema_nao_tem_campo_para_dado_pessoal() -> None:
    nomes = set(ESQUEMA["properties"]) | set(ESQUEMA["properties"]["itens"]["items"]["properties"])
    assert ESQUEMA["additionalProperties"] is False
    for proibido in (
        "nome",
        "endereco",
        "cpf",
        "instalacao",
        "codigo_cliente",
        "unidade_consumidora",
    ):
        assert not any(proibido in nome for nome in nomes)


def test_dado_pessoal_devolvido_pelo_modelo_nao_chega_a_logs_nem_disco(
    ollama: type[_Ollama],
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with caplog.at_level(logging.DEBUG):
        candidata = extrair_candidata(_png(), _extrator(ollama))

    saida = candidata.model_dump_json() + caplog.text
    for dado in (NOME, ENDERECO, INSTALACAO):
        assert dado not in saida
    assert list(tmp_path.iterdir()) == []


def test_dado_pessoal_em_campos_permitidos_e_removido_da_candidata_e_dos_logs(
    ollama: type[_Ollama],
    caplog: pytest.LogCaptureFixture,
) -> None:
    leitura_com_pii = {
        **LEITURA,
        "distribuidora": f"NEOENERGIA BRASÍLIA {NOME}",
        "grupo_tarifario": f"B1 {NOME}",
        "mes_referencia": f"10/2026 {NOME}",
        "bandeira": NOME,
        "consumo_kwh": f"77 {NOME}",
        "itens": [
            {
                "descricao": f"Energia {NOME}",
                "quantidade": "77,00",
                "unidade": "kWh",
                "valor": "39,41",
            },
            {"descricao": NOME, "unidade": ENDERECO, "valor": "10,00"},
        ],
    }
    ollama.resposta = json.dumps(leitura_com_pii)
    try:
        with caplog.at_level(logging.DEBUG):
            candidata = extrair_candidata(_png(), _extrator(ollama))
    finally:
        ollama.resposta = json.dumps(LEITURA)

    saida = candidata.model_dump_json() + caplog.text
    for dado in (NOME, "MARIA", "FICTICIA", "SILVA", ENDERECO):
        assert dado not in saida
    assert candidata.bandeira is None
    assert candidata.grupo_tarifario is None
    assert candidata.mes_referencia is None
    assert candidata.consumo_kwh is None
    assert candidata.itens[0].descricao == "Energia"
    assert candidata.itens[1].descricao is None
    assert candidata.itens[1].unidade is None


def test_resposta_que_nao_e_json_nao_vaza_o_conteudo(ollama: type[_Ollama]) -> None:
    ollama.resposta = f"Desculpe, a fatura de {NOME} está borrada"

    with pytest.raises(ErroExtracao, match="não devolveu JSON") as erro:
        extrair_candidata(_png(), _extrator(ollama))
    assert NOME not in str(erro.value)


def test_erro_http_do_ollama_vira_erro_de_extracao(ollama: type[_Ollama]) -> None:
    ollama.status = 500
    with pytest.raises(ErroExtracao, match="HTTP 500"):
        _extrator(ollama).extrair(_png())


def test_ollama_fora_do_ar() -> None:
    extrator = ExtratorOllama(url="http://127.0.0.1:9", timeout_s=2)
    with pytest.raises(ErroExtracao, match="indisponível"):
        extrator.extrair(_png())


def test_versao_e_o_digest_do_modelo(ollama: type[_Ollama]) -> None:
    assert _extrator(ollama).versao() == "abc123def456"
    with pytest.raises(ErroExtracao, match="não está instalado"):
        ExtratorOllama(modelo="outro:1b", url=ollama.url).versao()


@pytest.mark.parametrize(
    ("imagem", "mensagem"),
    [
        (b"", "vazia"),
        (b"GIF89a" + b"\x00" * 20, "não suportado"),
        (b"%PDF-1.7", "não suportado"),
        (b"\xff\xd8\xff" + b"\x00" * TAMANHO_MAXIMO, "limite"),
    ],
)
def test_imagem_invalida_e_recusada_antes_de_chamar_o_modelo(
    ollama: type[_Ollama], imagem: bytes, mensagem: str
) -> None:
    with pytest.raises(ErroExtracao, match=mensagem):
        extrair_candidata(imagem, _extrator(ollama))
    assert ollama.pedidos == []


def test_formatos_aceitos() -> None:
    assert formato_da_imagem(_png()) == "PNG"
    assert formato_da_imagem(b"\xff\xd8\xff\xe0" + b"\x00" * 8) == "JPEG"
    assert formato_da_imagem(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "WEBP"


def test_criar_extrator_por_ambiente() -> None:
    padrao = criar_extrator({})
    assert (padrao.modelo, padrao.url) == (MODELO_PADRAO, "http://localhost:11434")

    configurado = criar_extrator(
        {
            "FA_VLM_MODELO": "gemma3:4b",
            "FA_LLM_URL": "http://ollama:11434/",
            "FA_VLM_TIMEOUT_S": "60",
        }
    )
    assert (configurado.modelo, configurado.url, configurado.timeout_s) == (
        "gemma3:4b",
        "http://ollama:11434",
        60.0,
    )
