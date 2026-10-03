import { AlertTriangle, ArrowRight, Check, Circle, FolderOpen, Play, RotateCcw, Square } from "lucide-react";
import { enviar, type Criativo, type Linha } from "../api";
import type { Ctx } from "../App";
import { CardCriativo, Girando, useAcao } from "../componentes/base";
import { link } from "../rota";
import { nomeBonito, numero } from "../textos";

// ⛔ o registro tem caminhos de pasta: no painel so' entra o que a pessoa entende
const tecnica = /[A-Za-z]:\\|\\\\|https?:\/\//;

function Atividade({ linhas }: { linhas: Linha[] }) {
  const visiveis = linhas.filter((l) => !tecnica.test(l.texto)).slice(0, 8);
  if (!visiveis.length) return <p className="meta" style={{ marginTop: 12 }}>Nada aconteceu desde que o painel abriu.</p>;
  return (
    <ul className="feed">
      {visiveis.map((l, i) => {
        const ruim = /ERRO|⚠|falhou|AVISOS/i.test(l.texto);
        const bom = /OK ->|entregue|terminou/i.test(l.texto);
        return (
          <li key={i}>
            <time>{l.hora}</time>
            {ruim ? <AlertTriangle size={14} className="warn" aria-hidden /> : bom ? <Check size={14} className="ok" aria-hidden /> :
              <Circle size={8} className="neutro" aria-hidden />}
            <span>{l.texto.replace(/\s+AVISOS:.*/, " · conferir")}</span>
          </li>
        );
      })}
    </ul>
  );
}

export function GruposPorPublico({ criativos }: { criativos: Criativo[] }) {
  const grupos = new Map<number, Criativo[]>();
  criativos.forEach((c) => grupos.set(c.publico_n, [...(grupos.get(c.publico_n) ?? []), c]));
  return (
    <>
      {[...grupos.entries()].map(([n, lst]) => (
        <section key={n} className="grupo" aria-label={`Público ${n}`}>
          <div className="grupo-topo">
            <span className="label">Público {n}</span>
            <h3>{lst[0].publico}</h3>
            <span className="meta">{lst.filter((c) => c.entregue).length}/{lst.length} entregues</span>
          </div>
          <div className="grade">{lst.map((c) => <CardCriativo key={c.id} c={c} />)}</div>
        </section>
      ))}
    </>
  );
}

