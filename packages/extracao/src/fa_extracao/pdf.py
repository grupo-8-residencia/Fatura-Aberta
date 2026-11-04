"""Leitura do texto de um PDF de fatura."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from fa_extracao.erros import ErroExtracao


def extrair_texto(origem: Path | bytes) -> str:
    """Devolve o texto de todas as páginas do PDF, em ordem de leitura.

    O texto ainda contém dados pessoais: quem chama deve passá-lo direto ao parser e nunca
    registrá-lo em log nem gravá-lo em disco.
    """
    dados = origem if isinstance(origem, bytes) else origem.read_bytes()
    try:
        leitor = PdfReader(BytesIO(dados))
        return "\n".join(pagina.extract_text() for pagina in leitor.pages)
    except (PyPdfError, ValueError) as erro:
        raise ErroExtracao("PDF ilegível ou corrompido.") from erro
