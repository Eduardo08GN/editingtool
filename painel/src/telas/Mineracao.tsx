import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, Check, ChevronDown, ExternalLink, FileUp, Pickaxe, Play, Plus, RotateCcw, Search, Square, ThumbsDown, ThumbsUp, Trash2, X } from "lucide-react";
import { abrirLink, enviar, ler, type BancoTermos, type Decisao, type EstadoMineracao, type FaseMineracao, type Oferta, type RodadaMineracao } from "../api";
import type { Ctx } from "../App";
import { Girando, useAcao } from "../componentes/base";
import { numero } from "../textos";

// ── textos ────────────────────────────────────────────────────────────────────
const FASES: { id: FaseMineracao; texto: string; dica: string }[] = [
  { id: "coleta", texto: "Coleta", dica: "busca cada termo na Biblioteca de Anúncios" },
  { id: "grupos", texto: "Grupos", dica: "junta os anúncios por landing e tira físico e nicho proibido" },
  { id: "medicao", texto: "Medição", dica: "mede a página inteira: alcance real na UE e países" },
  { id: "landing", texto: "Landing", dica: "abre a landing só para ler preço e formato" },
  { id: "ofertas", texto: "Ranking", dica: "dá a nota e marca o buraco em francês/alemão" },
];

const CAMADA: Record<string, string> = {
  prova: "Prova de escala", funil: "Funil (quiz, VSL, advertorial)", entrega: "Entrega digital", fabrica: "Copy de fábrica",
  preco: "Preço e oferta", mecanismo: "Mecanismo único", gancho: "Gancho de curiosidade", publico: "Chamada de público",
  sazonal: "Sazonal", nicho: "Nicho", extra: "Seus termos",
};
const ORDEM_CAMADA = ["extra", "prova", "funil", "mecanismo", "gancho", "entrega", "fabrica", "preco", "publico", "sazonal", "nicho"];

const PAIS: Record<string, string> = {
  FR: "França", DE: "Alemanha", AT: "Áustria", BE: "Bélgica", LU: "Luxemburgo", PT: "Portugal", ES: "Espanha",
  IT: "Itália", NL: "Holanda", PL: "Polônia", GR: "Grécia", IE: "Irlanda", GB: "R. Unido", SE: "Suécia", DK: "Dinamarca",
  FI: "Finlândia", CZ: "Tchéquia", RO: "Romênia", HU: "Hungria", SK: "Eslováquia", SI: "Eslovênia", HR: "Croácia",
  BG: "Bulgária", RE: "Reunião", GP: "Guadalupe", MQ: "Martinica", GF: "Guiana Fr.",
};
const IDIOMA_MERCADO: Record<string, string> = { FR: "Francês", DE: "Alemão", PT: "Portugal" };

const BANDEIRA: Record<string, { texto: string; tom: "ok" | "voce" | "no" | "run" | "neutra"; dica: string }> = {
  escalando: { texto: "Escalando", tom: "run", dica: "mais de 40% do alcance veio de anúncios com menos de 15 dias" },
  novo: { texto: "Novo", tom: "voce", dica: "nenhum anúncio com 15+ dias: escala rápida, ainda não validada" },
  operador_br: { texto: "Operador BR", tom: "neutra", dica: "a landing mostra preço em R$" },
  isca: { texto: "Isca grátis", tom: "no", dica: "o anúncio oferece algo gratuito (captação de lead)" },
  assinatura: { texto: "Assinatura/app", tom: "no", dica: "parece assinatura, app ou software" },
  fisico: { texto: "Físico?", tom: "no", dica: "a landing fala em frete/envio ou o produto é um objeto" },
  ticket_alto: { texto: "Ticket alto", tom: "voce", dica: "o preço que mais aparece na landing passa de 60" },
  formacao: { texto: "Curso/carreira", tom: "voce", dica: "formação profissional, certificação, mentoria ou recrutamento: difícil de virar low ticket" },
};

const TODAS = "_todas";
const pessoas = (n: number) =>
  !n ? "—" : n >= 1_000_000 ? `${(n / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`
  : n >= 1000 ? `${Math.round(n / 1000).toLocaleString("pt-BR")} mil` : numero(n);
const data = (iso: string) => { const [a, m, d] = iso.slice(0, 10).split("-"); return `${d}/${m}/${a.slice(2)}`; };
const quando = (iso: string) => { try { return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); } catch { return iso; } };
const nomeRodada = (r: RodadaMineracao) => r.nome || `Rodada de ${quando(r.criada)}`;
const busca = (termo: string, mercado: string) =>
  `https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=${mercado}&q=${encodeURIComponent(`"${termo}"`)}&search_type=keyword_exact_phrase&media_type=all`;

function guardado<T>(k: string, padrao: T): T {
  try { const v = localStorage.getItem(k); return v ? (JSON.parse(v) as T) : padrao; } catch { return padrao; }
}
function guardar(k: string, v: unknown) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sem storage: so' nao lembra */ } }

// ── pecas ─────────────────────────────────────────────────────────────────────
function LinkExterno({ url, texto, variante = "ghost", avisar }: { url: string; texto: string; variante?: "ghost" | "abrir"; avisar: Ctx["avisar"] }) {
  return (
    <a href={url} target="_blank" rel="noreferrer noopener" className={`btn btn-sm ${variante === "abrir" ? "btn-abrir" : "btn-ghost"}`}
       onClick={(e) => { e.preventDefault(); e.stopPropagation(); abrirLink(url).catch((x) => { window.open(url, "_blank", "noopener"); avisar((x as Error).message, "erro"); }); }}>
      {texto}<ExternalLink size={13} aria-hidden />
    </a>
  );
}

