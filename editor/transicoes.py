# -*- coding: utf-8 -*-
"""TRANSICOES — o pool de transicoes "de editor" (2026-10-03, pedido do operador: mais variedade
e cara premium, so' com o que for pertinente ao nicho).

Cada transicao = um `xfade` nativo (a passagem de uma cena para a outra) + EFEITOS DE CORTE
aplicados ao video ja' montado, numa janela curta em volta do corte:
  zoom   — "punch" de zoom (curva gaussiana; sobe e volta)
  giro   — inclinacao rapida (vai e volta), com zoom que esconde as quinas
  blur_h / blur_v — borrao de movimento na direcao do chicote
  blur   — desfoque geral (zoom blur)
  flash  — estouro de exposicao
  tremor — camera chacoalha no impacto
  luz    — light leak quente atravessando a tela (gerado aqui, sem asset de terceiros)
Tudo em filtros nativos do ffmpeg com expressao no tempo: custa pouco e a legenda (sobreposta
DEPOIS) nunca borra nem treme.
⛔ Fora do pool por nao combinarem com o nicho (religioso/infantil): pixelize, glitch, cubo,
   wind, fatias (slices), diagonais duras.
"""
import os, random

# nome: xfade (lista = sorteia), dur do xfade, efeitos [(fx, params)], categoria de SFX
CATALOGO = {
    "chicote_h":  {"xfade": ["smoothleft", "smoothright"], "dur": 0.22, "fx": [("blur_h", 0.16), ("zoom", 0.05)], "sfx": "transicao"},
    "chicote_v":  {"xfade": ["smoothup", "smoothdown"], "dur": 0.22, "fx": [("blur_v", 0.16), ("zoom", 0.05)], "sfx": "transicao"},
    "zoom_punch": {"xfade": ["zoomin"], "dur": 0.24, "fx": [("zoom", 0.16), ("blur", 0.10)], "sfx": "transicao"},
    "zoom_suave": {"xfade": ["fade"], "dur": 0.30, "fx": [("zoom", 0.09)], "sfx": None},
    "giro":       {"xfade": ["fade"], "dur": 0.20, "fx": [("giro", 7.0), ("zoom", 0.26), ("blur", 0.12)], "sfx": "transicao"},
    "flash":      {"xfade": ["fadewhite"], "dur": 0.22, "fx": [("flash", 0.30), ("zoom", 0.06)], "sfx": "revelar"},
    "impacto":    {"xfade": ["fade"], "dur": 0.05, "fx": [("tremor", 16), ("zoom", 0.07)], "sfx": "impacto"},
    "desfoque":   {"xfade": ["hblur"], "dur": 0.26, "fx": [], "sfx": "transicao"},
    "deslize":    {"xfade": ["slideleft", "slideright", "slideup", "slidedown"], "dur": 0.24, "fx": [("blur_eixo", 0.12)], "sfx": "transicao"},
    "cortina":    {"xfade": ["coverleft", "coverright", "coverup", "coverdown"], "dur": 0.26, "fx": [], "sfx": "transicao"},
    "revelar":    {"xfade": ["revealleft", "revealright", "revealup", "revealdown"], "dur": 0.26, "fx": [], "sfx": "transicao"},
    "circulo":    {"xfade": ["circleopen"], "dur": 0.34, "fx": [], "sfx": "revelar"},
    "radial":     {"xfade": ["radial"], "dur": 0.32, "fx": [], "sfx": "transicao"},
    "dissolve":   {"xfade": ["dissolve"], "dur": 0.30, "fx": [], "sfx": None},
    "abre":       {"xfade": ["horzopen", "vertopen"], "dur": 0.28, "fx": [], "sfx": "transicao"},
    # ⛔ `squeezev` derruba o ffmpeg (segfault, build 2025-03, video vertical) — so' o horizontal
    "aperto":     {"xfade": ["squeezeh"], "dur": 0.24, "fx": [], "sfx": "transicao"},
    "luz":        {"xfade": ["fade"], "dur": 0.30, "fx": [("luz", 1.0), ("flash", 0.12)], "sfx": "revelar"},
    # ── CARTOON (2026-10-03: a campanha da Biblia do Bebe pede cara de desenho animado) ──
    "iris":         {"xfade": ["circleclose", "circleopen"], "dur": 0.36, "fx": [("elastico", 0.10)], "sfx": "pop"},
    "pop_elastico": {"xfade": ["zoomin"], "dur": 0.20, "fx": [("elastico", 0.18)], "sfx": "pop"},
    "boing":        {"xfade": ["squeezeh"], "dur": 0.24, "fx": [("elastico", 0.14)], "sfx": "brinquedo"},
    "balanco":      {"xfade": ["fade"], "dur": 0.14, "fx": [("balanco", 6.0), ("zoom", 0.20)], "sfx": "impacto"},
    "giro_cartoon": {"xfade": ["fade"], "dur": 0.18, "fx": [("giro", 13.0), ("zoom", 0.36), ("elastico", 0.06)], "sfx": "pop"},
}
CARTOON = ("iris", "pop_elastico", "boing", "balanco", "giro_cartoon")

