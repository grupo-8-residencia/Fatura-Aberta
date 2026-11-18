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

export type Achado = {
  item: string;
  nivel: Nivel;
  descricao: string;
  valor_esperado?: string | null;
  valor_cobrado?: string | null;
  citacoes?: Citacao[];
  abstencao?: boolean;
};

export type RespostaAnalise = { achados: Achado[]; aviso?: string | null };

export type DadosConfirmados = {
  distribuidora: string;
  mesReferencia: string;
  leituraAnterior: string;
  leituraAtual: string;
  consumo: string;
  somaItens: string;
  total: string;
};

export type Resultado = "Confere" | "Divergência encontrada" | "Não foi possível concluir";

export type Decisao = {
  chave: string;
  titulo: string;
  nivel: Nivel;
  resultado: Resultado;
  explicacao: string;
  valores?: string;
  fontes: Citacao[];
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** "14.512" -> "14512"; "1.234,56" -> "1234.56". */
export function numeroParaApi(valor: string): string {
  return valor.trim().replaceAll(".", "").replace(",", ".");
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
    itens: [{ descricao: "Soma dos itens informada", valor: numeroParaApi(dados.somaItens) }],
    total: numeroParaApi(dados.total),
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

export function paraDecisao(a: Achado, indice: number): Decisao {
  const resultado: Resultado = a.abstencao
    ? "Não foi possível concluir"
    : divergente(a)
      ? "Divergência encontrada"
      : "Confere";
  const valores =
    a.valor_esperado != null && a.valor_cobrado != null
      ? `Valor calculado: ${formatarNumero(a.valor_esperado)} · Valor na fatura: ${formatarNumero(a.valor_cobrado)}`
      : undefined;
  return {
    chave: `${indice}-${a.nivel}-${a.item}`,
    titulo: a.item,
    nivel: a.nivel,
    resultado,
    explicacao: a.descricao,
    valores,
    fontes: a.citacoes ?? [],
  };
}

export async function analisarFatura(dados: DadosConfirmados): Promise<RespostaAnalise> {
  const resposta = await fetch(`${API_URL}/analisar`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(montarFatura(dados)),
  });
  if (!resposta.ok) {
    throw new Error(`A API respondeu ${resposta.status}.`);
  }
  return (await resposta.json()) as RespostaAnalise;
}