// ⭐ janela de confirmacao: Esc fecha, o foco comeca no botao seguro (Cancelar)
function Modal({ titulo, fechar, children, acoes, perigo }: { titulo: string; fechar: () => void; children: ReactNode; acoes: ReactNode; perigo?: boolean }) {
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") fechar(); };
    window.addEventListener("keydown", tecla);
    caixa.current?.querySelector<HTMLElement>("[data-foco]")?.focus();
    return () => window.removeEventListener("keydown", tecla);
  }, [fechar]);
  return (
    <div className="modal-fundo" onMouseDown={(e) => { if (e.target === e.currentTarget) fechar(); }}>
      <div className={`panel modal${perigo ? " modal-perigo" : ""}`} role="dialog" aria-modal="true" aria-labelledby="modal-titulo" ref={caixa}>
        <div className="modal-topo">
          {perigo && <span className="ico-perigo" aria-hidden><Trash2 size={18} /></span>}
          <h2 id="modal-titulo">{titulo}</h2>
          <button type="button" className="btn btn-quiet btn-icon-sm" onClick={fechar} aria-label="Fechar"><X size={16} /></button>
        </div>
        <div className="modal-corpo">{children}</div>
        <div className="modal-acoes">{acoes}</div>
      </div>
    </div>
  );
}

// ── estado do servidor ────────────────────────────────────────────────────────
function useMineracao(avisar: Ctx["avisar"]) {
  const [est, setEst] = useState<EstadoMineracao | null>(null);
  const vivo = useRef(true);
  const puxar = useCallback(async () => {
    try { const e = await ler<EstadoMineracao>("/api/mineracao"); if (vivo.current) setEst(e); }
    catch (x) { if (vivo.current) avisar((x as Error).message, "erro"); }
  }, [avisar]);
  useEffect(() => {
    vivo.current = true; puxar();
    const t = window.setInterval(puxar, est?.rodando ? 2000 : 10000);
    return () => { vivo.current = false; window.clearInterval(t); };
  }, [puxar, est?.rodando]);
  return { est, puxar };
}

