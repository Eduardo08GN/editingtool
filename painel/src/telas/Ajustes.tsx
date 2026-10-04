import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { enviar } from "../api";
import type { Ctx } from "../App";
import { Girando, useAcao } from "../componentes/base";

// ⭐ ajustes valem PARA A CAMPANHA ABERTA (ficam no campanha.json); o padrao geral fica em config/padrao.json
const PESOS_CARTOON = { iris: 5, pop_elastico: 5, boing: 5, balanco: 4, giro_cartoon: 4, circulo: 2, zoom_punch: 1.5, chicote_h: 1, chicote_v: 1, luz: 1, flash: 1 };

function Interruptor({ ligado, mudar, rotulo }: { ligado: boolean; mudar: (v: boolean) => void; rotulo: string }) {
  return <button type="button" role="switch" aria-checked={ligado} aria-label={rotulo} className="switch" onClick={() => mudar(!ligado)} />;
}

export function Ajustes({ ctx }: { ctx: Ctx }) {
  const camp = ctx.camp;
  const { rodando, rodar } = useAcao(ctx.avisar);
  const ef = camp?.efetivo;
  const [voz, setVoz] = useState(ef?.voz ?? "");
  const [vel, setVel] = useState(ef?.velocidade ?? 1);
  const [modelo, setModelo] = useState(ef?.modelo ?? "alternar");
  const [motor, setMotor] = useState(ef?.motor ?? "remotion");
  const [gancho, setGancho] = useState(ef?.motion_graphics?.gancho ?? true);
  const [fecho, setFecho] = useState(ef?.motion_graphics?.fecho ?? true);
  const [musica, setMusica] = useState(ef?.musica === "auto");
  const [sfx, setSfx] = useState(ef?.sfx ?? true);
  const temCartoon = !!ef?.transicoes?.pesos && Object.keys(ef.transicoes.pesos).some((k) => k === "iris");
  const [estilo, setEstilo] = useState<"cartoon" | "padrao">(temCartoon ? "cartoon" : "padrao");
  const [prop, setProp] = useState(ef?.transicoes?.proporcao ?? 0.6);
  const [autoPub, setAutoPub] = useState(camp?.publicar?.auto !== false);
  useEffect(() => {
    if (!ef) return;
    setVoz(ef.voz); setVel(ef.velocidade); setModelo(ef.modelo ?? "alternar"); setMotor(ef.motor ?? "remotion");
    setGancho(ef.motion_graphics?.gancho ?? true); setFecho(ef.motion_graphics?.fecho ?? true); setMusica(ef.musica === "auto"); setSfx(ef.sfx);
    setEstilo(ef.transicoes?.pesos && "iris" in ef.transicoes.pesos ? "cartoon" : "padrao"); setProp(ef.transicoes?.proporcao ?? 0.6);
    setAutoPub(camp?.publicar?.auto !== false);
  }, [camp?.nome]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!camp) return <div className="tela"><div className="panel vazio"><h2>Abra uma campanha para ajustar</h2></div></div>;

  const salvar = () => rodar("salvar", async () => {
    await enviar(`/api/campanhas/${encodeURIComponent(camp.nome)}/ajustes`, {
      tts: { voz: voz.trim(), velocidade: Number(vel) },
      modelo,
      motor,
      video: { motion_graphics: { gancho, fecho } },
      audio: { musica: musica ? "auto" : "", sfx },
      transicoes: { proporcao: Number(prop), pesos: estilo === "cartoon" ? PESOS_CARTOON : {} },
      ...(camp.publicar?.repo ? { publicar: { auto: autoPub } } : {}),
    });
    ctx.recarregar();
  }, "Ajustes salvos. Valem para os próximos criativos produzidos (use Refazer para aplicar nos prontos).");

  return (
    <div className="tela">
      <header className="tela-topo">
        <div><p className="eyebrow">Ajustes · {camp.produto || camp.nome}</p><h1>Como os criativos <em>saem</em></h1>
          <p className="lead">Estes ajustes valem só para esta campanha.</p></div>
        <button className="btn btn-primary" type="button" disabled={!!rodando} onClick={salvar}>
          {rodando === "salvar" ? <Girando /> : <Save size={16} aria-hidden />}Salvar ajustes
        </button>
      </header>

      {ef?.turbo && (
        <div className="panel attn turbo-aviso">
          <span className="ico-box">⚡</span>
          <div><strong>Modo Turbo ligado</strong>
            <p>Motor Remotion, gancho e fecho animados, motion blur, corte na batida, música e SFX estão no máximo, valendo por cima dos itens abaixo. Voz, modelo e estilo das transições continuam os seus. Desligue no botão do Painel.</p></div>
        </div>
      )}

      <section className="panel bloco" aria-label="Voz">
        <h3>Voz (MiniMax)</h3>
        <div className="duas">
          <label className="campo-grupo"><span className="label">ID da voz</span>
            <input className="campo" value={voz} onChange={(e) => setVoz(e.target.value)} style={{ fontFamily: "var(--ow-font-mono)", fontSize: 13 }} /></label>
          <label className="campo-grupo"><span className="label">Velocidade natural ({Number(vel).toFixed(2)}×)</span>
            <input type="range" min={0.9} max={1.25} step={0.01} value={vel} onChange={(e) => setVel(Number(e.target.value))} /></label>
        </div>
        <p className="meta">A ferramenta ajusta a velocidade só um pouco (1,00 a 1,12) para encaixar no tempo da copy, sem mudar a cara da voz.</p>
      </section>

      <section className="panel bloco" aria-label="Motor de render">
        <h3>Motor de render</h3>
        <div className="seg" role="group" aria-label="Motor de render">
          <button type="button" aria-pressed={motor === "remotion"} onClick={() => setMotor("remotion")}>Remotion · legenda e gráficos animados</button>
          <button type="button" aria-pressed={motor === "ffmpeg"} onClick={() => setMotor("ffmpeg")}>Atual · mais rápido</button>
        </div>
        <p className="meta">Mesmos cortes, voz, música e SFX. O Remotion anima a legenda (a palavra falada pula), o título, o selo e o CTA, e tem transições com mola. Demora ~2 min por criativo (o atual, ~1 min).</p>
      </section>

      <section className="panel bloco" aria-label="Motion graphics">
        <h3>Motion graphics</h3>
        {motor !== "remotion" && <p className="meta">Só aparecem com o motor Remotion. No motor atual, estes ajustes ficam guardados mas não entram no vídeo.</p>}
        <div className="switch-linha"><div><strong>Gancho animado</strong>
          <p className="meta">Nos primeiros ~2 s: o ponto conta até o número do produto (ex.: 0 → 70), vira a pílula com o rótulo e sobe para virar o título.</p></div>
          <Interruptor ligado={gancho} mudar={setGancho} rotulo="Gancho animado" /></div>
        <div className="switch-linha"><div><strong>Cartão de fecho</strong>
          <p className="meta">No “clique em saiba mais”: o vídeo vira um cartão, o nome do produto se escreve e o botão SAIBA MAIS se forma com as setas.</p></div>
          <Interruptor ligado={fecho} mudar={setFecho} rotulo="Cartão de fecho" /></div>
      </section>

      <section className="panel bloco" aria-label="Edição">
        <h3>Edição</h3>
        <div className="campo-grupo"><span className="label">Modelo de criativo</span>
          <div className="seg" role="group" aria-label="Modelo">
            {[["alternar", "Alternar 1 e 2"], ["1", "Modelo 1 · CTA embaixo"], ["2", "Modelo 2 · título e CTA no topo"]].map(([v, t]) => (
              <button key={v} type="button" aria-pressed={modelo === v} onClick={() => setModelo(v)}>{t}</button>
            ))}
          </div>
        </div>
        <div className="campo-grupo"><span className="label">Estilo das transições</span>
          <div className="seg" role="group" aria-label="Estilo das transições">
            <button type="button" aria-pressed={estilo === "cartoon"} onClick={() => setEstilo("cartoon")}>Cartoon (íris, boing, pop, balanço)</button>
            <button type="button" aria-pressed={estilo === "padrao"} onClick={() => setEstilo("padrao")}>Editor (chicote, zoom, flash, luz)</button>
          </div>
        </div>
        <label className="campo-grupo"><span className="label">Cortes com transição animada · {Math.round(prop * 100)}%</span>
          <input type="range" min={0.2} max={1} step={0.05} value={prop} onChange={(e) => setProp(Number(e.target.value))} /></label>
      </section>

      <section className="panel bloco" aria-label="Áudio">
        <h3>Áudio</h3>
        <div className="switch-linha"><div><strong>Música automática</strong><p className="meta">A ferramenta lê o ângulo e escolhe a faixa da Meta Sound Collection.</p></div>
          <Interruptor ligado={musica} mudar={setMusica} rotulo="Música automática" /></div>
        {camp.publicar?.repo && (
          <div className="switch-linha"><div><strong>Enviar para o GitHub ao terminar</strong>
            <p className="meta">{camp.publicar.repo.replace("https://github.com/", "")} → {camp.publicar.pasta}</p></div>
            <Interruptor ligado={autoPub} mudar={setAutoPub} rotulo="Enviar para o GitHub ao terminar" /></div>
        )}
        <div className="switch-linha"><div><strong>Efeitos sonoros</strong><p className="meta">Nas transições, no preço e no CTA, só do pool liberado.</p></div>
          <Interruptor ligado={sfx} mudar={setSfx} rotulo="Efeitos sonoros" /></div>
      </section>
    </div>
  );
}
