import { ImageResponse } from "next/og";

// Ícones do PWA gerados no build a partir do desenho de app/icon.svg. Assim nenhum PNG entra no
// Git: a barreira de privacidade (scripts/bloquear_binarios.py) só aceita imagens em pastas de
// dados sintéticos e documentação.
const TAMANHOS = [192, 512] as const;

export const dynamic = "force-static";

export function generateStaticParams() {
  return TAMANHOS.map((t) => ({ tamanho: `${t}.png` }));
}

export async function GET(_: Request, { params }: { params: Promise<{ tamanho: string }> }) {
  const { tamanho } = await params;
  const lado = Number.parseInt(tamanho, 10);
  if (!TAMANHOS.includes(lado as (typeof TAMANHOS)[number])) {
    return new Response("Tamanho não disponível", { status: 404 });
  }
  const u = lado / 512;
  const circulo = (diametro: number, cor: string) => ({
    position: "absolute" as const,
    left: (344 - diametro / 2) * u,
    top: (352 - diametro / 2) * u,
    width: diametro * u,
    height: diametro * u,
    borderRadius: "50%",
    background: cor,
  });
  return new ImageResponse(
    (
      <div style={{ position: "relative", display: "flex", width: lado, height: lado, background: "#0B5D4B" }}>
        <div
          style={{
            position: "absolute",
            left: 152 * u,
            top: 96 * u,
            width: 208 * u,
            height: 320 * u,
            background: "#FFFFFF",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 200 * u,
            top: 216 * u,
            width: 112 * u,
            height: 24 * u,
            borderRadius: 12 * u,
            background: "#0B5D4B",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 200 * u,
            top: 272 * u,
            width: 112 * u,
            height: 24 * u,
            borderRadius: 12 * u,
            background: "#0B5D4B",
          }}
        />
        <div style={circulo(144, "#F59E0B")} />
        <div style={circulo(88, "#FEF3C7")} />
        <div style={circulo(36, "#FFFFFF")} />
      </div>
    ),
    { width: lado, height: lado },
  );
}