// ── andamento ─────────────────────────────────────────────────────────────────
function Andamento({ est, rodada, ctx, puxar }: { est: EstadoMineracao; rodada: RodadaMineracao | null; ctx: Ctx; puxar: () => void }) {
  const { rodando, rodar } = useAcao(ctx.avisar);
  const ligado = est.rodando;
  const fase = ligado ? est.fase : rodada?.fase ?? null;
  const idx = FASES.findIndex((f) => f.id === fase);
  const { feitos, total } = est.progresso;
  const pct = total ? Math.round((feitos / total) * 100) : 0;
  const parada = !ligado && rodada && (rodada.status === "parada" || rodada.status === "erro");
  const titulo = ligado ? (est.parando ? "Parando a mineração" : `Minerando · ${FASES[idx]?.texto ?? "…"}`) :
                 parada ? (rodada!.status === "erro" ? "A mineração parou com erro" : "Mineração parada no meio") :
                 rodada ? "Mineração pronta" : "Nenhuma mineração ainda";
  const sub = ligado ? (FASES[idx]?.dica ?? "") + (total ? ` · ${numero(feitos)} de ${numero(total)}` : "") :
              parada ? (rodada!.erro || "Retome: o que já foi coletado não se repete.") :
              rodada ? `${nomeRodada(rodada)} · ${rodada.mercados.join(", ")} · ${numero(rodada.ofertas ?? 0)} ofertas ranqueadas` :
              "Escolha os termos e os mercados e comece.";
  return (
    <section className={`panel pilot${ligado ? "" : " is-off"}`} aria-label="Andamento da mineração">
      <div className="pilot-l">
        <div className="pilot-state">
          <span className="live" aria-hidden />
          <div><h2>{titulo}</h2><p>{sub}</p></div>
          <div className="pilot-acoes">
            {ligado && (
              <button className="btn btn-stop" type="button" disabled={est.parando || !!rodando}
                      onClick={() => rodar("parar", async () => { await enviar("/api/mineracao/parar"); puxar(); })}>
                <Square size={14} aria-hidden />Parar
              </button>
            )}
            {parada && rodada!.tipo !== "planilha" && (
              <button className="btn btn-primary" type="button" disabled={!!rodando}
                      onClick={() => rodar("retomar", async () => { await enviar("/api/mineracao/retomar", { rodada: rodada!.id }); puxar(); }, "Retomando a mineração.")}>
                {rodando === "retomar" ? <Girando /> : <RotateCcw size={16} aria-hidden />}Retomar
              </button>
            )}
          </div>
        </div>
        <ol className="fases" aria-label="Etapas">
          {FASES.map((f, i) => {
            const feito = fase === "pronta" || idx > i;
            const agora = ligado && idx === i;
            return (
              <li key={f.id} className={feito ? "feito" : agora ? "agora" : ""} title={f.dica}>
                <span className="bola" aria-hidden>{feito ? <Check size={12} strokeWidth={3} /> : agora ? <Girando /> : i + 1}</span>{f.texto}
              </li>
            );
          })}
        </ol>
        {ligado && total > 0 && (
          <div><div className="linha-meta"><span className="label">{FASES[idx]?.texto}</span><span className="meta">{pct}%</span></div>
            <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${pct}%` }} /></div></div>
        )}
      </div>
      <div className="pilot-r">
        <span className="label">Agora há pouco</span>
        {est.registro.length ? (
          <ul className="feed">
            {est.registro.slice(0, 8).map((l, i) => (
              <li key={i}><time>{l.hora}</time>
                {/⚠|erro/i.test(l.texto) ? <AlertTriangle size={14} className="warn" aria-hidden /> : <Check size={14} className="ok" aria-hidden />}
                <span>{l.texto}</span></li>
            ))}
          </ul>
        ) : <p className="meta" style={{ marginTop: 12 }}>Nada aconteceu desde que o painel abriu.</p>}
      </div>
    </section>
  );
}

// ── nova mineracao: escolher os termos ────────────────────────────────────────
function NovaMineracao({ est, ctx, fechar, puxar }: { est: EstadoMineracao; ctx: Ctx; fechar: () => void; puxar: () => void }) {
  const { rodando, rodar } = useAcao(ctx.avisar);
  const [banco, setBanco] = useState<BancoTermos | null>(null);
  const [off, setOff] = useState<Record<string, string[]>>(() => guardado("edt_termos_off", {}));
  const [mercados, setMercados] = useState<string[]>(() => guardado("edt_mercados", Object.keys(est.mercados)));
  const [aba, setAba] = useState(Object.keys(est.mercados)[0] ?? "FR");
  const [texto, setTexto] = useState("");
  const [maximo, setMaximo] = useState(1000);
  const [finalistas, setFinalistas] = useState(40);

  const carregar = useCallback(() => {
    ler<BancoTermos>("/api/mineracao/termos").then(setBanco).catch((x) => ctx.avisar((x as Error).message, "erro"));
  }, [ctx]);
  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { guardar("edt_termos_off", off); }, [off]);
  useEffect(() => { guardar("edt_mercados", mercados); }, [mercados]);

  const desligados = (m: string) => new Set(off[m] ?? []);
  const marcados = (m: string) => (banco?.termos[m] ?? []).filter(([t]) => !desligados(m).has(t)).map(([t]) => t);
  const alternar = (m: string, t: string) => setOff((o) => {
    const s = new Set(o[m] ?? []); if (s.has(t)) s.delete(t); else s.add(t); return { ...o, [m]: [...s] };
  });
  const camadaToda = (m: string, termos: string[], ligar: boolean) => setOff((o) => {
    const s = new Set(o[m] ?? []); termos.forEach((t) => (ligar ? s.delete(t) : s.add(t))); return { ...o, [m]: [...s] };
  });
  const incluirMercado = (m: string) => setMercados((xs) => xs.includes(m) ? xs.filter((x) => x !== m) : [...xs, m]);

  const porMercado = mercados.map((m) => marcados(m).length);
  const totalTermos = porMercado.reduce((a, b) => a + b, 0);
  const minutos = Math.max(3, Math.round(Math.max(0, ...porMercado) * 0.7));

  const grupos = useMemo(() => {
    const g = new Map<string, [string, string, string][]>();
    (banco?.termos[aba] ?? []).forEach((t) => g.set(t[2] || "extra", [...(g.get(t[2] || "extra") ?? []), t]));
    return [...g.entries()].sort((a, b) => ORDEM_CAMADA.indexOf(a[0]) - ORDEM_CAMADA.indexOf(b[0]));
  }, [banco, aba]);

  const adicionar = () => rodar("adicionar", async () => {
    const termos = texto.split(/\n|;/).map((t) => t.trim()).filter(Boolean);
    if (!termos.length) throw new Error("Escreva pelo menos um termo.");
    const r = await enviar<{ novos: string[] }>("/api/mineracao/termos/extras", { mercado: aba, termos });
    setOff((o) => ({ ...o, [aba]: (o[aba] ?? []).filter((t) => !termos.includes(t)) }));
    if (!mercados.includes(aba)) setMercados((xs) => [...xs, aba]);
    setTexto(""); carregar();
    ctx.avisar(r.novos.length ? `${r.novos.length} termo(s) adicionado(s) em ${est.mercados[aba]?.nome}.` : "Esses termos já estavam no banco.");
  });

  return (
    <section className="panel bloco nova-mineracao" aria-label="Nova mineração">
      <div className="linha-titulo">
        <h3>Nova mineração</h3>
        <span className="meta">{numero(totalTermos)} termos marcados · {mercados.length} mercado(s) · uns {minutos} min (mercados em paralelo)</span>
      </div>
      {!est.token && (
        <div className="aviso-lista" role="alert">Falta o <code>META_TOKEN</code> no <code>.env</code> da ferramenta (token da Biblioteca de Anúncios da Meta).</div>
      )}

      <div className="campo-grupo">
        <span className="label">Mercados que entram nesta mineração</span>
        <div className="filtros">
          {Object.entries(est.mercados).map(([k, m]) => (
            <button key={k} type="button" className="filtro" aria-pressed={mercados.includes(k)} onClick={() => incluirMercado(k)}>
              {mercados.includes(k) ? <Check size={13} aria-hidden /> : null}{k} · {m.nome}<span>{marcados(k).length}/{banco?.termos[k]?.length ?? m.termos} termos</span>
            </button>
          ))}
        </div>
        <p className="meta">Portugal é a vitrine dos operadores brasileiros dentro da UE: a API mostra o alcance real deles.</p>
      </div>

      <div className="campo-grupo">
        <div className="linha-titulo" style={{ marginBottom: 0 }}>
          <span className="label">Palavras-chave · clique para ligar ou desligar</span>
          <div className="seg" role="tablist" aria-label="Mercado dos termos">
            {Object.entries(est.mercados).map(([k, m]) => (
              <button key={k} type="button" role="tab" aria-selected={aba === k} aria-pressed={aba === k} onClick={() => setAba(k)}>{m.nome}</button>
            ))}
          </div>
        </div>
        {!mercados.includes(aba) && <p className="meta">Este mercado está fora da mineração: ligue-o acima para os termos dele entrarem.</p>}
        {!banco ? <p className="meta"><Girando /> Carregando os termos…</p> : (
          <div className="camadas">
            {grupos.map(([camada, termos]) => {
              const lig = termos.filter(([t]) => !desligados(aba).has(t)).length;
              return (
                <div key={camada} className="camada">
                  <div className="camada-topo">
                    <strong>{CAMADA[camada] ?? camada}</strong>
                    <span className="meta">{lig}/{termos.length}</span>
                    <button type="button" className="btn btn-quiet btn-sm" onClick={() => camadaToda(aba, termos.map((t) => t[0]), true)}>todos</button>
                    <button type="button" className="btn btn-quiet btn-sm" onClick={() => camadaToda(aba, termos.map((t) => t[0]), false)}>nenhum</button>
                  </div>
                  <div className="termos">
                    {termos.map(([t, pt]) => {
                      const ligado = !desligados(aba).has(t);
                      return (
                        <span key={t} className={`chip-termo${ligado ? " on" : ""}`}>
                          <button type="button" aria-pressed={ligado} onClick={() => alternar(aba, t)} title={pt ? `em português: ${pt}` : undefined}>
                            {ligado ? <Check size={12} strokeWidth={3} aria-hidden /> : null}
                            <span className="t">{t}</span>{pt && pt.toLowerCase() !== t.toLowerCase() ? <span className="pt">{pt}</span> : null}
                          </button>
                          {camada === "extra" && (
                            <button type="button" className="x" aria-label={`Remover ${t}`} title="Remover do banco"
                                    onClick={() => rodar("remover", async () => { await enviar("/api/mineracao/termos/remover", { mercado: aba, termo: t }); carregar(); })}>
                              <X size={12} /></button>
                          )}
                        </span>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="campo-grupo">
        <label className="label" htmlFor="termos-novos">Adicionar seus termos em {est.mercados[aba]?.nome} (um por linha)</label>
        <div className="linha-campo">
          <textarea id="termos-novos" className="campo termos-novos" rows={3} value={texto} onChange={(e) => setTexto(e.target.value)}
                    placeholder={aba === "DE" ? "ex.: Zungentrick\nin nur 3 Minuten\nMontessori zum Ausdrucken" : aba === "PT" ? "ex.: truque dos 7 segundos\nmétodo montessori" : "ex.: astuce de 7 secondes\nméthode Montessori\nla bible des"}
                    onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) adicionar(); }} />
          <button className="btn btn-ghost" type="button" disabled={!texto.trim() || rodando === "adicionar"} onClick={adicionar}>
            {rodando === "adicionar" ? <Girando /> : <Plus size={16} aria-hidden />}Adicionar
          </button>
        </div>
        <p className="meta">A busca é por frase exata, no idioma do mercado. Seus termos ficam guardados para as próximas minerações (Ctrl+Enter adiciona).</p>
      </div>

      <div className="duas">
        <label className="campo-grupo"><span className="label">Anúncios lidos por termo</span>
          <select className="campo" value={maximo} onChange={(e) => setMaximo(+e.target.value)}>
            {[500, 1000, 2000].map((v) => <option key={v} value={v}>{numero(v)}</option>)}
          </select></label>
        <label className="campo-grupo"><span className="label">Finalistas medidas por página inteira</span>
          <select className="campo" value={finalistas} onChange={(e) => setFinalistas(+e.target.value)}>
            {[20, 40, 80].map((v) => <option key={v} value={v}>{v}</option>)}
          </select></label>
      </div>
      <div className="acoes">
        <button className="btn btn-primary" type="button" disabled={!est.token || !totalTermos || est.rodando || !!rodando}
                onClick={() => rodar("iniciar", async () => {
                  const termos = Object.fromEntries(mercados.map((m) => [m, marcados(m)]).filter(([, l]) => (l as string[]).length));
                  await enviar("/api/mineracao/iniciar", { mercados, max_por_termo: maximo, finalistas, termos }); fechar(); puxar();
                }, "Mineração começou.")}>
          {rodando === "iniciar" ? <Girando /> : <Play size={16} aria-hidden />}Minerar com {numero(totalTermos)} termos
        </button>
        <button className="btn btn-quiet" type="button" onClick={fechar}>Cancelar</button>
      </div>
    </section>
  );
}

// ── importar a planilha de garimpo do time ────────────────────────────────────
function ImportarPlanilha({ ctx, fechar, puxar }: { ctx: Ctx; fechar: () => void; puxar: () => void }) {
  const { rodando, rodar } = useAcao(ctx.avisar);
  const [nome, setNome] = useState("Garimpo do sócio");
  const [texto, setTexto] = useState("");
  const [arquivo, setArquivo] = useState<string | null>(null);
  const ler_ = (f: File | undefined) => { if (!f) return; setArquivo(f.name); f.text().then(setTexto); };
  return (
    <Modal titulo="Importar planilha de garimpo" fechar={fechar}
           acoes={<>
             <button type="button" className="btn btn-quiet" data-foco onClick={fechar}>Cancelar</button>
             <button type="button" className="btn btn-primary" disabled={!texto.trim() || !!rodando}
                     onClick={() => rodar("importar", async () => { await enviar("/api/mineracao/importar-planilha", { nome, texto }); fechar(); puxar(); },
                                         "Importando: cada oferta é medida na API (1 a 2 minutos).")}>
               {rodando === "importar" ? <Girando /> : <FileUp size={16} aria-hidden />}Importar
             </button>
           </>}>
      <p>Aceita o <code>dados-frances.js</code> / <code>dados-brasil.js</code> da Planilha de Ofertas (ou um JSON com a lista). Cada oferta vira
        uma linha da tabela e é medida na API: alcance real, países, 15+ dias e o buraco. Nota, nicho, concorrentes e observações da planilha ficam como estão.</p>
      <label className="campo-grupo"><span className="label">Nome desta origem</span>
        <input className="campo" value={nome} onChange={(e) => setNome(e.target.value)} /></label>
      <label className="campo-grupo"><span className="label">Arquivo</span>
        <input className="campo" type="file" accept=".js,.json,.txt" onChange={(e) => ler_(e.target.files?.[0])} /></label>
      <label className="campo-grupo"><span className="label">…ou cole o conteúdo</span>
        <textarea className="campo" rows={5} style={{ minHeight: 0 }} value={texto} onChange={(e) => { setTexto(e.target.value); setArquivo(null); }}
                  placeholder='window.OFERTAS["fr"] = [ ... ]' /></label>
      {arquivo && <p className="meta">Arquivo lido: {arquivo} · {numero(texto.length)} caracteres</p>}
    </Modal>
  );
}

// ── a tabela de ofertas ───────────────────────────────────────────────────────
type Aba = "todas" | "FR" | "DE" | "aprovadas" | "descartadas";
type Ordem = "nota" | "alcance" | "anuncios_15d" | "desde";

function Paises({ o }: { o: Oferta }) {
  const lst = Object.entries(o.paises_pct).filter(([, v]) => v > 0).slice(0, 3);
  if (!lst.length) return <span className="meta">—</span>;
  return <span className="paises">{lst.map(([k, v]) => <span key={k}>{PAIS[k] ?? k} <b>{v}%</b></span>)}</span>;
}

function LinhaOferta({ o, i, aberta, abrir, decidir, avisar }: {
  o: Oferta; i: number; aberta: boolean; abrir: () => void; decidir: (d: Partial<Decisao>) => void; avisar: Ctx["avisar"];
}) {
  const st = o.decisao.status;
  const notaFinal = o.decisao.nota ?? o.nota;
  const nicho = o.decisao.nicho || o.nicho || "";
  const obs = o.decisao.obs || o.observacao || "";
  const [obsTxt, setObs] = useState(o.decisao.obs ?? "");
  const [nichoTxt, setNicho] = useState(o.decisao.nicho ?? "");
  useEffect(() => { setObs(o.decisao.obs ?? ""); setNicho(o.decisao.nicho ?? ""); }, [o.chave, o.decisao.obs, o.decisao.nicho]);
  const conc = o.concorrentes ?? [];
  return (
    <Fragment>
      <tr className={`${st === "aprovada" ? "aprovada" : st === "descartada" ? "descartada" : ""}${i < 3 && st !== "descartada" ? " top" : ""}`} onClick={abrir}>
        <td className="c-pos"><span className={`pos${i < 3 ? " ouro" : ""}`}>{i + 1}</span></td>
        <td>
          <span className={`nota ${notaFinal >= 7.5 ? "alta" : notaFinal >= 5 ? "media" : "baixa"}`}>{notaFinal.toLocaleString("pt-BR")}</span>
          {o.nota_planilha != null && o.nota_planilha !== notaFinal && <span className="meta nota-socio" title="nota dada na planilha">planilha {o.nota_planilha.toLocaleString("pt-BR")}</span>}
        </td>
        <td className="c-oferta">
          <strong>{o.oferta}</strong>
          <span className="meta">{o.anunciante}</span>
          {i < 3 && st !== "descartada" && <span className="top3">Top 3</span>}
          {o.bandeiras.length > 0 && (
            <span className="chips">{o.bandeiras.map((b) => BANDEIRA[b] && <span key={b} className={`tag tag-${BANDEIRA[b].tom} tag-mini`} title={BANDEIRA[b].dica}>{BANDEIRA[b].texto}</span>)}</span>
          )}
        </td>
        <td className="c-nicho">{nicho || <span className="meta">—</span>}</td>
        <td><LinkExterno url={o.biblioteca} texto="Abrir" variante="abrir" avisar={avisar} /></td>
        <td>{o.landing ? <LinkExterno url={o.landing} texto="Ver" avisar={avisar} /> : <span className="meta">—</span>}</td>
        <td className="c-origem">
          {(o.fontes ?? []).map((f) => <span key={f} className="fonte">{f}</span>)}
          <span className="meta">{o.origem.map((m) => IDIOMA_MERCADO[m] ?? m).join(" · ")}</span>
        </td>
        <td className="c-num"><strong>{pessoas(o.alcance_ue)}</strong><span className="meta">{o.alcance_ue ? "pessoas" : "sem medição"}</span></td>
        <td className="c-num"><strong>{numero(o.anuncios_15d)}</strong><span className="meta">de {numero(o.anuncios)}</span></td>
        <td className="c-num meta">{data(o.rodando_desde)}<br />{o.max_dias} d</td>
        <td><Paises o={o} /></td>
        <td>{o.buraco.length ? <span className="buraco">{o.buraco.map((b) => b === "FR" ? "Francês" : "Alemão").join(" + ")}</span>
                             : <span className="meta">já roda</span>}</td>
        <td className="meta c-preco">{o.precos.slice(0, 3).join(" · ") || "—"}</td>
        <td className="c-conc" onClick={(e) => e.stopPropagation()}>
          {o.n_concorrentes != null || conc.length ? (
            <><strong className={conc.length || o.n_concorrentes ? "" : "nenhum"}>{conc.length || o.n_concorrentes ? numero(o.n_concorrentes ?? conc.length) : "nenhum"}</strong>
              <div className="variacoes">{conc.map((c, k) => c.url ? <LinkExterno key={k} url={c.url} texto={c.nome} avisar={avisar} /> : <span key={k} className="meta">{c.nome}</span>)}</div></>
          ) : <span className="meta">—</span>}
        </td>
        <td className="c-var" onClick={(e) => e.stopPropagation()}>
          <div className="variacoes">
            {o.variacoes.map((v, k) => <LinkExterno key={k} url={busca(v.termo, v.mercado)} texto={v.termo} avisar={avisar} />)}
          </div>
        </td>
        <td className="c-obs">{obs ? <span className="obs-curta">{obs}</span> : <span className="meta">—</span>}</td>
        <td className="c-acoes" onClick={(e) => e.stopPropagation()}>
          <button type="button" className={`btn btn-icon-sm btn-quiet${st === "aprovada" ? " on-ok" : ""}`} aria-pressed={st === "aprovada"}
                  aria-label="Aprovar" title="Aprovar" onClick={() => decidir({ status: st === "aprovada" ? undefined : "aprovada" })}><ThumbsUp size={15} /></button>
          <button type="button" className={`btn btn-icon-sm btn-quiet${st === "descartada" ? " on-no" : ""}`} aria-pressed={st === "descartada"}
                  aria-label="Descartar" title="Descartar" onClick={() => decidir({ status: st === "descartada" ? undefined : "descartada" })}><ThumbsDown size={15} /></button>
          <button type="button" className="btn btn-icon-sm btn-quiet" aria-expanded={aberta} aria-label="Detalhes" onClick={abrir}>
            <ChevronDown size={15} className={aberta ? "virado" : ""} /></button>
        </td>
      </tr>
      {aberta && (
        <tr className="detalhe-linha">
          <td colSpan={17}>
            <div className="oferta-detalhe">
              <div className="od-copy">
                <span className="label">{o.textos.length ? "Copy dos anúncios" : "Da planilha"}</span>
                {o.textos.map((t, k) => <p key={k}>{t}</p>)}
                {o.observacao && <p>{o.observacao}</p>}
                {(o.formato || o.adaptacao || o.paises_alvo) && (
                  <div className="dados" style={{ marginTop: 12 }}>
                    {o.formato && <div><span className="label">Formato</span><strong>{o.formato}</strong></div>}
                    {o.esforco && <div><span className="label">Esforço p/ recriar</span><strong>{o.esforco}</strong></div>}
                    {o.aceitacao && <div><span className="label">Aceitação FR</span><strong>{o.aceitacao}</strong></div>}
                    {o.anuncios_fr != null && <div><span className="label">Em francês (15+ / total)</span><strong>{o.anuncios_fr_15d ?? "—"} / {o.anuncios_fr}</strong></div>}
                    {o.paises_alvo && <div><span className="label">Países-alvo</span><strong>{o.paises_alvo}</strong></div>}
                    {o.adaptacao && <div><span className="label">Adaptação</span><strong>{o.adaptacao}</strong></div>}
                  </div>
                )}
                {o.titulo_landing && <p className="meta">Landing: {o.titulo_landing}</p>}
                {o.landing_erro && <p className="meta">A landing não abriu fora do anúncio ({o.landing_erro}): abra pelo anúncio na biblioteca.</p>}
              </div>
              <div className="od-dados">
                <div className="dados">
                  <div><span className="label">Alcance 15+ dias</span><strong>{pessoas(o.alcance_15d)}</strong></div>
                  <div><span className="label">Presença FR / DE</span><strong>{o.presenca.FR ?? 0}% / {o.presenca.DE ?? 0}%</strong></div>
                  <div><span className="label">Idiomas</span><strong>{Object.entries(o.idiomas).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}</strong></div>
                  <div><span className="label">{o.nota_planilha != null ? "Nota da planilha" : "Nota automática"}</span><strong>{(o.nota_planilha ?? o.nota).toLocaleString("pt-BR")}</strong></div>
                </div>
                {o.bibliotecas.length > 1 && (
                  <div className="acoes">{o.bibliotecas.map((b, k) => <LinkExterno key={k} url={b.url} texto={b.nome} avisar={avisar} />)}</div>
                )}
                <div className="duas">
                  <label className="campo-grupo"><span className="label">Nicho</span>
                    <input className="campo" value={nichoTxt} placeholder={o.nicho || "ex.: atividades para idosos"} onChange={(e) => setNicho(e.target.value)}
                           onBlur={() => nichoTxt !== (o.decisao.nicho ?? "") && decidir({ nicho: nichoTxt })} /></label>
                  <label className="campo-grupo"><span className="label">Sua nota (0 a 10)</span>
                    <input className="campo" type="number" min={0} max={10} step={0.5} defaultValue={o.decisao.nota ?? ""} placeholder={String(o.nota)}
                           onBlur={(e) => { const v = e.target.value === "" ? undefined : Math.max(0, Math.min(10, +e.target.value)); if (v !== o.decisao.nota) decidir({ nota: v }); }} /></label>
                </div>
                <label className="campo-grupo"><span className="label">Observação</span>
                  <input className="campo" value={obsTxt} placeholder="o que muda para FR/DE, concorrentes que você achou…" onChange={(e) => setObs(e.target.value)}
                         onBlur={() => obsTxt !== (o.decisao.obs ?? "") && decidir({ obs: obsTxt })} /></label>
              </div>
            </div>
          </td>
        </tr>
      )}
    </Fragment>
  );
}

function TabelaOfertas({ ofertas, ctx, mudar }: { ofertas: Oferta[]; ctx: Ctx; mudar: (chave: string, d: Partial<Decisao>) => void }) {
  const [aba, setAba] = useState<Aba>("todas");
  const [q, setQ] = useState("");
  const [ordem, setOrdem] = useState<Ordem>("nota");
  const [aberta, setAberta] = useState<string | null>(null);
  const conta = {
    todas: ofertas.filter((o) => o.decisao.status !== "descartada").length,
    FR: ofertas.filter((o) => o.buraco.includes("FR") && o.decisao.status !== "descartada").length,
    DE: ofertas.filter((o) => o.buraco.includes("DE") && o.decisao.status !== "descartada").length,
    aprovadas: ofertas.filter((o) => o.decisao.status === "aprovada").length,
    descartadas: ofertas.filter((o) => o.decisao.status === "descartada").length,
  };
  const lista = useMemo(() => {
    const t = q.trim().toLowerCase();
    return ofertas
      .filter((o) => aba === "aprovadas" ? o.decisao.status === "aprovada" : aba === "descartadas" ? o.decisao.status === "descartada" :
                     o.decisao.status !== "descartada" && (aba === "todas" || o.buraco.includes(aba)))
      .filter((o) => !t || [o.oferta, o.anunciante, o.chave, o.decisao.nicho ?? "", o.nicho ?? "", ...o.textos].join(" ").toLowerCase().includes(t))
      .sort((a, b) => ordem === "alcance" ? b.alcance_ue - a.alcance_ue : ordem === "anuncios_15d" ? b.anuncios_15d - a.anuncios_15d :
                      ordem === "desde" ? b.max_dias - a.max_dias : (b.decisao.nota ?? b.nota) - (a.decisao.nota ?? a.nota) || b.alcance_ue - a.alcance_ue);
  }, [ofertas, aba, q, ordem]);
  const cab = (id: Ordem, texto: string) => (
    <button type="button" className="th-ord" aria-pressed={ordem === id} onClick={() => setOrdem(id)}>{texto}{ordem === id ? " ▼" : ""}</button>
  );
  return (
    <section className="grupo" aria-label="Ofertas mineradas">
      <div className="tabela-topo">
        <div className="seg" role="group" aria-label="Filtro">
          {([["todas", "Todas"], ["FR", "Buraco em francês"], ["DE", "Buraco em alemão"], ["aprovadas", "Aprovadas"], ["descartadas", "Descartadas"]] as [Aba, string][]).map(([k, t]) => (
            <button key={k} type="button" aria-pressed={aba === k} onClick={() => setAba(k)}>{t} <span className="seg-n">{conta[k]}</span></button>
          ))}
        </div>
        <label className="busca"><Search size={15} aria-hidden />
          <input className="campo" placeholder="Buscar oferta, nicho, anunciante…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar" /></label>
      </div>
      <div className="panel tabela-wrap">
        <table className="tabela-ofertas">
          <thead>
            <tr>
              <th>#</th><th>{cab("nota", "Nota")}</th><th>Oferta</th><th>Nicho</th><th>Biblioteca</th><th>Landing</th><th>Origem</th>
              <th>{cab("alcance", "Alcance UE")}</th><th>{cab("anuncios_15d", "15+ dias")}</th><th>{cab("desde", "Rodando desde")}</th>
              <th>Onde roda</th><th>Buraco</th><th>Preço</th><th>Concorrentes</th><th>Variações pesquisadas</th><th>Observação</th><th><span className="sr">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {lista.map((o, i) => (
              <LinhaOferta key={o.chave} o={o} i={i} aberta={aberta === o.chave} avisar={ctx.avisar}
                           abrir={() => setAberta(aberta === o.chave ? null : o.chave)} decidir={(d) => mudar(o.chave, d)} />
            ))}
          </tbody>
        </table>
        {!lista.length && <p className="meta vazio-tabela">Nenhuma oferta neste filtro.</p>}
      </div>
    </section>
  );
}

// ── a tela ────────────────────────────────────────────────────────────────────
export function Mineracao({ ctx }: { ctx: Ctx }) {
  const { est, puxar } = useMineracao(ctx.avisar);
  const [rid, setRid] = useState<string>(() => guardado<string>("edt_rodada_v2", TODAS));
  const [ofertas, setOfertas] = useState<Oferta[] | null>(null);
  const [painel, setPainel] = useState<"nova" | "importar" | "excluir" | null>(null);
  const { rodando, rodar } = useAcao(ctx.avisar);
  const rodadas = est?.rodadas ?? [];
  const escolhida = rid === TODAS ? null : rodadas.find((r) => r.id === rid) ?? null;
  const ver = rid === TODAS || !escolhida ? TODAS : escolhida.id;
  const chaveCarga = `${ver}|${rodadas.map((r) => `${r.id}:${r.status}:${r.ofertas}`).join(",")}`;
  const escolher = (v: string) => { setRid(v); guardar("edt_rodada_v2", v); };

  useEffect(() => {
    if (!rodadas.length) { setOfertas(null); return; }
    let vivo = true;
    ler<{ ofertas: Oferta[] }>(`/api/mineracao/rodadas/${encodeURIComponent(ver)}`)
      .then((r) => vivo && setOfertas(r.ofertas)).catch((x) => ctx.avisar((x as Error).message, "erro"));
    return () => { vivo = false; };
  }, [chaveCarga]);                                                    // eslint-disable-line react-hooks/exhaustive-deps

  const mudar = useCallback((chave: string, d: Partial<Decisao>) => {
    setOfertas((xs) => xs?.map((o) => o.chave === chave ? { ...o, decisao: { ...o.decisao, ...d } } : o) ?? null);
    const corpo: Record<string, unknown> = { chave };
    for (const [k, v] of Object.entries(d)) corpo[k] = v === undefined ? "" : v;
    enviar("/api/mineracao/decidir", corpo).catch((x) => ctx.avisar((x as Error).message, "erro"));
  }, [ctx]);

  if (!est) return <div className="tela"><div className="panel vazio"><Girando /><p>Abrindo a mineração…</p></div></div>;
  const aprovadas = ofertas?.filter((o) => o.decisao.status === "aprovada").length ?? 0;
  const vivas = ofertas?.filter((o) => o.decisao.status !== "descartada").length ?? 0;
  const mostrada = est.rodando ? rodadas.find((r) => r.id === est.rodada) ?? escolhida ?? rodadas[0] ?? null : escolhida ?? rodadas[0] ?? null;

  return (
    <div className="tela tela-larga">
      <header className="tela-topo">
        <div>
          <p className="eyebrow">Mineração · Biblioteca de Anúncios da Meta</p>
          <h1>{numero(vivas)} ofertas <em>· {numero(aprovadas)} {aprovadas === 1 ? "aprovada" : "aprovadas"}</em></h1>
          <p className="lead">Ofertas de infoproduto escaladas na Europa, medidas pelo alcance real na UE. O buraco é o mercado (francês ou alemão) onde a oferta ainda não roda.</p>
        </div>
        <div className="acoes">
          {rodadas.length > 0 && (
            <select className="campo campo-rodada" aria-label="Rodada" value={ver} onChange={(e) => escolher(e.target.value)}>
              <option value={TODAS}>Todas as rodadas ({rodadas.length})</option>
              {rodadas.map((r) => <option key={r.id} value={r.id}>{nomeRodada(r)} · {r.mercados.join("/")} · {r.ofertas ?? 0} ofertas</option>)}
            </select>
          )}
          {escolhida && (
            <button className="btn btn-ghost btn-icon-lg" type="button" disabled={est.rodando && est.rodada === escolhida.id}
                    onClick={() => setPainel("excluir")} aria-label="Excluir esta rodada" title="Excluir esta rodada"><Trash2 size={17} /></button>
          )}
          <button className="btn btn-ghost" type="button" disabled={est.rodando} onClick={() => setPainel("importar")}>
            <FileUp size={16} aria-hidden />Importar planilha
          </button>
          <button className="btn btn-primary" type="button" disabled={est.rodando} onClick={() => setPainel(painel === "nova" ? null : "nova")}>
            <Pickaxe size={16} aria-hidden />Nova mineração
          </button>
        </div>
      </header>

      {painel === "nova" && <NovaMineracao est={est} ctx={ctx} fechar={() => setPainel(null)} puxar={puxar} />}
      {painel === "importar" && <ImportarPlanilha ctx={ctx} fechar={() => setPainel(null)} puxar={puxar} />}
      {painel === "excluir" && escolhida && (
        <Modal titulo="Excluir esta rodada?" perigo fechar={() => setPainel(null)}
               acoes={<>
                 <button type="button" className="btn btn-quiet" data-foco onClick={() => setPainel(null)}>Cancelar</button>
                 <button type="button" className="btn btn-danger" disabled={!!rodando}
                         onClick={() => rodar("excluir", async () => {
                           await enviar("/api/mineracao/excluir", { rodada: escolhida.id }); setPainel(null); escolher(TODAS); puxar();
                         }, "Rodada excluída.")}>
                   {rodando === "excluir" ? <Girando /> : <Trash2 size={16} aria-hidden />}Excluir para sempre
                 </button>
               </>}>
          <p><strong>{nomeRodada(escolhida)}</strong> · {escolhida.mercados.join(", ")} · {numero(escolhida.ofertas ?? 0)} ofertas</p>
          <p>Apaga do disco as ofertas desta rodada e todos os anúncios coletados nela. <strong>Não dá para desfazer.</strong></p>
          <p className="meta">Suas aprovações, descartes, notas e observações continuam guardados: valem se a oferta aparecer em outra rodada.</p>
        </Modal>
      )}
      <Andamento est={est} rodada={mostrada} ctx={ctx} puxar={puxar} />

      {ofertas && ofertas.length > 0 ? <TabelaOfertas ofertas={ofertas} ctx={ctx} mudar={mudar} /> :
        !est.rodando && (
          <div className="panel vazio">
            <Pickaxe size={40} aria-hidden />
            <h2>{rodadas.length ? "Esta rodada ainda não tem ofertas" : "Nenhuma oferta minerada ainda"}</h2>
            <p>Comece uma mineração ou importe a planilha de garimpo do time.</p>
          </div>
        )}
    </div>
  );
}
