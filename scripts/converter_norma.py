"""Converte uma norma pública (HTML ou PDF) em itens candidatos para o corpus do RAG.

Gera um JSON no formato de ``dados/normas/corpus_b1.json``, um item por artigo. Todo item sai
com ``conferido: "A verificar"``, então o índice o ignora até uma pessoa comparar o texto com a
fonte oficial e trocar para ``"sim"``. O script nunca altera o corpus: a saída é um arquivo à
parte, para revisão antes de entrar no Git.

Exemplos::

    uv run python scripts/converter_norma.py \\
        --url https://www2.aneel.gov.br/cedoc/ren20211000.html \\
        --ato "REN ANEEL nº 1.000/2021" --prefixo ren1000 --vigencia-inicio 2022-01-03 \\
        --artigos 177,260,327 --saida candidatos_ren1000.json

    uv run python scripts/converter_norma.py --arquivo norma.pdf --ato "..." \\
        --prefixo prodist8 --vigencia-inicio 2024-01-01 --url-oficial https://...

Limpeza automática: tira cabeçalhos e rodapés repetidos, numeração de página e linhas de
impressão do navegador, religa linhas quebradas e retira as notas de redação, como
"(Redação dada pela Lei nº ...)". As notas removidas ficam em ``observacoes``, porque indicam a
data em que o dispositivo mudou. Notas de dispositivo revogado ou vetado são mantidas no texto.
Use ``--manter-notas`` para não removê-las.

Modo lote: ``--manifesto dados/normas/manifesto_atos.json`` converte todos os atos do manifesto
que tiverem arquivo em ``normas_baixadas/`` (pasta fora do Git) ou ``url_download``.

Só normas públicas. Nada de fatura real ou dado pessoal.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_BLOCOS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}
_IGNORAR = {"script", "style", "head", "noscript"}
_ARTIGO = re.compile(r"^\s*Art(?:igo|\.)?\s*(\d+)\s*[º°o]?(-[A-Z](?!\w))?\.?(?=\s|$)", re.I)
_INICIO_DISPOSITIVO = re.compile(
    r"^\s*(?:Art(?:igo|\.)|§|Parágrafo\s+único|[IVXLCDM]+\s*[-–—]|[a-z]\)|CAPÍTULO|SEÇÃO|TÍTULO)",
    re.I,
)
_LIMITE_TIMEOUT_S = 60
_MIN_CHARS_CABECALHO = 25
_MIN_REPETICOES_CABECALHO = 4
_RUIDO_PAGINA = re.compile(
    r"^(?:p[áa]g(?:ina|\.)?\s*\d{1,4}(?:\s*(?:/|de)\s*\d{1,4})?|\d{1,4}\s*/\s*\d{1,4}|-\s*\d{1,4}\s*-)$",
    re.I,
)
_RUIDO_NAVEGADOR = re.compile(
    r"^\d{2}/\d{2}/\d{4},\s*\d{2}:\d{2}\b|^https?://\S+(?:\s+\d{1,4}/\d{1,4})?$|^about:blank\b",
    re.I,
)
_NOTA_REDACAO = re.compile(
    r"\s*\((?:[^()]*?\b)?(?:reda[çc][ãa]o dada|inclu[íi]d[oa]|renumerad[oa]|vide\b)[^()]*\)",
    re.I,
)
_RODAPE_DOU = re.compile(r"\s*Este texto não substitui o publicado.*\Z", re.I | re.S)
_REVOGADO_OU_VETADO = re.compile(r"\b(?:revogad[oa]s?|vetad[oa]s?)\b", re.I)


class _ExtratorHtml(HTMLParser):
    """Extrai o texto visível, com quebra de linha nos elementos de bloco."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORAR:
            self._ignorando += 1
        elif tag in _BLOCOS:
            self._partes.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORAR and self._ignorando:
            self._ignorando -= 1
        elif tag in _BLOCOS:
            self._partes.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignorando:
            self._partes.append(data)

    def texto(self) -> str:
        return "".join(self._partes)


def decodificar(conteudo: bytes) -> str:
    """Tenta UTF-8 e cai para cp1252, comum em páginas antigas de órgãos públicos."""
    try:
        return conteudo.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


def html_para_texto(conteudo: bytes) -> str:
    extrator = _ExtratorHtml()
    extrator.feed(decodificar(conteudo))
    return extrator.texto()


