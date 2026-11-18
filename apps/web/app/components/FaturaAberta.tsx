"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { Faisca, type EstadoFaisca } from "./Faisca";
import { Botao, SeloNivel } from "./ui";
import {
  analisarFatura,
  formatarData,
  paraDecisao,
  type DadosConfirmados,
  type Decisao,
  type Resultado,
} from "../lib/api";

type Tema = "light" | "dark";
type Destino = "fatura" | "conferencia" | "historico" | "ajuda";
type Filtro = "todos" | "confere" | "divergencia" | "sem_conclusao" | "A" | "B" | "C";
type Visao = "compacta" | "detalhada";
type Estado = "editando" | "conferindo" | "pronto" | "erro";

const CHAVE_TEMA = "fatura-aberta-tema";
const CHAVE_ONBOARDING = "fatura-aberta-onboarding-visto";

function ler(chave: string): string | null {
  try {
    return window.localStorage.getItem(chave);
  } catch {
    return null;
  }
}

function gravar(chave: string, valor: string): void {
  try {
    window.localStorage.setItem(chave, valor);
  } catch {
    // Modo privado ou armazenamento bloqueado: a preferência só vale nesta sessão.
  }
}

function temaInicial(): Tema {
  const salvo = ler(CHAVE_TEMA);
  if (salvo === "light" || salvo === "dark") return salvo;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function assinarConexao(aviso: () => void) {
  window.addEventListener("online", aviso);
  window.addEventListener("offline", aviso);
  return () => {
    window.removeEventListener("online", aviso);
    window.removeEventListener("offline", aviso);
  };
}

function useOnline(): boolean {
  return useSyncExternalStore(
    assinarConexao,
    () => navigator.onLine,
    () => true,
  );
}

const DESTINOS: { id: Destino; rotulo: string }[] = [
  { id: "fatura", rotulo: "Fatura" },
  { id: "conferencia", rotulo: "Conferência" },
  { id: "historico", rotulo: "Histórico" },
  { id: "ajuda", rotulo: "Ajuda" },
];

const DADOS_EXEMPLO: DadosConfirmados = {
  distribuidora: "Neoenergia Brasília",
  mesReferencia: "10/2026",
  leituraAnterior: "14.250",
  leituraAtual: "14.512",
  consumo: "262",
  somaItens: "228,00",
  total: "228,00",
};

const CAMPOS: Record<
  keyof DadosConfirmados,
  { rotulo: string; ajuda: string; modo: "text" | "numeric" | "decimal" }
> = {
  distribuidora: {
    rotulo: "Distribuidora",
    ajuda: "Confira o nome impresso no topo da fatura.",
    modo: "text",
  },
  mesReferencia: {
    rotulo: "Mês de referência",
    ajuda: "Use o formato MM/AAAA, como 10/2026.",
    modo: "numeric",
  },
  leituraAnterior: {
    rotulo: "Leitura anterior",
    ajuda: "Só números; o ponto de milhar é opcional.",
    modo: "numeric",
  },
  leituraAtual: {
    rotulo: "Leitura atual",
    ajuda: "Só números; o ponto de milhar é opcional.",
    modo: "numeric",
  },
  consumo: { rotulo: "Consumo (kWh)", ajuda: "O consumo total impresso na fatura.", modo: "numeric" },
  somaItens: {
    rotulo: "Soma dos itens (R$)",
    ajuda: "Use vírgula para os centavos, como 228,00.",
    modo: "decimal",
  },
  total: { rotulo: "Total (R$)", ajuda: "Use vírgula para os centavos, como 228,00.", modo: "decimal" },
};

const LEITURA = /^(?:\d+|\d{1,3}(?:\.\d{3})+)$/;
const MOEDA = /^(?:\d+|\d{1,3}(?:\.\d{3})+),\d{2}$/;

function validar(d: DadosConfirmados): Partial<Record<keyof DadosConfirmados, string>> {
  const erros: Partial<Record<keyof DadosConfirmados, string>> = {};
  if (!d.distribuidora.trim()) erros.distribuidora = "Informe o nome da distribuidora.";
  if (!/^(0[1-9]|1[0-2])\/\d{4}$/.test(d.mesReferencia))
    erros.mesReferencia = "Informe o mês com números, como 10/2026.";
  if (!LEITURA.test(d.leituraAnterior))
    erros.leituraAnterior = "Informe a leitura anterior com números, como 14.250.";
  if (!LEITURA.test(d.leituraAtual))
    erros.leituraAtual = "Informe a leitura atual com números, como 14.512.";
  if (!LEITURA.test(d.consumo)) erros.consumo = "Informe o consumo em números, como 262.";
  if (!MOEDA.test(d.somaItens)) erros.somaItens = "Informe a soma dos itens, como 228,00.";
  if (!MOEDA.test(d.total)) erros.total = "Informe o total, como 228,00.";
  return erros;
}

const ORIENTACAO =
  "Você pode pedir esclarecimento à distribuidora. Se tiver dúvida, procure o Procon-DF ou a Defensoria Pública do DF.";

function textoPedido(d: Decisao, mes: string): string {
  return `Peço esclarecimento sobre o item "${d.titulo}" da fatura de ${mes}, com a memória de cálculo usada pela distribuidora.`;
}

function useFocoPreso(
  aberto: boolean,
  ref: React.RefObject<HTMLElement | null>,
  aoFechar?: () => void,
) {
  useEffect(() => {
    if (!aberto) return;
    const anterior = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("[data-foco-inicial]")?.focus();
    const teclado = (evento: KeyboardEvent) => {
      if (evento.key === "Escape" && aoFechar) {
        evento.preventDefault();
        aoFechar();
        return;
      }
      if (evento.key !== "Tab") return;
      const focaveis = Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
      if (focaveis.length === 0) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      if (evento.shiftKey && document.activeElement === primeiro) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      }
    };
    document.addEventListener("keydown", teclado);
    return () => {
      document.removeEventListener("keydown", teclado);
      anterior?.focus();
    };
  }, [aberto, aoFechar, ref]);
}

