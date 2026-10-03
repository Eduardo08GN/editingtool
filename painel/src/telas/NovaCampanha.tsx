import { useState } from "react";
import { ArrowRight, Check, FileText, FolderSearch } from "lucide-react";
import { enviar, ler, miniatura, type Base } from "../api";
import type { Ctx } from "../App";
import { Girando, useAcao } from "../componentes/base";
import { link } from "../rota";

const EXEMPLO = `Público 1 - Religioso (copys escolhidas)

1.1 Padre (20 s, sem preço)
Padre, quantas famílias saem da missa sem saber ensinar a fé aos filhos pequenos? ... Clique em saiba mais e confira.

1.2 Pastor (31 s, com preço)
...`;

export function NovaCampanha({ ctx }: { ctx: Ctx }) {
  const { rodando, rodar } = useAcao(ctx.avisar);
  const [nome, setNome] = useState("");
  const [produto, setProduto] = useState("");
  const [texto, setTexto] = useState("");
  const [resultado, setResultado] = useState<{ nome: string; criativos: number; regra: string[] } | null>(null);
  const camp = ctx.camp;
  const [caminho, setCaminho] = useState(camp?.base ?? "");
  const [base, setBase] = useState<Base | null>(null);
  const alvoBase = resultado?.nome ?? camp?.nome ?? null;

  return (
    <div className="tela">
      <header className="tela-topo">
        <div><p className="eyebrow">Nova campanha</p><h1>Mapa de ângulos <em>→ criativos</em></h1>
          <p className="lead">Cole as copys no formato do time (público, ângulo, tempo, com ou sem preço). A ferramenta confere a regra 5×5 antes de gastar narração.</p></div>
      </header>

      <form className="panel bloco" onSubmit={(e) => {
        e.preventDefault();
        rodar("importar", async () => {
          const r = await enviar<{ nome: string; criativos: number; regra: string[] }>("/api/campanhas/importar", { nome, produto, texto });
          setResultado(r); ctx.recarregar();
        }, "Campanha importada.");
      }}>
        <div className="duas">
          <label className="campo-grupo"><span className="label">Nome da campanha</span>
            <input className="campo" value={nome} onChange={(e) => setNome(e.target.value)} placeholder="biblia-do-bebe" required /></label>
          <label className="campo-grupo"><span className="label">Produto (vira o título do modelo 2)</span>
            <input className="campo" value={produto} onChange={(e) => setProduto(e.target.value)} placeholder="Bíblia do Bebê: 70 Cards Lúdicos" /></label>
        </div>
        <label className="campo-grupo"><span className="label">Copys (mapa de ângulos)</span>
          <textarea className="campo" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={EXEMPLO} required /></label>
        <div className="acoes" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-primary" type="submit" disabled={!nome.trim() || !texto.trim() || !!rodando}>
            {rodando === "importar" ? <Girando /> : <FileText size={16} aria-hidden />}Importar e conferir
          </button>
        </div>
        {resultado && (
          <div className="switch-linha" style={{ display: "block" }}>
            <strong>{resultado.criativos} criativos importados</strong>
            {resultado.regra.length ? (
              <ul className="aviso-lista" style={{ marginTop: 10 }}>{resultado.regra.map((r, i) => <li key={i}>{r}</li>)}</ul>
            ) : <p className="regra-ok" style={{ marginTop: 6 }}><Check size={16} aria-hidden />Dentro da regra: 2×20s, 2×30s, 1×40s, 2 com preço e CTA em todos.</p>}
          </div>
        )}
      </form>

      <section className="panel bloco" aria-label="Vídeo base">
        <h3>Vídeo base {alvoBase ? <span className="meta">· campanha {alvoBase}</span> : null}</h3>
        <p>A pasta com os clipes brutos (sem legenda e sem narração) ou um único vídeo. As imagens de todos os criativos saem daqui, na ordem dos clipes.</p>
        <div className="linha-campo">
          <input className="campo" value={caminho} onChange={(e) => setCaminho(e.target.value)} placeholder="C:\...\Clipes" aria-label="Caminho do vídeo base" />
          <button className="btn btn-ghost" type="button" disabled={!caminho.trim() || !!rodando}
                  onClick={() => rodar("analisar", async () => setBase(await ler<Base>(`/api/base/analisar?caminho=${encodeURIComponent(caminho.trim())}`)))}>
            {rodando === "analisar" ? <Girando /> : <FolderSearch size={16} aria-hidden />}Ver clipes
          </button>
          <button className="btn btn-primary" type="button" disabled={!alvoBase || !caminho.trim() || !!rodando}
                  onClick={() => rodar("base", async () => {
                    setBase(await enviar<Base>(`/api/campanhas/${encodeURIComponent(alvoBase!)}/base`, { caminho: caminho.trim() }));
                    ctx.recarregar();
                  }, "Vídeo base definido.")}>
            {rodando === "base" ? <Girando /> : <Check size={16} aria-hidden />}Usar esta base
          </button>
        </div>
        {base && (
          <>
            <p className="meta">{base.clipes} {base.clipes === 1 ? "vídeo" : "clipes"} · {Math.round(base.duracao)}s de imagem no total</p>
            <ul className="clipes">
              {base.arquivos.map((a) => (
                <li key={a.caminho}><img src={miniatura(a.caminho, 160)} alt="" loading="lazy" /><span>{a.nome.replace(/\.\w+$/, "")} · {a.duracao}s</span></li>
              ))}
            </ul>
          </>
        )}
        {camp?.base_ok && <a className="btn btn-ghost" href={link.painel} style={{ justifySelf: "start" }}>Ir para o painel<ArrowRight size={16} aria-hidden /></a>}
      </section>
    </div>
  );
}
