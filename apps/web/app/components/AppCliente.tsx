"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";

// O app usa localStorage, navigator e matchMedia: renderiza só no navegador.
const FaturaAberta = dynamic(() => import("./FaturaAberta"), {
  ssr: false,
  loading: () => <p className="carregando">Carregando o Fatura Aberta…</p>,
});

export default function AppCliente() {
  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      void navigator.serviceWorker.register("/sw.js");
    }
  }, []);
  return <FaturaAberta />;
}
