/**
 * Contrato com a API (`POST /analisar`): monta a `Fatura` a partir dos campos confirmados e
 * converte cada `Achado` em um cartão de decisão. Os tipos espelham `fa_contratos`.
 */

export type Nivel = "A" | "B" | "C";

export type Citacao = {
  ato: string;
  dispositivo: string;
  vigencia_inicio: string;
  vigencia_fim?: string | null;
  url: string;
};

/** Categoria do achado (contrato 1.1.0): as cinco classes da análise jurídico-regulatória. */
export type CategoriaAchado =
  | "compativel"
  | "divergencia_identificada"
  | "verificacao_necessaria"
  | "dados_insuficientes"
  | "fora_do_escopo";

/** O que permite refazer e questionar o achado (fonte e vigência ficam em `citacoes`). */
export type RegistroAuditavel = {
  regra_aplicada: string;
  calculo?: string | null;
  data_consulta?: string | null;
  limitacoes?: string[];
};

export type Achado = {
  item: string;
  nivel: Nivel;
  descricao: string;
  valor_esperado?: string | null;
  valor_cobrado?: string | null;
  citacoes?: Citacao[];
  abstencao?: boolean;
  categoria?: CategoriaAchado | null;
  registro?: RegistroAuditavel | null;
};

export type RespostaAnalise = { achados: Achado[]; aviso?: string | null };

export type ItemDigitado = {
  id: number;
  descricao: string;
  quantidade: string;
  tarifa: string;
  valor: string;
};

export type DadosConfirmados = {
  distribuidora: string;
  mesReferencia: string;
  leituraAnterior: string;
  leituraAtual: string;
  consumo: string;
  /** Opcionais: vazios quando a fatura não informa, e então não entram na conferência. */
  bandeira: string;
  aliquotaIcms: string;
  itens: ItemDigitado[];
  total: string;
};

export type Resultado =
  | "Compatível"
  | "Divergência encontrada"
  | "Não foi possível concluir"
  | "Referência normativa"
  | "Verificação necessária"
  | "Dados insuficientes"
  | "Fora do escopo";

/** Resultados que não concluem sobre a cobrança (filtro "Sem conclusão"). */
export const RESULTADOS_SEM_CONCLUSAO: readonly Resultado[] = [
  "Não foi possível concluir",
  "Verificação necessária",
  "Dados insuficientes",
  "Fora do escopo",
];

export type Decisao = {
  chave: string;
  titulo: string;
  nivel: Nivel;
  resultado: Resultado;
  explicacao: string;
  valores?: string;
  fontes: Citacao[];
  /** Explicações dos agentes (níveis B/C) para o mesmo item, mostradas dentro deste cartão. */
  explicacoes: Decisao[];
  /** Regra, cálculo e limitações do achado (vazio para explicações dos agentes). */
  registro?: RegistroAuditavel | null;
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** "14.512" -> "14512"; "1.234,56" -> "1234.56". */
export function numeroParaApi(valor: string): string {
  return valor.trim().replaceAll(".", "").replace(",", ".");
}

/** Soma dos valores digitados, em centavos, para mostrar ao lado do total. */
export function somarItens(itens: ItemDigitado[]): string {
  const centavos = itens.reduce((soma, item) => {
    const n = Number(numeroParaApi(item.valor));
    return Number.isFinite(n) ? soma + Math.round(n * 100) : soma;
  }, 0);
  return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2 }).format(centavos / 100);
}

/** "10/2026" -> "2026-10-01". */
export function mesParaApi(mes: string): string {
  const [m, a] = mes.split("/");
  return `${a}-${m}-01`;
}

/** Mantém as casas decimais que a API mandou: "231.40" -> "231,40"; "14512" -> "14.512". */
export function formatarNumero(valor: string): string {
  const n = Number(valor);
  if (!Number.isFinite(n)) return valor;
  const casas = valor.includes(".") ? valor.split(".")[1].length : 0;
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(n);
}

