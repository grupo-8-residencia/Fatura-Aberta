# ruff: noqa: E501
"""Gerador do PDF e Memorial Técnico das Etapas da Frente F2 e Guia Prático de RAG.

Gera documento diagramado em PDF (Formato Portátil de Documento / Portable Document Format)
explicando a trajetória de Luiz Fernando Oryone Lemos (@luizoryone), a arquitetura de
RAG (Geração Aumentada por Recuperação / Retrieval-Augmented Generation) e as funções do sistema
em termos simples e acessíveis, com exemplos práticos de uso.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_ASSETS = ROOT / "docs" / "assets" / "manual_f2_rag_luizoryone.pdf"


class NumberedCanvas(canvas.Canvas):
    """Canvas com numeração total de páginas e cabeçalho institucional elegante."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, object]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()  # type: ignore[attr-defined]

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count: int) -> None:
        self.saveState()

        page_num: int = getattr(self, "_pageNumber", 1)

        # Cabeçalho a partir da página 2
        if page_num > 1:
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#4B5563"))
            self.drawString(
                40,
                812,
                "Projeto Fatura Aberta | Memorial Técnico Frente F2 & Guia RAG — @luizoryone",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.6)
            self.line(40, 806, 555, 806)

        # Rodapé em todas as páginas
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.6)
        self.line(40, 42, 555, 42)

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#4B5563"))
        self.drawString(
            40,
            30,
            "Residência em IA — Governo do DF / FAPDF | Frente F2: Conhecimento Jurídico e RAG",
        )
        texto_pag = f"Página {page_num} de {page_count}"
        self.drawRightString(555, 30, texto_pag)
        self.restoreState()


