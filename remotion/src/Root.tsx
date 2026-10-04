import React from "react";
import { Composition, continueRender, delayRender, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";
import { Criativo, type Props } from "./Criativo";

// Montserrat (OFL) vem do proprio projeto: o render nao depende de fonte instalada na maquina
const espera = delayRender("fonte Montserrat");
loadFont({ family: "Montserrat", url: staticFile("fonts/Montserrat.ttf"), weight: "100 900" })
  .then(() => continueRender(espera))
  .catch((e) => { console.error(e); continueRender(espera); });

const vazio: Props = {
  fps: 30, width: 1080, height: 1920, totalFrames: 90, pushIn: 0.045, shots: [], transicoes: [], cards: [],
  layout: { legendaY: 0.8, ctaY: 0.885, tituloY: 0.15, seloY: 0.22 }, cta: { from: 60, texto: "SAIBA MAIS" },
  preco: null, titulo: null, narracao: "", musica: null, sfx: [], fala: [],
};

export const Root: React.FC = () => (
  <Composition id="Criativo" component={Criativo as React.FC<any>} defaultProps={vazio}
               durationInFrames={90} fps={30} width={1080} height={1920}
               calculateMetadata={({ props }) => ({
                 durationInFrames: Math.max(1, (props as Props).totalFrames), fps: (props as Props).fps,
                 width: (props as Props).width, height: (props as Props).height,
               })} />
);