# ── CORTE NA CURVA (2026-10-05; "cut the curve" do HyperFrames, Apache-2.0) ──
# A cena velha ACELERA para o lado (power4.in, ~12% da tela + borrao de movimento), o corte cai no
# pico da velocidade e a nova chega do mesmo lado DESACELERANDO (power4.out): velocidade casada dos
# dois lados do corte. E' a transicao "padrao" do vocabulario de cada video.
CATALOGO["corte_curva"] = {"xfade": ["smoothleft"], "dur": 0.24, "fx": [("blur_h", 0.12)], "sfx": "transicao"}
PESO_PADRAO = {"corte_curva": 2.0}

# ⭐ A CORRENTE (motion-doctrine do HyperFrames): o video inteiro anda numa direcao so'. Antes cada
#    transicao sorteava o lado e uma ia para a esquerda e a seguinte para a direita ("pingue-pongue",
#    le-se como erro). A direcao vertical fica reservada para "revelacao" (sobe).
CORRENTE = {
    "esquerda": {"chicote_h": "smoothleft", "deslize": "slideleft", "cortina": "coverleft", "revelar": "revealleft",
                 "abre": "horzopen", "chicote_v": "smoothup", "corte_curva": "smoothleft"},
    "direita": {"chicote_h": "smoothright", "deslize": "slideright", "cortina": "coverright", "revelar": "revealright",
                "abre": "horzopen", "chicote_v": "smoothup", "corte_curva": "smoothright"},
}

EIXO = {"slideleft": "blur_h", "slideright": "blur_h", "slideup": "blur_v", "slidedown": "blur_v"}


