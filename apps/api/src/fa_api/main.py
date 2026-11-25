"""API para conferência determinística e análise complementar de agentes."""

import asyncio
import base64
import binascii
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date
from threading import Lock
from time import perf_counter
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError, model_validator

from fa_agentes import (
    Persona,
    analisar_com_agentes,
    obter_orquestrador,
    verificar_linguagem,
)
from fa_api import __version__
from fa_contratos import Achado, Citacao, Fatura
from fa_motor import analisar_nivel_a

logger = logging.getLogger("fa_api")
# Com LLM local cada chamada leva ~25 s; sem LLM (padrão) os agentes respondem em milissegundos.
TEMPO_MAXIMO_AGENTES_SEGUNDOS = float(os.getenv("FA_AGENTES_TIMEOUT_S", "15"))
# Thread não se cancela: quem estoura o tempo continua rodando até o fim. A vaga do semáforo só é
# devolvida quando o trabalho real termina (mesmo depois de a resposta já ter saído por timeout),
# então nunca há mais de FA_AGENTES_CONCORRENCIA análises dos agentes rodando ao mesmo tempo. Quem
# espera vaga gasta o próprio prazo na fila e, se ele acabar, recebe timeout sem abrir thread nova.
_VAGAS_AGENTES = asyncio.Semaphore(int(os.getenv("FA_AGENTES_CONCORRENCIA", "2")))


def _devolver_vaga(tarefa: "asyncio.Future[Any]") -> None:
    _VAGAS_AGENTES.release()
    if not tarefa.cancelled():
        tarefa.exception()  # já tratada por quem esperou; evita o aviso de exceção não lida


async def _com_vaga[T](trabalho: Callable[[], Awaitable[T]], timeout: float) -> T:
    """Roda ``trabalho`` numa vaga até ele terminar; quem chama espera no máximo ``timeout``."""
    loop = asyncio.get_running_loop()
    prazo = loop.time() + timeout
    await asyncio.wait_for(_VAGAS_AGENTES.acquire(), timeout=timeout)
    tarefa = asyncio.ensure_future(trabalho())
    tarefa.add_done_callback(_devolver_vaga)
    # shield: o timeout encerra a espera de quem chamou, mas não cancela o trabalho nem a vaga.
    return await asyncio.wait_for(asyncio.shield(tarefa), timeout=max(prazo - loop.time(), 0))


ExecutarAgentes = Callable[[Fatura], Awaitable[list[Achado]]]


