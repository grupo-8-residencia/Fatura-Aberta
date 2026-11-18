/**
 * Faísca, o vagalume: SVG geométrico, só formas sólidas (sem degradê, brilho nem transparência).
 * É decorativo (`aria-hidden`); o significado vem sempre do texto do balão.
 */

export type EstadoFaisca = "idle" | "happy" | "guiding" | "thinking" | "alert";

function Olhos({ estado }: { estado: EstadoFaisca }) {
  if (estado === "happy") {
    return <path className="faisca-traco" d="M40 34q3-4 6 0M50 34q3-4 6 0" />;
  }
  const dy = estado === "thinking" ? -3 : 0;
  const dx = estado === "guiding" ? 2 : 0;
  return (
    <>
      <circle className="faisca-olho" cx={43 + dx} cy={33 + dy} r="3" />
      <circle className="faisca-olho" cx={53 + dx} cy={33 + dy} r="3" />
    </>
  );
}

function Antenas({ estado }: { estado: EstadoFaisca }) {
  const reta = estado === "alert";
  return (
    <>
      <path className="faisca-antena" d={reta ? "M43 21 43 7" : "M43 21Q38 11 32 9"} />
      <path className="faisca-antena" d={reta ? "M53 21 53 7" : "M53 21Q58 11 64 9"} />
      <circle className="faisca-ponta" cx={reta ? 43 : 32} cy={reta ? 7 : 9} r="2.5" />
      <circle className="faisca-ponta" cx={reta ? 53 : 64} cy={reta ? 7 : 9} r="2.5" />
    </>
  );
}

function Detalhe({ estado }: { estado: EstadoFaisca }) {
  if (estado === "happy") {
    return (
      <>
        <path className="faisca-traco" d="M43 40q5 4 10 0" />
        <circle className="faisca-ponta" cx="16" cy="24" r="2.5" />
        <circle className="faisca-ponta" cx="80" cy="20" r="2.5" />
        <circle className="faisca-ponta" cx="84" cy="44" r="2.5" />
      </>
    );
  }
  if (estado === "guiding") {
    return <path className="faisca-seta" d="M80 58l12 6-12 6Z" />;
  }
  if (estado === "thinking") {
    return (
      <>
        <rect className="faisca-balao" x="66" y="4" width="26" height="14" rx="7" />
        <circle className="faisca-pensamento" cx="72" cy="11" r="2" />
        <circle className="faisca-pensamento" cx="79" cy="11" r="2" />
        <circle className="faisca-pensamento" cx="86" cy="11" r="2" />
      </>
    );
  }
  if (estado === "alert") {
    return (
      <>
        <circle className="faisca-alerta" cx="80" cy="16" r="10" />
        <path className="faisca-alerta-sinal" d="M80 10v7M80 21v.5" />
      </>
    );
  }
  return null;
}

export function Faisca({ estado, mensagem }: { estado: EstadoFaisca; mensagem: string }) {
  const asaDireita = estado === "guiding" ? "rotate(-55 58 46)" : "rotate(25 58 46)";
  return (
    <figure className={`faisca faisca--${estado}`}>
      <svg className="faisca-desenho" viewBox="0 0 96 96" aria-hidden="true" focusable="false">
        <ellipse className="faisca-asa" cx="38" cy="46" rx="10" ry="18" transform="rotate(-25 38 46)" />
        <ellipse className="faisca-asa" cx="58" cy="46" rx="10" ry="18" transform={asaDireita} />
        <g className="faisca-lanterna">
          <circle className="faisca-lanterna-externa" cx="48" cy="64" r="22" />
          <circle className="faisca-lanterna-meio" cx="48" cy="64" r="14" />
          <circle className="faisca-lanterna-centro" cx="48" cy="64" r="6" />
        </g>
        <Antenas estado={estado} />
        <circle className="faisca-cabeca" cx="48" cy="34" r="14" />
        <Olhos estado={estado} />
        <Detalhe estado={estado} />
      </svg>
      <figcaption className="faisca-fala">{mensagem}</figcaption>
    </figure>
  );
}
