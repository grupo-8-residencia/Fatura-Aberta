"use client";

import { ChangeEvent, FormEvent, useState } from "react";

type Achado = {
  item: string;
  nivel: "A" | "B" | "C";
  descricao: string;
  valor_esperado?: string;
  valor_cobrado?: string;
};
type Resposta = { achados: Achado[]; aviso?: string };
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [arquivo, setArquivo] = useState("");
  const [consumo, setConsumo] = useState("100");
  const [leituraAnterior, setLeituraAnterior] = useState("100");
  const [leituraAtual, setLeituraAtual] = useState("200");
  const [total, setTotal] = useState("80.00");
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
          distribuidora: "Distribuidora informada pelo usuário",
          mes_referencia: "2026-01-01",
          leitura_anterior: leituraAnterior,
          leitura_atual: leituraAtual,
          consumo_kwh: consumo,
          itens: [{ descricao: "Total informado", valor: total }],
          total,
        }),
      });
      if (!resposta.ok) throw new Error("Não foi possível analisar os campos informados.");
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
        <a className="brand" href="#inicio"><span className="brand-mark">F</span>Fatura <strong>Aberta</strong></a>
        <span className="secure"><i /> Sessão privada</span>
      </header>
      <section className="hero" id="inicio">
        <div><p className="eyebrow">CONFERÊNCIA TRANSPARENTE DE ENERGIA</p><h1>Entenda sua fatura,<br /><em>item por item.</em></h1><p className="hero-copy">Verificações reproduzíveis, linguagem clara e evidências que você pode acompanhar.</p><div className="trust"><span>✓ Sem aconselhamento jurídico</span><span>✓ Dados não são armazenados</span></div></div>
        <aside className="hero-card"><b>✓</b><div><strong>Como funciona</strong><p>Você confirma os dados antes de qualquer análise.</p></div></aside>
      </section>
      <nav className="steps" aria-label="Etapas"><span className="done"><b>1</b>Enviar</span><i /><span className="done"><b>2</b>Confirmar</span><i /><span className={resultado ? "done" : ""}><b>3</b>Resultado</span></nav>
      <section className="workspace">
        <form className="analysis-card" onSubmit={analisar} aria-label="Confirmar dados da fatura">
          <section><div className="section-title"><b>01</b><div><h2>Adicione sua fatura</h2><p>PDF ou imagem. Nesta versão, o arquivo permanece no seu dispositivo.</p></div></div>
            <label className={`dropzone ${arquivo ? "selected" : ""}`} htmlFor="arquivo"><span className="upload">↑</span><span><strong>{arquivo || "Escolha um arquivo"}</strong><small>{arquivo ? "Arquivo selecionado — confirme os dados abaixo." : "PDF, PNG ou JPG · até 10 MB"}</small></span><em>Selecionar</em></label><input className="hidden" id="arquivo" type="file" accept="application/pdf,image/*" onChange={selecionarArquivo} />
          </section>
          <section className="data-section"><div className="section-title"><b>02</b><div><h2>Confira os dados lidos</h2><p>Revise os valores antes de solicitar a conferência.</p></div></div>
            <div className="fields"><label>Leitura anterior<input inputMode="decimal" value={leituraAnterior} onChange={(e) => setLeituraAnterior(e.target.value)} required /></label><label>Leitura atual<input inputMode="decimal" value={leituraAtual} onChange={(e) => setLeituraAtual(e.target.value)} required /></label><label>Consumo <small>kWh</small><input inputMode="decimal" value={consumo} onChange={(e) => setConsumo(e.target.value)} required /></label><label>Total da fatura <small>R$</small><input inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} required /></label></div>
            <button type="submit" disabled={enviando}>{enviando ? "Conferindo dados…" : "Conferir fatura"}<span>→</span></button>
          </section>{erro && <p className="error" role="alert">{erro}</p>}
        </form>
        <aside className="levels"><p className="eyebrow">NOSSO COMPROMISSO</p><h2>Resultados que explicam <em>o porquê.</em></h2><div><b>A</b><p><strong>Nível A</strong>Conferência matemática com os dados da própria fatura.</p></div><div><b>B</b><p><strong>Nível B</strong>Comparação com fonte oficial e vigência identificada.</p></div><div><b>C</b><p><strong>Nível C</strong>Indício que pede esclarecimento à distribuidora.</p></div></aside>
      </section>
      {resultado && <section className="results" aria-live="polite"><header><div><p className="eyebrow">RESULTADO DA CONFERÊNCIA</p><h2>Cartão de decisão</h2></div><span>Concluído agora</span></header>{resultado.aviso && <p className="notice">{resultado.aviso}</p>}<div className="findings">{resultado.achados.map((achado) => <article key={achado.item}><div className="finding-top"><b>Nível {achado.nivel}</b><i>✓</i></div><h3>{achado.item}</h3><p>{achado.descricao}</p>{achado.valor_esperado && <div className="comparison"><span><small>Calculado</small><strong>{achado.valor_esperado}</strong></span><span><small>Informado</small><strong>{achado.valor_cobrado}</strong></span></div>}<footer>◷ Evidência: valores confirmados nesta sessão</footer></article>)}</div><footer className="legal">Este resultado não afirma ilegalidade nem estima restituição. Em caso de dúvida, procure a distribuidora ou órgãos de defesa do consumidor.</footer></section>}
    </main>
  );
}
