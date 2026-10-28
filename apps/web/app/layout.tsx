export const metadata = {
  title: "Fatura Aberta",
  description: "Verificador aberto e auditável de faturas de energia (B1) da Neoenergia Brasília.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
