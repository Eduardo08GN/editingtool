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
  musica: string | null; voz: number | null; sfx: number; modelo: string | null; motor: string | null; zona_segura: string[]; bpm: number | null; motion: string[];
  entrega: { falhas: string[]; avisos: string[]; lufs: number | null; pico: number | null; folha: string | null } | null; turbo: boolean; transicoes: string[];
  perfil_musica: string; pasta: string | null;
}

export interface Campanha {
  nome: string; produto: string; pasta: string; base: string | null; base_ok: boolean; regra: string[];
  turbo_recursos: { id: string; nome: string; ativo: boolean; nota: string }[];
  criativos: Criativo[]; ajustes: Record<string, any>; entregues_dir: string; publicar?: { repo: string; pasta: string; auto?: boolean; herdado?: string } | null;
  efetivo: { turbo: boolean; voz: string; velocidade: number; modelo: string; motor: string; motion_graphics: { gancho?: boolean; fecho?: boolean }; emojis?: boolean; selos?: boolean; camera_lenta?: boolean; musica: string; sfx: boolean; legenda_estilo: number;
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

// ── Mineracao de ofertas (editor/mineracao.py) ──────────────────────────────
export type FaseMineracao = "coleta" | "grupos" | "medicao" | "landing" | "ofertas" | "pronta";

export interface RodadaMineracao {
  id: string; criada: string; mercados: string[]; max_por_termo: number; finalistas: number;
  fase: FaseMineracao; status: "rodando" | "pronta" | "parada" | "erro"; erro?: string | null; ofertas?: number; nota?: string;
  nome?: string; tipo?: "planilha"; n_termos?: number | null;
  compartilhada?: boolean;   // veio do time pelo GitHub (compartilhado/mineracao): so' leitura
  publicada?: boolean;       // este PC ja' mandou esta rodada para o time
}

// [termo, traducao em portugues, camada]
export interface BancoTermos {
  mercados: Record<string, { nome: string; paises: string[]; idioma: string }>;
  termos: Record<string, [string, string, string][]>;
}

export interface EstadoMineracao {
  token: boolean; rodando: boolean; rodada: string | null; fase: FaseMineracao | null; parando: boolean;
  progresso: { feitos: number; total: number }; registro: Linha[]; rodadas: RodadaMineracao[];
  mercados: Record<string, { nome: string; paises: string[]; idioma: string; termos: number }>;
}

export interface Decisao { status?: "aprovada" | "descartada"; nota?: number; obs?: string; nicho?: string; quando?: string }

export interface Oferta {
  chave: string; oferta: string; titulo_landing: string; anunciante: string;
  biblioteca: string; bibliotecas: { nome: string; url: string }[]; landing: string | null; landing_erro?: string | null;
  origem: string[]; variacoes: { termo: string; mercado: string }[];
  alcance_ue: number; alcance_15d: number; anuncios: number; anuncios_15d: number; max_dias: number; rodando_desde: string;
  paises_pct: Record<string, number>; idiomas: Record<string, number>; presenca: Record<string, number>; buraco: string[];
  precos: string[]; preco_min: number | null; digital: number; bandeiras: string[]; textos: string[]; titulos: string[];
  nota: number; decisao: Decisao; fontes?: string[];
  // vindos da planilha de garimpo do time (quando a oferta foi importada de la')
  nicho?: string; formato?: string; observacao?: string; nota_planilha?: number | null;
  concorrentes?: { nome: string; url?: string; obs?: string }[]; n_concorrentes?: number | null;
  anuncios_fr?: number | null; anuncios_fr_15d?: number | null; esforco?: string; aceitacao?: string; adaptacao?: string; paises_alvo?: string;
}

// ⭐ biblioteca/landing abrem no navegador PADRAO do operador (logado), nao na janela da ferramenta
export const abrirLink = (url: string) => enviar("/api/abrir-link", { url });
