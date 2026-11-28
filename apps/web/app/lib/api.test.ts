/** Testes da camada de contrato da tela (#43, #169). Dados 100% sintéticos. */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  extrairFoto,
  extrairPdf,
  faturaParaDados,
  montarDecisoes,
  montarFatura,
  numeroParaApi,
  paraDecisao,
  type Achado,
  type DadosConfirmados,
  type FaturaApi,
} from "./api";

const dadosBase: DadosConfirmados = {
  distribuidora: "Neoenergia Brasília",
  mesReferencia: "10/2026",
  leituraAnterior: "14.250",
  leituraAtual: "14.512",
  consumo: "262",
  bandeira: "Amarela",
  aliquotaIcms: "12,00",
  itens: [{ id: 1, descricao: "Energia", quantidade: "262", tarifa: "0,78000", valor: "204,36" }],
  total: "228,00",
};

const faturaApiBase: FaturaApi = {
  distribuidora: "Neoenergia Brasília",
  mes_referencia: "2026-10-01",
  leitura_anterior: "14250",
  leitura_atual: "14512",
  consumo_kwh: "262",
  itens: [{ descricao: "Energia", quantidade: "262", tarifa: "0.78000", valor: "204.36" }],
  total: "228.00",
  bandeira: "Amarela",
  aliquota_icms: "0.12",
};

function resposta(status: number, corpo: unknown = {}): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function foto(tipo: string, tamanho = 4): File {
  return new File([new Uint8Array(tamanho)], "foto.jpg", { type: tipo });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("numeroParaApi", () => {
  it("converte o número brasileiro para o formato da API", () => {
    expect(numeroParaApi("14.512")).toBe("14512");
    expect(numeroParaApi("1.234,56")).toBe("1234.56");
  });
});

describe("montarFatura", () => {
  it("envia a bandeira e a alíquota como fração", () => {
    const fatura = montarFatura(dadosBase);
    expect(fatura.mes_referencia).toBe("2026-10-01");
    expect(fatura.leitura_anterior).toBe("14250");
    expect(fatura.bandeira).toBe("Amarela");
    expect(fatura.aliquota_icms).toBe("0.12");
    expect(fatura.itens[0]).toMatchObject({ quantidade: "262", unidade: "kWh", tarifa: "0.78000" });
  });

  it("não envia bandeira nem alíquota quando a fatura não as informa", () => {
    const fatura = montarFatura({ ...dadosBase, bandeira: "", aliquotaIcms: "" });
    expect(fatura).not.toHaveProperty("bandeira");
    expect(fatura).not.toHaveProperty("aliquota_icms");
  });
});

describe("faturaParaDados", () => {
  it("converte a fatura lida de volta para os campos da tela", () => {
    const dados = faturaParaDados(faturaApiBase);
    expect(dados.mesReferencia).toBe("10/2026");
    expect(dados.leituraAnterior).toBe("14.250");
    expect(dados.consumo).toBe("262");
    expect(dados.bandeira).toBe("Amarela");
    expect(dados.aliquotaIcms).toBe("12,00");
  });

  it("deixa a alíquota vazia quando a API não a devolve", () => {
    const dados = faturaParaDados({ ...faturaApiBase, aliquota_icms: null, bandeira: null });
    expect(dados.aliquotaIcms).toBe("");
    expect(dados.bandeira).toBe("");
  });
});

describe("cartões de decisão", () => {
  const base: Achado = { item: "Consumo medido", nivel: "A", descricao: "Texto sintético." };

  it("usa a categoria do contrato para o rótulo do cartão", () => {
    expect(paraDecisao({ ...base, categoria: "compativel" }, 0).resultado).toBe("Compatível");
    expect(paraDecisao({ ...base, categoria: "verificacao_necessaria" }, 0).resultado).toBe(
      "Verificação necessária",
    );
    expect(paraDecisao({ ...base, categoria: "dados_insuficientes" }, 0).resultado).toBe(
      "Dados insuficientes",
    );
    expect(paraDecisao({ ...base, categoria: "fora_do_escopo" }, 0).resultado).toBe(
      "Fora do escopo",
    );
  });

  it("leva o registro auditável para o cartão", () => {
    const registro = { regra_aplicada: "A2: leituras", limitacoes: ["sem medição externa"] };
    expect(paraDecisao({ ...base, registro }, 0).registro).toEqual(registro);
    expect(paraDecisao(base, 0).registro).toBeNull();
  });

  it("mantém o nível B como cartão próprio e mescla o nível C ao cartão do item A", () => {
    const achados: Achado[] = [
      { item: "Total da fatura", nivel: "A", descricao: "Soma confere.", valor_esperado: "10", valor_cobrado: "10" },
      { item: "Tarifa TUSD+TE", nivel: "B", descricao: "Tabela.", abstencao: true },
      { item: "Total da fatura", nivel: "C", descricao: "Norma sobre o total." },
    ];
    const cartoes = montarDecisoes(achados);
    expect(cartoes.map((c) => c.titulo)).toEqual(["Total da fatura", "Tarifa TUSD+TE"]);
    expect(cartoes[0].explicacoes).toHaveLength(1);
    expect(cartoes[1].nivel).toBe("B");
  });
});

describe("extrairFoto", () => {
  it("recusa formato que não é JPG, PNG ou WEBP sem chamar a API", async () => {
    const fetchFalso = vi.fn();
    vi.stubGlobal("fetch", fetchFalso);
    const r = await extrairFoto(foto("image/heic"));
    expect(r.motivo).toBe("formato");
    expect(fetchFalso).not.toHaveBeenCalled();
  });

  it("recusa foto acima de 10 MB sem chamar a API", async () => {
    const fetchFalso = vi.fn();
    vi.stubGlobal("fetch", fetchFalso);
    const r = await extrairFoto(foto("image/jpeg", 10 * 1024 * 1024 + 1));
    expect(r.motivo).toBe("tamanho");
    expect(fetchFalso).not.toHaveBeenCalled();
  });

  it("devolve os campos quando a API responde 200", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => resposta(200, { fatura: faturaApiBase, motivo: null })));
    const r = await extrairFoto(foto("image/jpeg"));
    expect(r.fatura?.distribuidora).toBe("Neoenergia Brasília");
  });

  it.each([
    [422, "arquivo_invalido"],
    [503, "leitor_indisponivel"],
    [504, "tempo_esgotado"],
  ])("trata a resposta %i com motivo distinto", async (status, motivo) => {
    vi.stubGlobal("fetch", vi.fn(async () => resposta(status, { detail: "x" })));
    const r = await extrairFoto(foto("image/png"));
    expect(r.motivo).toBe(motivo);
    expect(r.erro).toBeTruthy();
  });

  it("lança erro para resposta 500, sem mensagem inventada", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => resposta(500, {})));
    await expect(extrairFoto(foto("image/webp"))).rejects.toThrow("500");
  });
});

describe("extrairPdf", () => {
  it("trata 504 como tempo esgotado", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => resposta(504, {})));
    const pdf = new File([new Uint8Array(4)], "fatura.pdf", { type: "application/pdf" });
    const r = await extrairPdf(pdf);
    expect(r.motivo).toBe("tempo_esgotado");
  });
});
