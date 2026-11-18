import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import type { Nivel } from "../lib/api";

type Variante = "primary" | "secondary" | "danger";

type BotaoProps = ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante };

export const Botao = forwardRef<HTMLButtonElement, BotaoProps>(function Botao(
  { variante = "primary", className = "", type = "button", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`button button--${variante} ${className}`.trim()}
      {...props}
    />
  );
});

const DESCRICAO_NIVEL: Record<Nivel, string> = {
  A: "conta feita com os dados da própria fatura",
  B: "comparação com a tabela oficial da ANEEL",
  C: "situação que os dados da fatura não permitem confirmar, com apoio informativo",
};

export function SeloNivel({ nivel }: { nivel: Nivel }) {
  return (
    <span className={`level-badge level-badge--${nivel.toLowerCase()}`}>
      Nível {nivel}
      <span className="sr-only">: {DESCRICAO_NIVEL[nivel]}</span>
    </span>
  );
}
