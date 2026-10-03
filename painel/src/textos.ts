import type { Etapa } from "./api";

export type Tom = "ok" | "run" | "fila" | "voce" | "no";
export const ETAPA: Record<Etapa, { texto: string; tom: Tom }> = {
  pendente: { texto: "Pendente", tom: "fila" },
  fila: { texto: "Na fila", tom: "fila" },
  narrando: { texto: "Narrando", tom: "run" },
  renderizando: { texto: "Editando", tom: "run" },
  entregue: { texto: "Entregue", tom: "ok" },
  aviso: { texto: "Conferir", tom: "voce" },
  erro: { texto: "Erro", tom: "no" },
  parado: { texto: "Parado", tom: "fila" },
};

export const PERFIL: Record<string, string> = {
  fe_emocional: "Fé e emoção", familia_doce: "Família, doce", brincar_alegre: "Brincar, alegre",
  legado_nostalgia: "Legado, nostalgia", oferta_energia: "Oferta, energia",
};

export const TRANSICAO: Record<string, string> = {
  iris: "Íris", pop_elastico: "Pop elástico", boing: "Boing", balanco: "Balanço", giro_cartoon: "Giro cartoon",
  chicote_h: "Chicote", chicote_v: "Chicote vertical", zoom_punch: "Zoom punch", zoom_suave: "Zoom suave",
  giro: "Giro", flash: "Flash", impacto: "Impacto", desfoque: "Desfoque", deslize: "Deslize", cortina: "Cortina",
  revelar: "Revelar", circulo: "Círculo", radial: "Radial", dissolve: "Dissolver", abre: "Abre", aperto: "Aperto", luz: "Light leak",
};

export const numero = (n: number) => n.toLocaleString("pt-BR");
export const seg = (s: number | null | undefined) => (s == null ? "—" : `${Math.round(s)}s`);
export const nomeBonito = (slug: string) => slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
