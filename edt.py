# -*- coding: utf-8 -*-
"""edt — editor automatico de criativos low ticket (9:16, legenda queimada, voz MiniMax).

    python edt.py importar <copys.txt> --campanha <nome> [--produto "..."]
    python edt.py validar <campanha>
    python edt.py produzir <campanha> --base <video.mp4> [--so 1.1,2.3] [--workers 2] [--borrar-faixa 0.62:0.80]
    python edt.py amostra <campanha> --base <video.mp4> --id 1.1       (um criativo, para aprovar o visual)
    python edt.py player <campanha>
    python edt.py vozes [--filtro portug]
    python edt.py sfx [sync|listar]
    python edt.py musica <campanha>                                     (qual faixa cada criativo usaria)
    python edt.py painel [--porta 8791] [--sem-janela]                 (abre a interface)
    python edt.py publicar <campanha> [--repo URL --pasta "dentro/do/repo"]  (manda os entregues ao GitHub)
    python edt.py minerar [--mercados FR,DE,PT] [--max 1000] [--finalistas 40]  (garimpa ofertas na Biblioteca da Meta)
    python edt.py minerar --rodada <id>                                 (retoma uma rodada / refaz a analise)
"""
import argparse, os, sys

from editor import config, campanha, lote, musica, player, sfx, tts


def _ajustes(a):
    aj = {}
    if getattr(a, "borrar_faixa", None):
        aj.setdefault("video", {})["borrar_faixa"] = [[float(v) for v in f.split(":")] for f in a.borrar_faixa.split(",")]
    if getattr(a, "janela", None):
        aj.setdefault("video", {})["janela_base"] = [float(v) for v in a.janela.split(":")]
    if getattr(a, "voz", None): aj.setdefault("tts", {})["voz"] = a.voz
    if getattr(a, "tts", None): aj.setdefault("tts", {})["provedor"] = a.tts
    if getattr(a, "sem_musica", False): aj.setdefault("audio", {})["musica"] = ""
    return aj


