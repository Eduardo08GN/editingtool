import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, X } from "lucide-react";
import { midia, miniatura, type Criativo } from "../api";
import { link } from "../rota";
import { ETAPA, seg } from "../textos";

export function Selo({ etapa }: { etapa: Criativo["etapa"] }) {
  const s = ETAPA[etapa];
  const icone = s.tom === "ok" ? <Check size={13} strokeWidth={2.4} aria-hidden /> :
                s.tom === "no" ? <X size={13} strokeWidth={2.4} aria-hidden /> : <span className="dot" aria-hidden />;
  return <span className={`tag tag-${s.tom}`}>{icone}{s.texto}</span>;
}

export function Girando() { return <span className="spin" aria-hidden />; }

// ⭐ entregue: o cartao E' o video; passando o mouse ele toca (com som; se o navegador barrar, mudo)
export function CardCriativo({ c }: { c: Criativo }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [tocando, setTocando] = useState(false);
  const tocar = (sim: boolean) => {
    const el = ref.current; if (!el) return;
    if (sim) {
      el.currentTime = 0; el.muted = false;
      el.play().catch(() => { el.muted = true; return el.play(); }).then(() => setTocando(true)).catch(() => undefined);
    } else { el.pause(); setTocando(false); }
  };
  const trabalhando = c.etapa === "narrando" || c.etapa === "renderizando";
  return (
    <a className="panel vcard" href={link.criativo(c.id)}
       onMouseEnter={() => c.entregue && tocar(true)} onMouseLeave={() => c.entregue && tocar(false)}>
      <div className="stage">
        {c.entregue && !trabalhando ? (
          <>
            <img src={miniatura(c.entregue, 360, 2.0)} alt="" loading="lazy" decoding="async" className={tocando ? "some" : ""} />
            <video ref={ref} src={midia(c.entregue)} loop playsInline preload="none" aria-hidden className={tocando ? "" : "some"} />
          </>
        ) : (
          <div className="stage-vazio"><div>{trabalhando && <Girando />}<strong>{c.angulo}</strong></div></div>
        )}
        <Selo etapa={c.etapa} />
        {c.duracao ? <span className="canto">{seg(c.duracao)}</span> : null}
      </div>
      <div className="body">
        <div className="quote">{c.id} · {c.angulo}</div>
        <p className="meta">alvo {c.alvo_s}s{c.preco ? <><b>/</b>com preço</> : null}{c.musica ? <><b>/</b>♪ {c.musica}</> : null}</p>
      </div>
    </a>
  );
}

export interface Aviso { texto: string; tom: "ok" | "erro"; id: number }

export function Toast({ aviso, fechar }: { aviso: Aviso | null; fechar: () => void }) {
  useEffect(() => {
    if (!aviso) return;
    const t = window.setTimeout(fechar, 6000);
    return () => window.clearTimeout(t);
  }, [aviso, fechar]);
  if (!aviso) return null;
  return (
    <div className={`toast ${aviso.tom === "erro" ? "erro" : ""}`} role={aviso.tom === "erro" ? "alert" : "status"} key={aviso.id}>
      {aviso.tom === "erro" ? <AlertTriangle size={18} aria-hidden /> : <Check size={18} aria-hidden />}
      <p>{aviso.texto}</p>
      <button className="btn btn-quiet btn-icon-sm" onClick={fechar} aria-label="Fechar aviso"><X size={16} /></button>
    </div>
  );
}

// um botao que mostra o girando enquanto a acao roda e avisa o resultado
export function useAcao(avisar: (t: string, tom?: "ok" | "erro") => void) {
  const [rodando, setRodando] = useState<string | null>(null);
  const rodar = async (nome: string, fn: () => Promise<unknown>, ok?: string) => {
    setRodando(nome);
    try { await fn(); if (ok) avisar(ok); }
    catch (x) { avisar((x as Error).message, "erro"); }
    finally { setRodando(null); }
  };
  return { rodando, rodar };
}