def pdf_para_texto(conteudo: bytes) -> str:
    """Usa o ``pdftotext`` (poppler). Falha com mensagem clara se ele não estiver instalado."""
    with tempfile.TemporaryDirectory() as pasta:
        origem = Path(pasta) / "norma.pdf"
        origem.write_bytes(conteudo)
        try:
            resultado = subprocess.run(  # noqa: S603 -- binário fixo, sem shell
                ["pdftotext", str(origem), "-"],  # noqa: S607
                capture_output=True,
                check=True,
                timeout=_LIMITE_TIMEOUT_S,
            )
        except FileNotFoundError as erro:
            raise SystemExit("pdftotext não encontrado: instale o poppler.") from erro
        except subprocess.CalledProcessError as erro:
            raise SystemExit(f"pdftotext falhou: {erro.stderr.decode(errors='replace')}") from erro
    return decodificar(resultado.stdout)


def ler_fonte(url: str | None, arquivo: Path | None) -> str:
    """Devolve o texto bruto da fonte (PDF, HTML ou texto simples)."""
    if arquivo is not None:
        conteudo = arquivo.read_bytes()
    else:
        assert url is not None
        if urlparse(url).scheme not in {"http", "https"}:
            raise SystemExit("a URL deve começar com http:// ou https://")
        requisicao = Request(url, headers={"User-Agent": "fatura-aberta-corpus/0.1"})  # noqa: S310
        try:
            with urlopen(requisicao, timeout=_LIMITE_TIMEOUT_S) as resposta:  # noqa: S310
                conteudo = resposta.read()
        except (HTTPError, URLError, TimeoutError) as erro:
            raise SystemExit(
                f"Não foi possível baixar {url}: {erro}.\n"
                "Se o site bloqueia acesso automatizado, abra a norma no navegador, salve a "
                "página (HTML ou PDF) e use --arquivo com --url-oficial."
            ) from erro
    if conteudo.lstrip()[:4] == b"%PDF":
        return pdf_para_texto(conteudo)
    if arquivo is not None and arquivo.suffix.lower() in {".txt", ".md"}:
        return decodificar(conteudo)
    return html_para_texto(conteudo)


def _chave_cabecalho(linha: str) -> str:
    return re.sub(r"\d+", "#", linha.lower())


def _remover_ruido(linhas: list[str]) -> list[str]:
    """Tira numeração de página, linhas de impressão e cabeçalhos ou rodapés repetidos.

    Linhas curtas e números soltos ficam, porque podem ser células de tabela de tarifas.
    """
    contagem = Counter(_chave_cabecalho(x) for x in linhas if len(x) >= _MIN_CHARS_CABECALHO)

    def eh_ruido(linha: str) -> bool:
        if _RUIDO_PAGINA.match(linha) or _RUIDO_NAVEGADOR.match(linha):
            return True
        repetida = contagem[_chave_cabecalho(linha)] >= _MIN_REPETICOES_CABECALHO
        return (
            len(linha) >= _MIN_CHARS_CABECALHO and repetida and not _INICIO_DISPOSITIVO.match(linha)
        )

    return [linha for linha in linhas if not eh_ruido(linha)]


def limpar(texto: str, *, religar_linhas: bool, remover_ruido: bool = True) -> str:
    texto = texto.replace("\xa0", " ").replace("\u00ad", "").replace("\r", "")
    linhas = [" ".join(linha.split()) for linha in texto.split("\n")]
    linhas = [linha for linha in linhas if linha]
    if remover_ruido:
        linhas = _remover_ruido(linhas)
    if not religar_linhas:
        return "\n".join(linhas)
    unidas: list[str] = []
    for linha in linhas:
        if unidas and not _INICIO_DISPOSITIVO.match(linha):
            unidas[-1] = f"{unidas[-1]} {linha}"
        else:
            unidas.append(linha)
    return "\n".join(unidas)


def remover_notas(texto: str) -> tuple[str, list[str]]:
    """Retira as notas de redação e o rodapé do D.O.; devolve o texto limpo e as notas removidas."""
    notas = [" ".join(m.group(0).split()) for m in _NOTA_REDACAO.finditer(texto)]
    return _RODAPE_DOU.sub("", _NOTA_REDACAO.sub("", texto)), notas


