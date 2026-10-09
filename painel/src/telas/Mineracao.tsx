import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Check, ChevronDown, ExternalLink, Pickaxe, Play, RotateCcw, Search, Square, ThumbsDown, ThumbsUp } from "lucide-react";
import { abrirLink, enviar, ler, type Decisao, type EstadoMineracao, type FaseMineracao, type Oferta, type RodadaMineracao } from "../api";
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

const PAIS: Record<string, string> = {
  FR: "França", DE: "Alemanha", AT: "Áustria", BE: "Bélgica", LU: "Luxemburgo", PT: "Portugal", ES: "Espanha",
  IT: "Itália", NL: "Holanda", PL: "Polônia", GR: "Grécia", IE: "Irlanda", GB: "R. Unido", SE: "Suécia", DK: "Dinamarca",
  FI: "Finlândia", CZ: "Tchéquia", RO: "Romênia", HU: "Hungria", SK: "Eslováquia", SI: "Eslovênia", HR: "Croácia",
  BG: "Bulgária", RE: "Reunião", GP: "Guadalupe", MQ: "Martinica", GF: "Guiana Fr.",
};

const BANDEIRA: Record<string, { texto: string; tom: "ok" | "voce" | "no" | "run" | "neutra"; dica: string }> = {
  escalando: { texto: "Escalando", tom: "run", dica: "mais de 40% do alcance veio de anúncios com menos de 15 dias" },
  novo: { texto: "Novo", tom: "voce", dica: "nenhum anúncio com 15+ dias: escala rápida, ainda não validada" },
  operador_br: { texto: "Operador BR", tom: "neutra", dica: "a landing mostra preço em R$" },
  isca: { texto: "Isca grátis", tom: "no", dica: "o anúncio oferece algo gratuito (captação de lead)" },
  assinatura: { texto: "Assinatura/app", tom: "no", dica: "parece assinatura, app ou teste grátis" },
  fisico: { texto: "Físico?", tom: "no", dica: "a landing fala em frete/envio e não em digital" },
  ticket_alto: { texto: "Ticket alto", tom: "voce", dica: "o preço que mais aparece na landing passa de 60" },
  formacao: { texto: "Curso/carreira", tom: "voce", dica: "formação profissional, certificação, mentoria ou recrutamento: difícil de virar low ticket" },
};

