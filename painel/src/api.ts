// A ponte com o servidor local (editor/servidor.py). Toda rota /api pede a senha da sessao.

export type Etapa = "pendente" | "fila" | "narrando" | "renderizando" | "entregue" | "aviso" | "erro" | "parado";

export interface Linha { hora: string; texto: string }

export interface Estado {
  campanha: string | null;
  campanhas: { nome: string; produto: string; criativos: number; prontos: number }[];
  rodando: boolean;
  produzindo: string | null;
  parando: boolean;
  etapas: Record<string, Etapa>;
  registro: Linha[];
  minimax: boolean;
  transicoes: string[];
  cartoon: string[];
}

export interface Criativo {
  id: string; publico_n: number; publico: string; angulo: string; alvo_s: number; preco: boolean; copy: string;
  etapa: Etapa; entregue: string | null; duracao: number | null; avisos: string[];
  musica: string | null; voz: number | null; sfx: number; modelo: string | null; transicoes: string[];
  perfil_musica: string; pasta: string | null;
}

export interface Campanha {
  nome: string; produto: string; pasta: string; base: string | null; base_ok: boolean; regra: string[];
  criativos: Criativo[]; ajustes: Record<string, any>; entregues_dir: string; publicar?: { repo: string; pasta: string } | null;
  efetivo: { voz: string; velocidade: number; modelo: string; musica: string; sfx: boolean; legenda_estilo: number;
             transicoes: { proporcao?: number; pesos?: Record<string, number> } };
}

export interface Base { pasta: boolean; clipes: number; duracao: number; arquivos: { nome: string; caminho: string; duracao: number }[] }

// ⭐ a senha e' relida a CADA chamada: se o servidor reiniciar e a janela receber /#t=<nova>, ela vale na hora
// (antes ficava presa na memoria e toda chamada voltava 401)
function senha(): string {
  const m = location.hash.match(/[#&]t=([^&]+)/);
  if (m) { sessionStorage.setItem("edt_t", decodeURIComponent(m[1])); history.replaceState(null, "", "#/"); }
  return sessionStorage.getItem("edt_t") ?? "";
}
senha();

async function chamar<R>(metodo: "GET" | "POST", rota: string, corpo?: unknown): Promise<R> {
  const r = await fetch(rota, {
    method: metodo,
    headers: { "X-EDT-Token": senha(), ...(corpo !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
  });
  const dado = await r.json().catch(() => ({}));
  if (r.status === 401) throw new Error("A sessão do painel expirou. Feche esta janela e abra de novo (python edt.py painel).");
  if (!r.ok) throw new Error((dado as any).detail || (dado as any).erro || `erro ${r.status}`);
  return dado as R;
}

export const ler = <R,>(rota: string) => chamar<R>("GET", rota);
export const enviar = <R = { ok: boolean },>(rota: string, corpo: unknown = {}) => chamar<R>("POST", rota, corpo);

export const midia = (caminho: string) => `/api/midia?caminho=${encodeURIComponent(caminho)}&k=${encodeURIComponent(senha())}`;
export const miniatura = (caminho: string, w = 360, t?: number) =>
  `/api/miniatura?caminho=${encodeURIComponent(caminho)}&w=${w}${t !== undefined ? `&t=${t}` : ""}&k=${encodeURIComponent(senha())}`;
export const temSenha = () => !!senha();
