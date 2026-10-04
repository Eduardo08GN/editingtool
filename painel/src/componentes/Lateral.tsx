import { Clapperboard, LayoutDashboard, PlusSquare, SlidersHorizontal } from "lucide-react";
import { enviar } from "../api";
import type { Ctx } from "../App";
import { link, type Rota } from "../rota";
import { nomeBonito } from "../textos";

export function Lateral({ ctx, rota }: { ctx: Ctx; rota: Rota }) {
  const { estado, camp } = ctx;
  const conferir = camp?.criativos.filter((c) => c.etapa === "aviso" || c.etapa === "erro").length ?? 0;
  const itens = [
    { href: link.painel, tela: "painel", icone: <LayoutDashboard size={18} />, texto: "Painel" },
    { href: link.criativos, tela: "criativos", icone: <Clapperboard size={18} />, texto: "Criativos", count: conferir },
    { href: link.nova, tela: "nova", icone: <PlusSquare size={18} />, texto: "Nova campanha" },
    { href: link.ajustes, tela: "ajustes", icone: <SlidersHorizontal size={18} />, texto: "Ajustes" },
  ];
  return (
    <aside className="side">
      <div className="lockup">
        <img src="/logo.svg" alt="" width={30} height={30} />
        <div className="marca"><span className="wordmark">EditingTool</span>
          <span className="selos-marca"><span className="ver">1.0</span>{camp?.efetivo?.turbo && <span className="ver turbo-pill">⚡ TURBO</span>}</span></div>
      </div>
      <nav aria-label="Telas">
        {itens.map((i) => (
          <a key={i.tela} className="nav-i" href={i.href} aria-current={rota.tela === i.tela ? "page" : undefined}>
            {i.icone}<span>{i.texto}</span>
            {i.count ? <span className="count" aria-label={`${i.count} para conferir`}>{i.count}</span> : null}
          </a>
        ))}
      </nav>
      <div className="foot">
        <span className="label">Campanha aberta</span>
        <select className="campo" value={estado.campanha ?? ""} aria-label="Campanha aberta"
                onChange={async (e) => {
                  if (!e.target.value) return;
                  try { await enviar(`/api/campanhas/${encodeURIComponent(e.target.value)}/abrir`); ctx.recarregar(); }
                  catch (x) { ctx.avisar((x as Error).message, "erro"); }
                }}>
          {!estado.campanha && <option value="">— escolha —</option>}
          {estado.campanhas.map((c) => <option key={c.nome} value={c.nome}>{nomeBonito(c.nome)} ({c.prontos}/{c.criativos})</option>)}
        </select>
        <div className={`conexao${estado.minimax ? " on" : ""}`}>
          <span className="dot" aria-hidden />{estado.minimax ? "MiniMax conectada" : "Falta a chave da MiniMax (.env)"}
        </div>
      </div>
    </aside>
  );
}
