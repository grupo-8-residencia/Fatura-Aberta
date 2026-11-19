import AppCliente from "./components/AppCliente";

export default function Home() {
  return (
    <>
      <noscript>
        <p>O Fatura Aberta precisa de JavaScript ativado para conferir a fatura.</p>
      </noscript>
      <AppCliente />
    </>
  );
}
