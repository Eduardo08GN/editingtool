# -*- coding: utf-8 -*-
"""LEGENDAS — o pool de estilos e o desenho de cada cartao (PNG transparente).

⭐ PORTADO do ow_agente (organic-wave-studio/motor/legendas.py, so' leitura): `png_cartao`,
`papel`, tracking otico, contorno em passe separado, sombra suave, encolhe-ate'-caber. O repo
original nao foi tocado; este arquivo e' uma copia adaptada.

Novo aqui:
  - estilo 11 LOWTICKET (padrao) — medido no criativo de referencia: caixa alta branca,
    contorno preto grosso, palavra falada em amarelo, 2-3 palavras, ~70% da altura.
  - `png_cta`   — a pilula amarela "SAIBA MAIS" do fim do criativo.
  - `png_seta`  — a seta vermelha que pula ao lado da pilula.
  - `png_selo`  — selo de preco ("SO' R$ 10") que entra quando a narracao fala o preco.

O que faz legenda parecer cara (do original): tracking negativo, contorno separado do
preenchimento, sombra em vez de contorno gordo, cores desenhadas, corpo pela caixa alta,
encaixe garantido por largura.
"""
import os

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from . import config

FONTES = {
    "poppins":    ("Poppins-ExtraBold.ttf", None),
    "anton":      ("Anton-Regular.ttf", None),
    "bebas":      ("BebasNeue-Regular.ttf", None),
    "luckiest":   ("LuckiestGuy-Regular.ttf", None),
    "mont900":    ("Montserrat[wght].ttf", [900]),
    "mont800":    ("Montserrat[wght].ttf", [800]),
    "arch_larga": ("Archivo[wdth,wght].ttf", [900, 125]),
    "arch_black": ("Archivo[wdth,wght].ttf", [900, 100]),
}

BRANCO = (255, 255, 255)
AMARELO = (255, 214, 10)
AMARELO_REF = (255, 226, 0)          # o amarelo do criativo de referencia
AMBAR = (255, 176, 0)
AGUA = (34, 226, 208)
LIMA = (198, 255, 41)
VERDE_CTA = (0, 230, 90)
VERMELHO = (232, 28, 36)
GRAFITE = (17, 17, 20)

_PADRAO = dict(caso="alta", track=-0.025, esp=0.30, lh=1.42, contorno=1 / 20., cor_contorno=GRAFITE,
               sombra=(0, 0.075, 0.045, 145), extrude=None, glow=None, placa=None, escala=1.0,
               base=BRANCO, realce=AMARELO, cta_forma="pilula", cta_cor=VERDE_CTA, cta_texto=GRAFITE,
               alt=0.050)


def _e(numero, nome, fonte, desc, **kw):
    d = dict(_PADRAO); d.update(kw); d.update(numero=numero, nome=nome, fonte=fonte, desc=desc); return d


# ⭐ Numero e' o que a pessoa escolhe; nunca renumere. Acrescente no fim.
ESTILOS = [
    _e(1, "CLASSICA", "poppins", "a de sempre, afinada", track=-0.03, sombra=(0, 0.08, 0.05, 150)),
    _e(2, "PILULA", "mont900", "a mais usada em reels", track=-0.03, contorno=1 / 26., sombra=(0, 0.07, 0.045, 120), alt=0.047),
    _e(3, "BLOCO", "anton", "estilo Hormozi", track=-0.005, esp=0.26, contorno=1 / 15., sombra=(0, 0.07, 0.04, 160),
       cta_forma="bloco", cta_texto=BRANCO, alt=0.056),
    _e(4, "LARGA", "arch_larga", "expandida, look caro", track=-0.035, esp=0.26, contorno=1 / 24.,
       sombra=(0, 0.075, 0.05, 150), realce=AGUA, alt=0.044),
    _e(5, "TORRE", "bebas", "condensada alta", track=0.005, esp=0.32, contorno=1 / 24., sombra=(0, 0.07, 0.05, 165),
       realce=AMBAR, cta_forma="bloco", cta_texto=BRANCO, alt=0.056),
    _e(6, "PLACA", "mont800", "com fundo, le em tudo", track=-0.025, contorno=0, placa=(170, 0.52, 0.40), sombra=None,
       realce=AGUA, alt=0.045),
    _e(7, "NEON", "poppins", "com brilho", track=-0.03, contorno=1 / 26., glow=(0.115, 255, AGUA),
       sombra=(0, 0.06, 0.05, 130), realce=AGUA, alt=0.048),
    _e(8, "FESTA", "luckiest", "estilo MrBeast", track=-0.005, contorno=1 / 14., sombra=(0, 0.09, 0.05, 165), escala=1.12,
       cta_forma="bloco", cta_texto=BRANCO),
    _e(9, "AMARELA", "arch_black", "toda amarela, sem piscar", track=-0.03, contorno=1 / 20., sombra=(0, 0.08, 0.05, 160),
       base=AMARELO, realce=None, alt=0.048),
    _e(10, "BRANCA", "mont800", "toda branca, sem piscar", track=-0.028, contorno=1 / 20., sombra=(0, 0.08, 0.05, 160),
       base=BRANCO, realce=None, alt=0.048),
    # ⭐ medido no criativo_low_ticket.mp4 (1080x1920): caixa alta ~0.034 H, contorno grosso, amarelo na palavra falada
    # ⛔ 2026-10-03: "so' a legenda, nada atras" — sombra colada no contorno (sem halo espalhado)
    _e(11, "LOWTICKET", "mont900", "a do criativo de referencia", track=-0.02, esp=0.27, lh=1.32, contorno=1 / 8.,
       sombra=(0, 0.045, 0.012, 120), base=BRANCO, realce=AMARELO_REF, alt=0.036),
]
POR_NUMERO = {e["numero"]: e for e in ESTILOS}
FOLGA_FORMA = 0.18


