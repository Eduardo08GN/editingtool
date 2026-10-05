# -*- coding: utf-8 -*-
"""SELOS DE CONFIANCA — quando a narracao fala de garantia, suporte no WhatsApp, acesso imediato ou
compra segura, um selo animado entra na tela (ideia dos blocos trust-strip / badge-pop / success-check
do catalogo do HyperFrames, Apache-2.0; desenho e codigo nossos, no Remotion).

Para low ticket isso e' argumento de venda: o selo transforma a frase em prova visual.
Regras: no maximo `max` por video (padrao 3), um a cada 3 s, nada no gancho (2 s) nem depois do CTA.
"""
import unicodedata

NUM = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8,
       "nove": 9, "dez": 10, "quinze": 15, "trinta": 30, "sessenta": 60, "noventa": 90}


def _n(w):
    w = unicodedata.normalize("NFKD", (w or "").lower()).encode("ascii", "ignore").decode()
    return "".join(c for c in w if c.isalnum())


def _numero(w):
    n = _n(w)
    return int(n) if n.isdigit() else NUM.get(n)


def detectar(palavras, t_cta, cfg_s, inicio_min=2.0):
    """[{'t','dur','tipo','linhas'}] — tipo: garantia | whatsapp | imediato | seguro."""
    if not cfg_s or not cfg_s.get("ativo", True): return []
    ws = [(_n(w), float(a)) for w, a, _b in palavras]
    achados = []
    for i, (w, a) in enumerate(ws):
        ant = [x for x, _ in ws[max(0, i - 6):i]]
        if w == "garantia":
            dias = next((ws[j - 1][0] for j in range(i - 1, max(0, i - 5), -1) if ws[j][0] == "dias" and j > 0), None)
            n = _numero(dias) if dias else None
            achados.append({"t": a, "tipo": "garantia", "linhas": [f"{n} DIAS DE", "GARANTIA"] if n else ["GARANTIA", "TOTAL"]})
        elif w.startswith("whatsapp") or w in ("whats", "zap", "zapzap"):
            topo = "SUPORTE NO" if any(x.startswith("suporte") for x in ant) else "ATENDIMENTO NO"
            achados.append({"t": a, "tipo": "whatsapp", "linhas": [topo, "WHATSAPP"]})
        elif w in ("reembolso", "devolucao"):            # sem a palavra "garantia" (com ela, o tipo ja' saiu)
            achados.append({"t": a, "tipo": "garantia", "linhas": ["SEU DINHEIRO", "DE VOLTA"]})
        elif w.startswith("imediat") and any(x in ("acesso", "entrega", "receba", "recebe") for x in ant[-3:]):
            achados.append({"t": a, "tipo": "imediato", "linhas": ["ACESSO", "IMEDIATO"]})
        elif w in ("segura", "seguro") and any(x in ("compra", "pagamento", "site") for x in ant[-3:]):
            achados.append({"t": a, "tipo": "seguro", "linhas": ["COMPRA", "100% SEGURA"]})
    maximo, espaco, dur = int(cfg_s.get("max", 3)), float(cfg_s.get("espaco_s", 3.0)), float(cfg_s.get("dur_s", 2.4))
    out, tipos = [], set()
    for s in achados:
        if s["t"] < inicio_min or s["t"] > t_cta - 1.0 or s["tipo"] in tipos: continue
        if out and s["t"] - out[-1]["t"] < espaco: continue
        tipos.add(s["tipo"])
        out.append(dict(s, t=round(s["t"] - 0.05, 3), dur=round(min(dur, t_cta - s["t"]), 3)))
        if len(out) >= maximo: break
    return out
