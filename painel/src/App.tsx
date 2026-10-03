import { useCallback, useEffect, useRef, useState } from "react";
import { ler, type Campanha, type Estado } from "./api";
import { useRota } from "./rota";
import { Lateral } from "./componentes/Lateral";
import { Toast, type Aviso } from "./componentes/base";
import { Painel } from "./telas/Painel";
import { Criativos } from "./telas/Criativos";
import { NovaCampanha } from "./telas/NovaCampanha";
import { Ajustes } from "./telas/Ajustes";

export interface Ctx {
  estado: Estado;
  camp: Campanha | null;
  recarregar: () => void;
  avisar: (texto: string, tom?: "ok" | "erro") => void;
}

// ⭐ o painel le' o servidor de tempos em tempos: rapido enquanto produz, devagar parado
function useServidor() {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [camp, setCamp] = useState<Campanha | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const vivo = useRef(true);
  const puxar = useCallback(async () => {
    try {
      const e = await ler<Estado>("/api/estado");
      if (!vivo.current) return;
      setEstado(e); setErro(null);
      if (e.campanha) setCamp(await ler<Campanha>(`/api/campanhas/${encodeURIComponent(e.campanha)}`));
      else setCamp(null);
    } catch (x) { if (vivo.current) setErro((x as Error).message); }
  }, []);
  useEffect(() => {
    vivo.current = true; puxar();
    const t = window.setInterval(puxar, estado?.rodando ? 1500 : 4000);
    return () => { vivo.current = false; window.clearInterval(t); };
  }, [puxar, estado?.rodando]);
  return { estado, camp, erro, puxar };
}

export function App() {
  const rota = useRota();
  const { estado, camp, erro, puxar } = useServidor();
  const [aviso, setAviso] = useState<Aviso | null>(null);
  const avisar = useCallback((texto: string, tom: "ok" | "erro" = "ok") => setAviso({ texto, tom, id: Date.now() }), []);

  if (!estado) {
    return (
      <div className="tela"><div className="panel vazio">
        <h2>{erro ? "Não consegui falar com a ferramenta" : "Abrindo…"}</h2>
        {erro && <p>Feche esta janela e abra de novo com <code>python edt.py painel</code>. ({erro})</p>}
      </div></div>
    );
  }
  const ctx: Ctx = { estado, camp, recarregar: puxar, avisar };
  return (
    <div className="app">
      <Lateral ctx={ctx} rota={rota} />
      <main>
        {rota.tela === "painel" && <Painel ctx={ctx} />}
        {rota.tela === "criativos" && <Criativos ctx={ctx} aberto={rota.criativo} />}
        {rota.tela === "nova" && <NovaCampanha ctx={ctx} />}
        {rota.tela === "ajustes" && <Ajustes ctx={ctx} />}
      </main>
      <Toast aviso={aviso} fechar={() => setAviso(null)} />
    </div>
  );
}