def montar_estilos() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    estilos: dict[str, ParagraphStyle] = {}

    estilos["DocTitle"] = ParagraphStyle(
        name="DocTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=0,
        spaceAfter=4,
    )
    estilos["DocSubtitle"] = ParagraphStyle(
        name="DocSubtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0D9488"),
        spaceAfter=10,
    )
    estilos["H1"] = ParagraphStyle(
        name="H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )
    estilos["H2"] = ParagraphStyle(
        name="H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0F766E"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )
    estilos["H3"] = ParagraphStyle(
        name="H3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1F2937"),
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    )
    estilos["Body"] = ParagraphStyle(
        name="Body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.8,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=4,
    )
    estilos["Bullet"] = ParagraphStyle(
        name="Bullet",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.3,
        leading=11.4,
        textColor=colors.HexColor("#1F2937"),
        leftIndent=12,
        spaceAfter=3,
    )
    estilos["Callout"] = ParagraphStyle(
        name="Callout",
        parent=base["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.2,
        leading=11.2,
        textColor=colors.HexColor("#1E3A8A"),
    )
    estilos["Code"] = ParagraphStyle(
        name="Code",
        parent=base["Normal"],
        fontName="Courier",
        fontSize=7.2,
        leading=9.2,
        textColor=colors.HexColor("#111827"),
    )
    estilos["TableHeader"] = ParagraphStyle(
        name="TableHeader",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )
    estilos["TableCell"] = ParagraphStyle(
        name="TableCell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.8,
        textColor=colors.HexColor("#1F2937"),
    )
    estilos["TableCellBold"] = ParagraphStyle(
        name="TableCellBold",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.8,
        textColor=colors.HexColor("#111827"),
    )
    return estilos


def criar_caixa_destaque(
    texto: str, estilo_texto: ParagraphStyle, cor_borda: str = "#0D9488", cor_fundo: str = "#F0FDFA"
) -> Table:
    p = Paragraph(texto, estilo_texto)
    t = Table([[p]], colWidths=[515])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(cor_fundo)),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("LINEBEFORE", (0, 0), (0, -1), 3.5, colors.HexColor(cor_borda)),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def criar_caixa_codigo(codigo: str, estilo_codigo: ParagraphStyle) -> Table:
    p = Preformatted(codigo, estilo_codigo)
    t = Table([[p]], colWidths=[515])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor("#64748B")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def construir_story(estilos: dict[str, ParagraphStyle]) -> list[Flowable]:
    story: list[Flowable] = []

    # =========================================================================
    # CAPA / CABEÇALHO DO DOCUMENTO
    # =========================================================================
    story.append(Paragraph("PROJETO FATURA ABERTA", estilos["DocTitle"]))
    story.append(
        Paragraph(
            "<b>Memorial Técnico e Guia Prático de RAG (Geração Aumentada por Recuperação / "
            "Retrieval-Augmented Generation) e Funções do Sistema</b>",
            estilos["DocSubtitle"],
        )
    )

    tabela_meta = Table(
        [
            [
                Paragraph(
                    "<b>Autor:</b> Luiz Fernando Oryone Lemos (@luizoryone)", estilos["TableCell"]
                ),
                Paragraph(
                    "<b>Papel:</b> Líder da F2 (Frente 2 — Conhecimento Jurídico e Recuperação)",
                    estilos["TableCell"],
                ),
            ],
            [
                Paragraph(
                    "<b>Colaborações Transversais:</b> F1 (Jurídica), F4 (Motor) e F5 (Ciência)",
                    estilos["TableCell"],
                ),
                Paragraph(
                    "<b>Programa:</b> Residência em IA (Governo do DF / FAPDF)",
                    estilos["TableCell"],
                ),
            ],
            [
                Paragraph(
                    "<b>Formato:</b> PDF (Formato Portátil de Documento / Portable Document Format)",
                    estilos["TableCell"],
                ),
                Paragraph(
                    "<b>Data da Consolidação:</b> 25 de Novembro de 2026", estilos["TableCell"]
                ),
            ],
        ],
        colWidths=[257, 258],
    )
    tabela_meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tabela_meta)
    story.append(Spacer(1, 8))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=8)
    )

    # =========================================================================
    # SEÇÃO 1: CONTEXTO GERAL E OBJETIVO DO PROJETO FATURA ABERTA
    # =========================================================================
    story.append(
        Paragraph("1. O que é o Projeto Fatura Aberta e Por Que Ele Existe?", estilos["H1"])
    )
    story.append(
        Paragraph(
            "O <b>Projeto Fatura Aberta</b> é uma iniciativa de pesquisa aplicada e desenvolvimento tecnológico "
            "criada no âmbito da Residência em Inteligência Artificial, financiada pela "
            "<b>FAPDF (Fundação de Apoio à Pesquisa do Distrito Federal)</b> em parceria com o Governo do Distrito Federal. "
            "Seu propósito é desenvolver uma plataforma de código aberto, auditável, transparente e estritamente "
            "aderente à <b>LGPD (Lei Geral de Proteção de Dados Pessoais)</b> para analisar e auditar faturas de "
            "energia elétrica de consumidores residenciais do subgrupo B1 atendidos pela distribuidora Neoenergia Distribuição Brasília.",
            estilos["Body"],
        )
    )
    story.append(
        Paragraph(
            "A conta de luz brasileira é repleta de siglas e fórmulas complexas: <b>TUSD (Tarifa de Uso do Sistema de Distribuição)</b>, "
            "<b>TE (Tarifa de Energia)</b>, bandeiras tarifárias verde, amarela e vermelha, <b>ICMS (Imposto sobre Circulação de "
            "Mercadorias e Serviços)</b>, <b>PIS (Programa de Integração Social)</b>, <b>COFINS (Contribuição para o Financiamento "
            "da Seguridade Social)</b>, <b>CIP (Contribuição de Iluminação Pública)</b> / <b>COSIP (Contribuição para o Custeio do "
            "Serviço de Iluminação Pública)</b> e o custo de disponibilidade. O consumidor leigo não consegue verificar se o que "
            "está sendo cobrado respeita as resoluções da <b>ANEEL (Agência Nacional de Energia Elétrica)</b>.",
            estilos["Body"],
        )
    )

    caixa_missao = (
        "<b>Em Termos Simples:</b> O Fatura Aberta atua como um verificador aberto e auditável. Ele lê os dados da conta "
        "de energia, confere a aritmética (Nível A), compara com tabelas oficiais versionadas da <b>ANEEL (Agência Nacional de Energia Elétrica)</b> "
        "(Nível B) e cita o texto vigente da norma (Nível C), para que o consumidor possa pedir esclarecimentos ou buscar o Procon-DF/Defensoria."
    )
    story.append(criar_caixa_destaque(caixa_missao, estilos["Callout"], "#1E3A8A", "#EFF6FF"))
    story.append(Spacer(1, 6))

    # =========================================================================
    # SEÇÃO 2: A JORNADA DE LUIZ ORYONE — ETAPAS DA FRENTE F2 E TRANSVERSAIS
    # =========================================================================
    story.append(Paragraph("2. A Jornada Técnica de Luiz Oryone: Sprints S1 a S6", estilos["H1"]))
    story.append(
        Paragraph(
            "Como líder da <b>F2 (Frente 2 — Conhecimento Jurídico e Recuperação)</b> e colaborador ativo nas frentes "
            "<b>F1 (Frente 1 — Jurídica e Regulatória)</b>, <b>F4 (Frente 4 — Motor e Regras de Negócio)</b> e "
            "<b>F5 (Frente 5 — Agentes, Avaliação e Ciência)</b>, Luiz Oryone foi o responsável por desenhar, "
            "implementar e testar todo o ecossistema de conhecimento regulatório e recuperação semântica do projeto. "
            "Abaixo estão detalhadas as etapas construídas em cada sprint:",
            estilos["Body"],
        )
    )

    # Tabela de Sprints e Issues
    dados_tabela_sprints = [
        [
            Paragraph("Sprint / Fase", estilos["TableHeader"]),
            Paragraph("Issue e Escopo", estilos["TableHeader"]),
            Paragraph("O que foi Construído e Entregue por Luiz Oryone", estilos["TableHeader"]),
            Paragraph("Impacto no Projeto", estilos["TableHeader"]),
        ],
        [
            Paragraph("<b>S1 (Sprint 1)</b><br/>Definição e Delimitação", estilos["TableCellBold"]),
            Paragraph("Issue #7<br/>Issue #21<br/>Issue #24", estilos["TableCell"]),
            Paragraph(
                "• Inventariou o corpus normativo oficial da <b>ANEEL (Agência Nacional de Energia Elétrica)</b> com URLs oficiais e vigência temporal.<br/>"
                "• Formulou as 10 <i>guiding questions</i> regulatórias fundamentais.<br/>"
                "• Revisou formalmente o pacote de delimitação como leitor externo.",
                estilos["TableCell"],
            ),
            Paragraph(
                "Definiu as fronteiras regulatórias e evitou escopos inviáveis.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph("<b>S2 (Sprint 2)</b><br/>Primeiro RAG", estilos["TableCellBold"]),
            Paragraph("Issue #26<br/>Issue #27", estilos["TableCell"]),
            Paragraph(
                "• Criou a estratégia de <b>chunking literal por dispositivo legal</b> (artigo, parágrafo, tabela tarifária).<br/>"
                "• Implementou o <b>IndiceHibrido</b> com busca vetorial + busca léxica filtrada por vigência.<br/>"
                "• Atingiu <b>100% de recall@5</b> em 30 perguntas no Gate regulatório.",
                estilos["TableCell"],
            ),
            Paragraph(
                "Recuperação determinística restrita a trechos literais vigentes; 30/30 de recall@5 na amostra estratificada do gate S2 (docs/avaliacao/resultados.md).",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph("<b>S3 (Sprint 3)</b><br/>Avaliação LLM × RAG", estilos["TableCellBold"]),
            Paragraph("Issue #35<br/>Issue #111<br/>Issue #112", estilos["TableCell"]),
            Paragraph(
                "• Ajustou a recuperação léxica para mapear sinônimos leigos e termos negativos.<br/>"
                "• Expandiu o corpus com o <b>PRODIST (Procedimentos de Distribuição de Energia Elétrica no Sistema Elétrico Nacional) Módulo 8</b> "
                "(indicadores DIC, FIC, DMIC, DICRI, DISE) e a <b>REH (Resolução Homologatória) ANEEL nº 3.614/2026</b>.<br/>"
                "• Elaborou o conjunto independente de 36 perguntas com teste de disjunção estrita.",
                estilos["TableCell"],
            ),
            Paragraph(
                "Blindou o sistema contra mudanças de tarifas e garantiu generalização empírica.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>S4 (Sprint 4)</b><br/>Multiagentes e Embedders", estilos["TableCellBold"]
            ),
            Paragraph("Issue #38<br/>Issue #114", estilos["TableCell"]),
            Paragraph(
                "• Criou a ferramenta de busca com citação formal para agentes de IA (<b>buscar_norma_com_citacao</b>).<br/>"
                "• Conduziu avaliação controlada pareada de embedders nas 51 perguntas com norma do split de teste (<b>EmbedderHash</b> vs <b>bge-m3</b> e <b>qwen3-embedding:0.6b</b> via Ollama, além de <b>EmbedderSemanticoPtBr</b>).<br/>"
                "• Realizou testes pareados (bootstrap B=10.000, semente 42, e McNemar) e medição de RAM (docs/avaliacao/resultados.md).",
                estilos["TableCell"],
            ),
            Paragraph(
                "Diferenças numéricas pequenas sem ganho estatisticamente significativo dos alternativos a 5% no conjunto avaliado; hashing 29x a 42x mais rápido e com 2,55 MB no processo.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph("<b>S5 (Sprint 5)</b><br/>Multimodalidade", estilos["TableCellBold"]),
            Paragraph("Suporte a F5<br/>Issue #184", estilos["TableCell"]),
            Paragraph(
                "• Apoiou a integração multimodal de documentos em <b>PDF (Formato Portátil de Documento / Portable Document Format)</b> e texto extraído.<br/>"
                "• Garantiu a persistência segura dos dados normativos e tarifários no contêiner da <b>API (Interface de Programação de Aplicações / Application Programming Interface)</b>.",
                estilos["TableCell"],
            ),
            Paragraph(
                "Garantia de que a API encontra as leis mesmo rodando isolada em Docker.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph("<b>S6 (Sprint 6)</b><br/>Aplicação Funcional", estilos["TableCellBold"]),
            Paragraph("Issue #186<br/>Issue #178<br/>Issue #193", estilos["TableCell"]),
            Paragraph(
                "• Fixou a política de fim de linha em <b>LF (Alimentação de Linha / Line Feed)</b> no .gitattributes, garantindo checksum idêntico no Windows (CRLF) e Linux/Mac (#186, PR #192).<br/>"
                "• Validou a inclusão do corpus normativo e da tabela tarifária no contêiner da API (PR #183), apoiando a integração do Nível B no endpoint /analisar (trabalho em andamento na issue #178, aberta).<br/>"
                "• Acompanhou a governança para evolução futura do contrato Achado v1.1 (trabalho em andamento na issue #193, aberta).",
                estilos["TableCell"],
            ),
            Paragraph(
                "Reprodutibilidade multiplataforma no CI e base tarifária pronta no contêiner para a S6.",
                estilos["TableCell"],
            ),
        ],
    ]

    tabela_sprints = Table(dados_tabela_sprints, colWidths=[70, 75, 250, 120])
    tabela_sprints.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(tabela_sprints)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SEÇÃO 3: O QUE É RAG EM TERMOS SIMPLES?
    # =========================================================================
    story.append(PageBreak())
    story.append(
        Paragraph(
            "3. O que é RAG (Geração Aumentada por Recuperação / Retrieval-Augmented Generation) em Termos Simples?",
            estilos["H1"],
        )
    )
    story.append(
        Paragraph(
            "A sigla <b>RAG (Geração Aumentada por Recuperação / Retrieval-Augmented Generation)</b> parece intimidadora, "
            "mas seu princípio fundamental é intuitivo e transparente. Vamos compreendê-la com uma comparação do dia a dia:",
            estilos["Body"],
        )
    )

    story.append(Paragraph("A Metáfora da Prova com Consulta", estilos["H2"]))
    story.append(
        Paragraph(
            "Imagine um estudante prestando um concurso público de Direito Regulatório de Energia Elétrica. "
            "Existem duas maneiras de esse estudante responder às questões da prova:",
            estilos["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>1. O Modelo Sem RAG (A Prova Sem Consulta):</b> O estudante responde tudo apenas confiando na sua memória. "
            "Se ele leu sobre o assunto anos atrás, ele pode errar o valor exato da tarifa, confundir a lei do Distrito Federal "
            "com a lei de São Paulo ou até 'inventar' com convicção um artigo de lei que nunca existiu. Nos sistemas de inteligência "
            "artificial, essa invenção convincente é chamada de <b>alucinação</b>.",
            estilos["Bullet"],
        )
    )
    story.append(
        Paragraph(
            "<b>2. O Modelo Com RAG (A Prova Com Consulta Obrigatória à Lei Oficial):</b> O estudante não tem permissão para inventar nada. "
            "Antes de escrever qualquer linha da resposta, ele é obrigado a ir até a estante de livros, abrir a pasta com as resoluções vigentes da "
            "<b>ANEEL (Agência Nacional de Energia Elétrica)</b>, achar o artigo exato, transcrever o texto literal oficial e "
            "apontar o número da resolução, o artigo, o parágrafo e o link oficial da agência reguladora.",
            estilos["Bullet"],
        )
    )

    caixa_rag = (
        "<b>Definição em Termos Simples:</b> <b>RAG (Geração Aumentada por Recuperação / Retrieval-Augmented Generation)</b> é o processo "
        "no qual o computador <b>primeiro busca</b> documentos oficiais de confiança (Recuperação / Retrieval) e <b>depois sintetiza</b> "
        "a resposta (Geração / Generation) fundamentada 100% nesses documentos. Se a busca não encontrar o artigo correto, ele tem a "
        "humildade de dizer <i>'não sei'</i> em vez de inventar uma mentira."
    )
    story.append(criar_caixa_destaque(caixa_rag, estilos["Callout"], "#0D9488", "#F0FDFA"))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Os Três Pilares do Mecanismo RAG no Fatura Aberta", estilos["H2"]))
    story.append(
        Paragraph(
            "Na arquitetura desenhada por Luiz Oryone no pacote `packages/rag/src/fa_rag/`, o RAG é composto por três peças fundamentais:",
            estilos["Body"],
        )
    )
    story.append(
        Paragraph(
            "• <b>Chunking Literal por Dispositivo Legal:</b> As leis não são divididas de forma arbitrária (como 'a cada 500 caracteres'). "
            "Elas são fatiadas respeitando a estrutura do legislador: um artigo é um pedaço (chunk); um parágrafo relevante é um pedaço; uma tabela "
            "tarifária oficial é um pedaço. Isso preserva a integridade semântica jurídica.",
            estilos["Bullet"],
        )
    )
    story.append(
        Paragraph(
            "• <b>Índice Híbrido (Vetorial + Léxico com Filtro Temporal):</b> Combina o melhor dos dois mundos. A busca vetorial entende "
            "o sentido amplo da pergunta (mesmo com palavras diferentes), enquanto a busca léxica garante que termos técnicos exatos "
            "(como <i>'DMIC'</i> ou <i>'art. 323'</i>) recebam nota máxima. Além disso, o filtro temporal descarta qualquer artigo que já "
            "tinha sido revogado na data da conta.",
            estilos["Bullet"],
        )
    )
    story.append(
        Paragraph(
            "• <b>Síntese Extrativa e Limiar de Abstenção Rigoroso ($0,30$):</b> O sistema nunca tenta enfeitar a resposta. Se a melhor norma "
            "encontrada tiver relevância menor que $0,30$, o sistema se cala (abstenção segura). Quando atinge nota maior ou igual a $0,30$, ele "
            "devolve a redação oficial literal com citação canônica e URL.",
            estilos["Bullet"],
        )
    )
    story.append(Spacer(1, 6))

    # =========================================================================
    # SEÇÃO 4: GUIA PRÁTICO DAS FUNÇÕES — COMO USAR NO CÓDIGO E NO SISTEMA
    # =========================================================================
    story.append(Paragraph("4. Guia Prático das Funções do Sistema: Como Usar", estilos["H1"]))
    story.append(
        Paragraph(
            "Abaixo estão detalhadas as principais funções do sistema construídas e integradas pela Frente F2, com explicações "
            "acessíveis e exemplos práticos de código em Python de como invocá-las:",
            estilos["Body"],
        )
    )

    # Função 1
    story.append(
        Paragraph("Função 1: IndiceHibrido.buscar() — O Localizador de Leis", estilos["H2"])
    )
    story.append(
        Paragraph(
            "<b>O que faz em termos simples:</b> É como um mecanismo de busca privativo que vasculha o acervo regulatório da "
            "<b>ANEEL (Agência Nacional de Energia Elétrica)</b> para encontrar os 5 trechos legais mais relevantes para a dúvida do usuário, "
            "garantindo que a norma consultada estava em vigor na data em que a fatura foi emitida.",
            estilos["Body"],
        )
    )
    codigo_busca = (
        "from datetime import date\n"
        "from fa_rag import IndiceHibrido\n\n"
        "# 1. Carrega ou constrói o índice de normas do subgrupo B1 residencial\n"
        "indice = IndiceHibrido.carregar_ou_construir()\n\n"
        "# 2. Faz uma busca passando a pergunta e a data de referência da conta de luz\n"
        "resultados = indice.buscar(\n"
        '    texto="Como funciona a devolução em dobro quando a distribuidora cobra a maior?",\n'
        "    data_referencia=date(2026, 11, 9),\n"
        "    top_k=5,\n"
        "    um_por_dispositivo=True\n"
        ")\n\n"
        "# 3. Inspeciona o artigo mais relevante encontrado\n"
        "melhor_artigo = resultados[0]\n"
        'print(f"Artigo encontrado: {melhor_artigo.titulo} | Score de Relevância: {melhor_artigo.score:.3f}")\n'
        'print(f"URL oficial da ANEEL: {melhor_artigo.url}")'
    )
    story.append(criar_caixa_codigo(codigo_busca, estilos["Code"]))
    story.append(Spacer(1, 6))

    # Função 2
    story.append(
        Paragraph("Função 2: responder() — O Decisor de Síntese e Abstenção Segura", estilos["H2"])
    )
    story.append(
        Paragraph(
            "<b>O que faz em termos simples:</b> Pega a lista de trechos retornada pelo buscador e aplica a régua de corte de segurança "
            "(`LIMIAR_PADRAO = 0.30`). Se a semelhança for igual ou superior a 0,30, monta a resposta com base na lei oficial. "
            "Se for menor que 0,30, liga o alerta de <b>abstenção</b> para proteger o usuário de falsas informações.",
            estilos["Body"],
        )
    )
    codigo_responder = (
        "from fa_rag import responder\n"
        "from fa_rag.sintese import LIMIAR_PADRAO\n\n"
        "# Processa a resposta passando os trechos recuperados e o limiar congelado de 0,30\n"
        "resposta = responder(resultados, limiar=LIMIAR_PADRAO)\n\n"
        "if resposta.abstencao:\n"
        '    print("O sistema se ABSTEVE com segurança: Não há base jurídica confiável para essa pergunta.")\n'
        "else:\n"
        '    print("Resposta Jurídica Oficial:\\n", resposta.texto)\n'
        '    print("Citação Canônica Aplicada:", resposta.citacao_canonica)\n'
        '    print("Links Oficiais de Consulta:", resposta.urls)'
    )
    story.append(criar_caixa_codigo(codigo_responder, estilos["Code"]))
    story.append(Spacer(1, 6))

    # Função 3
    story.append(PageBreak())
    story.append(
        Paragraph("Função 3: EmbedderHash — O Tradutor de Palavras em Vetores", estilos["H2"])
    )
    story.append(
        Paragraph(
            "<b>O que faz em termos simples:</b> Os computadores não comparam frases lendo como seres humanos; eles transformam "
            "textos em coordenadas matemáticas (vetores de 384 dimensões). O `EmbedderHash` faz isso usando funções de espalhamento matemático "
            "(hashing) sem depender de rede, sem baixar modelos de 1,2 GB e consumindo apenas 2,55 MB no processo (docs/avaliacao/resultados.md).",
            estilos["Body"],
        )
    )
    caixa_embedder = (
        "<b>Por que o Hashing Seguiu como Padrão? (docs/avaliacao/resultados.md):</b><br/>"
        "Na comparação pareada de embedders sobre as 51 perguntas com norma do split de teste (bootstrap B=10.000, semente 42, e teste de McNemar), "
        "o `EmbedderHash` obteve recall@5 = 0,990 (MRR = 0,902), contra 1,000 (MRR = 0,925) do `bge-m3` e 0,990 (MRR = 0,915) do `qwen3-embedding:0.6b` via Ollama local. "
        "<b>Resultado:</b> Há pequenas diferenças numéricas nas métricas, mas sem ganho estatisticamente significativo dos alternativos a 5% (McNemar p = 1,000 / p = 0,480); "
        "já a latência p50 dos modelos neurais foi 29x a 42x maior (113,6 ms e 166,9 ms contra 3,9 ms) com ~762 MB a ~1.380 MB de RAM no servidor. "
        "Decisão registrada em docs/avaliacao/resultados.md: manter o `EmbedderHash` como padrão offline de produção e CI."
    )
    story.append(criar_caixa_destaque(caixa_embedder, estilos["Callout"], "#D97706", "#FFFBEB"))
    story.append(Spacer(1, 6))

    # Função 4
    story.append(
        Paragraph(
            "Função 4: buscar_norma_com_citacao() — A Ferramenta dos Agentes de IA", estilos["H2"]
        )
    )
    story.append(
        Paragraph(
            "<b>O que faz em termos simples:</b> É a função-ponte que permite aos agentes inteligentes autônomos "
            "(como o Agente Analista e o Agente Auditor) 'conversarem' com a base jurídica. Quando o agente nota uma cobrança esquisita "
            "na conta, ele chama essa ferramenta para buscar o artigo exato e embasar o seu relatório de auditoria.",
            estilos["Body"],
        )
    )
    codigo_ferramenta = (
        "from fa_agentes.ferramentas import buscar_norma_com_citacao\n\n"
        "# Exemplo de invocação feita por um agente durante a auditoria da fatura\n"
        "resposta_agente = buscar_norma_com_citacao(\n"
        '    termo="limite de duracao continua de interrupcao DMIC grupo B1",\n'
        '    data_referencia="2026-11-09"\n'
        ")\n"
        'print("Trecho para o Relatório do Agente:", resposta_agente)'
    )
    story.append(criar_caixa_codigo(codigo_ferramenta, estilos["Code"]))
    story.append(Spacer(1, 6))

    # Função 5
    story.append(
        Paragraph("Função 5: Motor de Regras de Auditoria (Nível A e Nível B)", estilos["H2"])
    )
    story.append(
        Paragraph(
            "<b>O que faz em termos simples:</b> É o cérebro que executa as contas e comparações matemáticas da auditoria. Ele divide "
            "o trabalho em dois níveis de complexidade:",
            estilos["Body"],
        )
    )
    story.append(
        Paragraph(
            "• <b>Nível A (Auditoria Aritmética Imediata):</b> Confere a diferença entre leituras e consumo, a soma das linhas com o total, o produto quantidade × tarifa, a alíquota de ICMS impressa e a parcela até 80 kWh.",
            estilos["Bullet"],
        )
    )
    story.append(
        Paragraph(
            "• <b>Nível B (Comparação Tarifária com a Tabela ANEEL Versionada):</b> Implementado em `packages/motor/src/fa_motor/nivel_b.py`, cruza TUSD, TE e bandeira contra a planilha oficial versionada em `dados/tarifas/`, emitindo achados descritivos com fonte, ato e data de obtenção (sem estimar restituição). A conexão ao endpoint `/analisar` está em andamento na issue #178.",
            estilos["Bullet"],
        )
    )
    story.append(Spacer(1, 8))

    # =========================================================================
    # SEÇÃO 5: GLOSSÁRIO REGULATÓRIO E TÉCNICO DESCOMPLICADO
    # =========================================================================
    story.append(Paragraph("5. Glossário Descomplicado de Termos Regulatórios", estilos["H1"]))
    story.append(
        Paragraph(
            "Para facilitar o entendimento de qualquer cidadão, estudante ou pesquisador, abaixo está a tradução dos principais "
            "termos regulatórios presentes no sistema:",
            estilos["Body"],
        )
    )

    dados_glossario = [
        [
            Paragraph("Termo / Sigla", estilos["TableHeader"]),
            Paragraph("O que Significa na Prática (Linguagem do Cidadão)", estilos["TableHeader"]),
        ],
        [
            Paragraph(
                "<b>TUSD</b><br/>(Tarifa de Uso do Sistema de Distribuição)",
                estilos["TableCellBold"],
            ),
            Paragraph(
                "É o custo do transporte da eletricidade. Paga a infraestrutura de postes, cabos, transformadores e equipes de manutenção da distribuidora.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph("<b>TE</b><br/>(Tarifa de Energia)", estilos["TableCellBold"]),
            Paragraph(
                "É o preço da energia em si, gerada nas usinas hidrelétricas, solares ou térmicas, consumida pelos eletrodomésticos da sua residência.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>Subgrupo B1</b><br/>(Residencial Baixa Tensão)", estilos["TableCellBold"]
            ),
            Paragraph(
                "Classificação da ANEEL para casas, apartamentos e moradias populares atendidas em baixa tensão (127V ou 220V).",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>Custo de Disponibilidade</b><br/>(Taxa Mínima da Rede)",
                estilos["TableCellBold"],
            ),
            Paragraph(
                "Valor mínimo cobrado pela empresa só para deixar a rede ligada na sua casa (30 kWh monofásico, 50 kWh bifásico e 100 kWh trifásico), mesmo que a casa esteja vazia.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>DIC / FIC / DMIC / DICRI</b><br/>(Indicadores de Qualidade)",
                estilos["TableCellBold"],
            ),
            Paragraph(
                "Metas que definem quantas horas e quantas vezes a luz pode faltar. Se a empresa ultrapassar os limites do PRODIST Módulo 8, ela é obrigada por lei a dar um desconto na fatura.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>Devolução em Dobro</b><br/>(Art. 323 da REN 1.000/2021)",
                estilos["TableCellBold"],
            ),
            Paragraph(
                "Previsão do art. 323 da REN ANEEL nº 1.000/2021 para devolução em dobro de valores cobrados a maior por erro atribuível à distribuidora; o Fatura Aberta apenas aponta a diferença e cita a norma, sem afirmar ilegalidade nem estimar restituição.",
                estilos["TableCell"],
            ),
        ],
        [
            Paragraph(
                "<b>Limiar de Abstenção (0,30)</b><br/>(Filtro de Segurança RAG)",
                estilos["TableCellBold"],
            ),
            Paragraph(
                "Trava de proteção do robô de busca: se a melhor lei encontrada for fraca ou distante da pergunta (nota menor que 0,30), ele não responde, evitando inventar informações erradas.",
                estilos["TableCell"],
            ),
        ],
    ]

    tabela_glossario = Table(dados_glossario, colWidths=[150, 365])
    tabela_glossario.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D9488")),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tabela_glossario)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SEÇÃO 6: CONCLUSÃO E LEGADO DA FRENTE F2
    # =========================================================================
    story.append(Paragraph("6. Conclusão e Legado da Frente F2", estilos["H1"]))
    story.append(
        Paragraph(
            "O trabalho conduzido por Luiz Fernando Oryone Lemos na <b>Frente F2 (Conhecimento Jurídico e Recuperação)</b> "
            "consolidou a base sobre a qual todo o Projeto Fatura Aberta opera com segurança. "
            "Entre os legados técnicos permanentes entregues, destacam-se:",
            estilos["Body"],
        )
    )
    story.append(
        Paragraph(
            "1. <b>Zero Dependências Pesadas e CI 100% Offline:</b> Na avaliação sobre as 51 perguntas com norma do split de teste (docs/avaliacao/resultados.md), os extratores alternativos apresentaram pequenas diferenças numéricas sem ganho estatisticamente significativo sobre o `EmbedderHash` a 5%, sendo 29x a 42x mais lentos e exigindo até ~1.380 MB de RAM no servidor. Manter o `EmbedderHash` como padrão viabilizou rodar a suíte automatizada de testes (mais de 400 testes no repositório, no ambiente local e no CI `ubuntu-latest`) 100% offline, sem servidor de GPU nem custos de nuvem.",
            estilos["Bullet"],
        )
    )
    story.append(
        Paragraph(
            "2. <b>Auditoria Determinística e Rastreável:</b> Cada resposta devolvida pelo sistema carrega o trecho literal da norma, "
            "o artigo exato e o link oficial do portal da ANEEL, assegurando que o relatório gerado possa ser apresentado a órgãos de "
            "defesa do consumidor (como Procon e Defensoria Pública) com força probatória.",
            estilos["Bullet"],
        )
    )
    story.append(
        Paragraph(
            "3. <b>Reprodutibilidade Multiplataforma e LGPD:</b> A padronização estrita de quebras de linha em LF e a proibição absoluta "
            "de upload de faturas reais no repositório blindam o projeto quanto à privacidade de dados dos cidadãos e facilitam a colaboração "
            "entre pesquisadores utilizando sistemas Linux, macOS ou Windows.",
            estilos["Bullet"],
        )
    )
    story.append(Spacer(1, 10))

    caixa_encerramento = (
        "<b>Mensagem Final:</b> O Projeto Fatura Aberta demonstra que a inteligência artificial, quando ancorada "
        "em princípios rigorosos de engenharia de software e respeito à lei, tem o poder de democratizar a cidadania, "
        "tornando contas de energia transparentes e acessíveis para toda a sociedade brasileira."
    )
    story.append(criar_caixa_destaque(caixa_encerramento, estilos["Callout"], "#1E3A8A", "#EFF6FF"))

    return story


def main() -> None:
    estilos = montar_estilos()
    story = construir_story(estilos)

    OUT_ASSETS.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUT_ASSETS),
        pagesize=A4,
        leftMargin=38,
        rightMargin=38,
        topMargin=46,
        bottomMargin=46,
    )

    print(f"Compilando documento PDF em: {OUT_ASSETS}")
    doc.build(story, canvasmaker=NumberedCanvas)
    tamanho = OUT_ASSETS.stat().st_size
    print(f"Documento PDF gerado com sucesso! Tamanho: {tamanho} bytes")


if __name__ == "__main__":
    main()