def estilo(n):
    try: return POR_NUMERO[int(n)]
    except Exception: return POR_NUMERO[11]


_cache = {}


def fonte_caminho(chave):
    arq, _ = FONTES[chave]
    for c in (os.path.join(config.FONTES_DIR, arq), os.path.join(config.FONTES_DIR, "Poppins-ExtraBold.ttf")):
        if os.path.exists(c): return c
    for c in (r"C:\Windows\Fonts\impact.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
        if os.path.exists(c): return c
    raise SystemExit("nenhuma fonte encontrada em fontes/")


def carregar(chave, size):
    k = (chave, size)
    if k in _cache: return _cache[k]
    caminho = fonte_caminho(chave); eixos = FONTES[chave][1]
    f = ImageFont.truetype(caminho, size)
    if eixos and caminho.endswith(FONTES[chave][0]):
        try: f.set_variation_by_axes(list(eixos))
        except Exception: pass
    _cache[k] = f
    return f


def corpo_para_caixa(chave, alt_px):
    f = carregar(chave, 200); bb = f.getbbox("H")
    return max(8, int(round(200 * alt_px / (bb[3] - bb[1]))))


def _avancos(f, s, track):
    out = []
    for i, ch in enumerate(s):
        a = f.getlength(ch)
        if i + 1 < len(s): a += f.getlength(s[i:i + 2]) - f.getlength(ch) - f.getlength(s[i + 1])
        out.append(a + track)
    return out


def _largura(f, s, track):
    av = _avancos(f, s, track); return sum(av) - (track if av else 0)


def _letras(p):
    return "".join(c for c in p.lower() if c.isalnum())


def papel(pecas, idx, cta, est):
    """'cta' | 'realce' | 'base' por palavra. Na frase do CTA so' ele se destaca."""
    alvo = _letras(cta) if cta else None
    tem_cta = bool(alvo) and any(_letras(p) == alvo for p in pecas)
    out = []
    for i, p in enumerate(pecas):
        if tem_cta: out.append("cta" if _letras(p) == alvo else "base")
        elif i == idx and est.get("realce"): out.append("realce")
        else: out.append("base")
    return out


def png_cartao(palavras, idx, alt_px, path, W, max_w, cta, est):
    """Desenha UM cartao (palavras, a `idx` sendo falada) num PNG transparente; devolve (w, h).
    A altura do PNG so' depende do numero de linhas: a linha de base nao pula entre cartoes."""
    pecas = [p.upper() if est["caso"] == "alta" else p for p in palavras]
    papeis = papel(pecas, idx, cta, est)
    escala_i = idx if papeis[idx] == "realce" and est["escala"] != 1.0 else None

    def layout(alt):
        size = corpo_para_caixa(est["fonte"], alt)
        f = carregar(est["fonte"], size)
        fa = carregar(est["fonte"], max(8, int(round(size * est["escala"]))))
        track, esp = est["track"] * alt, est["esp"] * alt
        larg = [_largura(fa if i == escala_i else f, p, track) for i, p in enumerate(pecas)]
        n = len(pecas); linhas = [list(range(n))]
        if sum(larg) + esp * (n - 1) > max_w and n > 1:
            melhor = min(range(1, n), key=lambda c: abs((sum(larg[:c]) + esp * (c - 1)) - (sum(larg[c:]) + esp * (n - c - 1))))
            linhas = [list(range(melhor)), list(range(melhor, n))]
        pior = max(sum(larg[i] for i in ln) + esp * (len(ln) - 1) for ln in linhas)
        return size, f, fa, track, esp, larg, linhas, pior

    alt = float(alt_px); piso = alt * 0.58
    size, f, fa, track, esp, larg, linhas, pior = layout(alt)
    while pior > max_w and alt > piso:
        alt = max(piso, alt * 0.955)
        size, f, fa, track, esp, larg, linhas, pior = layout(alt)

    bbH = f.getbbox("H"); caixa = bbH[3] - bbH[1]
    lh = est["lh"] * caixa
    pad = int(caixa * 0.95)
    alt_total = lh * (len(linhas) - 1) + caixa
    tw = max(sum(larg[i] for i in ln) + esp * (len(ln) - 1) for ln in linhas)
    CW, CH = int(tw + 2 * pad), int(alt_total + 2 * pad)
    y0 = pad
    pos = {}
    for r, ln in enumerate(linhas):
        wl = sum(larg[i] for i in ln) + esp * (len(ln) - 1); x = (CW - wl) / 2
        for i in ln:
            pos[i] = (x, y0 + r * lh); x += larg[i] + esp

    def nova(): return Image.new("RGBA", (CW, CH), (0, 0, 0, 0))

    def cor_de(i):
        pp = papeis[i]
        if pp == "cta": return est["cta_texto"] if est["cta_forma"] in ("pilula", "bloco") else est["cta_cor"]
        if pp == "realce": return est["realce"]
        return est["base"]

    def passe(alvo, so_contorno, cor_fixa=None, dx=0, dy=0, sw=0, pular=()):
        d = ImageDraw.Draw(alvo)
        for i, p in enumerate(pecas):
            if i in pular: continue
            ff = fa if i == escala_i else f
            bb = ff.getbbox("H"); x, y = pos[i]
            y = y + caixa - (bb[3] - bb[1]) + dy; x += dx
            cor = tuple(cor_fixa if cor_fixa is not None else cor_de(i)) + (255,)
            av = _avancos(ff, p, track)
            for j, ch in enumerate(p):
                if so_contorno: d.text((x, y - bb[1]), ch, font=ff, fill=cor, stroke_width=sw, stroke_fill=cor)
                else: d.text((x, y - bb[1]), ch, font=ff, fill=cor)
                x += av[j]

    camada = nova()
    i_cta = next((i for i, pp in enumerate(papeis) if pp == "cta"), None)
    com_forma = (i_cta,) if (i_cta is not None and est["cta_forma"] in ("pilula", "bloco")) else ()

    if est["placa"]:
        alpha, padf, radf = est["placa"]; pf = padf * caixa
        xs = [pos[i][0] for i in pos] + [pos[i][0] + larg[i] for i in pos]
        pl = nova()
        ImageDraw.Draw(pl).rounded_rectangle((min(xs) - pf, y0 - pf * 0.8, max(xs) + pf, y0 + alt_total + pf * 0.8),
                                             radius=radf * caixa, fill=(8, 8, 12, alpha))
        camada = Image.alpha_composite(camada, pl.filter(ImageFilter.GaussianBlur(caixa * 0.10)))
    if est["glow"]:
        raio, alpha, cor = est["glow"]; g = nova()
        passe(g, True, cor_fixa=cor, sw=max(1, int(size * 0.05)))
        g = g.filter(ImageFilter.GaussianBlur(raio * caixa)); g.putalpha(g.getchannel("A").point(lambda v: v * alpha // 255))
        camada = Image.alpha_composite(camada, g)
    if est["sombra"]:
        dx, dy, blur, alpha = est["sombra"]; s = nova()
        passe(s, True, cor_fixa=(0, 0, 0), dx=dx * caixa, dy=dy * caixa,
              sw=max(1, int(size * max(est["contorno"], 1 / 26.))), pular=com_forma)
        s = s.filter(ImageFilter.GaussianBlur(blur * caixa)); s.putalpha(s.getchannel("A").point(lambda v: v * alpha // 255))
        camada = Image.alpha_composite(camada, s)
    if com_forma:
        x, y = pos[i_cta]; px, py = caixa * 0.26, caixa * FOLGA_FORMA
        box = (x - px, y - py, x + larg[i_cta] + px, y + caixa + py); pl = nova(); dd = ImageDraw.Draw(pl)
        rad = (box[3] - box[1]) / 2 if est["cta_forma"] == "pilula" else caixa * 0.10
        dd.rounded_rectangle(box, radius=rad, fill=tuple(est["cta_cor"]) + (255,))
        camada = Image.alpha_composite(camada, pl)
    if est["contorno"]:
        c = nova()
        passe(c, True, cor_fixa=est["cor_contorno"], sw=max(1, int(size * est["contorno"])), pular=com_forma)
        camada = Image.alpha_composite(camada, c)
    t = nova(); passe(t, False); camada = Image.alpha_composite(camada, t)
    camada.save(path)
    return camada.size


# ── elementos do fim do criativo ──────────────────────────────────────────────
def png_cta(texto, W, path, cor=AMARELO_REF, cor_texto=GRAFITE):
    """A pilula do CTA (referencia: amarela, texto preto, ~45% da largura). Devolve (w, h)."""
    alt_caixa = int(W * 0.054)          # medido na referencia: caixa alta ~5,4% da largura
    size = corpo_para_caixa("mont800", alt_caixa)
    f = carregar("mont800", size)
    bb = f.getbbox(texto.upper()); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    px, py = int(alt_caixa * 0.95), int(alt_caixa * 0.62)
    sh = int(alt_caixa * 0.35)
    w, h = tw + 2 * px, th + 2 * py
    img = Image.new("RGBA", (w + 2 * sh, h + 2 * sh), (0, 0, 0, 0))
    s = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((sh, sh + sh // 3, sh + w, sh + h + sh // 3), radius=int(h * 0.28), fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, s.filter(ImageFilter.GaussianBlur(sh * 0.5)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((sh, sh, sh + w, sh + h), radius=int(h * 0.28), fill=tuple(cor) + (255,))
    d.text((sh + px - bb[0], sh + py - bb[1]), texto.upper(), font=f, fill=tuple(cor_texto) + (255,))
    img.save(path)
    return img.size


def png_seta(W, path, cor=VERMELHO):
    """Seta para baixo, vermelha com contorno escuro (como na referencia). Devolve (w, h)."""
    a = int(W * 0.075); pad = int(a * 0.15)
    img = Image.new("RGBA", (a + 2 * pad, int(a * 1.25) + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hast_w = a * 0.22; cx = pad + a / 2; topo = pad; ponta = pad + a * 1.25; cab = a * 0.55
    poly = [(cx - hast_w / 2, topo), (cx + hast_w / 2, topo), (cx + hast_w / 2, ponta - cab), (pad + a, ponta - cab),
            (cx, ponta), (pad, ponta - cab), (cx - hast_w / 2, ponta - cab)]
    d.polygon(poly, fill=tuple(cor) + (255,), outline=(60, 0, 0, 255))
    d.line(poly + [poly[0]], fill=(60, 0, 0, 255), width=max(2, int(a * 0.05)), joint="curve")
    img.save(path)
    return img.size


def png_selo(texto, W, path, cor=AMARELO_REF):
    """Selo de preco inclinado (ex.: "SO' R$ 10"). Devolve (w, h)."""
    alt_caixa = int(W * 0.06)
    f = carregar("mont900", corpo_para_caixa("mont900", alt_caixa))
    bb = f.getbbox(texto.upper()); tw, th = bb[2] - bb[0], bb[3] - bb[1]
    px, py = int(alt_caixa * 0.7), int(alt_caixa * 0.5)
    w, h = tw + 2 * px, th + 2 * py
    base = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), radius=int(h * 0.22), fill=tuple(cor) + (255,), outline=GRAFITE + (255,),
                        width=max(3, int(alt_caixa * 0.08)))
    d.text((20 + px - bb[0], 20 + py - bb[1]), texto.upper(), font=f, fill=GRAFITE + (255,))
    img = base.rotate(-5, resample=Image.BICUBIC, expand=True)
    img.save(path)
    return img.size


def png_titulo(linhas, W, path, cor=AMARELO_REF, cor_texto=GRAFITE):
    """Selo fixo do produto no topo (modelo 2, criavito2.mp4): caixa amarela arredondada, texto
    preto em caixa alta, 1-2 linhas centradas. Devolve (w, h)."""
    alt_caixa = int(W * 0.036)
    f = carregar("mont800", corpo_para_caixa("mont800", alt_caixa))
    linhas = [l.upper() for l in linhas if l.strip()]
    bbs = [f.getbbox(l) for l in linhas]
    tw = max(b[2] - b[0] for b in bbs); lh = int(alt_caixa * 1.55)
    px, py = int(alt_caixa * 0.8), int(alt_caixa * 0.62)
    w, h = tw + 2 * px, lh * (len(linhas) - 1) + alt_caixa + 2 * py
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w, h), radius=int(alt_caixa * 0.55), fill=tuple(cor) + (255,))
    bh = f.getbbox("H")
    for i, (l, b) in enumerate(zip(linhas, bbs)):
        d.text(((w - (b[2] - b[0])) / 2 - b[0], py + i * lh - bh[1]), l, font=f, fill=tuple(cor_texto) + (255,))
    img.save(path)
    return img.size