def sortear(cortes, cfg_t, sem):
    """Uma transicao por corte. ~`proporcao` ganha efeito animado; nunca o mesmo tipo duas vezes
    seguidas; o resto e' corte seco (1 quadro). `pool` (config) restringe os nomes usados."""
    rng = random.Random(sem ^ 0x5EED)
    pool = [n for n in (cfg_t.get("pool") or list(CATALOGO)) if n in CATALOGO]
    pesos = dict(PESO_PADRAO, **(cfg_t.get("pesos") or {}))
    corrente = cfg_t.get("corrente") or "esquerda"
    sinal = rng.choice((-1, 1))                     # giros e balancos: o MESMO sentido no video todo
    # ⭐ VOCABULARIO: poucas transicoes por video, repetidas (o "corte na curva" + N do pool por peso).
    #    Variedade ENTRE os videos; consistencia DENTRO de cada um.
    n_vocab = int(cfg_t.get("vocabulario", 4))
    if n_vocab and len(pool) > n_vocab:
        resto = [n for n in pool if n != "corte_curva"]
        vocab = ["corte_curva"] if "corte_curva" in pool else []
        # ⛔ 2026-10-05: sorteando so' por peso, um video da Biblia saiu sem NENHUMA transicao cartoon.
        #    As FAVORITAS da campanha (peso > 1,5 nos ajustes) garantem 2 vagas do vocabulario.
        fav = [n for n in resto if float((cfg_t.get("pesos") or {}).get(n, 1.0)) > 1.5]
        for _ in range(min(2, len(fav), n_vocab - len(vocab))):
            n = rng.choices(fav, weights=[float(pesos.get(x, 1.0)) for x in fav])[0]
            vocab.append(n); fav.remove(n); resto.remove(n)
        while len(vocab) < n_vocab and resto:
            n = rng.choices(resto, weights=[float(pesos.get(x, 1.0)) ** 1.5 for x in resto])[0]
            vocab.append(n); resto.remove(n)
        pool = vocab
    out, ultimo = [], None
    for k, c in enumerate(cortes):
        if not (rng.random() < float(cfg_t.get("proporcao", 0.6)) or k == 0):
            out.append({"t": round(c, 3), "tipo": "seco", "xfade": "fade", "dur": float(cfg_t.get("duro_s", 0.034)), "fx": [], "sfx": None})
            continue
        opcoes = [n for n in pool if n != ultimo or n == "corte_curva"] or pool
        nome = rng.choices(opcoes, weights=[float(pesos.get(n, 1.0)) for n in opcoes])[0]; ultimo = nome
        spec = CATALOGO[nome]
        xf = CORRENTE.get(corrente, {}).get(nome) or rng.choice(spec["xfade"])
        fx = [list(f) for f in spec["fx"]]
        for f in fx:
            if f[0] == "blur_eixo": f[0] = EIXO.get(xf, "blur_h")
            if f[0] in ("giro", "balanco"): f[1] = f[1] * sinal
        out.append({"t": round(c, 3), "tipo": nome, "xfade": xf, "dur": spec["dur"], "fx": fx, "sfx": spec["sfx"],
                    "sinal": sinal, "corrente": corrente})
    return out


def _janelas(trans, nome, pre=0.10, pos=0.12):
    return [(t["t"] - pre, t["t"] + pos, p) for t in trans for f, p in t.get("fx", []) if f == nome]


def _between(js):
    return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b, _ in js) or "0"


