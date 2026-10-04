import { useState } from "react";
import { ArrowLeft, FolderOpen, Mic, RotateCcw, ScanLine } from "lucide-react";
import { enviar, midia, type Criativo } from "../api";
import type { Ctx } from "../App";
import { CardCriativo, Girando, Selo, useAcao } from "../componentes/base";
import { link } from "../rota";
import { ETAPA, PERFIL, TRANSICAO, seg } from "../textos";

type Filtro = "todos" | "entregue" | "conferir" | "pendente";

// ⭐ as faixas onde o Reels/Stories da Meta desenha a interface por cima do video (guia 2026, unificado)
function ZonaSegura() {
  return (
    <div className="zona" aria-hidden>
      <div className="z-topo"><span>topo · perfil e barra (14%)</span></div>
      <div className="z-base"><span>base · legenda do post e botão (35%)</span></div>
      <div className="z-esq" /><div className="z-dir" />
    </div>
  );
}

function Detalhe({ c, ctx }: { c: Criativo; ctx: Ctx }) {
  const { rodando, rodar } = useAcao(ctx.avisar);
  const [zona, setZona] = useState(false);
  const camp = ctx.camp!;
  const ocupado = ctx.estado.rodando;
  return (
    <div className="tela">
      <a className="btn btn-quiet voltar" href={link.criativos}><ArrowLeft size={16} aria-hidden />Criativos</a>
      <header className="tela-topo">
        <div>
          <p className="eyebrow">Público {c.publico_n} · {c.publico}</p>
          <h1>{c.id} · {c.angulo}</h1>
        </div>
        <div className="acoes">
          {c.pasta && (
            <button className="btn btn-ghost" type="button" onClick={() => rodar("pasta", () => enviar("/api/abrir-pasta", { caminho: c.entregue ?? c.pasta! }))}>
              <FolderOpen size={16} aria-hidden />Abrir pasta
            </button>
          )}
          {c.entregue && (
            <button className="btn btn-ghost" type="button" disabled={ocupado || !camp.base_ok || !!rodando}
                    title="Pede outra leitura da MiniMax para esta copy (entonação, ênfase ou palavra arrastada)"
                    onClick={() => rodar("voz", () => enviar("/api/nova-narracao", { campanha: camp.nome, id: c.id }),
                                        `Nova narração do ${c.id} a caminho. O vídeo é refeito com ela.`)}>
              {rodando === "voz" ? <Girando /> : <Mic size={16} aria-hidden />}Nova narração
            </button>
          )}
          <button className="btn btn-primary" type="button" disabled={ocupado || !camp.base_ok || !!rodando}
                  onClick={() => rodar("refazer", () => enviar("/api/produzir", { campanha: camp.nome, ids: [c.id], refazer: true }),
                                      `Refazendo o ${c.id}. Ele aparece aqui quando ficar pronto.`)}>
            {rodando === "refazer" ? <Girando /> : <RotateCcw size={16} aria-hidden />}{c.entregue ? "Refazer este" : "Produzir este"}
          </button>
        </div>
      </header>
      <div className="detalhe">
        {c.entregue && c.etapa !== "narrando" && c.etapa !== "renderizando" ? (
          <div className="video-zona">
            <video key={c.entregue + String(c.duracao)} src={midia(c.entregue)} controls playsInline preload="metadata" />
            {zona && <ZonaSegura />}
            <button className={`btn btn-sm ${zona ? "btn-primary" : "btn-ghost"} botao-zona`} type="button" onClick={() => setZona(!zona)}
                    aria-pressed={zona}><ScanLine size={14} aria-hidden />Zona segura da Meta</button>
          </div>
        ) : (
          <div className="panel sem-video">{c.etapa === "narrando" || c.etapa === "renderizando" ? <div><Girando /> {ETAPA[c.etapa].texto}…</div> : "Ainda não produzido."}</div>
        )}
        <section className="panel ficha">
          <div className="chips"><Selo etapa={c.etapa} />{c.preco && <span className="tag tag-voce">com preço</span>}
            {c.modelo && <span className="tag tag-neutra">modelo {c.modelo}</span>}
            {c.motor && <span className="tag tag-neutra">{c.motor === "remotion" ? "Remotion" : "motor atual"}</span>}
            {c.motion.length > 0 && <span className="tag tag-neutra">motion: {c.motion.join(" + ")}</span>}</div>
          {c.avisos.length > 0 && <ul className="aviso-lista">{c.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>}
          {c.zona_segura.length > 0 && (
            <div className="info-zona"><span className="label">Zona segura (informativo)</span>
              <ul>{c.zona_segura.map((z, i) => <li key={i}>{z}</li>)}</ul></div>
          )}
          <div><span className="label">Narração (copy)</span><p className="copy">{c.copy}</p></div>
          <div className="dados">
            <div><span className="label">Duração</span><strong>{seg(c.duracao)} <span className="meta">alvo {c.alvo_s}s</span></strong></div>
            <div><span className="label">Velocidade da voz</span><strong>{c.voz ? `${c.voz.toFixed(2)}×` : "—"}</strong></div>
            <div><span className="label">Música</span><strong>{c.musica ?? "—"}</strong><span className="meta">{PERFIL[c.perfil_musica] ?? c.perfil_musica}</span></div>
            <div><span className="label">Efeitos sonoros</span><strong>{c.sfx || "—"}</strong></div>
            <div><span className="label">Ritmo da música</span><strong>{c.bpm ? `${Math.round(c.bpm)} BPM` : "—"}</strong><span className="meta">cortes na batida</span></div>
          </div>
          {c.transicoes.length > 0 && (
            <div><span className="label">Transições</span>
              <div className="chips" style={{ marginTop: 6 }}>{c.transicoes.map((t, i) => <span key={i} className="tag tag-neutra">{TRANSICAO[t] ?? t}</span>)}</div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function Criativos({ ctx, aberto }: { ctx: Ctx; aberto?: string }) {
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [pub, setPub] = useState<number | null>(null);
  const camp = ctx.camp;
  if (!camp) return <div className="tela"><div className="panel vazio"><h2>Nenhuma campanha aberta</h2></div></div>;
  if (aberto) {
    const c = camp.criativos.find((x) => x.id === aberto);
    if (c) return <Detalhe c={c} ctx={ctx} />;
  }
  const passa = (c: Criativo) =>
    (pub === null || c.publico_n === pub) &&
    (filtro === "todos" || (filtro === "entregue" && c.etapa === "entregue") ||
     (filtro === "conferir" && (c.etapa === "aviso" || c.etapa === "erro")) || (filtro === "pendente" && !c.entregue));
  const conta = (f: Filtro) => camp.criativos.filter((c) => f === "todos" || (f === "entregue" && c.etapa === "entregue") ||
    (f === "conferir" && (c.etapa === "aviso" || c.etapa === "erro")) || (f === "pendente" && !c.entregue)).length;
  const publicos = [...new Map(camp.criativos.map((c) => [c.publico_n, c.publico])).entries()];
  const lista = camp.criativos.filter(passa);
  return (
    <div className="tela">
      <header className="tela-topo">
        <div><p className="eyebrow">Criativos</p><h1>{lista.length} <em>de {camp.criativos.length}</em></h1></div>
      </header>
      <div className="filtros" role="group" aria-label="Situação">
        {(["todos", "entregue", "conferir", "pendente"] as Filtro[]).map((f) => (
          <button key={f} className="filtro" aria-pressed={filtro === f} onClick={() => setFiltro(f)}>
            {{ todos: "Todos", entregue: "Entregues", conferir: "Para conferir", pendente: "Pendentes" }[f]}<span>{conta(f)}</span>
          </button>
        ))}
      </div>
      <div className="filtros" role="group" aria-label="Público">
        <button className="filtro" aria-pressed={pub === null} onClick={() => setPub(null)}>Todos os públicos</button>
        {publicos.map(([n, nome]) => (
          <button key={n} className="filtro" aria-pressed={pub === n} onClick={() => setPub(n)}>P{n} · {nome}</button>
        ))}
      </div>
      {lista.length ? <div className="grade">{lista.map((c) => <CardCriativo key={c.id} c={c} />)}</div> :
        <div className="panel vazio"><p>Nenhum criativo com esse filtro.</p></div>}
    </div>
  );
}