const pessoas = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`
  : n >= 1000 ? `${Math.round(n / 1000).toLocaleString("pt-BR")} mil` : numero(n);
const data = (iso: string) => { const [a, m, d] = iso.slice(0, 10).split("-"); return `${d}/${m}/${a.slice(2)}`; };
const quando = (iso: string) => { try { return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); } catch { return iso; } };
const busca = (termo: string, mercado: string) =>
  `https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=${mercado === "PT" ? "PT" : mercado}&q=${encodeURIComponent(`"${termo}"`)}&search_type=keyword_exact_phrase&media_type=all`;

function lembrar(k: string, v?: string): string | null {
  try { if (v !== undefined) localStorage.setItem(k, v); return localStorage.getItem(k); } catch { return null; }
}

// ── link que abre no navegador padrao ─────────────────────────────────────────
function LinkExterno({ url, texto, variante = "ghost", avisar }: { url: string; texto: string; variante?: "ghost" | "abrir"; avisar: Ctx["avisar"] }) {
  return (
    <a href={url} target="_blank" rel="noreferrer noopener" className={`btn btn-sm ${variante === "abrir" ? "btn-abrir" : "btn-ghost"}`}
       onClick={(e) => { e.preventDefault(); e.stopPropagation(); abrirLink(url).catch((x) => { window.open(url, "_blank", "noopener"); avisar((x as Error).message, "erro"); }); }}>
      {texto}<ExternalLink size={13} aria-hidden />
    </a>
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

// ── o cartao de producao da mineracao ─────────────────────────────────────────
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
              rodada ? `Rodada de ${quando(rodada.criada)} · ${rodada.mercados.join(", ")} · ${numero(rodada.ofertas ?? 0)} ofertas ranqueadas` :
              "Escolha os mercados e comece. A coleta inteira leva uns 30 a 40 minutos.";
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
            {parada && (
              <button className="btn btn-primary" type="button" disabled={!!rodando}
                      onClick={() => rodar("retomar", async () => { await enviar("/api/mineracao/retomar", { rodada: rodada!.id }); puxar(); }, "Retomando a mineração.")}>
                {rodando === "retomar" ? <Girando /> : <RotateCcw size={16} aria-hidden />}Retomar
              </button>
            )}
          </div>
        </div>
        <ol className="fases" aria-label="Etapas">
          {FASES.map((f, i) => {
            const feito = fase === "pronta" || (idx > i) ;
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

// ── formulario de nova mineracao ──────────────────────────────────────────────
function NovaMineracao({ est, ctx, fechar, puxar }: { est: EstadoMineracao; ctx: Ctx; fechar: () => void; puxar: () => void }) {
  const { rodando, rodar } = useAcao(ctx.avisar);
  const [mercados, setMercados] = useState<string[]>(Object.keys(est.mercados));
  const [maximo, setMaximo] = useState(1000);
  const [finalistas, setFinalistas] = useState(40);
  const termos = mercados.reduce((s, m) => s + (est.mercados[m]?.termos ?? 0), 0);
  const alternar = (m: string) => setMercados((xs) => xs.includes(m) ? xs.filter((x) => x !== m) : [...xs, m]);
  return (
    <section className="panel bloco" aria-label="Nova mineração">
      <div className="linha-titulo"><h3>Nova mineração</h3>
        <span className="meta">{numero(termos)} termos · uns {Math.max(5, Math.round(termos / Math.max(1, mercados.length) * 0.7))} min por mercado, em paralelo</span></div>
      {!est.token && (
        <div className="aviso-lista" role="alert">Falta o <code>META_TOKEN</code> no <code>.env</code> da ferramenta (token da Biblioteca de Anúncios da Meta).</div>
      )}
      <div className="campo-grupo">
        <span className="label">Mercados para garimpar</span>
        <div className="filtros">
          {Object.entries(est.mercados).map(([k, m]) => (
            <button key={k} type="button" className="filtro" aria-pressed={mercados.includes(k)} onClick={() => alternar(k)}>
              {k} · {m.nome}<span>{m.termos} termos</span>
            </button>
          ))}
        </div>
        <p className="meta">Portugal é a vitrine dos operadores brasileiros dentro da UE: a API mostra o alcance real deles.</p>
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
        <button className="btn btn-primary" type="button" disabled={!est.token || !mercados.length || est.rodando || !!rodando}
                onClick={() => rodar("iniciar", async () => { await enviar("/api/mineracao/iniciar", { mercados, max_por_termo: maximo, finalistas }); fechar(); puxar(); }, "Mineração começou.")}>
          {rodando === "iniciar" ? <Girando /> : <Play size={16} aria-hidden />}Começar mineração
        </button>
        <button className="btn btn-quiet" type="button" onClick={fechar}>Cancelar</button>
      </div>
    </section>
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
  const [obs, setObs] = useState(o.decisao.obs ?? "");
  const [nicho, setNicho] = useState(o.decisao.nicho ?? "");
  useEffect(() => { setObs(o.decisao.obs ?? ""); setNicho(o.decisao.nicho ?? ""); }, [o.chave, o.decisao.obs, o.decisao.nicho]);
  return (
    <Fragment>
      <tr className={`${st === "aprovada" ? "aprovada" : st === "descartada" ? "descartada" : ""}${i < 3 && st !== "descartada" ? " top" : ""}`} onClick={abrir}>
        <td className="c-pos"><span className={`pos${i < 3 ? " ouro" : ""}`}>{i + 1}</span></td>
        <td><span className={`nota ${notaFinal >= 7.5 ? "alta" : notaFinal >= 5 ? "media" : "baixa"}`}>{notaFinal.toLocaleString("pt-BR")}</span></td>
        <td className="c-oferta">
          <strong>{o.oferta}</strong>
          <span className="meta">{o.anunciante}</span>
          {i < 3 && st !== "descartada" && <span className="top3">Top 3</span>}
          {o.bandeiras.length > 0 && (
            <span className="chips">{o.bandeiras.map((b) => BANDEIRA[b] && <span key={b} className={`tag tag-${BANDEIRA[b].tom} tag-mini`} title={BANDEIRA[b].dica}>{BANDEIRA[b].texto}</span>)}</span>
          )}
        </td>
        <td><LinkExterno url={o.biblioteca} texto="Abrir" variante="abrir" avisar={avisar} /></td>
        <td>{o.landing ? <LinkExterno url={o.landing} texto="Ver" avisar={avisar} /> : <span className="meta">—</span>}</td>
        <td className="meta">{o.origem.map((m) => m === "PT" ? "Portugal" : m === "DE" ? "Alemão" : "Francês").join(" · ")}</td>
        <td className="c-num"><strong>{pessoas(o.alcance_ue)}</strong><span className="meta">pessoas</span></td>
        <td className="c-num"><strong>{numero(o.anuncios_15d)}</strong><span className="meta">de {numero(o.anuncios)}</span></td>
        <td className="c-num meta">{data(o.rodando_desde)}<br />{o.max_dias} d</td>
        <td><Paises o={o} /></td>
        <td>{o.buraco.length ? <span className="buraco">{o.buraco.map((b) => b === "FR" ? "Francês" : "Alemão").join(" + ")}</span>
                             : <span className="meta">já roda</span>}</td>
        <td className="meta c-preco">{o.precos.slice(0, 3).join(" · ") || "—"}</td>
        <td className="c-var" onClick={(e) => e.stopPropagation()}>
          <div className="variacoes">
            {o.variacoes.map((v, k) => <LinkExterno key={k} url={busca(v.termo, v.mercado)} texto={v.termo} avisar={avisar} />)}
          </div>
        </td>
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
          <td colSpan={14}>
            <div className="oferta-detalhe">
              <div className="od-copy">
                <span className="label">Copy dos anúncios</span>
                {o.textos.map((t, k) => <p key={k}>{t}</p>)}
                {o.titulo_landing && <p className="meta">Landing: {o.titulo_landing}</p>}
                {o.landing_erro && <p className="meta">A landing não abriu fora do anúncio ({o.landing_erro}): abra pelo anúncio na biblioteca.</p>}
              </div>
              <div className="od-dados">
                <div className="dados">
                  <div><span className="label">Alcance 15+ dias</span><strong>{pessoas(o.alcance_15d)}</strong></div>
                  <div><span className="label">Presença FR / DE</span><strong>{o.presenca.FR ?? 0}% / {o.presenca.DE ?? 0}%</strong></div>
                  <div><span className="label">Idiomas</span><strong>{Object.entries(o.idiomas).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}</strong></div>
                  <div><span className="label">Nota automática</span><strong>{o.nota.toLocaleString("pt-BR")}</strong></div>
                </div>
                {o.bibliotecas.length > 1 && (
                  <div className="acoes">{o.bibliotecas.map((b, k) => <LinkExterno key={k} url={b.url} texto={b.nome} avisar={avisar} />)}</div>
                )}
                <div className="duas">
                  <label className="campo-grupo"><span className="label">Nicho</span>
                    <input className="campo" value={nicho} placeholder="ex.: atividades para idosos" onChange={(e) => setNicho(e.target.value)}
                           onBlur={() => nicho !== (o.decisao.nicho ?? "") && decidir({ nicho })} /></label>
                  <label className="campo-grupo"><span className="label">Sua nota (0 a 10)</span>
                    <input className="campo" type="number" min={0} max={10} step={0.5} defaultValue={o.decisao.nota ?? ""} placeholder={String(o.nota)}
                           onBlur={(e) => { const v = e.target.value === "" ? undefined : Math.max(0, Math.min(10, +e.target.value)); if (v !== o.decisao.nota) decidir({ nota: v }); }} /></label>
                </div>
                <label className="campo-grupo"><span className="label">Observação</span>
                  <input className="campo" value={obs} placeholder="o que muda para FR/DE, concorrentes que você achou…" onChange={(e) => setObs(e.target.value)}
                         onBlur={() => obs !== (o.decisao.obs ?? "") && decidir({ obs })} /></label>
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
      .filter((o) => !t || [o.oferta, o.anunciante, o.chave, o.decisao.nicho ?? "", ...o.textos].join(" ").toLowerCase().includes(t))
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
              <th>#</th><th>{cab("nota", "Nota")}</th><th>Oferta</th><th>Biblioteca</th><th>Landing</th><th>Origem</th>
              <th>{cab("alcance", "Alcance UE")}</th><th>{cab("anuncios_15d", "15+ dias")}</th><th>{cab("desde", "Rodando desde")}</th>
              <th>Onde roda</th><th>Buraco</th><th>Preço</th><th>Variações pesquisadas</th><th><span className="sr">Ações</span></th>
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
  const [rid, setRid] = useState<string | null>(lembrar("edt_rodada"));
  const [ofertas, setOfertas] = useState<Oferta[] | null>(null);
  const [nova, setNova] = useState(false);
  const rodadas = est?.rodadas ?? [];
  const atual = rodadas.find((r) => r.id === rid) ?? rodadas[0] ?? null;
  const chaveCarga = `${atual?.id}|${atual?.status}|${atual?.ofertas}`;

  useEffect(() => {
    if (!atual) { setOfertas(null); return; }
    let vivo = true;
    ler<{ ofertas: Oferta[] }>(`/api/mineracao/rodadas/${encodeURIComponent(atual.id)}`)
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
            <select className="campo campo-rodada" aria-label="Rodada" value={atual?.id ?? ""}
                    onChange={(e) => { setRid(e.target.value); lembrar("edt_rodada", e.target.value); }}>
              {rodadas.map((r) => <option key={r.id} value={r.id}>{quando(r.criada)} · {r.mercados.join("/")} · {r.ofertas ?? 0} ofertas</option>)}
            </select>
          )}
          <button className="btn btn-primary" type="button" disabled={est.rodando} onClick={() => setNova((v) => !v)}>
            <Pickaxe size={16} aria-hidden />Nova mineração
          </button>
        </div>
      </header>

      {nova && <NovaMineracao est={est} ctx={ctx} fechar={() => setNova(false)} puxar={puxar} />}
      <Andamento est={est} rodada={est.rodando ? rodadas.find((r) => r.id === est.rodada) ?? atual : atual} ctx={ctx} puxar={puxar} />

      {ofertas && ofertas.length > 0 ? <TabelaOfertas ofertas={ofertas} ctx={ctx} mudar={mudar} /> :
        !est.rodando && (
          <div className="panel vazio">
            <Pickaxe size={40} aria-hidden />
            <h2>{rodadas.length ? "Esta rodada ainda não tem ofertas" : "Nenhuma oferta minerada ainda"}</h2>
            <p>Comece uma mineração: a ferramenta busca os termos de mecanismo, entrega digital e prova de escala em francês, alemão e português de Portugal.</p>
          </div>
        )}
    </div>
  );
}
