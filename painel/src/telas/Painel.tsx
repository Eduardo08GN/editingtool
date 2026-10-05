import { AlertTriangle, ArrowRight, Check, Circle, FolderOpen, CloudUpload, Play, RotateCcw, Square, Zap } from "lucide-react";
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
        const bom = /OK ->|OK —|entregue|terminou/i.test(l.texto);
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

// ⭐ a faixa do Modo Turbo: o que esta ligado, o que nao se aplica (e por que) e quantos ja sairam no turbo
function FaixaTurbo({ ctx }: { ctx: Ctx }) {
  const camp = ctx.camp!;
  const { rodando, rodar } = useAcao(ctx.avisar);
  const feitos = camp.criativos.filter((c) => c.turbo && c.entregue).length;
  const faltam = camp.criativos.filter((c) => !c.turbo).map((c) => c.id);
  return (
    <div className="faixa-turbo">
      <div className="faixa-topo">
        <span className="raio" aria-hidden><Zap size={18} /></span>
        <div>
          <strong>Turbo ativo</strong>
          <p className="meta">{feitos}/{camp.criativos.length} criativos já saíram no Turbo</p>
        </div>
        {faltam.length > 0 && !ctx.estado.rodando && (
          <button className="btn btn-primary btn-sm" type="button" disabled={!camp.base_ok || !!rodando}
                  onClick={() => rodar("turbo-refazer", () => enviar("/api/produzir", { campanha: camp.nome, ids: faltam, refazer: true }),
                                      `Refazendo ${faltam.length} criativo(s) no Turbo.`)}>
            {rodando === "turbo-refazer" ? <Girando /> : <Zap size={14} aria-hidden />}Aplicar nos {faltam.length} restantes
          </button>
        )}
      </div>
      <ul className="recursos">
        {camp.turbo_recursos.map((r, i) => (
          <li key={r.id} className={r.ativo ? "on" : "off"} style={{ animationDelay: `${i * 70}ms` }} title={r.nota || undefined}>
            {r.ativo ? <Check size={13} strokeWidth={2.6} aria-hidden /> : <span className="x" aria-hidden>–</span>}
            {r.nome}{r.nota && !r.ativo ? <em> · {r.nota}</em> : null}
          </li>
        ))}
      </ul>
    </div>
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
        <div className="acoes">
          <button className="btn btn-turbo" type="button" aria-pressed={camp.efetivo.turbo} disabled={!!rodando}
                  title="Liga todos os recursos tops quando pertinentes: Remotion, gancho e fecho animados, emojis, selos de confiança, câmera lenta por IA, corte na batida, música recortada e SFX no pico"
                  onClick={() => rodar("turbo", async () => {
                    await enviar(`/api/campanhas/${encodeURIComponent(camp.nome)}/ajustes`, { turbo: !camp.efetivo.turbo });
                    ctx.recarregar();
                  }, camp.efetivo.turbo ? "Modo Turbo desligado: valem os Ajustes da campanha."
                                        : "Modo Turbo ligado: os próximos criativos saem com todos os recursos tops. Use Refazer para aplicar nos prontos.")}>
            {rodando === "turbo" ? <Girando /> : <Zap size={16} aria-hidden />}Modo Turbo{camp.efetivo.turbo ? " · ligado" : ""}
          </button>
          {/* ⭐ sempre a vista; sem destino (nem herdado de outra campanha do produto) fica desligado e explica */}
          {(
            <button className="btn btn-ghost" type="button" disabled={estado.rodando || !entregues || !!rodando || !camp.publicar?.repo}
                    title={camp.publicar?.repo ? `${camp.publicar.repo} → ${camp.publicar.pasta}`
                                               : "Sem destino no GitHub: rode uma vez  edt publicar <campanha> --repo <url> --pasta <pasta>"}
                    onClick={() => rodar("pub", () => enviar("/api/publicar", { caminho: camp.nome }), "Enviando para o GitHub. Acompanhe em “Agora há pouco”.")}>
              {rodando === "pub" ? <Girando /> : <CloudUpload size={16} aria-hidden />}Enviar para o GitHub
            </button>
          )}
          <button className="btn btn-ghost" type="button" onClick={() => rodar("pasta", () => enviar("/api/abrir-pasta", { caminho: camp.entregues_dir }))}>
            <FolderOpen size={16} aria-hidden />Abrir pasta de entregues
          </button>
        </div>
      </header>

      <section className={`panel pilot ${ligado ? "" : "is-off"}${camp.efetivo.turbo ? " pilot-turbo" : ""}`} aria-label="Produção">
        <div className="pilot-l">
          {camp.efetivo.turbo && <FaixaTurbo ctx={ctx} />}
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