def filtros_de_corte(entrada, saida, trans, W, H, tmp, n_entrada, log=None):
    """Devolve (filtros, entradas_extra) que levam [entrada] -> [saida] com os efeitos de corte."""
    fil, extra = [], []
    cur = entrada
    w = 0.09     # largura da gaussiana (s): o "punch" dura ~0.25 s

    def gauss(c): return f"exp(-pow((t-{c:.3f})/{w},2))"

    # giro (antes do zoom: o zoom esconde as quinas)
    giros = _janelas(trans, "giro")
    balancos = _janelas(trans, "balanco")
    if giros or balancos:
        partes = [f"({p * 3.14159 / 180:.4f})*((t-{(a + b) / 2:.3f})/{w})*{gauss((a + b) / 2)}*2.33" for a, b, p in giros]
        # balanco: vai-e-volta amortecido depois do corte (gelatina)
        partes += [f"({p * 3.14159 / 180:.4f})*between(t,{(a + b) / 2:.3f},{(a + b) / 2 + 0.8:.3f})*exp(-(t-{(a + b) / 2:.3f})*5)"
                   f"*sin((t-{(a + b) / 2:.3f})*22)" for a, b, p in balancos]
        fil.append(f"[{cur}]rotate=a='{'+'.join(partes)}':fillcolor=black:ow=iw:oh=ih[g0]"); cur = "g0"
    # zoom punch + tremor (scale com expressao no tempo, depois crop com deslocamento)
    zooms = _janelas(trans, "zoom")
    tremores = _janelas(trans, "tremor")
    elasticos = _janelas(trans, "elastico")
    zexpr = "+".join(f"{p:.3f}*{gauss((a + b) / 2)}" for a, b, p in zooms) or "0"
    # ⭐ elastico: depois do corte o zoom QUICA (oscilacao amortecida, ~3 balancos em 0.6 s) — o "boing" do desenho
    if elasticos:
        zexpr += "+" + "+".join(f"{p:.3f}*between(t,{(a + b) / 2:.3f},{(a + b) / 2 + 0.7:.3f})*exp(-(t-{(a + b) / 2:.3f})*6)"
                                f"*abs(cos((t-{(a + b) / 2:.3f})*16))" for a, b, p in elasticos)
    if tremores: zexpr += "+" + "+".join(f"0.05*{gauss((a + b) / 2)}" for a, b, p in tremores)
    if zooms or tremores or elasticos:
        sx = "+".join(f"{p:.0f}*sin(t*97)*{gauss((a + b) / 2)}" for a, b, p in tremores) or "0"
        sy = "+".join(f"{p:.0f}*cos(t*83)*{gauss((a + b) / 2)}" for a, b, p in tremores) or "0"
        fil.append(f"[{cur}]scale=w='trunc({W}*(1+{zexpr})/2)*2':h='trunc({H}*(1+{zexpr})/2)*2':eval=frame:flags=bicubic,"
                   f"crop={W}:{H}:x='max(0,min(iw-{W},(iw-{W})/2+{sx}))':y='max(0,min(ih-{H},(ih-{H})/2+{sy}))',setsar=1[z0]")
        cur = "z0"
    # borroes (ligados so' na janela do corte)
    for nome, filtro in (("blur_h", "avgblur=sizeX=34:sizeY=1"), ("blur_v", "avgblur=sizeX=1:sizeY=60"),
                         ("blur", "gblur=sigma=14")):
        js = _janelas(trans, nome, pre=0.07, pos=0.08)
        if js:
            fil.append(f"[{cur}]{filtro}:enable='{_between(js)}'[{nome}0]"); cur = f"{nome}0"
    # flash de exposicao
    fl = _janelas(trans, "flash")
    if fl:
        br = "+".join(f"{p:.2f}*{gauss((a + b) / 2)}" for a, b, p in fl)
        fil.append(f"[{cur}]eq=brightness='{br}':eval=frame[fl0]"); cur = "fl0"
    # light leak quente (PNG gerado aqui, entra como input proprio por transicao)
    luzes = _janelas(trans, "luz", pre=0.30, pos=0.45)
    if luzes:
        png = os.path.join(tmp, "luz.png"); _png_luz(png, W, H)
        for i, (a, b, _p) in enumerate(luzes):
            idx = n_entrada + len(extra) // 6       # 6 itens por input: -loop 1 -t X -i png
            extra += ["-loop", "1", "-t", f"{b + 0.1:.3f}", "-i", png]
            fil.append(f"[{idx}:v]format=rgba,fade=t=in:st={a:.3f}:d=0.18:alpha=1,fade=t=out:st={b - 0.25:.3f}:d=0.25:alpha=1[lz{i}]")
            fil.append(f"[{cur}][lz{i}]overlay=x='-w*0.35+(t-{a:.3f})/{b - a:.3f}*({W}+w*0.1)':y=0:"
                       f"enable='between(t,{a:.3f},{b:.3f})':eval=frame:eof_action=pass[lzv{i}]")
            cur = f"lzv{i}"
    fil.append(f"[{cur}]null[{saida}]")
    return fil, extra


def _png_luz(path, W, H):
    """Light leak procedural: faixa diagonal ambar/rosada, bem suave (alpha <= 0.55)."""
    if os.path.exists(path): return
    from PIL import Image, ImageDraw, ImageFilter
    lw = int(W * 1.1)
    img = Image.new("RGBA", (lw, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    for cor, cx, rx, a in (((255, 170, 60), 0.45, 0.30, 140), ((255, 110, 80), 0.62, 0.20, 110), ((255, 230, 150), 0.38, 0.12, 120)):
        d.ellipse((lw * (cx - rx), -H * 0.1, lw * (cx + rx), H * 1.1), fill=cor + (a,))
    img = img.filter(ImageFilter.GaussianBlur(W * 0.12)).rotate(12, resample=Image.BICUBIC)
    img.save(path)
