// Selos de confianca (garantia / WhatsApp / acesso imediato / compra segura) e confete do preco.
// Ideia dos blocos trust-strip / badge-pop / success-check do HyperFrames (Apache-2.0); desenho nosso.
// Regras de movimento (motion-doctrine): entra NA CORRENTE do video (da direita para a esquerda),
// com back.out ~1.6 (sem elastico), o icone se desenha DEPOIS de pousar, um brilho atravessa uma vez,
// e sai seguindo a mesma direcao em ~75% do tempo de entrada.
import React from "react";
import { AbsoluteFill, Easing, interpolate, random, useCurrentFrame } from "remotion";

export type SeloConf = { tipo: "garantia" | "whatsapp" | "imediato" | "seguro"; linhas: string[]; from: number; frames: number };

const GRAFITE = "#111114", AMARELO = "#FFE200";
const COR: Record<SeloConf["tipo"], string> = { garantia: "#19A974", whatsapp: "#1FAF5A", imediato: "#F2994A", seguro: "#2F80ED" };
const FONTE = "Montserrat, sans-serif";
const ENTRA = 12, SAI = 9;

const Icone: React.FC<{ tipo: SeloConf["tipo"]; desenho: number; tam: number }> = ({ tipo, desenho, tam }) => {
  const traco = { fill: "none", stroke: "#fff", strokeWidth: 3.2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const risco = (len: number) => ({ strokeDasharray: len, strokeDashoffset: len * (1 - desenho) });
  return (
    <svg width={tam} height={tam} viewBox="0 0 40 40">
      {tipo === "garantia" && <>
        <path d="M20 5 L32 9.5 V19 C32 26.5 26.8 32.2 20 35 C13.2 32.2 8 26.5 8 19 V9.5 Z" {...traco} style={risco(90)} />
        <path d="M14.5 19.5 L18.5 23.5 L26 15.5" {...traco} strokeWidth={3.6} style={risco(20)} />
      </>}
      {tipo === "whatsapp" && <>
        <path d="M20 7 C27.7 7 33 12.2 33 19 C33 25.8 27.7 31 20 31 C18 31 16.1 30.6 14.4 29.9 L8 32 L9.9 26.3 C8.1 24.3 7 21.8 7 19 C7 12.2 12.3 7 20 7 Z" {...traco} style={risco(95)} />
        <path d="M14.5 19 h0.1 M20 19 h0.1 M25.5 19 h0.1" {...traco} strokeWidth={4.2} style={{ opacity: desenho }} />
      </>}
      {tipo === "imediato" && <path d="M22 5 L11 22 H19 L17 35 L29 17 H21 Z" {...traco} style={risco(80)} />}
      {tipo === "seguro" && <>
        <rect x="10" y="18" width="20" height="15" rx="3" {...traco} style={risco(70)} />
        <path d="M14 18 V13.5 C14 10 16.7 7.5 20 7.5 C23.3 7.5 26 10 26 13.5 V18" {...traco} style={risco(30)} />
      </>}
    </svg>
  );
};

export const SeloConfianca: React.FC<{ s: SeloConf; y: number; W: number; H: number }> = ({ s, y, W, H }) => {
  const f = useCurrentFrame();
  const back = Easing.out(Easing.back(1.6));
  const ent = interpolate(f, [0, ENTRA], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const sai = interpolate(f, [s.frames - SAI, s.frames], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const x = (1 - back(ent)) * 18 - Easing.in(Easing.cubic)(sai) * 18;        // entra da direita, sai para a esquerda
  const opac = Math.min(1, ent * 3) * (1 - sai);
  const desenho = interpolate(f, [ENTRA - 3, ENTRA + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const brilho = interpolate(f, [ENTRA + 4, ENTRA + 20], [-60, 160], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const ic = W * 0.12;
  return (
    <AbsoluteFill style={{ alignItems: "center", top: H * y - ic * 0.6 }}>
      <div style={{ display: "flex", alignItems: "center", gap: W * 0.028, background: "#fff", border: `${W * 0.006}px solid ${GRAFITE}`,
                    borderRadius: ic, padding: `${W * 0.012}px ${W * 0.05}px ${W * 0.012}px ${W * 0.014}px`, position: "relative", overflow: "hidden",
                    transform: `translateX(${x}%) scale(${0.85 + 0.15 * back(ent)})`, opacity: opac, boxShadow: "0 14px 34px rgba(0,0,0,.38)" }}>
        <div style={{ width: ic, height: ic, borderRadius: ic, background: COR[s.tipo], display: "flex", alignItems: "center", justifyContent: "center",
                      boxShadow: `inset 0 -${W * 0.006}px 0 rgba(0,0,0,.18)` }}>
          <Icone tipo={s.tipo} desenho={desenho} tam={ic * 0.78} />
        </div>
        <div style={{ fontFamily: FONTE, color: GRAFITE, textTransform: "uppercase", lineHeight: 1.0 }}>
          {s.linhas.length > 1 && <div style={{ fontSize: W * 0.036, fontWeight: 800, opacity: 0.72, letterSpacing: W * 0.001 }}>{s.linhas[0]}</div>}
          <div style={{ fontSize: W * 0.066, fontWeight: 900 }}>{s.linhas[s.linhas.length - 1]}</div>
        </div>
        <div style={{ position: "absolute", top: 0, bottom: 0, left: `${brilho}%`, width: "28%", transform: "skewX(-20deg)",
                      background: "linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.75), rgba(255,255,255,0))" }} />
      </div>
    </AbsoluteFill>
  );
};

// confete curto que estoura do selo de preco (fisica simples, deterministica por semente)
export const Confete: React.FC<{ y: number; W: number; H: number; n?: number }> = ({ y, W, H, n = 28 }) => {
  const f = useCurrentFrame();
  const cores = [AMARELO, "#E81C24", "#1FAF5A", "#2F80ED", "#FFFFFF", "#F2994A"];
  if (f > 46) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {Array.from({ length: n }).map((_, i) => {
        const ang = (-90 + (random(`a${i}`) - 0.5) * 150) * Math.PI / 180;
        const vel = W * (0.018 + random(`v${i}`) * 0.022);
        const t = f;
        const px = W / 2 + Math.cos(ang) * vel * t;
        const py = H * y + Math.sin(ang) * vel * t + 0.5 * W * 0.0016 * t * t;   // gravidade
        const rot = random(`r${i}`) * 360 + t * (random(`w${i}`) - 0.5) * 40;
        const tam = W * (0.012 + random(`t${i}`) * 0.012);
        const op = interpolate(t, [30, 46], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        return <div key={i} style={{ position: "absolute", left: px, top: py, width: tam, height: tam * 0.55, background: cores[i % cores.length],
                                     transform: `rotate(${rot}deg)`, opacity: op, borderRadius: 2 }} />;
      })}
    </AbsoluteFill>
  );
};