def main(argv):
    ap = argparse.ArgumentParser(prog="edt", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("importar"); p.add_argument("txt"); p.add_argument("--campanha", required=True); p.add_argument("--produto", default="")
    p = sub.add_parser("validar"); p.add_argument("campanha")
    for nome in ("produzir", "amostra"):
        p = sub.add_parser(nome); p.add_argument("campanha"); p.add_argument("--base")
        p.add_argument("--so", help="ids separados por virgula"); p.add_argument("--id")
        p.add_argument("--workers", type=int, default=2); p.add_argument("--borrar-faixa", dest="borrar_faixa", help="ex.: 0.63:0.80 ou 0.63:0.80,0.85:0.95")
        p.add_argument("--janela", help="trecho util do base em s, ex.: 0:33.5")
        p.add_argument("--voz"); p.add_argument("--tts", choices=["minimax", "kokoro"]); p.add_argument("--sem-musica", action="store_true")
        p.add_argument("--refazer", action="store_true", help="ignora o que ja' esta' pronto")
    p = sub.add_parser("player"); p.add_argument("campanha")
    p = sub.add_parser("vozes"); p.add_argument("--filtro", default="portug")
    p = sub.add_parser("sfx"); p.add_argument("acao", nargs="?", default="listar", choices=["listar", "sync"])
    p = sub.add_parser("musica"); p.add_argument("campanha")
    p = sub.add_parser("remotion"); p.add_argument("campanha"); p.add_argument("--id", required=True); p.add_argument("--motion", action="store_true")
    p = sub.add_parser("publicar"); p.add_argument("campanha"); p.add_argument("--repo"); p.add_argument("--pasta")
    p = sub.add_parser("painel"); p.add_argument("--porta", type=int, default=8791); p.add_argument("--sem-janela", action="store_true")
    p = sub.add_parser("minerar"); p.add_argument("--mercados", default="FR,DE,PT"); p.add_argument("--max", type=int, default=1000)
    p.add_argument("--finalistas", type=int, default=40); p.add_argument("--rodada", help="retoma esta rodada em vez de abrir outra")
    a = ap.parse_args(argv)

    if a.cmd == "minerar":
        from editor import mineracao
        if a.rodada:
            rid = a.rodada
            if not mineracao.meta(rid): raise SystemExit(f"rodada {rid} nao existe")
            ofs = (mineracao.rodar if mineracao.tem_token() else mineracao.analisar)(rid)
        else:
            rid = mineracao.nova_rodada([m.strip().upper() for m in a.mercados.split(",") if m.strip()], a.max, a.finalistas)["id"]
            ofs = mineracao.rodar(rid)
        mineracao.salvar_meta(rid, status="pronta", fase="pronta")
        for i, o in enumerate(ofs[:20], 1):
            print(f"{i:>2}. {o['nota']:>4}  {o['oferta'][:48]:<48} {o['alcance_ue']:>10,} pessoas  buraco: {'/'.join(o['buraco']) or '-'}")
            print(f"      {o['biblioteca']}")
        return 0

    if a.cmd == "remotion":
        from editor import motor_remotion
        r = motor_remotion.renderizar(a.campanha, a.id, motion=a.motion)
        print(f"{r['saida']}  ({r['duracao']}s de video, render em {r['segundos_render']}s)"); return 0
    if a.cmd == "publicar":
        from editor import publicar
        r = publicar.publicar(a.campanha, a.repo, a.pasta)
        print(f"{r['total']} videos em {r['pasta']} ({r['enviados']} alteracoes) -> {r['repo']}"); return 0
    if a.cmd == "painel":
        from editor import servidor
        servidor.rodar(a.porta, janela=not a.sem_janela); return 0

    if a.cmd == "importar":
        camp, pasta = campanha.importar(a.txt, a.campanha, a.produto)
        print(f"{len(camp['criativos'])} criativos -> {pasta}\n" + campanha.resumo(camp))
        av = campanha.validar(camp)
        print("\nREGRA: " + ("tudo dentro" if not av else f"{len(av)} aviso(s)\n  - " + "\n  - ".join(av)))
        return 0
    if a.cmd == "validar":
        camp = campanha.carregar(a.campanha); av = campanha.validar(camp)
        print(campanha.resumo(camp)); print("\nREGRA: " + ("tudo dentro" if not av else "\n  - " + "\n  - ".join(av)))
        return 0 if not av else 1
    if a.cmd in ("produzir", "amostra"):
        so = None
        if a.cmd == "amostra":
            if not a.id: raise SystemExit("amostra precisa de --id")
            so = {a.id}
        elif a.so: so = {s.strip() for s in a.so.split(",")}
        r = lote.produzir(a.campanha, a.base, so, a.workers, _ajustes(a), refazer=a.refazer)
        print(f"\nfeitos: {r['feitos']}  erros: {len(r['erros'])}\nplayer: {r['player']}")
        for i, e in r["erros"]: print(f"  ERRO {i}: {e[:300]}")
        return 0 if not r["erros"] else 1
    if a.cmd == "player":
        camp = campanha.carregar(a.campanha)
        saida = os.path.join(camp["_pasta"], "saida")
        qas = [config.ler_json(os.path.join(saida, d, "qa.json")) for d in sorted(os.listdir(saida)) if not d.startswith("_")]
        print(player.gerar(camp, [q for q in qas if q])); return 0
    if a.cmd == "vozes":
        for v in tts.listar_vozes(a.filtro): print(f"  {v['voice_id']:<42} {v['tipo']:<16} {v['desc'][:80]}")
        return 0
    if a.cmd == "sfx":
        print(sfx.sync() if a.acao == "sync" else sfx.relatorio()); return 0
    if a.cmd == "musica":
        camp = campanha.carregar(a.campanha); usadas = {}
        from editor import montagem
        for c in camp["criativos"]:
            m = musica.escolher(c, usadas.get(c["publico_n"], set()), montagem.semente(c["id"], camp.get("nome", "")))
            if m: usadas.setdefault(c["publico_n"], set()).add(os.path.basename(m["arquivo"]))
            print(f"  {c['id']:<5} {c['angulo'][:34]:<34} {(m or {}).get('perfil', '-'):<17} {(m or {}).get('titulo', '-')}")
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