function Gaveta({
  aberta,
  titulo,
  aoFechar,
  lateral = false,
  children,
}: {
  aberta: boolean;
  titulo: string;
  aoFechar: () => void;
  lateral?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useFocoPreso(aberta, ref, aoFechar);
  if (!aberta) return null;
  return (
    <div
      ref={ref}
      className={`side-sheet ${lateral ? "side-sheet--side" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="gaveta-titulo"
    >
      <div className="side-sheet-header">
        <h2 id="gaveta-titulo">{titulo}</h2>
        <Botao variante="secondary" data-foco-inicial onClick={aoFechar}>
          Fechar
        </Botao>
      </div>
      <div className="side-sheet-content">{children}</div>
    </div>
  );
}

function Modal({
  aberto,
  titulo,
  aoFechar,
  acoes,
  children,
}: {
  aberto: boolean;
  titulo: string;
  aoFechar: () => void;
  acoes: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useFocoPreso(aberto, ref, aoFechar);
  if (!aberto) return null;
  return (
    <div className="modal-layer">
      <div
        ref={ref}
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="modal-titulo"
        aria-describedby="modal-descricao"
      >
        <h2 id="modal-titulo">{titulo}</h2>
        <div id="modal-descricao" className="modal-content">
          {children}
        </div>
        <div className="modal-actions">{acoes}</div>
      </div>
    </div>
  );
}

function Onboarding({ aoConcluir }: { aoConcluir: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useFocoPreso(true, ref);
  const passos = [
    { titulo: "Enviar", texto: "Informe só os dados necessários para a conferência." },
    { titulo: "Confirmar", texto: "Revise os valores antes de qualquer cálculo." },
    { titulo: "Entender", texto: "Veja o que confere e onde cabe pedir esclarecimento." },
  ];
  return (
    <div
      ref={ref}
      className="onboarding"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-titulo"
    >
      <div className="onboarding-card">
        <Faisca estado="guiding" mensagem="Vamos entender sua fatura." />
        <div className="onboarding-heading">
          <p className="section-kicker">Boas-vindas</p>
          <h1 id="onboarding-titulo">Entenda sua fatura</h1>
          <p>Três passos simples. Nesta demonstração, use apenas dados fictícios.</p>
        </div>
        <ol className="onboarding-steps">
          {passos.map((p, i) => (
            <li key={p.titulo}>
              <span aria-hidden="true">{i + 1}</span>
              <div>
                <strong>{p.titulo}</strong>
                <p>{p.texto}</p>
              </div>
            </li>
          ))}
        </ol>
        <div className="onboarding-actions">
          <Botao data-foco-inicial onClick={aoConcluir}>
            Começar
          </Botao>
          <Botao variante="secondary" onClick={aoConcluir}>
            Pular
          </Botao>
        </div>
      </div>
    </div>
  );
}

function Guia() {
  return (
    <>
      <Faisca estado="guiding" mensagem="Vou explicar estes termos." />
      <div className="guide-terms">
        <section>
          <h3>Bandeira tarifária</h3>
          <p>
            A bandeira mostra o custo de gerar energia no período. Na amarela e na vermelha, há
            um adicional por kWh consumido.
          </p>
        </section>
        <section>
          <h3>ICMS</h3>
          <p>
            ICMS é um imposto estadual que entra na conta de energia. A fatura informa a
            porcentagem usada no cálculo.
          </p>
        </section>
        <section>
          <h3>kWh</h3>
          <p>
            kWh é a unidade da energia consumida. O consumo do mês é a diferença entre a leitura
            atual e a anterior.
          </p>
        </section>
        <section>
          <h3>Níveis A, B e C</h3>
          <p>
            A é conta feita com os dados da própria fatura. B compara com a tabela oficial da
            ANEEL. C é indício que não dá para confirmar e vira pedido de esclarecimento.
          </p>
        </section>
      </div>
    </>
  );
}

function IconeResultado({ resultado }: { resultado: Resultado }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="7.5" stroke="currentColor" />
      {resultado === "Confere" ? (
        <path d="m6.5 10 2.25 2.25 4.75-4.75" stroke="currentColor" />
      ) : (
        <path d="M10 6.5v4M10 13.5v.25" stroke="currentColor" />
      )}
    </svg>
  );
}

function CartaoDecisao({
  decisao,
  revisado,
  aoPedir,
  aoRevisar,
}: {
  decisao: Decisao;
  revisado: boolean;
  aoPedir: () => void;
  aoRevisar: () => void;
}) {
  const semConclusao = decisao.resultado === "Não foi possível concluir";
  const diverge = decisao.resultado === "Divergência encontrada";
  return (
    <article className={`decision-card ${revisado ? "decision-card--reviewed" : ""}`}>
      <div className="decision-card-heading">
        <h3>{decisao.titulo}</h3>
        <SeloNivel nivel={decisao.nivel} />
      </div>
      <p
        className={`decision-result ${
          semConclusao ? "decision-result--inconclusive" : diverge ? "decision-result--divergence" : ""
        }`}
      >
        <IconeResultado resultado={decisao.resultado} />
        <strong>{decisao.resultado}</strong>
      </p>
      <p className="decision-explanation">{decisao.explicacao}</p>
      {decisao.valores && <p className="decision-values">{decisao.valores}</p>}
      {(diverge || semConclusao) && <p className="decision-guidance">{ORIENTACAO}</p>}
      <div className="decision-source">
        <strong>Fonte:</strong>{" "}
        {decisao.fontes.length === 0 ? (
          "dados informados nesta fatura."
        ) : (
          <ul>
            {decisao.fontes.map((c) => (
              <li key={`${c.ato}-${c.dispositivo}`}>
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.ato}, {c.dispositivo}
                </a>
                , vigente desde {formatarData(c.vigencia_inicio)}
                {c.vigencia_fim ? ` até ${formatarData(c.vigencia_fim)}` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="decision-actions">
        {(diverge || semConclusao) && (
          <Botao variante="secondary" onClick={aoPedir}>
            Pedir esclarecimento
          </Botao>
        )}
        <Botao variante="secondary" disabled={revisado} onClick={aoRevisar}>
          {revisado ? "Revisado" : "Marcar como revisado"}
        </Botao>
      </div>
    </article>
  );
}

function FormularioConfirmacao({
  dados,
  online,
  conferindo,
  aoMudar,
  aoConfirmar,
}: {
  dados: DadosConfirmados;
  online: boolean;
  conferindo: boolean;
  aoMudar: (campo: keyof DadosConfirmados, valor: string) => void;
  aoConfirmar: () => void;
}) {
  const erros = validar(dados);
  const valido = Object.keys(erros).length === 0;
  return (
    <section className="content-card confirmation-card" aria-labelledby="confirmacao-titulo">
      <div className="confirmation-intro">
        <span className="step-marker" aria-hidden="true">
          1
        </span>
        <div>
          <p className="section-kicker">Antes da conferência</p>
          <h2 id="confirmacao-titulo">Confirme os dados da fatura</h2>
          <p>Nenhuma conta é feita antes da confirmação. Os campos vêm com um exemplo fictício.</p>
        </div>
      </div>
      <form
        className="confirmation-form"
        noValidate
        onSubmit={(evento) => {
          evento.preventDefault();
          if (valido && online && !conferindo) aoConfirmar();
        }}
      >
        {(Object.keys(CAMPOS) as (keyof DadosConfirmados)[]).map((campo) => {
          const { rotulo, ajuda, modo } = CAMPOS[campo];
          const erro = erros[campo];
          return (
            <div className="field" key={campo}>
              <label htmlFor={campo}>{rotulo}</label>
              <input
                className="input"
                id={campo}
                name={campo}
                value={dados[campo]}
                inputMode={modo}
                autoComplete="off"
                onChange={(e) => aoMudar(campo, e.target.value)}
                aria-describedby={`${campo}-ajuda${erro ? ` ${campo}-erro` : ""}`}
                aria-invalid={Boolean(erro)}
              />
              <span className="field-hint" id={`${campo}-ajuda`}>
                {ajuda}
              </span>
              {erro && (
                <span className="field-error" id={`${campo}-erro`}>
                  {erro}
                </span>
              )}
            </div>
          );
        })}
        <p className="privacy-note">
          <span aria-hidden="true">i</span>
          Nome, endereço, CPF e número da instalação não são pedidos nem guardados.
        </p>
        <div className="confirmation-actions">
          <Botao type="submit" disabled={!valido || !online || conferindo}>
            {conferindo ? "Conferindo os dados…" : "Confirmar e conferir"}
          </Botao>
          <p aria-live="polite">
            {!online
              ? "Sem conexão: a conferência precisa da internet."
              : valido
                ? "Campos prontos para a conferência."
                : "Revise os campos indicados antes de continuar."}
          </p>
        </div>
      </form>
    </section>
  );
}

const FILTROS: { id: Filtro; rotulo: string }[] = [
  { id: "todos", rotulo: "Todos" },
  { id: "confere", rotulo: "Confere" },
  { id: "divergencia", rotulo: "Divergência" },
  { id: "sem_conclusao", rotulo: "Sem conclusão" },
  { id: "A", rotulo: "Nível A" },
  { id: "B", rotulo: "Nível B" },
  { id: "C", rotulo: "Nível C" },
];

function passaFiltro(d: Decisao, filtro: Filtro): boolean {
  if (filtro === "todos") return true;
  if (filtro === "confere") return d.resultado === "Confere";
  if (filtro === "divergencia") return d.resultado === "Divergência encontrada";
  if (filtro === "sem_conclusao") return d.resultado === "Não foi possível concluir";
  return d.nivel === filtro;
}

export default function FaturaAberta() {
  const [tema, setTema] = useState<Tema>(temaInicial);
  const [destino, setDestino] = useState<Destino>("fatura");
  const online = useOnline();
  const [mostrarOnboarding, setMostrarOnboarding] = useState(() => ler(CHAVE_ONBOARDING) !== "1");
  const [dados, setDados] = useState<DadosConfirmados>(DADOS_EXEMPLO);
  const [estado, setEstado] = useState<Estado>("editando");
  const [decisoes, setDecisoes] = useState<Decisao[]>([]);
  const [aviso, setAviso] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [visao, setVisao] = useState<Visao>("detalhada");
  const [revisados, setRevisados] = useState<string[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [guiaAberto, setGuiaAberto] = useState(false);
  const [pedido, setPedido] = useState<Decisao | null>(null);
  const [copiado, setCopiado] = useState("");
  const [modalLimpar, setModalLimpar] = useState(false);
  const buscaRef = useRef<HTMLInputElement>(null);
  const tituloConferenciaRef = useRef<HTMLHeadingElement>(null);

  const fecharGuia = useCallback(() => setGuiaAberto(false), []);
  const fecharPedido = useCallback(() => setPedido(null), []);
  const fecharModal = useCallback(() => setModalLimpar(false), []);

  useEffect(() => {
    document.documentElement.dataset.theme = tema;
    document.documentElement.style.colorScheme = tema;
    gravar(CHAVE_TEMA, tema);
  }, [tema]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 8_000);
    return () => window.clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    const atalho = (evento: KeyboardEvent) => {
      const alvo = evento.target as HTMLElement;
      const digitando = ["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName);
      if (evento.key === "/" && !digitando && destino === "conferencia" && buscaRef.current) {
        evento.preventDefault();
        buscaRef.current.focus();
      }
    };
    window.addEventListener("keydown", atalho);
    return () => window.removeEventListener("keydown", atalho);
  }, [destino]);

  async function conferir() {
    setEstado("conferindo");
    setAviso(null);
    try {
      const resposta = await analisarFatura(dados);
      setDecisoes(resposta.achados.map(paraDecisao));
      setAviso(resposta.aviso ?? null);
      setRevisados([]);
      setEstado("pronto");
    } catch {
      setEstado("erro");
    }
    setDestino("conferencia");
    // Leva o foco ao título da conferência, para o leitor de tela anunciar o resultado.
    window.requestAnimationFrame(() => tituloConferenciaRef.current?.focus());
  }

  function concluirOnboarding() {
    gravar(CHAVE_ONBOARDING, "1");
    setMostrarOnboarding(false);
    window.requestAnimationFrame(() => document.getElementById("conteudo")?.focus());
  }

  function limpar() {
    setDados(DADOS_EXEMPLO);
    setDecisoes([]);
    setAviso(null);
    setRevisados([]);
    setEstado("editando");
    setDestino("fatura");
    setModalLimpar(false);
  }

  const termo = busca.trim().toLocaleLowerCase("pt-BR");
  const visiveis = decisoes.filter(
    (d) =>
      passaFiltro(d, filtro) &&
      (!termo ||
        `${d.titulo} ${d.resultado} ${d.explicacao}`.toLocaleLowerCase("pt-BR").includes(termo)),
  );
  const proximoTema: Tema = tema === "light" ? "dark" : "light";
  const totalTexto = `R$ ${dados.total}`;
  const mascote: Record<Destino, { estado: EstadoFaisca; mensagem: string }> = {
    fatura: { estado: "idle", mensagem: "Comece confirmando os dados da fatura." },
    conferencia: {
      estado:
        estado === "erro"
          ? "alert"
          : estado === "conferindo"
            ? "thinking"
            : decisoes.some((d) => d.resultado !== "Confere")
              ? "guiding"
              : decisoes.length
                ? "happy"
                : "idle",
      mensagem:
        estado === "erro"
          ? "Não consegui conferir agora."
          : decisoes.some((d) => d.resultado !== "Confere")
            ? "Veja os itens destacados."
            : decisoes.length
              ? "Tudo certo com os itens conferidos."
              : "Confirme a fatura para ver a conferência.",
    },
    historico: { estado: "idle", mensagem: "Nada fica guardado por aqui." },
    ajuda: { estado: "guiding", mensagem: "Abra o Guia do Faísca quando precisar." },
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conteudo">
        Pular para o conteúdo principal
      </a>
      <header className="site-header">
        <div className="header-content">
          <button className="brand" type="button" onClick={() => setDestino("fatura")}>
            <span className="brand-icon" aria-hidden="true">
              <svg className="brand-mark" viewBox="0 0 24 24" fill="none">
                <path d="M7 3.5h8l3 3v14H7v-17Z" stroke="currentColor" />
                <path d="M15 3.5v3h3M10 11h5M10 15h5" stroke="currentColor" />
              </svg>
            </span>
            <span className="brand-copy">
              <strong>Fatura Aberta</strong>
              <span>Entenda sua conta de energia</span>
            </span>
          </button>
          <div className="header-actions">
            <p
              className={`connection-status connection-status--${online ? "online" : "offline"}`}
              role="status"
            >
              <span className="connection-symbol" aria-hidden="true">
                {online ? "✓" : "×"}
              </span>
              {online ? "Online" : "Offline"}
            </p>
            <Botao variante="secondary" onClick={() => setTema(proximoTema)}>
              Tema: {tema === "light" ? "claro" : "escuro"}
            </Botao>
            <Botao
              variante="secondary"
              onClick={() => {
                setPedido(null);
                setGuiaAberto(true);
              }}
            >
              Guia do Faísca
            </Botao>
          </div>
        </div>
      </header>

      <nav className="primary-navigation" aria-label="Navegação principal">
        <div className="navigation-items">
          {DESTINOS.map(({ id, rotulo }) => (
            <button
              key={id}
              type="button"
              className="navigation-item"
              aria-current={destino === id ? "page" : undefined}
              onClick={() => setDestino(id)}
            >
              {rotulo}
            </button>
          ))}
        </div>
      </nav>

      <main className="app-main" id="conteudo" tabIndex={-1}>
        {!online && (
          <div className="offline-banner" role="status">
            <strong>Você está offline.</strong> Os dados digitados continuam aqui. A conferência
            volta a funcionar quando a conexão voltar.
          </div>
        )}
        {destino === "conferencia" && estado === "pronto" && (
          <section className="bill-summary-strip" aria-label="Resumo da fatura">
            <div>
              <span className="summary-strip-label">Total informado</span>
              <strong>{totalTexto}</strong>
            </div>
            <div>
              <span className="summary-strip-label">Mês de referência</span>
              <strong>{dados.mesReferencia}</strong>
            </div>
            <div>
              <span className="summary-strip-label">Consumo</span>
              <strong>{dados.consumo} kWh</strong>
            </div>
          </section>
        )}
        <div className="content-grid">
          <div className="detail-column">
            {destino === "fatura" && (
              <>
                <div className="page-heading">
                  <p className="eyebrow">Grupo B1 · Neoenergia Brasília · DF</p>
                  <h1>Confirmar dados da fatura</h1>
                  <p>Revise os valores antes de qualquer cálculo.</p>
                </div>
                <FormularioConfirmacao
                  dados={dados}
                  online={online}
                  conferindo={estado === "conferindo"}
                  aoMudar={(campo, valor) => setDados((atual) => ({ ...atual, [campo]: valor }))}
                  aoConfirmar={() => void conferir()}
                />
              </>
            )}

            {destino === "conferencia" && (
              <>
                <div className="page-heading">
                  <p className="eyebrow">Fatura de {dados.mesReferencia}</p>
                  <h1 ref={tituloConferenciaRef} tabIndex={-1}>
                    Conferência
                  </h1>
                  <p>O que conseguimos verificar, item por item.</p>
                  {estado === "pronto" && (
                    <div className="heading-actions">
                      <Botao variante="secondary" onClick={() => setDestino("fatura")}>
                        Editar dados
                      </Botao>
                      <Botao variante="danger" onClick={() => setModalLimpar(true)}>
                        Limpar dados
                      </Botao>
                    </div>
                  )}
                </div>

                {estado === "editando" && (
                  <section className="content-card standalone-state">
                    <h2>Nenhuma conferência ainda</h2>
                    <Faisca estado="idle" mensagem="Confirme os dados da fatura para começar." />
                    <Botao onClick={() => setDestino("fatura")}>Confirmar dados</Botao>
                  </section>
                )}

                {estado === "conferindo" && (
                  <section className="content-card standalone-state" aria-busy="true">
                    <h2>Conferindo</h2>
                    <Faisca estado="thinking" mensagem="Conferindo os dados." />
                  </section>
                )}

                {estado === "erro" && (
                  <section className="content-card standalone-state" role="alert">
                    <h2>Falha na conferência</h2>
                    <Faisca
                      estado="alert"
                      mensagem="Não consegui conferir agora. Revise os campos e tente de novo."
                    />
                    <div className="heading-actions">
                      <Botao onClick={() => void conferir()} disabled={!online}>
                        Tentar novamente
                      </Botao>
                      <Botao variante="secondary" onClick={() => setDestino("fatura")}>
                        Revisar campos
                      </Botao>
                    </div>
                  </section>
                )}

                {estado === "pronto" && (
                  <>
                    {aviso && (
                      <p className="api-notice" role="status">
                        {aviso}
                      </p>
                    )}
                    <section className="content-card search-controls" aria-labelledby="busca-titulo">
                      <h2 id="busca-titulo">Encontre uma checagem</h2>
                      <div className="search-field">
                        <label htmlFor="busca">Buscar nas checagens</label>
                        <input
                          ref={buscaRef}
                          id="busca"
                          className="input"
                          type="search"
                          value={busca}
                          onChange={(e) => setBusca(e.target.value)}
                          aria-describedby="busca-ajuda contagem"
                        />
                        <span className="field-hint" id="busca-ajuda">
                          Digite para filtrar. Pressione / para focar este campo.
                        </span>
                      </div>
                      <div className="filter-row" role="group" aria-label="Filtrar checagens">
                        {FILTROS.map(({ id, rotulo }) => (
                          <button
                            key={id}
                            type="button"
                            className="filter-chip"
                            aria-pressed={filtro === id}
                            onClick={() => setFiltro(id)}
                          >
                            {rotulo}
                          </button>
                        ))}
                      </div>
                      <div className="search-actions">
                        <Botao
                          variante="secondary"
                          onClick={() => {
                            setBusca("");
                            setFiltro("todos");
                          }}
                        >
                          Limpar filtros
                        </Botao>
                        <div className="view-toggle" role="group" aria-label="Modo de visualização">
                          {(["compacta", "detalhada"] as Visao[]).map((v) => (
                            <button
                              key={v}
                              type="button"
                              aria-pressed={visao === v}
                              onClick={() => setVisao(v)}
                            >
                              Visão {v}
                            </button>
                          ))}
                        </div>
                      </div>
                      <p id="contagem" className="results-count" aria-live="polite">
                        {visiveis.length}{" "}
                        {visiveis.length === 1 ? "checagem encontrada" : "checagens encontradas"}.
                      </p>
                    </section>

                    <section className="decisions-section" aria-labelledby="decisoes-titulo">
                      <h2 id="decisoes-titulo">Cartões de decisão</h2>
                      <p className="level-legend">
                        <strong>Legenda:</strong> A é conta com os dados da fatura; B compara com a
                        tabela ANEEL; C é indício que vira pedido de esclarecimento.
                      </p>
                      <div className={`decision-list decision-list--${visao}`}>
                        {visiveis.map((d) => (
                          <CartaoDecisao
                            key={d.chave}
                            decisao={d}
                            revisado={revisados.includes(d.chave)}
                            aoPedir={() => {
                              setGuiaAberto(false);
                              setCopiado("");
                              setPedido(d);
                            }}
                            aoRevisar={() => {
                              setRevisados((atual) => [...atual, d.chave]);
                              setToast(d.chave);
                            }}
                          />
                        ))}
                        {visiveis.length === 0 && (
                          <div className="empty-search-result">
                            <h3>Filtro sem resultado</h3>
                            <Faisca
                              estado="thinking"
                              mensagem="Não encontrei checagens com estes filtros."
                            />
                            <Botao
                              variante="secondary"
                              onClick={() => {
                                setBusca("");
                                setFiltro("todos");
                              }}
                            >
                              Limpar filtros
                            </Botao>
                          </div>
                        )}
                      </div>
                    </section>
                  </>
                )}
              </>
            )}

            {destino === "historico" && (
              <>
                <div className="page-heading">
                  <h1>Histórico</h1>
                  <p>Comparação entre meses.</p>
                </div>
                <section className="content-card">
                  <h2>Nada fica guardado</h2>
                  <p className="card-text">
                    O Fatura Aberta não guarda faturas: os dados ficam só nesta tela e somem ao
                    limpar ou fechar. Por isso ainda não há histórico.
                  </p>
                </section>
              </>
            )}

            {destino === "ajuda" && (
              <>
                <div className="page-heading">
                  <h1>Ajuda</h1>
                  <p>Como a ferramenta funciona e até onde ela vai.</p>
                </div>
                <section className="content-card">
                  <Guia />
                </section>
                <section className="content-card">
                  <h2>Limites da análise</h2>
                  <p className="card-text">
                    A ferramenta é acadêmica e informativa. Ela não dá parecer jurídico nem estima
                    valores a receber. Quando não consegue concluir, diz isso e sugere um pedido de
                    esclarecimento à distribuidora.
                  </p>
                </section>
              </>
            )}
          </div>

          <aside className="summary-column" aria-label="Resumo e dicas">
            <section className="mascot-card" aria-labelledby="dica-titulo">
              <h2 id="dica-titulo">Dica do Faísca</h2>
              <Faisca estado={mascote[destino].estado} mensagem={mascote[destino].mensagem} />
            </section>
          </aside>
        </div>
      </main>

      <footer className="site-footer">
        <p>
          Ferramenta acadêmica e informativa de apoio à leitura da conta de luz. Não substitui a
          distribuidora, a ANEEL, o Procon-DF nem a Defensoria Pública. Use apenas dados fictícios.
        </p>
      </footer>

      <Gaveta aberta={guiaAberto} titulo="Guia do Faísca" aoFechar={fecharGuia}>
        <Guia />
      </Gaveta>

      <Gaveta aberta={pedido !== null} titulo="Pedido de esclarecimento" aoFechar={fecharPedido} lateral>
        {pedido && (
          <>
            <Faisca estado="guiding" mensagem="Use os dados da fatura no pedido." />
            <p className="clarification-intro">Texto baseado só no que a fatura informa:</p>
            <blockquote className="clarification-copy">
              {textoPedido(pedido, dados.mesReferencia)}
            </blockquote>
            <Botao
              onClick={() => {
                const texto = textoPedido(pedido, dados.mesReferencia);
                if (!navigator.clipboard) {
                  setCopiado("Selecione o texto para copiar.");
                  return;
                }
                navigator.clipboard
                  .writeText(texto)
                  .then(() => setCopiado("Texto copiado."))
                  .catch(() => setCopiado("Selecione o texto para copiar."));
              }}
            >
              Copiar texto
            </Botao>
            <p className="copy-feedback" role="status">
              {copiado}
            </p>
          </>
        )}
      </Gaveta>

      <Modal
        aberto={modalLimpar}
        titulo="Limpar os dados desta conferência?"
        aoFechar={fecharModal}
        acoes={
          <>
            <Botao variante="secondary" data-foco-inicial onClick={fecharModal}>
              Cancelar
            </Botao>
            <Botao variante="danger" onClick={limpar}>
              Limpar
            </Botao>
          </>
        }
      >
        <p>Isso apaga os valores digitados e o resultado. Não dá para recuperar.</p>
      </Modal>

      {toast && (
        <div className="review-toast" role="status">
          <span>Item marcado como revisado.</span>
          <Botao
            variante="secondary"
            onClick={() => {
              setRevisados((atual) => atual.filter((c) => c !== toast));
              setToast(null);
            }}
          >
            Desfazer
          </Botao>
        </div>
      )}

      {mostrarOnboarding && <Onboarding aoConcluir={concluirOnboarding} />}
    </div>
  );
}
