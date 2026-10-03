# -*- coding: utf-8 -*-
"""PLAYER — uma pagina local para revisar a leva inteira (grade por publico, com copy e avisos)."""
import html, os

from . import config

CSS = """
:root{--bg:#0f1012;--card:#1a1b1f;--tx:#eceef2;--mut:#9aa0aa;--ok:#2fbf71;--av:#ffb020;--ac:#ffe200}
@media (prefers-color-scheme: light){:root{--bg:#f4f5f7;--card:#fff;--tx:#15171a;--mut:#5d6470}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.45 system-ui,Segoe UI,sans-serif}
header{padding:20px 16px 8px;max-width:1400px;margin:auto}h1{margin:0;font-size:22px}header p{color:var(--mut);margin:4px 0 0}
section{max-width:1400px;margin:auto;padding:8px 16px 24px}h2{font-size:16px;margin:18px 0 10px}
.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.c{background:var(--card);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
video{width:100%;aspect-ratio:9/16;background:#000;display:block}
.m{padding:10px 12px;display:flex;flex-direction:column;gap:6px}
.t{font-weight:650}.tags{display:flex;gap:6px;flex-wrap:wrap}.tag{font-size:12px;padding:2px 8px;border-radius:99px;background:rgba(127,127,127,.18)}
.tag.p{background:var(--ac);color:#111}.av{color:var(--av);font-size:12px}.ok{color:var(--ok);font-size:12px}
details{font-size:12px;color:var(--mut)}summary{cursor:pointer}
"""


def gerar(camp, qas):
    saida = os.path.join(camp["_pasta"], "saida")
    por_pub = {}
    for q in qas: por_pub.setdefault(q["publico"], []).append(q)
    blocos = []
    for pub, lst in por_pub.items():
        cards = []
        for q in sorted(lst, key=lambda x: [int(p) for p in x["id"].split(".")]):
            rel = os.path.relpath(q["entregue"], saida).replace("\\", "/")
            av = "".join(f"<div class=av>⚠ {html.escape(a)}</div>" for a in q.get("avisos") or []) or "<div class=ok>✓ sem avisos</div>"
            mus = (q.get("musica") or {}).get("titulo") or "-"
            cards.append(f"""<div class=c><video src="{html.escape(rel)}" controls preload=metadata playsinline></video>
<div class=m><div class=t>{html.escape(q['id'])} · {html.escape(q['angulo'])}</div>
<div class=tags><span class=tag>{q['duracao']}s (alvo {q['alvo_s']}s)</span>{'<span class="tag p">com preço</span>' if q['preco'] else ''}
<span class=tag>♪ {html.escape(mus)}</span><span class=tag>{len(q.get('sfx') or [])} sfx</span></div>{av}
<details><summary>copy</summary>{html.escape(q['copy'])}</details></div></div>""")
        blocos.append(f"<section><h2>{html.escape(pub)}</h2><div class=g>{''.join(cards)}</div></section>")
    pagina = f"""<!doctype html><html lang=pt-BR><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{html.escape(camp.get('nome') or 'Campanha')} — criativos</title><style>{CSS}</style></head><body>
<header><h1>{html.escape(camp.get('produto') or camp.get('nome') or '')}</h1><p>{len(qas)} criativos · campanha {html.escape(camp.get('nome') or '')}</p></header>
{''.join(blocos)}</body></html>"""
    caminho = os.path.join(saida, "player.html")
    with open(caminho, "w", encoding="utf-8") as f: f.write(pagina)
    return caminho
