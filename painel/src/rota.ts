import { useEffect, useState } from "react";

// rotas por hash: #/ · #/criativos · #/nova · #/ajustes · #/c/1.5
export type Rota = { tela: "painel" | "criativos" | "nova" | "ajustes"; criativo?: string };

function ler(): Rota {
  const h = location.hash.replace(/^#\/?/, "");
  if (h.startsWith("c/")) return { tela: "criativos", criativo: decodeURIComponent(h.slice(2)) };
  if (h.startsWith("criativos")) return { tela: "criativos" };
  if (h.startsWith("nova")) return { tela: "nova" };
  if (h.startsWith("ajustes")) return { tela: "ajustes" };
  return { tela: "painel" };
}

export function useRota(): Rota {
  const [r, setR] = useState(ler());
  useEffect(() => {
    const f = () => setR(ler());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return r;
}

export const link = {
  painel: "#/", criativos: "#/criativos", nova: "#/nova", ajustes: "#/ajustes",
  criativo: (id: string) => `#/c/${encodeURIComponent(id)}`,
};