def _numero(bruto: str) -> str:
    return re.sub(r"\s+", "", bruto).upper()


def separar_artigos(texto: str) -> dict[str, str]:
    """Agrupa as linhas por artigo. Se o número se repetir, vale a primeira ocorrência."""
    artigos: dict[str, list[str]] = {}
    atual: str | None = None
    ignorando_repetido = False
    for linha in texto.split("\n"):
        achado = _ARTIGO.match(linha)
        if achado:
            numero = _numero(achado.group(1) + (achado.group(2) or ""))
            if numero in artigos:
                ignorando_repetido, atual = True, None
                continue
            ignorando_repetido, atual = False, numero
            artigos[numero] = [linha]
        elif atual is not None and not ignorando_repetido:
            artigos[atual].append(linha)
    return {numero: "\n".join(linhas) for numero, linhas in artigos.items()}


def _selecionar(artigos: dict[str, str], pedidos: Iterable[str] | None) -> dict[str, str]:
    if pedidos is None:
        return artigos
    quer = [_numero(p) for p in pedidos]
    ausentes = [p for p in quer if p not in artigos]
    if ausentes:
        print(f"Aviso: artigos não encontrados: {', '.join(ausentes)}", file=sys.stderr)
    return {p: artigos[p] for p in quer if p in artigos}


def montar_itens(
    artigos: dict[str, str],
    *,
    ato: str,
    prefixo: str,
    url: str,
    vigencia_inicio: date | None,
    subgrupos: list[str],
    manter_notas: bool = False,
) -> list[dict[str, object]]:
    aviso = "" if vigencia_inicio else " Vigência não informada: preencher antes de marcar 'sim'."
    itens: list[dict[str, object]] = []
    for numero, bruto in artigos.items():
        texto, notas = (bruto, []) if manter_notas else remover_notas(bruto)
        extra = ""
        if notas:
            extra += " Notas de redação removidas (conferir a vigência): " + " | ".join(notas)[:600]
        if _REVOGADO_OU_VETADO.search(texto):
            extra += " Contém trecho revogado ou vetado: conferir a vigência."
        itens.append(
            _item(numero, texto, ato, prefixo, url, vigencia_inicio, subgrupos, aviso + extra)
        )
    return itens


def _item(
    numero: str,
    texto: str,
    ato: str,
    prefixo: str,
    url: str,
    vigencia_inicio: date | None,
    subgrupos: list[str],
    observacao_extra: str,
) -> dict[str, object]:
    return {
        "id": f"{prefixo}-art-{numero.lower()}",
        "titulo": "A PREENCHER",
        "texto": texto,
        "citacao": {
            "ato": ato,
            "dispositivo": f"art. {numero.lower()}",
            "vigencia_inicio": vigencia_inicio.isoformat() if vigencia_inicio else None,
            "vigencia_fim": None,
            "url": url,
        },
        "subgrupos": subgrupos,
        "tags": [],
        "conferido": "A verificar",
        "conferido_em": None,
        "fonte_conferencia": "",
        "observacoes": (
            "Extraído automaticamente; comparar com o texto oficial antes de marcar 'sim'."
            + observacao_extra
        ),
    }


def _achar_arquivo_manual(pasta: Path, prefixo: str) -> Path | None:
    for sufixo in (".pdf", ".html", ".htm", ".txt"):
        candidato = pasta / f"{prefixo}{sufixo}"
        if candidato.is_file():
            return candidato
    return None


