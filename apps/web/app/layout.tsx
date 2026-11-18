import type { Metadata, Viewport } from "next";
import { Atkinson_Hyperlegible } from "next/font/google";
import "./globals.css";

// next/font baixa a fonte no build e a serve do próprio app: o navegador não chama o Google.
const atkinson = Atkinson_Hyperlegible({
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
  variable: "--fonte-base",
});

export const metadata: Metadata = {
  title: "Fatura Aberta",
  description: "Verificador aberto e auditável de faturas de energia (B1) da Neoenergia Brasília.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#0B5D4B",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={atkinson.variable}>
      <body>{children}</body>
    </html>
  );
}