/** "2022-01-03" -> "03/01/2022". */
export function formatarData(iso: string): string {
  const [a, m, d] = iso.split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}

export function montarFatura(dados: DadosConfirmados) {
  return {
    distribuidora: dados.distribuidora.trim(),
    mes_referencia: mesParaApi(dados.mesReferencia),
    leitura_anterior: numeroParaApi(dados.leituraAnterior),
    leitura_atual: numeroParaApi(dados.leituraAtual),
    consumo_kwh: numeroParaApi(dados.consumo),
    itens: dados.itens.map((item) => ({
      descricao: item.descricao.trim(),
      ...(item.quantidade.trim() ? { quantidade: numeroParaApi(item.quantidade), unidade: "kWh" } : {}),
      ...(item.tarifa.trim() ? { tarifa: numeroParaApi(item.tarifa) } : {}),
      valor: numeroParaApi(item.valor),
    })),
    total: numeroParaApi(dados.total),
    ...(dados.bandeira.trim() ? { bandeira: dados.bandeira.trim() } : {}),
    // A tela mostra a alíquota em porcentagem (12,00); a API recebe a fração (0.12).
    ...(dados.aliquotaIcms.trim()
      ? { aliquota_icms: String(Number(numeroParaApi(dados.aliquotaIcms)) / 100) }
      : {}),
  };
}

function divergente(a: Achado): boolean {
  return (
    !a.abstencao &&
    a.valor_esperado != null &&
    a.valor_cobrado != null &&
    Number(a.valor_esperado) !== Number(a.valor_cobrado)
  );
}

/**
 * Resultado do cartão. Um achado fora do nível A, sem abstenção e sem valores para comparar, é a
 * explicação de um agente (referência normativa do item), e não uma conclusão de compatibilidade.
 */
function resultadoDe(a: Achado): Resultado {
  const porCategoria = resultadoDaCategoria(a.categoria);
  if (porCategoria) return porCategoria;
  if (a.abstencao) return "Não foi possível concluir";
  if (divergente(a)) return "Divergência encontrada";
  const semValores = a.valor_esperado == null || a.valor_cobrado == null;
  if (a.nivel !== "A" && semValores) return "Referência normativa";
  return "Compatível";
}

/** Rótulo do cartão para a categoria do contrato; `undefined` para achados sem categoria. */
function resultadoDaCategoria(categoria: CategoriaAchado | null | undefined): Resultado | undefined {
  switch (categoria) {
    case "compativel":
      return "Compatível";
    case "divergencia_identificada":
      return "Divergência encontrada";
    case "verificacao_necessaria":
      return "Verificação necessária";
    case "dados_insuficientes":
      return "Dados insuficientes";
    case "fora_do_escopo":
      return "Fora do escopo";
    default:
      return undefined;
  }
}

export function paraDecisao(a: Achado, indice: number): Decisao {
  const resultado = resultadoDe(a);
  const valores =
    a.valor_esperado != null && a.valor_cobrado != null
      ? `Valor calculado: ${formatarNumero(a.valor_esperado)} · Valor na fatura: ${formatarNumero(a.valor_cobrado)}`
      : undefined;
  return {
    registro: a.registro ?? null,
    chave: `${indice}-${a.nivel}-${a.item}`,
    titulo: a.item,
    nivel: a.nivel,
    resultado,
    explicacao: a.descricao,
    valores,
    fontes: a.citacoes ?? [],
    explicacoes: [],
  };
}

/**
 * Converte a resposta do `/analisar` em cartões: cada explicação dos agentes (nível B ou C, para
 * o mesmo `item` de um achado do motor) entra dentro do cartão desse achado, em vez de virar um
 * cartão separado.
 */