export function Painel({ ctx }: { ctx: Ctx }) {
  const { estado, camp } = ctx;
  const { rodando, rodar } = useAcao(ctx.avisar);
  if (!camp) {
    return (
      <div className="tela"><div className="panel vazio">
        <img src="/logo.svg" alt="" width={64} height={64} />
        <h2>Nenhuma campanha aberta</h2>
        <p>Cole o mapa de ângulos de uma campanha nova ou escolha uma existente na barra lateral.</p>
        <a className="btn btn-primary" href={link.nova}>Nova campanha<ArrowRight size={16} aria-hidden /></a>
      </div></div>
    );
  }
  const cs = camp.criativos;
  const entregues = cs.filter((c) => c.entregue).length;
  const produzindo = cs.filter((c) => c.etapa === "narrando" || c.etapa === "renderizando").length;
  const fila = cs.filter((c) => c.etapa === "fila").length;
  const conferir = cs.filter((c) => c.etapa === "aviso" || c.etapa === "erro").length;
  const pct = cs.length ? Math.round((entregues / cs.length) * 100) : 0;
  const daqui = estado.produzindo === camp.nome;
  const ligado = estado.rodando && daqui;
  const pendentes = cs.filter((c) => !c.entregue).map((c) => c.id);
  const titulo = ligado ? (estado.parando ? "Terminando o criativo atual" : "Produzindo") :
                 estado.rodando ? "Outra campanha produzindo" : entregues === cs.length ? "Campanha pronta" : "Produção parada";
  const sub = ligado ? "Narração MiniMax → legenda → edição com transições, SFX e música. Você pode parar a qualquer momento." :
              estado.rodando ? `A campanha ${nomeBonito(estado.produzindo ?? "")} está na vez. Uma produção por vez.` :
              entregues === cs.length ? "Todos os criativos foram entregues. Refaça só os que quiser ajustar." :
              `${numero(pendentes.length)} criativo(s) esperando. Produza tudo ou abra um criativo para fazer só ele.`;

  return (
    <div className="tela">
      <header className="tela-topo">
        <div>
          <p className="eyebrow">Campanha · {camp.produto || nomeBonito(camp.nome)}</p>
          <h1>{numero(cs.length)} criativos <em>· {numero(entregues)} {entregues === 1 ? "entregue" : "entregues"}</em></h1>
        </div>
        <button className="btn btn-ghost" type="button" onClick={() => rodar("pasta", () => enviar("/api/abrir-pasta", { caminho: camp.entregues_dir }))}>
          <FolderOpen size={16} aria-hidden />Abrir pasta de entregues
        </button>
      </header>

      <section className={`panel pilot ${ligado ? "" : "is-off"}`} aria-label="Produção">
        <div className="pilot-l">
          <div className="pilot-state">
            <span className="live" aria-hidden />
            <div><h2>{titulo}</h2><p>{sub}</p></div>
            <div className="pilot-acoes">
              {ligado ? (
                <button className="btn btn-stop" type="button" disabled={estado.parando || !!rodando}
                        onClick={() => rodar("parar", () => enviar("/api/parar"), "Vou parar depois do criativo atual.")}>
                  {rodando === "parar" ? <Girando /> : <Square size={15} aria-hidden />}Parar
                </button>
              ) : (
                <>
                  {entregues > 0 && (
                    <button className="btn btn-quiet" type="button" disabled={estado.rodando || !camp.base_ok || !!rodando}
                            onClick={() => confirm("Refazer TODOS os criativos? Os vídeos atuais serão substituídos.") &&
                              rodar("tudo", () => enviar("/api/produzir", { campanha: camp.nome, refazer: true }), "Refazendo a campanha inteira.")}>
                      <RotateCcw size={15} aria-hidden />Refazer tudo
                    </button>
                  )}
                  <button className="btn btn-primary" type="button" disabled={estado.rodando || !camp.base_ok || !pendentes.length || !!rodando}
                          onClick={() => rodar("prod", () => enviar("/api/produzir", { campanha: camp.nome, ids: pendentes }), "Produção iniciada.")}>
                    {rodando === "prod" ? <Girando /> : <Play size={16} aria-hidden />}
                    {entregues ? `Produzir ${pendentes.length} pendentes` : "Produzir campanha"}
                  </button>
                </>
              )}
            </div>
          </div>
          <div className="metrics">
            <div><span className="label">Entregues</span><span className="num accent">{numero(entregues)}<small>/{numero(cs.length)}</small></span></div>
            <div><span className="label">Produzindo</span><span className="num">{numero(produzindo)}</span></div>
            <div><span className="label">Na fila</span><span className="num">{numero(fila)}</span></div>
            <div><span className="label">Para conferir</span><span className="num">{numero(conferir)}</span></div>
          </div>
          <div>
            <div className="linha-meta"><span className="meta">Campanha</span><span className="meta">{pct}% entregue</span></div>
            <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso da campanha">
              <span style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
        <div className="pilot-r">
          <span className="label">Agora há pouco</span>
          <Atividade linhas={estado.registro} />
        </div>
      </section>

      {!camp.base_ok && (
        <a className="panel attn" href={link.nova}>
          <span className="ico-box"><AlertTriangle size={18} aria-hidden /></span>
          <div><strong>Falta o vídeo base</strong><p>Escolha a pasta de clipes (ou o vídeo) de onde saem as imagens dos criativos.</p></div>
          <span className="btn btn-ghost">Escolher<ArrowRight size={16} aria-hidden /></span>
        </a>
      )}
      {camp.regra.length > 0 && (
        <div className="panel attn">
          <span className="ico-box"><AlertTriangle size={18} aria-hidden /></span>
          <div><strong>A copy foge da regra da operação em {camp.regra.length} ponto(s)</strong>
            <ul>{camp.regra.slice(0, 5).map((r, i) => <li key={i}>{r}</li>)}</ul></div>
        </div>
      )}

      <GruposPorPublico criativos={cs} />
    </div>
  );
}
