"use client";

import { ChangeEvent, FormEvent, useState } from "react";

type Achado = {
  item: string;
  nivel: "A" | "B" | "C";
  descricao: string;
  valor_esperado?: string;
  valor_cobrado?: string;
  abstencao?: boolean;
};
type Resposta = { achados: Achado[]; aviso?: string };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function decimalParaApi(valor: string) {
  return valor.trim().replaceAll(".", "").replace(",", ".");
}

function achadoDivergente(achado: Achado) {
  return !achado.abstencao &&
    achado.valor_esperado !== undefined &&
    achado.valor_cobrado !== undefined &&
    achado.valor_esperado !== achado.valor_cobrado;
}

export default function Home() {
  const [arquivo, setArquivo] = useState("");
  const [distribuidora, setDistribuidora] = useState("");
  const [mesReferencia, setMesReferencia] = useState("");
  const [consumo, setConsumo] = useState("");
  const [leituraAnterior, setLeituraAnterior] = useState("");
  const [leituraAtual, setLeituraAtual] = useState("");
  const [valorItens, setValorItens] = useState("");
  const [total, setTotal] = useState("");
  const [resultado, setResultado] = useState<Resposta>();
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  function selecionarArquivo(event: ChangeEvent<HTMLInputElement>) {
    setArquivo(event.target.files?.[0]?.name ?? "");
  }

  async function analisar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setEnviando(true);
    setErro("");
    setResultado(undefined);
    try {
      const resposta = await fetch(`${apiUrl}/analisar`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          distribuidora,
          mes_referencia: `${mesReferencia}-01`,
          leitura_anterior: decimalParaApi(leituraAnterior),
          leitura_atual: decimalParaApi(leituraAtual),
          consumo_kwh: decimalParaApi(consumo),
          itens: [{ descricao: "Soma dos itens informada", valor: decimalParaApi(valorItens) }],
          total: decimalParaApi(total),
        }),
      });
      if (!resposta.ok) {
        throw new Error("Revise os campos informados e tente novamente.");
      }
      setResultado((await resposta.json()) as Resposta);
    } catch (causa) {
      setErro(causa instanceof Error ? causa.message : "Falha inesperada na análise.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#inicio">
          <span className="brand-mark">F</span>Fatura <strong>Aberta</strong>
        </a>
        <span className="secure"><i /> Demonstração pública</span>
      </header>
      <section className="hero" id="inicio">
        <div>
          <p className="eyebrow">CONFERÊNCIA TRANSPARENTE DE ENERGIA</p>
          <h1>Entenda sua fatura,<br /><em>item por item.</em></h1>
          <p className="hero-copy">Verificações reproduzíveis, linguagem clara e evidências que você pode acompanhar.</p>
          <div className="trust"><span>✓ Sem aconselhamento jurídico</span><span>✓ Use apenas dados fictícios</span></div>
        </div>
        <aside className="hero-card"><b>✓</b><div><strong>Como funciona</strong><p>Você informa e confirma os valores antes de qualquer análise.</p></div></aside>
      </section>
      <p className="public-warning" role="note"><strong>Use apenas dados sintéticos.</strong> Os valores digitados são enviados à API configurada para esta demonstração, hospedada no Render na versão pública. Não digite dados pessoais nem selecione uma fatura real.</p>
      <nav className="steps" aria-label="Etapas"><span className="done"><b>1</b>Enviar</span><i /><span className="done"><b>2</b>Confirmar</span><i /><span className={resultado ? "done" : ""}><b>3</b>Resultado</span></nav>
      <section className="workspace">
        <form className="analysis-card" onSubmit={analisar} aria-label="Informar dados da fatura">
          <section>
            <div className="section-title"><b>01</b><div><h2>Adicione sua fatura</h2><p>O envio é opcional e o arquivo ainda não é lido nesta etapa.</p></div></div>
            <label className={`dropzone ${arquivo ? "selected" : ""}`} htmlFor="arquivo"><span className="upload">↑</span><span><strong>{arquivo || "Escolha um arquivo"}</strong><small>{arquivo ? "Arquivo selecionado; informe os dados abaixo." : "PDF, PNG ou JPG · até 10 MB"}</small></span><em>Selecionar</em></label>
            <input className="hidden" id="arquivo" type="file" accept="application/pdf,image/*" onChange={selecionarArquivo} />
          </section>
          <section className="data-section">
            <div className="section-title"><b>02</b><div><h2>Informe os dados da fatura</h2><p>Para testar a conferência, preencha somente valores fictícios.</p></div></div>
            <div className="fields">
              <label>Distribuidora<input value={distribuidora} onChange={(event) => setDistribuidora(event.target.value)} required /></label>
              <label>Mês de referência<input type="month" value={mesReferencia} onChange={(event) => setMesReferencia(event.target.value)} required /></label>
              <label>Leitura anterior<input inputMode="decimal" value={leituraAnterior} onChange={(event) => setLeituraAnterior(event.target.value)} required /></label>
              <label>Leitura atual<input inputMode="decimal" value={leituraAtual} onChange={(event) => setLeituraAtual(event.target.value)} required /></label>
              <label>Consumo <small>kWh</small><input inputMode="decimal" value={consumo} onChange={(event) => setConsumo(event.target.value)} required /></label>
              <label>Soma dos itens <small>R$</small><input inputMode="decimal" value={valorItens} onChange={(event) => setValorItens(event.target.value)} required /></label>
              <label>Total da fatura <small>R$</small><input inputMode="decimal" value={total} onChange={(event) => setTotal(event.target.value)} required /></label>
            </div>
            <button type="submit" disabled={enviando}>{enviando ? "Conferindo dados…" : "Conferir fatura"}<span>→</span></button>
          </section>
          {erro && <p className="error" role="alert">{erro}</p>}
        </form>
        <aside className="levels"><p className="eyebrow">NOSSO COMPROMISSO</p><h2>Resultados que explicam <em>o porquê.</em></h2><div><b>A</b><p><strong>Nível A</strong>Conferência matemática com os dados da própria fatura.</p></div><div><b>B</b><p><strong>Nível B</strong>Comparação com fonte oficial e vigência identificada.</p></div><div><b>C</b><p><strong>Nível C</strong>Indício que pede esclarecimento à distribuidora.</p></div></aside>
      </section>
      {resultado && <section className="results" aria-live="polite"><header><div><p className="eyebrow">RESULTADO DA CONFERÊNCIA</p><h2>Cartão de decisão</h2></div><span>Concluído agora</span></header>{resultado.aviso && <p className="notice">{resultado.aviso}</p>}<div className="findings">{resultado.achados.map((achado) => { const divergente = achadoDivergente(achado); return <article className={divergente ? "divergent" : ""} key={achado.item}><div className="finding-top"><b>Nível {achado.nivel}</b><i className={divergente ? "divergent" : ""}>{divergente ? "!" : "✓"}</i></div><h3>{achado.item}</h3><p>{achado.descricao}</p>{achado.valor_esperado && <div className="comparison"><span><small>Calculado</small><strong>{achado.valor_esperado}</strong></span><span><small>Informado</small><strong>{achado.valor_cobrado}</strong></span></div>}<footer>◷ Evidência: valores informados nesta sessão</footer></article>; })}</div><footer className="legal">Este resultado não afirma ilegalidade nem estima restituição. Em caso de dúvida, procure a distribuidora ou órgãos de defesa do consumidor.</footer></section>}
    </main>
  );
}