def converter_lote(
    manifesto: Path, pasta_manual: Path, saida_dir: Path, *, manter_notas: bool = False
) -> int:
    """Converte todos os atos contados do manifesto e imprime o que ainda falta fazer."""
    atos = json.loads(manifesto.read_text(encoding="utf-8"))
    saida_dir.mkdir(parents=True, exist_ok=True)
    contados = [a for a in atos if a["status"] != "excluido"]
    linhas: list[str] = []
    for ato in contados:
        prefixo = ato["prefixo"]
        try:
            if ato.get("url_download"):
                texto = ler_fonte(ato["url_download"], None)
            elif (arquivo := _achar_arquivo_manual(pasta_manual, prefixo)) is not None:
                texto = ler_fonte(None, arquivo)
            else:
                linhas.append(
                    f"FALTA ARQUIVO  {prefixo}: salvar em {pasta_manual}/{prefixo}.pdf|html"
                )
                continue
        except SystemExit as erro:
            linhas.append(f"ERRO           {prefixo}: {erro}")
            continue
        artigos = separar_artigos(limpar(texto, religar_linhas=True))
        if not artigos:
            linhas.append(
                f"SEM ARTIGOS    {prefixo}: formato sem 'Art. N' (decidir chunking à mão)"
            )
            continue
        vigencia = (
            date.fromisoformat(ato["vigencia_inicio"]) if ato.get("vigencia_inicio") else None
        )
        itens = montar_itens(
            artigos,
            ato=ato["ato"],
            prefixo=prefixo,
            url=ato["url_oficial"],
            vigencia_inicio=vigencia,
            subgrupos=ato.get("subgrupos", ["B1"]),
            manter_notas=manter_notas,
        )
        (saida_dir / f"{prefixo}.json").write_text(
            json.dumps(itens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        nota = "" if ato["status"] == "ok" else f"  [{ato['status']}]"
        linhas.append(f"CONVERTIDO     {prefixo}: {len(itens)} artigos{nota}")
    print("\n".join(linhas))
    print(f"\nAtos contados: {len(contados)} de {len(atos)} no manifesto.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    origem = parser.add_mutually_exclusive_group()
    origem.add_argument("--url", help="URL pública da norma (HTML ou PDF)")
    origem.add_argument("--arquivo", type=Path, help="arquivo local (.html, .pdf, .txt)")
    parser.add_argument(
        "--url-oficial", help="URL a citar, se diferente de --url (obrigatória com --arquivo)"
    )
    parser.add_argument("--ato", help='ex.: "REN ANEEL nº 1.000/2021"')
    parser.add_argument("--prefixo", help="prefixo dos ids, ex.: ren1000")
    parser.add_argument("--vigencia-inicio", type=date.fromisoformat, help="AAAA-MM-DD")
    parser.add_argument("--manifesto", type=Path, help="modo lote: JSON com a lista de atos")
    parser.add_argument("--pasta-manual", type=Path, default=Path("normas_baixadas"))
    parser.add_argument("--saida-dir", type=Path, default=Path("candidatos"))
    parser.add_argument("--subgrupos", default="B1", help="separados por vírgula (padrão: B1)")
    parser.add_argument(
        "--manter-notas",
        action="store_true",
        help='não remove as notas de redação, como "(Redação dada pela Lei ...)"',
    )
    parser.add_argument("--artigos", help="artigos a manter, separados por vírgula (padrão: todos)")
    parser.add_argument("--saida", type=Path, help="arquivo JSON de saída (padrão: stdout)")
    args = parser.parse_args(argv)

    if args.manifesto:
        return converter_lote(
            args.manifesto, args.pasta_manual, args.saida_dir, manter_notas=args.manter_notas
        )
    if not (args.url or args.arquivo):
        parser.error("informe --url, --arquivo ou --manifesto")
    if not (args.ato and args.prefixo and args.vigencia_inicio):
        parser.error("no modo unitário, --ato, --prefixo e --vigencia-inicio são obrigatórios")
    url_citada = args.url_oficial or args.url
    if not url_citada:
        parser.error("com --arquivo, informe --url-oficial para a citação")
    texto = ler_fonte(args.url, args.arquivo)
    artigos = separar_artigos(limpar(texto, religar_linhas=True))
    pedidos = [p.strip() for p in args.artigos.split(",") if p.strip()] if args.artigos else None
    artigos = _selecionar(artigos, pedidos)
    if not artigos:
        print("Nenhum artigo encontrado: confira a fonte ou o formato.", file=sys.stderr)
        return 1

    itens = montar_itens(
        artigos,
        ato=args.ato,
        prefixo=args.prefixo,
        url=url_citada,
        vigencia_inicio=args.vigencia_inicio,
        subgrupos=[s.strip() for s in args.subgrupos.split(",") if s.strip()],
        manter_notas=args.manter_notas,
    )
    saida = json.dumps(itens, ensure_ascii=False, indent=2)
    if args.saida:
        args.saida.write_text(saida + "\n", encoding="utf-8")
        print(f"{len(itens)} artigos candidatos gravados em {args.saida}", file=sys.stderr)
    else:
        print(saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
