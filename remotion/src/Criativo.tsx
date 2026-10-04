// O criativo inteiro, desenhado a partir do plano.json (via editor/motor_remotion.py).
import React from "react";
import {
  AbsoluteFill, Audio, Easing, OffthreadVideo, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { apresentacao } from "./transicoes";

export type Props = {
  fps: number; width: number; height: number; totalFrames: number; pushIn: number;
  shots: { src: string; trim: number; frames: number; zoom: number }[];
  transicoes: { tipo: string; xfade: string; frames: number }[];
  cards: { words: string[]; starts: number[]; from: number; to: number }[];
  layout: { legendaY: number; ctaY: number; tituloY: number; seloY: number };
  cta: { from: number; texto: string };
  preco: { from: number; texto: string } | null;
  titulo: { linhas: string[]; from: number; to: number } | null;
  narracao: string; musica: { src: string; volume: number } | null;
  sfx: { src: string; from: number; frames: number; volume: number }[];
  fala: [number, number][];
};

const AMARELO = "#FFE200", GRAFITE = "#111114";
const FONTE = "Montserrat, sans-serif";

// ── base: os planos com push-in, encadeados pelas transicoes ──────────────────
const Plano: React.FC<{ s: Props["shots"][number]; push: number }> = ({ s, push }) => {
  const f = useCurrentFrame();
  const z = s.zoom + push * Math.min(1, f / s.frames);
  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000" }}>
      <OffthreadVideo src={staticFile(s.src)} trimBefore={s.trim} muted
                      style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${z})` }} />
    </AbsoluteFill>
  );
};

// ── texto com contorno: uma copia grossa atras (contorno) + o preenchimento na frente ──
const Contornado: React.FC<{ children: string; cor: string; tam: number; peso?: number; borda?: number; style?: React.CSSProperties }> =
  ({ children, cor, tam, peso = 900, borda = 0.16, style }) => {
    const base: React.CSSProperties = { fontFamily: FONTE, fontWeight: peso, fontSize: tam, lineHeight: 1, letterSpacing: "-0.02em", gridArea: "1/1" };
    return (
      <span style={{ display: "inline-grid", ...style }}>
        <span aria-hidden style={{ ...base, position: "relative", zIndex: 0, color: GRAFITE, WebkitTextStroke: `${tam * borda}px ${GRAFITE}`,
                                   filter: `drop-shadow(0 ${tam * 0.06}px ${tam * 0.03}px rgba(0,0,0,.55))` }}>{children}</span>
        {/* ⛔ a copia de tras tem `filter` (sombra), e elemento com filter e' pintado ACIMA dos irmaos normais:
            sem posicao + z-index o preenchimento sumia por baixo do contorno (legenda virava borrao preto) */}
        <span style={{ ...base, color: cor, position: "relative", zIndex: 1 }}>{children}</span>
      </span>
    );
  };

// ── legenda: o cartao entra com mola; a palavra falada fica amarela e "pula" ──
const Cartao: React.FC<{ c: Props["cards"][number]; y: number; W: number }> = ({ c, y, W }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const abs = c.from + f;
  const entrada = spring({ frame: f, fps, config: { damping: 12, stiffness: 220, mass: 0.6 } });
  let ativa = 0; c.starts.forEach((s, i) => { if (abs >= s) ativa = i; });
  const tam = W * 0.073;
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", top: `${(y - 0.5) * 100}%` }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: `${tam * 0.12}px ${tam * 0.42}px`, maxWidth: W * 0.84,
                    transform: `scale(${0.7 + 0.3 * entrada}) translateY(${(1 - entrada) * 30}px)`, opacity: Math.min(1, entrada * 1.4) }}>
        {c.words.map((w, i) => {
          const dt = abs - c.starts[i];
          const pulo = i === ativa ? spring({ frame: dt, fps, config: { damping: 9, stiffness: 300, mass: 0.5 } }) : 1;
          // ⛔ escala nao empurra os vizinhos (transform nao mexe no layout): pulo contido + vao maior entre palavras
          const escala = i === ativa ? 1 + 0.12 * (1 - pulo) + 0.04 : 1;
          return (
            <Contornado key={i} cor={i === ativa ? AMARELO : "#fff"} tam={tam}
                        style={{ transform: `scale(${escala}) rotate(${i === ativa ? (1 - pulo) * -4 : 0}deg)`, textTransform: "uppercase" }}>
              {w.toUpperCase()}
            </Contornado>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── titulo do produto (modelo 2): desce com mola e sai encolhendo ──
const Titulo: React.FC<{ t: NonNullable<Props["titulo"]>; y: number; W: number }> = ({ t, y, W }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const dur = t.to - t.from;
  const ent = spring({ frame: f, fps, config: { damping: 11, stiffness: 160 } });
  const sai = interpolate(f, [dur - 8, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic) });
  return (
    <AbsoluteFill style={{ alignItems: "center", top: `${y * 100 - 5}%` }}>
      <div style={{ background: AMARELO, color: GRAFITE, borderRadius: W * 0.022, padding: `${W * 0.02}px ${W * 0.035}px`, textAlign: "center",
                    fontFamily: FONTE, fontWeight: 800, fontSize: W * 0.045, lineHeight: 1.25, textTransform: "uppercase",
                    boxShadow: "0 10px 30px rgba(0,0,0,.35)", transform: `translateY(${(1 - ent) * -140}%) scale(${sai})`, opacity: sai }}>
        {t.linhas.map((l, i) => <div key={i}>{l}</div>)}
      </div>
    </AbsoluteFill>
  );
};

// ── selo de preco: estoura girando ──
const Selo: React.FC<{ texto: string; y: number; W: number }> = ({ texto, y, W }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const ent = spring({ frame: f, fps, config: { damping: 8, stiffness: 260, mass: 0.6 } });
  const sai = interpolate(f, [70, 78], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ alignItems: "center", top: `${y * 100 - 4}%` }}>
      <div style={{ background: AMARELO, color: GRAFITE, border: `${W * 0.007}px solid ${GRAFITE}`, borderRadius: W * 0.02,
                    padding: `${W * 0.018}px ${W * 0.04}px`, fontFamily: FONTE, fontWeight: 900, fontSize: W * 0.075, textTransform: "uppercase",
                    transform: `scale(${ent * sai}) rotate(${-6 + (1 - ent) * 25}deg)`, boxShadow: "0 12px 30px rgba(0,0,0,.4)" }}>{texto}</div>
    </AbsoluteFill>
  );
};

// ── CTA: a pilula estoura e fica pulsando; as setas quicam ──
const Seta: React.FC<{ tam: number; fase: number }> = ({ tam, fase }) => {
  const f = useCurrentFrame();
  const y = Math.abs(Math.sin((f / 30) * Math.PI * 1.7 + fase)) * tam * 0.28;
  return (
    <svg width={tam} height={tam * 1.25} viewBox="0 0 40 50" style={{ transform: `translateY(${y}px)`, filter: "drop-shadow(0 4px 6px rgba(0,0,0,.4))" }}>
      <path d="M15 2h10v24h12L20 48 3 26h12z" fill="#E81C24" stroke="#3C0000" strokeWidth="2.5" strokeLinejoin="round" />
    </svg>
  );
};
const Cta: React.FC<{ texto: string; y: number; W: number }> = ({ texto, y, W }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig();
  const ent = spring({ frame: f, fps, config: { damping: 9, stiffness: 240, mass: 0.6 } });
  const pulso = 1 + 0.045 * Math.sin((f / fps) * Math.PI * 2.2) * Math.min(1, f / 15);
  return (
    <AbsoluteFill style={{ alignItems: "center", top: `${y * 100 - 4}%`, flexDirection: "row", justifyContent: "center", gap: W * 0.04, height: "auto" }}>
      <Seta tam={W * 0.075} fase={0} />
      <div style={{ background: AMARELO, color: GRAFITE, borderRadius: W * 0.03, padding: `${W * 0.022}px ${W * 0.06}px`,
                    fontFamily: FONTE, fontWeight: 800, fontSize: W * 0.06, textTransform: "uppercase", boxShadow: "0 12px 30px rgba(0,0,0,.4)",
                    transform: `scale(${ent * pulso})` }}>{texto}</div>
      <Seta tam={W * 0.075} fase={0.6} />
    </AbsoluteFill>
  );
};

export const Criativo: React.FC<Props> = (p) => {
  const { width: W, height: H } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <TransitionSeries>
        {p.shots.map((s, i) => (
          <React.Fragment key={i}>
            <TransitionSeries.Sequence durationInFrames={s.frames}><Plano s={s} push={p.pushIn} /></TransitionSeries.Sequence>
            {i < p.transicoes.length && p.transicoes[i].frames > 0 && (
              <TransitionSeries.Transition presentation={apresentacao(p.transicoes[i].tipo, p.transicoes[i].xfade, W, H, i)}
                                           timing={linearTiming({ durationInFrames: p.transicoes[i].frames })} />
            )}
          </React.Fragment>
        ))}
      </TransitionSeries>

      {p.titulo && <Sequence from={p.titulo.from} durationInFrames={p.titulo.to - p.titulo.from}><Titulo t={p.titulo} y={p.layout.tituloY} W={W} /></Sequence>}
      {p.cards.map((c, i) => (
        <Sequence key={i} from={c.from} durationInFrames={c.to - c.from}><Cartao c={c} y={p.layout.legendaY} W={W} /></Sequence>
      ))}
      {p.preco && <Sequence from={p.preco.from} durationInFrames={80}><Selo texto={p.preco.texto} y={p.layout.seloY} W={W} /></Sequence>}
      <Sequence from={p.cta.from}><Cta texto={p.cta.texto} y={p.layout.ctaY} W={W} /></Sequence>

      <Audio src={staticFile(p.narracao)} />
      {p.musica && (
        <Audio src={staticFile(p.musica.src)} loop
               volume={(f) => {
                 // a musica abaixa enquanto a voz fala (ducking) e some no fim
                 const falando = p.fala.some(([a, b]) => f >= a - 4 && f <= b + 4);
                 const fim = interpolate(f, [p.totalFrames - 25, p.totalFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
                 return p.musica!.volume * (falando ? 0.55 : 1) * fim;
               }} />
      )}
      {p.sfx.map((s, i) => (
        <Sequence key={i} from={s.from} durationInFrames={s.frames}>
          <Audio src={staticFile(s.src)} volume={(f) => s.volume * interpolate(f, [s.frames - 6, s.frames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
