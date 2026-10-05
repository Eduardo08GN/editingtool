// Transicoes do EditingTool desenhadas no Remotion.
// Nativas do Remotion (estaveis): iris, slide, wipe, clock-wipe, fade.
// Cartoon / editor feitas aqui com curvas de mola: pop, boing, balanco, giro, chicote, flash, desfoque.
import React from "react";
import { AbsoluteFill, Easing } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { iris } from "@remotion/transitions/iris";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { clockWipe } from "@remotion/transitions/clock-wipe";
import { fade } from "@remotion/transitions/fade";

type Estilo = { eixo?: "x" | "y"; sinal?: 1 | -1 };
type P = TransitionPresentationComponentProps<Estilo>;

const voltaComMola = Easing.out(Easing.back(2.2));     // passa do ponto e volta: o "pop" de desenho animado
const amortecido = (p: number, ciclos: number) => Math.sin(p * Math.PI * ciclos) * (1 - p);

function Camada({ style, children }: { style: React.CSSProperties; children: React.ReactNode }) {
  return <AbsoluteFill style={{ ...style, willChange: "transform, opacity, filter" }}>{children}</AbsoluteFill>;
}

// POP: a cena nova "nasce" pequena e estoura com mola; a velha cresce e some
const Pop: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p }) =>
  d === "entering"
    ? <Camada style={{ transform: `scale(${0.55 + 0.45 * voltaComMola(p)})`, opacity: Math.min(1, p * 3) }}>{children}</Camada>
    : <Camada style={{ transform: `scale(${1 + 0.18 * p})`, opacity: 1 - p, filter: `blur(${p * 10}px)` }}>{children}</Camada>;

// BOING: entra de baixo esmagando e esticando, como borracha
const Boing: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p }) => {
  if (d === "exiting") return <Camada style={{ opacity: 1 - p }}>{children}</Camada>;
  const s = amortecido(p, 2.5) * 0.22;
  return <Camada style={{ transform: `translateY(${(1 - voltaComMola(p)) * 100}%) scale(${1 + s}, ${1 - s})`, transformOrigin: "50% 100%" }}>{children}</Camada>;
};

// BALANCO: chega inclinada e balanca como gelatina ate' parar
const Balanco: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p, passedProps }) => {
  const sinal = passedProps.sinal ?? 1;
  if (d === "exiting") return <Camada style={{ transform: `rotate(${-sinal * 6 * p}deg) scale(${1 + 0.2 * p})`, opacity: 1 - p }}>{children}</Camada>;
  return <Camada style={{ transform: `rotate(${sinal * 9 * amortecido(p, 3)}deg) scale(${1.22 - 0.22 * voltaComMola(p)})` }}>{children}</Camada>;
};

// GIRO: a velha gira e borra para fora, a nova vem girando do outro lado
const Giro: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p, passedProps }) => {
  const sinal = passedProps.sinal ?? 1;
  return d === "exiting"
    ? <Camada style={{ transform: `rotate(${sinal * 28 * p}deg) scale(${1 + 0.45 * p})`, filter: `blur(${p * 14}px)`, opacity: 1 - p * 0.6 }}>{children}</Camada>
    : <Camada style={{ transform: `rotate(${-sinal * 28 * (1 - p)}deg) scale(${1.45 - 0.45 * voltaComMola(p)})`, filter: `blur(${(1 - p) * 14}px)`, opacity: Math.min(1, p * 2.5) }}>{children}</Camada>;
};

// CHICOTE: whip pan de verdade — empurra a cena com borrao de movimento no eixo do movimento
const Chicote: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p, passedProps }) => {
  const eixo = passedProps.eixo ?? "x"; const sinal = passedProps.sinal ?? 1;
  const ease = Easing.inOut(Easing.cubic)(p);
  const borrao = Math.sin(p * Math.PI) * 26;
  const pos = d === "exiting" ? -sinal * ease * 100 : sinal * (1 - ease) * 100;
  const t = eixo === "x" ? `translateX(${pos}%)` : `translateY(${pos}%)`;
  return <Camada style={{ transform: t, filter: `blur(${borrao}px)` }}>{children}</Camada>;
};

