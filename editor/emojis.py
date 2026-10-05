# -*- coding: utf-8 -*-
"""EMOJIS ANIMADOS — um emoji animado sobe acima da legenda quando a narracao diz uma palavra-chave.

Os emojis sao os "Animated Emoji" do Google (Noto), licenca CC BY 4.0 (uso comercial ok, com
atribuicao — ver README), via @remotion/animated-emoji. So' no motor Remotion.
Os arquivos (.webm com transparencia, 512 px) sao baixados na primeira vez e ficam em .cache/emojis.

Regras (para nao virar carnaval):
  - no maximo `max` por video (padrao 4) e um a cada `espaco_s` (padrao 5 s);
  - nada durante o gancho animado (primeiros 2 s) nem depois do CTA (o fecho e' do produto);
  - o mesmo emoji nao repete no mesmo video.
"""
import os, random, unicodedata, urllib.request

from . import config

DIR = os.path.join(config.CACHE_DIR, "emojis")
URL = "https://raw.githubusercontent.com/remotion-dev/animated-emoji/main/public/{nome}-0.5x.webm"

# (comeco das palavras, sem acento) -> emojis possiveis. Ordem = prioridade quando a frase tem varias.
MAPA = [
    (("deus", "jesus", "senhor", "oracao", "orar", "ore", "reza", "abenco", "bencao", "fe"), ["folded-hands", "halo"]),
    (("biblia", "igreja", "batism", "evangel", "cristo", "espiritual"), ["halo", "sparkles"]),
    (("amor", "amar", "ama", "carinho", "coracao", "afeto"), ["red-heart", "heart-grow", "two-hearts"]),
    (("bebe", "nene", "recem", "filhinh"), ["hatching-chick", "baby-chick"]),
    (("filho", "filha", "crianca", "pequen", "netinh"), ["warm-smile", "hug-face"]),
    (("familia", "pais", "mae", "papai", "mamae", "avo", "padrinh", "madrinh", "juntos"), ["hug-face", "two-hearts"]),
    (("presente", "presentear", "lembranca"), ["wrapped-gift", "gift-heart"]),
    (("brinca", "diverti", "ludic", "jogo", "jogar"), ["partying-face", "balloon"]),
    (("aprend", "ensin", "educa", "licao", "historia"), ["light-bulb", "sparkles"]),
    (("facil", "simples", "pratic", "rapido", "pronto"), ["check-mark", "thumbs-up"]),
    (("minuto", "tempo", "rotina", "noite", "dormir", "sono"), ["alarm-clock", "sleep"]),
    (("feliz", "alegria", "sorri", "sorriso"), ["smile", "grin"]),
    (("especial", "magic", "lindo", "linda", "unico", "unica"), ["sparkles", "glowing-star"]),
    (("promoc", "desconto", "oferta", "barato", "preco", "reais"), ["fire", "money-with-wings"]),
    (("gratis", "bonus", "brinde"), ["party-popper", "wrapped-gift"]),
    (("imprim", "impressa"), ["sparkles"]),
    (("medo", "preocup", "dificil", "cansad"), ["worried", "weary"]),
    (("surpre", "incrivel", "uau"), ["star-struck", "mind-blown"]),
]


def _norm(w):
    w = unicodedata.normalize("NFKD", (w or "").lower()).encode("ascii", "ignore").decode()
    return "".join(c for c in w if c.isalnum())


def _emoji_da_palavra(w):
    n = _norm(w)
    if len(n) < 2: return None
    for radicais, emojis in MAPA:
        for r in radicais:
            # radical curto (fe, ama, ore) so' vale como palavra INTEIRA: "fe" nao pega "feliz"
            if (len(r) <= 3 and n == r) or (len(r) > 3 and n.startswith(r)): return emojis
    return None


def escolher(palavras, t_cta, cfg_e, semente, inicio_min=2.0):
    """[{'t','dur','nome','palavra'}] para o plano."""
    if not cfg_e or not cfg_e.get("ativo", True): return []
    rng = random.Random(semente * 7 + 3)
    maximo, espaco, dur = int(cfg_e.get("max", 4)), float(cfg_e.get("espaco_s", 5.0)), float(cfg_e.get("dur_s", 1.7))
    usados, out = set(), []
    for w, a, _b in palavras:
        if a < inicio_min or a > t_cta - dur * 0.6: continue
        if out and a - out[-1]["t"] < espaco: continue
        opcoes = [e for e in (_emoji_da_palavra(w) or []) if e not in usados]
        if not opcoes: continue
        nome = opcoes[0] if rng.random() < 0.7 else rng.choice(opcoes)
        usados.add(nome)
        out.append({"t": round(float(a) - 0.08, 3), "dur": dur, "nome": nome, "palavra": w})
        if len(out) >= maximo: break
    return out


def arquivo(nome):
    """Caminho local do .webm (baixa na primeira vez)."""
    os.makedirs(DIR, exist_ok=True)
    dest = os.path.join(DIR, f"{nome}-0.5x.webm")
    if not os.path.exists(dest):
        tmp = dest + ".parcial"
        with urllib.request.urlopen(URL.format(nome=nome), timeout=60) as r, open(tmp, "wb") as f:
            f.write(r.read())
        os.replace(tmp, dest)
    return dest