export function montarDecisoes(achados: Achado[]): Decisao[] {
  const todas = achados.map(paraDecisao);
  const doMotor = new Map<string, Decisao>();
  for (const d of todas) {
    if (d.nivel === "A" && !doMotor.has(d.titulo)) doMotor.set(d.titulo, d);
  }
  const cartoes: Decisao[] = [];
  for (const d of todas) {
    const principal = doMotor.get(d.titulo);
    if (d.nivel !== "A" && principal) {
      principal.explicacoes.push(d);
    } else {
      cartoes.push(d);
    }
  }
  return cartoes;
}

export async function analisarFatura(dados: DadosConfirmados): Promise<RespostaAnalise> {
  const resposta = await fetch(`${API_URL}/analisar`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(montarFatura(dados)),
    signal: AbortSignal.timeout(TEMPO_LIMITE_TEXTO_MS),
  });
  if (!resposta.ok) {
    throw new Error(`A API respondeu ${resposta.status}.`);
  }
  return (await resposta.json()) as RespostaAnalise;
}

/** Fatura como a API devolve (`fa_contratos.Fatura`): números como texto com ponto decimal. */
export type FaturaApi = {
  distribuidora: string;
  mes_referencia: string;
  leitura_anterior?: string | null;
  leitura_atual?: string | null;
  consumo_kwh: string;
  itens: { descricao: string; quantidade?: string | null; tarifa?: string | null; valor: string }[];
  total: string;
  bandeira?: string | null;
  aliquota_icms?: string | null;
};

/** Resposta de `POST /extrair`: campos lidos do PDF para confirmar, ou o motivo claro da falha. */
export type RespostaExtracao = {
  fatura?: FaturaApi | null;
  erro?: string | null;
  motivo?: string | null;
  /** Campos obrigatórios que a foto não trouxe (só vem em `POST /extrair-foto`). */
  pendentes?: string[] | null;
};

/** Resposta de `POST /perguntar` usada na tela (os demais campos existem e são ignorados aqui). */
export type RespostaPergunta = {
  resposta: string;
  citacoes: Citacao[];
  abstencao: boolean;
  origem: string;
  motivo_abstencao: string;
  aviso?: string | null;
  modo: "texto" | "fatura";
};

export const PDF_TAMANHO_MAXIMO_BYTES = 5 * 1024 * 1024;

function brDecimal(valor: string | null | undefined, casas?: number): string {
  if (valor == null || valor === "") return "";
  const n = Number(valor);
  if (!Number.isFinite(n)) return valor;
  const fixo = casas != null ? n.toFixed(casas) : String(valor).replace(/0+$/, "").replace(/\.$/, "");
  return fixo.replace(".", ",");
}

function milhar(inteiro: string): string {
  return inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function brInteiro(valor: string | null | undefined): string {
  if (valor == null || valor === "") return "";
  const n = Number(valor);
  return Number.isFinite(n) ? milhar(String(Math.round(n))) : valor;
}

function brMoeda(valor: string): string {
  const n = Number(valor);
  if (!Number.isFinite(n)) return valor;
  const [inteiro, centavos] = n.toFixed(2).split(".");
  return `${milhar(inteiro)},${centavos}`;
}

/** "2026-06-01" -> "06/2026". */
export function mesDaApi(iso: string): string {
  const [a, m] = iso.split("-");
  return `${m}/${a}`;
}

/** Converte a `Fatura` lida do PDF nos campos do formulário de confirmação (formato pt-BR). */
export function faturaParaDados(f: FaturaApi): DadosConfirmados {
  return {
    distribuidora: f.distribuidora,
    mesReferencia: mesDaApi(f.mes_referencia),
    leituraAnterior: brInteiro(f.leitura_anterior),
    leituraAtual: brInteiro(f.leitura_atual),
    consumo: brInteiro(f.consumo_kwh),
    bandeira: f.bandeira ?? "",
    aliquotaIcms: f.aliquota_icms != null ? brMoeda(String(Number(f.aliquota_icms) * 100)) : "",
    itens: f.itens.map((item, i) => ({
      id: i + 1,
      descricao: item.descricao,
      quantidade: brDecimal(item.quantidade),
      tarifa: brDecimal(item.tarifa),
      valor: brMoeda(item.valor),
    })),
    total: brMoeda(f.total),
  };
}

function paraBase64(bytes: Uint8Array): string {
  let binario = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binario);
}