// FLASH: troca no meio de um estouro branco
const Flash: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p }) =>
  d === "exiting" ? <Camada style={{}}>{children}</Camada> : (
    <AbsoluteFill>
      <Camada style={{ opacity: p }}>{children}</Camada>
      <AbsoluteFill style={{ background: "#fff", opacity: Math.sin(p * Math.PI) * 0.92 }} />
    </AbsoluteFill>
  );

// DESFOQUE: cruza as cenas passando por um desfoque forte
const Desfoque: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p }) => {
  const b = Math.sin(p * Math.PI) * 22;
  return <Camada style={{ opacity: d === "entering" ? p : 1, filter: `blur(${b}px)` }}>{children}</Camada>;
};

// CORTE NA CURVA ("cut the curve", HyperFrames/Apache-2.0): a velha acelera para o lado (power4.in, ~12% da
// tela, borrao subindo ate' 18px), o corte cai no PICO da velocidade, e a nova chega do mesmo lado
// desacelerando (power4.out): as duas metades de um power4.inOut, entao a velocidade casa no corte.
// Nunca as duas visiveis ao mesmo tempo. A faixa que o deslocamento expoe mostra a propria cena
// desfocada (nada de borda preta) e le-se como borrao de movimento.
const CorteCurva: React.FC<P> = ({ children, presentationDirection: d, presentationProgress: p, passedProps }) => {
  const sinal = passedProps.sinal ?? 1;              // 1 = a corrente vai para a esquerda
  const viagem = 12, borraoMax = 18;
  let x = 0, b = 0;
  if (d === "exiting") {
    if (p >= 0.5) return null;
    const e = Math.pow(p / 0.5, 4);
    x = -sinal * viagem * e; b = borraoMax * e;
  } else {
    if (p < 0.5) return null;
    const q = (p - 0.5) / 0.5; const e = 1 - Math.pow(1 - q, 4);
    x = sinal * viagem * (1 - e); b = borraoMax * (1 - e);
  }
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: "scale(1.3)", filter: "blur(40px)" }}>{children}</AbsoluteFill>
      <Camada style={{ transform: `translateX(${x}%)`, filter: `blur(${b}px)` }}>{children}</Camada>
    </AbsoluteFill>
  );
};

const custom = (c: React.FC<P>, props: Estilo = {}): TransitionPresentation<Estilo> => ({ component: c, props });

const DIR: Record<string, "from-left" | "from-right" | "from-top" | "from-bottom"> = {
  slideleft: "from-right", slideright: "from-left", slideup: "from-bottom", slidedown: "from-top",
  coverleft: "from-right", coverright: "from-left", coverup: "from-bottom", coverdown: "from-top",
  revealleft: "from-right", revealright: "from-left", revealup: "from-bottom", revealdown: "from-top",
  horzopen: "from-left", vertopen: "from-top",
};

// o pool do Python (editor/transicoes.py) -> uma apresentacao do Remotion
export function apresentacao(tipo: string, xfade: string, w: number, h: number, i: number, sinalDoPlano?: number): TransitionPresentation<any> {
  // ⭐ o sentido vem do plano (o MESMO no video todo); antes alternava a cada corte (pingue-pongue)
  const sinal = ((sinalDoPlano ?? (i % 2 ? -1 : 1)) < 0 ? -1 : 1) as 1 | -1;
  switch (tipo) {
    case "iris": case "circulo": return iris({ width: w, height: h });
    case "pop_elastico": case "zoom_punch": return custom(Pop);
    case "boing": case "aperto": case "impacto": return custom(Boing);
    case "balanco": return custom(Balanco, { sinal });
    case "giro_cartoon": case "giro": return custom(Giro, { sinal });
    case "chicote_h": return custom(Chicote, { eixo: "x", sinal: xfade === "smoothright" ? -1 : 1 });
    case "chicote_v": return custom(Chicote, { eixo: "y", sinal: xfade === "smoothdown" ? -1 : 1 });
    case "deslize": return slide({ direction: DIR[xfade] ?? "from-right" });
    case "cortina": case "revelar": case "abre": return wipe({ direction: DIR[xfade] ?? "from-left" });
    case "radial": return clockWipe({ width: w, height: h });
    case "flash": case "luz": return custom(Flash);
    case "desfoque": return custom(Desfoque);
    case "corte_curva": return custom(CorteCurva, { sinal: xfade === "smoothright" ? -1 : 1 });
    default: return fade();
  }
}