class MetricasAnalise:
    """Contadores em memória para acompanhar a operação local da API."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requisicoes = 0
        self._duracao_total_segundos = 0.0

    def registrar(self, duracao_segundos: float) -> None:
        with self._lock:
            self._requisicoes += 1
            self._duracao_total_segundos += duracao_segundos

    def resumo(self) -> dict[str, float | int]:
        with self._lock:
            media = self._duracao_total_segundos / self._requisicoes if self._requisicoes else 0.0
            return {
                "requisicoes_analisadas": self._requisicoes,
                "duracao_media_segundos": round(media, 6),
            }


class RespostaAnalise(BaseModel):
    """Achados determinísticos para a fatura recebida."""

    achados: list[Achado]
    aviso: str | None = None


PDF_TAMANHO_MAXIMO_BYTES = int(os.getenv("FA_PDF_MAX_BYTES", str(5 * 1024 * 1024)))
PDF_PAGINAS_MAXIMAS = int(os.getenv("FA_PDF_MAX_PAGINAS", "5"))

CampoCorrigivel = Literal[
    "distribuidora",
    "grupo_tarifario",
    "mes_referencia",
    "leitura_anterior",
    "leitura_atual",
    "consumo_kwh",
    "bandeira",
    "aliquota_icms",
    "total",
]

MSG_PDF_INVALIDO = (
    "Não foi possível ler o PDF: o arquivo está corrompido ou não é um PDF válido. "
    "Envie outro arquivo ou digite os dados da fatura."
)
MSG_PDF_SEM_TEXTO = (
    "O PDF não tem camada de texto (parece digitalizado ou é uma imagem). "
    "Envie o PDF original da distribuidora ou digite os dados da fatura."
)
MSG_PDF_PROTEGIDO = (
    "O PDF está protegido por senha e não pode ser lido. "
    "Envie uma cópia sem proteção ou digite os dados da fatura."
)
MSG_PDF_MUITAS_PAGINAS = (
    "O PDF tem mais páginas do que o limite aceito ({limite}). "
    "Envie só as páginas da fatura ou digite os dados."
)
MSG_EXTRACAO_FALHOU = (
    "Não foi possível extrair os dados da fatura do PDF. "
    "Confira o arquivo ou digite os dados manualmente."
)
MSG_CORRECAO_INVALIDA = "As correções informadas são inválidas para os campos: {campos}."
MSG_AGENTES_INDISPONIVEIS = (
    "A análise com os agentes está indisponível no momento; "
    "os achados determinísticos do motor foram preservados e nenhuma conclusão foi inferida."
)
MSG_SAIDA_BLOQUEADA = "Texto omitido por não atender à política de linguagem do produto."


def _validar_pdf_base64(texto: str) -> bytes:
    """Base64 válido, dentro do tamanho máximo e com a assinatura ``%PDF-`` (senão, 422)."""
    try:
        dados = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError) as erro:
        raise ValueError("pdf_base64 não é base64 válido.") from erro
    if len(dados) > PDF_TAMANHO_MAXIMO_BYTES:
        raise ValueError("PDF acima do tamanho máximo permitido.")
    if not dados.startswith(b"%PDF-"):
        raise ValueError("O arquivo não tem a assinatura de um PDF.")
    return dados


class PedidoExtracao(BaseModel):
    """PDF em base64 para extração dos campos; a análise só roda depois da confirmação."""

    pdf_base64: str = Field(min_length=1)

    @model_validator(mode="after")
    def _pdf_valido(self) -> "PedidoExtracao":
        _validar_pdf_base64(self.pdf_base64)
        return self


class RespostaExtracao(BaseModel):
    """Campos lidos do PDF para o usuário confirmar, ou o motivo claro da falha."""

    fatura: Fatura | None = None
    erro: str | None = None
    motivo: str | None = None


class PedidoPergunta(BaseModel):
    """Pergunta regulatória, opcionalmente junto com a fatura confirmada ou o PDF dela.

    Modos: ``pergunta`` isolada; ``fatura`` confirmada + ``pergunta``; ``pdf_base64``
    (+ ``correcoes`` confirmadas pelo usuário) + ``pergunta``.
    """

    pergunta: str = Field(min_length=3, max_length=500)
    data_referencia: date = Field(default_factory=date.today)
    persona: Persona = Persona.MARCIA
    fatura: Fatura | None = None
    pdf_base64: str | None = Field(default=None, min_length=1)
    correcoes: dict[CampoCorrigivel, str] | None = None

    @model_validator(mode="after")
    def _combinacao_valida(self) -> "PedidoPergunta":
        if self.fatura is not None and self.pdf_base64 is not None:
            raise ValueError("Informe fatura ou pdf_base64, não os dois.")
        if self.correcoes and self.pdf_base64 is None:
            raise ValueError("correcoes só se aplicam junto com pdf_base64.")
        if self.pdf_base64 is not None:
            _validar_pdf_base64(self.pdf_base64)
        return self

    def bytes_pdf(self) -> bytes:
        return base64.b64decode(self.pdf_base64 or "", validate=True)


class PassoRastro(BaseModel):
    agente: str
    acao: str
    detalhe: str
    duracao_s: float


class RespostaPerguntaAPI(BaseModel):
    """Resposta dos agentes: texto para a persona, citações, origem e rastro da colaboração.

    Os campos ``modo``, ``achados_motor``, ``campos_fatura`` e ``aviso`` são aditivos: clientes
    antigos que só leem os demais continuam funcionando.
    """

    resposta: str
    mensagem: str
    persona: Persona
    citacoes: list[Citacao]
    abstencao: bool
    origem: str
    motivo_abstencao: str
    rastro: list[PassoRastro]
    modo: Literal["texto", "fatura", "pdf"] = "texto"
    achados_motor: list[Achado] = Field(default_factory=list)
    campos_fatura: dict[str, str] = Field(default_factory=dict)
    aviso: str | None = None


def origens_permitidas() -> list[str]:
    """Inclui a origem pública configurada sem liberar origens arbitrárias."""
    locais = ["http://localhost:3000", "http://127.0.0.1:3000"]
    publicas = []
    for valor in os.getenv("FA_CORS_ORIGINS", "").split(","):
        origem = valor.strip().rstrip("/")
        if not origem:
            continue
        partes = urlsplit(origem)
        if (
            partes.scheme != "https"
            or not partes.hostname
            or partes.username
            or partes.password
            or partes.path
            or partes.query
            or partes.fragment
        ):
            raise ValueError("FA_CORS_ORIGINS deve conter apenas origens HTTPS exatas")
        publicas.append(origem)
    return [*locais, *publicas]


app = FastAPI(title="Fatura Aberta - API", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_permitidas(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)
metricas = MetricasAnalise()


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok", "versao": __version__}


@app.get("/metricas")
def obter_metricas() -> dict[str, float | int]:
    """Expõe métricas operacionais sem registrar conteúdo de faturas."""
    return metricas.resumo()


async def _executar_agentes(
    fatura: Fatura, executar: ExecutarAgentes
) -> tuple[list[Achado], str | None]:
    try:
        return await _com_vaga(lambda: executar(fatura), TEMPO_MAXIMO_AGENTES_SEGUNDOS), None
    except TimeoutError:
        logger.warning("agentes excederam o tempo limite")
        return [], "A análise adicional não respondeu a tempo; os achados A seguem disponíveis."
    except Exception as erro:
        logger.warning("agentes indisponíveis: %s", type(erro).__name__)
        return [], "A análise adicional está indisponível; os achados A seguem disponíveis."


@app.post("/analisar", response_model=RespostaAnalise)
async def analisar(fatura: Fatura, response: Response) -> RespostaAnalise:
    """Preserva o nível A quando agentes falham ou excedem o tempo máximo."""
    inicio = perf_counter()
    response.headers["Cache-Control"] = "no-store"
    achados = analisar_nivel_a(fatura)
    adicionais, aviso = await _executar_agentes(fatura, lambda f: analisar_com_agentes(f, achados))
    metricas.registrar(perf_counter() - inicio)
    return RespostaAnalise(achados=[*achados, *adicionais], aviso=aviso)


def _limpo(texto: str, *, literal: bool = False) -> str:
    """RF-15 de ponta a ponta: texto com termo vedado nunca sai pela API."""
    return (
        MSG_SAIDA_BLOQUEADA
        if verificar_linguagem(texto, permitir_citacao_literal=literal)
        else texto
    )


def _sanitizar_saida(r: RespostaPerguntaAPI) -> RespostaPerguntaAPI:
    """Aplica o verificador de linguagem em todos os campos textuais devolvidos ao cliente."""
    literal = bool(r.citacoes)
    return r.model_copy(
        update={
            "resposta": _limpo(r.resposta, literal=literal),
            "mensagem": _limpo(r.mensagem, literal=literal),
            "aviso": None if r.aviso is None else _limpo(r.aviso),
            "motivo_abstencao": _limpo(r.motivo_abstencao),
            "achados_motor": [
                a.model_copy(update={"descricao": _limpo(a.descricao)}) for a in r.achados_motor
            ],
            "rastro": [p.model_copy(update={"detalhe": _limpo(p.detalhe)}) for p in r.rastro],
        }
    )


def _falha(
    pedido: PedidoPergunta,
    modo: Literal["texto", "fatura", "pdf"],
    mensagem: str,
    origem: str,
    motivo: str,
    *,
    achados: list[Achado] | None = None,
    campos: dict[str, str] | None = None,
    rastro: list[PassoRastro] | None = None,
) -> RespostaPerguntaAPI:
    """Abstenção estruturada: mensagem clara, sem conclusão inventada."""
    return RespostaPerguntaAPI(
        resposta=mensagem,
        mensagem=mensagem,
        persona=pedido.persona,
        citacoes=[],
        abstencao=True,
        origem=origem,
        motivo_abstencao=motivo,
        rastro=rastro or [],
        modo=modo,
        achados_motor=achados or [],
        campos_fatura=campos or {},
        aviso=mensagem,
    )


class _FalhaExtracao(Exception):
    def __init__(self, mensagem: str, motivo: str) -> None:
        super().__init__(motivo)
        self.mensagem = mensagem
        self.motivo = motivo


def _extrair_fatura(dados: bytes) -> Fatura:
    """Bytes de PDF -> Fatura, com limites. Mensagens nunca repetem dados da fatura."""
    from io import BytesIO

    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    from fa_extracao import ErroExtracao, parse_texto  # importação lazy: pacote opcional na API
    from fa_extracao.pdf import extrair_texto

    try:
        leitor = PdfReader(BytesIO(dados))
        if leitor.is_encrypted:
            raise _FalhaExtracao(MSG_PDF_PROTEGIDO, "pdf_protegido")
        if len(leitor.pages) > PDF_PAGINAS_MAXIMAS:
            raise _FalhaExtracao(
                MSG_PDF_MUITAS_PAGINAS.format(limite=PDF_PAGINAS_MAXIMAS), "pdf_muitas_paginas"
            )
    except (PyPdfError, ValueError) as erro:
        raise _FalhaExtracao(MSG_PDF_INVALIDO, "pdf_invalido") from erro
    try:
        texto = extrair_texto(dados)
    except ErroExtracao as erro:
        raise _FalhaExtracao(MSG_PDF_INVALIDO, "pdf_invalido") from erro
    if not texto.strip():
        raise _FalhaExtracao(MSG_PDF_SEM_TEXTO, "pdf_sem_texto")
    try:
        return parse_texto(texto)
    except ErroExtracao as erro:
        raise _FalhaExtracao(MSG_EXTRACAO_FALHOU, "extracao_falhou") from erro


def _fatura_do_pdf(pedido: PedidoPergunta) -> Fatura:
    """PDF -> Fatura (com as correções confirmadas)."""
    fatura = _extrair_fatura(pedido.bytes_pdf())
    if pedido.correcoes:
        try:
            fatura = Fatura.model_validate({**fatura.model_dump(), **pedido.correcoes})
        except ValidationError as erro:
            campos = sorted({str(e["loc"][0]) for e in erro.errors() if e["loc"]})
            raise _FalhaExtracao(
                MSG_CORRECAO_INVALIDA.format(campos=", ".join(campos) or "informados"),
                "correcao_invalida",
            ) from None
    return fatura


def _resposta_da_fatura(
    pedido: PedidoPergunta, modo: Literal["fatura", "pdf"], fatura: Fatura, achados: list[Achado]
) -> RespostaPerguntaAPI:
    r = obter_orquestrador().responder_sobre_fatura(
        pedido.pergunta, fatura, achados_motor=achados, persona=pedido.persona
    )
    return RespostaPerguntaAPI(
        resposta=r.resposta.texto,
        mensagem=r.mensagem.texto,
        persona=r.mensagem.persona,
        citacoes=list(r.resposta.citacoes),
        abstencao=r.abstencao,
        origem=r.origem,
        motivo_abstencao=r.motivo_abstencao,
        rastro=[
            PassoRastro(agente=p.agente, acao=p.acao, detalhe=p.detalhe, duracao_s=p.duracao_s)
            for p in r.rastro
        ],
        modo=modo,
        achados_motor=achados,
        campos_fatura=r.campos_usados,
    )


@app.post("/extrair", response_model=RespostaExtracao)
async def extrair(pedido: PedidoExtracao, response: Response) -> RespostaExtracao:
    """Lê o PDF e devolve os campos para confirmação; não roda motor nem agentes."""
    response.headers["Cache-Control"] = "no-store"
    try:
        dados = base64.b64decode(pedido.pdf_base64, validate=True)
        fatura = await asyncio.to_thread(_extrair_fatura, dados)
    except _FalhaExtracao as erro:
        return RespostaExtracao(erro=erro.mensagem, motivo=erro.motivo)
    return RespostaExtracao(fatura=fatura)


@app.post("/perguntar", response_model=RespostaPerguntaAPI)
async def perguntar(pedido: PedidoPergunta, response: Response) -> RespostaPerguntaAPI:
    """Pergunta regulatória respondida pelos 4 agentes, com fatura/PDF confirmados opcionais."""
    response.headers["Cache-Control"] = "no-store"
    if pedido.fatura is None and pedido.pdf_base64 is None:
        return _sanitizar_saida(await _perguntar_texto(pedido))

    modo: Literal["fatura", "pdf"] = "pdf" if pedido.pdf_base64 is not None else "fatura"
    if pedido.pdf_base64 is not None:
        try:
            fatura = await asyncio.to_thread(_fatura_do_pdf, pedido)
        except _FalhaExtracao as erro:
            passo = PassoRastro(agente="Extração", acao="falha", detalhe=erro.motivo, duracao_s=0.0)
            return _sanitizar_saida(
                _falha(pedido, "pdf", erro.mensagem, "falha_extracao", erro.motivo, rastro=[passo])
            )
    else:
        assert pedido.fatura is not None
        fatura = pedido.fatura

    achados = analisar_nivel_a(fatura)
    try:
        r = await _com_vaga(
            lambda: asyncio.to_thread(_resposta_da_fatura, pedido, modo, fatura, achados),
            TEMPO_MAXIMO_AGENTES_SEGUNDOS,
        )
    except Exception as erro:
        logger.warning("agentes indisponíveis na pergunta combinada: %s", type(erro).__name__)
        passo = PassoRastro(
            agente="Motor",
            acao="analisar_nivel_a",
            detalhe=f"{len(achados)} achado(s) preservado(s)",
            duracao_s=0.0,
        )
        return _sanitizar_saida(
            _falha(
                pedido,
                modo,
                MSG_AGENTES_INDISPONIVEIS,
                "agentes_indisponiveis",
                "agentes_indisponiveis",
                achados=achados,
                rastro=[passo],
            )
        )
    return _sanitizar_saida(r)


async def _perguntar_texto(pedido: PedidoPergunta) -> RespostaPerguntaAPI:
    try:
        r = await _com_vaga(
            lambda: asyncio.to_thread(
                obter_orquestrador().responder_pergunta,
                pedido.pergunta,
                data_referencia=pedido.data_referencia,
                persona=pedido.persona,
            ),
            TEMPO_MAXIMO_AGENTES_SEGUNDOS,
        )
    except TimeoutError as erro:
        raise HTTPException(504, "Os agentes não responderam a tempo.") from erro
    return RespostaPerguntaAPI(
        resposta=r.resposta.texto,
        mensagem=r.mensagem.texto,
        persona=r.mensagem.persona,
        citacoes=list(r.resposta.citacoes),
        abstencao=r.abstencao,
        origem=r.origem,
        motivo_abstencao=r.motivo_abstencao,
        rastro=[
            PassoRastro(agente=p.agente, acao=p.acao, detalhe=p.detalhe, duracao_s=p.duracao_s)
            for p in r.rastro
        ],
    )