/** Prazos do navegador: a leitura de foto roda um modelo local e pode levar minutos. */
const TEMPO_LIMITE_TEXTO_MS = 60_000;
const TEMPO_LIMITE_FOTO_MS = 330_000;

export const FORMATOS_FOTO = ["image/jpeg", "image/png", "image/webp"];
const FOTO_TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024;

export async function extrairPdf(arquivo: File): Promise<RespostaExtracao> {
  if (arquivo.size > PDF_TAMANHO_MAXIMO_BYTES) {
    return { erro: "O arquivo passa de 5 MB. Envie só as páginas da fatura ou digite os dados.", motivo: "tamanho" };
  }
  const pdf_base64 = paraBase64(new Uint8Array(await arquivo.arrayBuffer()));
  const resposta = await fetch(`${API_URL}/extrair`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ pdf_base64 }),
    signal: AbortSignal.timeout(TEMPO_LIMITE_TEXTO_MS),
  });
  if (resposta.status === 422) {
    return { erro: "O arquivo não parece um PDF válido ou passa do tamanho aceito.", motivo: "arquivo_invalido" };
  }
  if (resposta.status === 504) {
    return { erro: "A leitura do PDF demorou demais. Tente de novo ou digite os dados.", motivo: "tempo_esgotado" };
  }
  if (!resposta.ok) throw new Error(`A API respondeu ${resposta.status}.`);
  return (await resposta.json()) as RespostaExtracao;
}

/** Foto da fatura: a leitura roda no modelo de visão local da API (nada sai da máquina). */
export async function extrairFoto(arquivo: File): Promise<RespostaExtracao> {
  if (!FORMATOS_FOTO.includes(arquivo.type)) {
    return {
      erro: "Use uma foto em JPG, PNG ou WEBP. Fotos HEIC do iPhone não são aceitas: troque o formato da câmera para JPEG ou envie o PDF.",
      motivo: "formato",
    };
  }
  if (arquivo.size > FOTO_TAMANHO_MAXIMO_BYTES) {
    return { erro: "A foto passa de 10 MB. Tire outra foto ou envie o PDF.", motivo: "tamanho" };
  }
  const imagem_base64 = paraBase64(new Uint8Array(await arquivo.arrayBuffer()));
  const resposta = await fetch(`${API_URL}/extrair-foto`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ imagem_base64 }),
    signal: AbortSignal.timeout(TEMPO_LIMITE_FOTO_MS),
  });
  if (resposta.status === 422) {
    return { erro: "Não foi possível enviar esta foto. Tente outra ou envie o PDF.", motivo: "arquivo_invalido" };
  }
  if (resposta.status === 503) {
    return {
      erro: "O leitor de fotos não está disponível agora. Envie o PDF da fatura ou digite os dados.",
      motivo: "leitor_indisponivel",
    };
  }
  if (resposta.status === 504) {
    return { erro: "A leitura da foto demorou demais. Tente outra foto ou digite os dados.", motivo: "tempo_esgotado" };
  }
  if (!resposta.ok) throw new Error(`A API respondeu ${resposta.status}.`);
  return (await resposta.json()) as RespostaExtracao;
}

export async function perguntar(dados: DadosConfirmados, pergunta: string): Promise<RespostaPergunta> {
  const resposta = await fetch(`${API_URL}/perguntar`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ pergunta: pergunta.trim(), fatura: montarFatura(dados) }),
    signal: AbortSignal.timeout(TEMPO_LIMITE_TEXTO_MS),
  });
  if (!resposta.ok) throw new Error(`A API respondeu ${resposta.status}.`);
  return (await resposta.json()) as RespostaPergunta;
}
