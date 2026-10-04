// Motion graphics do criativo: GANCHO animado (abertura) e CARTAO DE FECHO (CTA).
// Desenho proprio, nas cores do produto. Tudo calculado a partir do quadro (sem keyframes),
// e dentro da zona segura da Meta (entre 14% e 65% da altura).
import React from "react";
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

const AMARELO = "#FFE200", GRAFITE = "#111114", CREME = "#FFF4DC";
const PASTEIS = ["#F4B6A6", "#A8D5E2", "#B9DFA6", "#F6D58E", "#C9B6E8", "#F7C6D9"];
const FONTE = "Montserrat, sans-serif";
const clamp = { extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const };

export type Gancho = { numero: string; rotulo: string; frames: number; tituloY: number };
export type Fecho = { from: number; linhas: string[]; cta: string };

// ── GANCHO: ponto -> contador 0..N -> pilula com o rotulo -> sobe e vira o titulo ──
export const GanchoAnimado: React.FC<{ g: Gancho }> = ({ g }) => {
  const f = useCurrentFrame(); const { fps, width: W, height: H } = useVideoConfig();
  const D = W * 0.34;                                                    // diametro do circulo
  const nasce = spring({ frame: f, fps, config: { damping: 9, stiffness: 210, mass: 0.7 } });
  const alvo = parseInt(g.numero, 10) || 0;
  const conta = Math.round(alvo * Easing.out(Easing.cubic)(Math.min(1, f / 22)));
  const estica = spring({ frame: f - 24, fps, config: { damping: 14, stiffness: 170 } });     // circulo -> pilula
  const larg = interpolate(estica, [0, 1], [D, W * 0.78]);
  const rot = spring({ frame: f - 30, fps, config: { damping: 15, stiffness: 160 } });         // rotulo sobe da mascara
  const sai = interpolate(f, [g.frames - 14, g.frames], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const yCentro = interpolate(sai, [0, 1], [0.42, g.tituloY]);
  const escala = interpolate(sai, [0, 1], [1, 0.55]) * nasce;
  const veu = interpolate(f, [0, 6, g.frames - 12, g.frames], [0, 0.5, 0.5, 0], clamp);
  const pulso = 1 + 0.06 * Math.max(0, 1 - Math.abs(f - 22) / 6);       // "batida" quando o contador chega no N
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 42%, rgba(0,0,0,${veu * 0.4}), rgba(0,0,0,${veu}))` }} />
      {/* faiscas quando o numero chega */}
      {f >= 20 && f < 34 && Array.from({ length: 10 }).map((_, i) => {
        const a = (i / 10) * Math.PI * 2; const p = (f - 20) / 14;
        const r0 = D * 0.62 + p * D * 0.5, r1 = r0 + D * 0.16 * (1 - p);
        return (
          <svg key={i} style={{ position: "absolute", left: 0, top: 0 }} width={W} height={H}>
            <line x1={W / 2 + Math.cos(a) * r0} y1={H * 0.42 + Math.sin(a) * r0} x2={W / 2 + Math.cos(a) * r1} y2={H * 0.42 + Math.sin(a) * r1}
                  stroke={AMARELO} strokeWidth={W * 0.012} strokeLinecap="round" opacity={1 - p} />
          </svg>
        );
      })}
      <div style={{ position: "absolute", left: "50%", top: `${yCentro * 100}%`, transform: `translate(-50%, -50%) scale(${escala * pulso})`,
                    width: larg, height: D, borderRadius: D / 2, background: AMARELO, boxShadow: "0 24px 60px rgba(0,0,0,.45)",
                    display: "flex", alignItems: "center", justifyContent: "center", gap: W * 0.03, overflow: "hidden",
                    opacity: interpolate(sai, [0.75, 1], [1, 0], clamp) }}>
        <span style={{ fontFamily: FONTE, fontWeight: 900, fontSize: D * 0.5, color: GRAFITE, lineHeight: 1, letterSpacing: "-0.04em",
                       fontVariantNumeric: "tabular-nums" }}>{conta}</span>
        <div style={{ overflow: "hidden", maxWidth: interpolate(estica, [0, 1], [0, W * 0.5]) }}>
          <div style={{ transform: `translateY(${(1 - rot) * 110}%)`, fontFamily: FONTE, fontWeight: 900, fontSize: D * 0.17, color: GRAFITE,
                        lineHeight: 1.05, textTransform: "uppercase", whiteSpace: "nowrap" }}>
            {g.rotulo.split(" ").map((w, i) => <div key={i}>{w}</div>)}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// fundo do fecho: creme com mini-cards pasteis flutuando (os cards do produto, estilizados)
const FundoCards: React.FC<{ g: number }> = ({ g }) => {
  const { width: W, height: H } = useVideoConfig();
  const cols = 5, linhas = 9, cw = W / cols, ch = H / linhas;
  return (
    <AbsoluteFill style={{ background: CREME, overflow: "hidden" }}>
      {Array.from({ length: cols * linhas }).map((_, i) => {
        const c = i % cols, l = Math.floor(i / cols);
        const atraso = (c + l) * 1.2;
        const ent = spring({ frame: g - atraso, fps: 30, config: { damping: 13, stiffness: 120 } });
        const flutua = Math.sin((g + i * 7) / 18) * 6;
        return (
          <div key={i} style={{ position: "absolute", left: c * cw + cw * 0.18, top: l * ch + ch * 0.14 + flutua, width: cw * 0.64, height: ch * 0.72,
                                borderRadius: cw * 0.08, border: `${W * 0.004}px solid ${PASTEIS[i % PASTEIS.length]}`, background: "rgba(255,255,255,.55)",
                                transform: `scale(${ent}) rotate(${((i * 37) % 13) - 6}deg)`, opacity: 0.85 * ent }} />
        );
      })}
    </AbsoluteFill>
  );
};

// a cena do video encolhe para um cartao no meio do fecho (envolve a camada de video)
export const VideoQueEncolhe: React.FC<{ fecho: Fecho | null; children: React.ReactNode }> = ({ fecho, children }) => {
  const f = useCurrentFrame(); const { fps, width: W } = useVideoConfig();
  if (!fecho || f < fecho.from) return <>{children}</>;
  const g = f - fecho.from;
  const k = spring({ frame: g, fps, config: { damping: 15, stiffness: 140 } });
  const escala = interpolate(k, [0, 1], [1, 0.48]);
  const y = interpolate(k, [0, 1], [0, -1]);            // cartao entre ~25% e ~73% da altura: abaixo do titulo
  return (
    <AbsoluteFill>
      <FundoCards g={g} />
      <AbsoluteFill style={{ transform: `translateY(${y}%) scale(${escala}) rotate(${interpolate(k, [0, 1], [0, -2])}deg)`,
                             borderRadius: interpolate(k, [0, 1], [0, W * 0.06]), overflow: "hidden",
                             boxShadow: `0 ${40 * k}px ${90 * k}px rgba(0,0,0,${0.45 * k})`, border: `${W * 0.012 * k}px solid #fff` }}>
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ── FECHO: nome do produto se escreve, ponto vira o botao SAIBA MAIS, setas apontam ──
export const FechoAnimado: React.FC<{ fecho: Fecho }> = ({ fecho }) => {
  const g = useCurrentFrame(); const { fps, width: W, height: H } = useVideoConfig();
  const palavras = fecho.linhas.map((l) => l.split(" "));
  let n = 0;
  const nasceBotao = spring({ frame: g - 14, fps, config: { damping: 10, stiffness: 220, mass: 0.6 } });
  const estica = spring({ frame: g - 20, fps, config: { damping: 13, stiffness: 180 } });
  const texto = spring({ frame: g - 26, fps, config: { damping: 14, stiffness: 180 } });
  const pulso = 1 + 0.04 * Math.sin((g / fps) * Math.PI * 2.4) * (g > 34 ? 1 : 0);
  const bh = W * 0.15, bw = interpolate(estica, [0, 1], [bh, W * 0.62]);
  const seta = (lado: number) => {
    const ent = spring({ frame: g - 30, fps, config: { damping: 11, stiffness: 200 } });
    const quica = Math.abs(Math.sin((g / fps) * Math.PI * 1.8)) * W * 0.02;
    return (
      <svg width={W * 0.09} height={W * 0.09} viewBox="0 0 40 40"
           style={{ position: "absolute", top: H * 0.585 - W * 0.045, left: W / 2 + lado * (bw / 2 + W * 0.075) - W * 0.045,
                    transform: `translateX(${lado * quica}px) scale(${ent}) rotate(${lado < 0 ? 180 : 0}deg)`, filter: "drop-shadow(0 4px 6px rgba(0,0,0,.35))" }}>
        <path d="M4 20 L22 4 L22 13 L36 13 L36 27 L22 27 L22 36 Z" fill="#E81C24" stroke="#3C0000" strokeWidth="2.2" strokeLinejoin="round" />
      </svg>
    );
  };
  return (
    <AbsoluteFill>
      {/* nome do produto: cada palavra sobe da sua mascara, em sequencia */}
      <div style={{ position: "absolute", top: H * 0.148, left: 0, right: 0, textAlign: "center" }}>
        {palavras.map((linha, li) => (
          <div key={li} style={{ display: "flex", justifyContent: "center", gap: W * 0.022, marginBottom: W * 0.006 }}>
            {linha.map((w, wi) => {
              const k = spring({ frame: g - 4 - 2.2 * n++, fps, config: { damping: 14, stiffness: 190 } });
              return (
                <span key={wi} style={{ overflow: "hidden", display: "inline-block", paddingBottom: W * 0.006 }}>
                  <span style={{ display: "inline-block", transform: `translateY(${(1 - k) * 110}%)`, fontFamily: FONTE,
                                 fontWeight: li === 0 ? 900 : 800, fontSize: li === 0 ? W * 0.074 : W * 0.05, color: GRAFITE,
                                 textTransform: "uppercase", letterSpacing: "-0.02em", lineHeight: 1 }}>{w}</span>
                </span>
              );
            })}
          </div>
        ))}
      </div>
      {/* o ponto que vira o botao */}
      <div style={{ position: "absolute", left: "50%", top: H * 0.585, width: bw, height: bh, borderRadius: bh / 2, background: AMARELO,
                    border: `${W * 0.007}px solid ${GRAFITE}`, transform: `translate(-50%, -50%) scale(${nasceBotao * pulso})`,
                    boxShadow: "0 18px 40px rgba(0,0,0,.3)", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
        <span style={{ transform: `translateY(${(1 - texto) * 120}%)`, fontFamily: FONTE, fontWeight: 900, fontSize: W * 0.068,
                       color: GRAFITE, textTransform: "uppercase", whiteSpace: "nowrap", letterSpacing: "-0.01em" }}>{fecho.cta}</span>
      </div>
      {seta(-1)}{seta(1)}
    </AbsoluteFill>
  );
};
