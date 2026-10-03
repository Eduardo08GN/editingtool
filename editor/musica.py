# -*- coding: utf-8 -*-
"""MUSICA — a ferramenta entende o contexto do criativo e escolhe sozinha a faixa.

1. `perfil(criativo)`: le angulo + publico + copy e decide o clima (fe_emocional, familia_doce,
   brincar_alegre, legado_nostalgia, oferta_energia). Palavra no ANGULO pesa mais que na copy.
2. `escolher(...)`: pontua as faixas de musica/catalogo.json pelos moods/instrumentos do perfil e
   pega uma do topo, sem repetir dentro do mesmo publico (5 criativos, 5 faixas diferentes).
⭐ Biblioteca = Meta Sound Collection (uso livre em FB/IG, inclusive anuncio). Fora da Meta, nao.
"""
import io, json, os, random, unicodedata

from . import config

DIR = os.path.join(config.RAIZ, "musica")
CATALOGO = os.path.join(DIR, "catalogo.json")
BIBLIOTECA = os.path.join(DIR, "biblioteca")

SINAIS = {
    "fe_emocional":     ["padre", "pastor", "igreja", "batismo", "ministerio", "celula", "paroquia", "fe", "deus", "lider"],
    "familia_doce":     ["mae", "madrinha", "padrinho", "dinda", "afilhado", "presente", "colo", "dormir", "batizado"],
    "brincar_alegre":   ["professora", "professor", "pro", "rodinha", "turma", "brincadeira", "brincando", "escola", "aprender", "tela"],
    "legado_nostalgia": ["vo", "avo", "avos", "netos", "legado", "lembrar", "lembre", "lembra", "sempre", "menina"],
    "oferta_energia":   ["reais", "barato", "material", "aniversario", "dez"],
}


def _toks(t):
    t = unicodedata.normalize("NFKD", (t or "").lower()).encode("ascii", "ignore").decode()
    return ["".join(c for c in w if c.isalnum()) for w in t.split()]


def perfil(cri):
    pts = {k: 0.0 for k in SINAIS}
    for texto, peso in ((cri.get("angulo"), 3.0), (cri.get("publico"), 2.0), (cri.get("copy"), 0.5)):
        toks = _toks(texto)
        for k, sinais in SINAIS.items():
            pts[k] += peso * sum(1 for w in toks if w in sinais)
    if cri.get("preco"): pts["oferta_energia"] += 1.5
    return max(pts, key=lambda k: (pts[k], k == "familia_doce"))


def catalogo():
    return json.load(io.open(CATALOGO, encoding="utf-8")) if os.path.exists(CATALOGO) else None


def escolher(cri, usadas=(), semente=0, minimo_s=0.0):
    """{'arquivo', 'titulo', 'perfil', 'pontos'} ou None (sem biblioteca)."""
    cat = catalogo()
    if not cat: return None
    pf = perfil(cri); spec = cat["perfis"][pf]
    cands = []
    for f in cat["faixas"]:
        p = os.path.join(BIBLIOTECA, f["arquivo"])
        if not os.path.exists(p): continue
        s = sum(spec["moods"].get(m, 0) for m in f["moods"])
        if f.get("instrumento") in spec.get("instrumentos", []): s += 2
        if f.get("tempo") == "Fast" and pf != "brincar_alegre": s -= 2
        if "Moody" in f["moods"] or "sad" in f["titulo"].lower(): s -= 4     # anuncio de oferta nao pode soar triste
        if f["dur_s"] < minimo_s: s -= 1          # curta demais: vai em loop, perde um pouco
        cands.append((s, f, p))
    if not cands: return None
    cands.sort(key=lambda x: -x[0])
    livres = [c for c in cands if c[1]["arquivo"] not in usadas] or cands
    topo = livres[:5]
    s, f, p = random.Random(semente).choice(topo)
    return {"arquivo": p, "titulo": f["titulo"], "artista": f["artista"], "perfil": pf, "pontos": s, "dur_s": f["dur_s"]}
