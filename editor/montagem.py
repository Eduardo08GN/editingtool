# -*- coding: utf-8 -*-
"""MONTAGEM — do video base + narracao alinhada ao PLANO de edicao (puro dado, sem render).

O plano (plano.json) diz tudo que o render precisa: planos de camera (de onde vem cada trecho
do video base, com que zoom), cartoes de legenda, CTA, selo de preco, SFX e musica. Separar
plano de render permite conferir/ajustar um criativo sem re-renderizar e testar as regras sem
ffmpeg.

⭐ Cortes casados com a VOZ: o corte cai no inicio de um cartao de legenda (troca de frase),
   entre `plano_min_s` e `plano_max_s` — e' o que faz parecer editado por gente.
⭐ Variacao entre criativos: a semente (id do criativo) gira o ponto de partida no video base
   e o padrao de zoom; o ultimo plano (CTA) fica fixo no FIM do base, onde costuma estar o
   "money shot" (no exemplo: o leque de cards).
"""
import os, random, re, unicodedata, zlib

from . import config, sfx as _sfx

PONTUACAO_FIM = re.compile(r"[.,!?;:]$")


def semente(cri_id, campanha=""):
    return zlib.crc32(f"{campanha}|{cri_id}".encode()) & 0xFFFFFFFF


# ── video base ────────────────────────────────────────────────────────────────
def analisar_base(base):
    """{'duracao','w','h','fps','cortes':[t...]} com cache ao lado do arquivo."""
    cache = base + ".analise.json"
    st = os.stat(base); chave = f"{st.st_size}|{int(st.st_mtime)}"
    d = config.ler_json(cache)
    if d and d.get("chave") == chave: return d
    info = config.probe(base)
    r = config.run([config.FFMPEG, "-hide_banner", "-i", base, "-an", "-vf",
                    "scale=320:-2,select='gt(scene,0.30)',showinfo", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    cortes = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr or "")]
    d = {"chave": chave, "duracao": info["duracao"], "w": info.get("w"), "h": info.get("h"),
         "fps": info.get("fps"), "cortes": cortes}
    config.escrever_json(cache, d)
    return d


def janela(an, cfg_v):
    """(ini, fim) do trecho UTIL do base. `video.janela_base` corta pontas (ex.: um fim com CTA antigo)."""
    j = cfg_v.get("janela_base") or [0.0, an["duracao"]]
    ini = max(0.0, float(j[0])); fim = min(an["duracao"], float(j[1]) if j[1] else an["duracao"])
    return ini, fim


def pecas_do_base(an, alvo=2.6, ini=0.0, fim=None):
    """Divide o base em pecas: corta nos cortes de cena e quebra trechos longos em ~alvo s."""
    fim = an["duracao"] if fim is None else fim
    marcas = [ini] + [c for c in an["cortes"] if ini + 0.3 < c < fim - 0.3] + [fim]
    pecas = []
    for a, b in zip(marcas, marcas[1:]):
        n = max(1, int(round((b - a) / alvo)))
        for k in range(n):
            pecas.append((a + (b - a) * k / n, a + (b - a) * (k + 1) / n))
    return pecas


# ── legenda ───────────────────────────────────────────────────────────────────
def cartoes(palavras, n_max=3, ate=None):
    """Agrupa palavras em cartoes: nunca atravessa fim de frase/virgula e, dentro da frase,
    divide EQUILIBRADO (16 palavras -> 3,3,3,3,2,2), sem sobrar palavra sozinha no fim
    ("COMPROMISSO O TEMPO" / "TODO:" era o defeito). Devolve [{'palavras','tempos','t0','t1'}]."""
    import math
    lim = len(palavras) if ate is None else ate
    frases, atual = [], []
    for w in palavras[:lim]:
        atual.append(w)
        if PONTUACAO_FIM.search(w[0]): frases.append(atual); atual = []
    if atual: frases.append(atual)
    out = []
    for fr in frases:
        k = max(1, math.ceil(len(fr) / n_max))
        base, extra = divmod(len(fr), k)
        i = 0
        for j in range(k):
            n = base + (1 if j < extra else 0)
            out.append(fr[i:i + n]); i += n
    res = []
    for c in out:
        res.append({"palavras": [w for w, _, _ in c], "tempos": [(a, b) for _, a, b in c], "t0": c[0][1], "t1": c[-1][2]})
    return res


# ── linha do tempo ────────────────────────────────────────────────────────────
def linha_do_tempo(total, inicios_cartao, an, cfg_v, sem):
    """[{'dur','src','zoom'}] cobrindo `total` s."""
    rng = random.Random(sem)
    mn, mx = float(cfg_v["plano_min_s"]), float(cfg_v["plano_max_s"])
    cortes, t = [], 0.0
    cand = sorted(c for c in inicios_cartao if c > mn * 0.9)
    while total - t > mx:
        ok = [c for c in cand if t + mn <= c <= t + mx]
        nxt = rng.choice(ok[:3]) if ok else t + (mn + mx) / 2
        if total - nxt < mn: break
        cortes.append(nxt); t = nxt
    marcas = [0.0] + cortes + [total]
    duracoes = [b - a for a, b in zip(marcas, marcas[1:])]

    ini, D = janela(an, cfg_v)
    pecas = pecas_do_base(an, ini=ini, fim=D)
    zooms = list(cfg_v.get("zooms") or [1.0])
    z0 = rng.randrange(len(zooms))
    ordem = cfg_v.get("ordem", "rotacionada")
    if ordem == "embaralhada": idx = list(range(len(pecas))); rng.shuffle(idx)
    else:
        ini = rng.randrange(len(pecas)); idx = [(ini + k) % len(pecas) for k in range(len(pecas))]
    planos = []
    for k, d in enumerate(duracoes):
        ultimo = k == len(duracoes) - 1
        if ultimo and cfg_v.get("ultimo_plano_fixo", True):
            src = max(ini, D - d - 0.15)
        else:
            a, b = pecas[idx[k % len(idx)]]
            folga = (b - a) - d
            src = a + (rng.uniform(0, folga) if folga > 0 else 0.0)
            src = max(ini, min(src, D - d - 0.05))
        planos.append({"dur": round(d, 3), "src": round(src, 3), "zoom": zooms[(z0 + k) % len(zooms)]})
    return planos, cortes


# ── preco ─────────────────────────────────────────────────────────────────────
NUM = {"um": 1, "dois": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
       "onze": 11, "doze": 12, "treze": 13, "quinze": 15, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
       "sessenta": 60, "setenta": 70, "noventa": 90, "cem": 100}


def _norm(p):
    p = unicodedata.normalize("NFKD", (p or "").lower()).encode("ascii", "ignore").decode()
    return "".join(c for c in p if c.isalnum())


def momento_preco(palavras, cfg_p):
    """(t, texto_do_selo) quando a narracao fala o preco, ou None."""
    g = _norm(cfg_p.get("gatilho") or "reais")
    for i, (w, t0, _t1) in enumerate(palavras):
        if _norm(w) == g:
            if cfg_p.get("selo"): return t0, cfg_p["selo"]
            ant = _norm(palavras[i - 1][0]) if i else ""
            val = int(ant) if ant.isdigit() else NUM.get(ant)
            t_ini = palavras[i - 1][1] if i else t0
            return (t_ini, f"SÓ R$ {val}") if val else (t_ini, "PREÇO ESPECIAL")
    return None


# ── o plano inteiro ───────────────────────────────────────────────────────────
def planejar(cri, palavras, dur_narracao, base, cfg, campanha="", musica_escolhida=None):
    sem = semente(cri["id"], campanha)
    an = analisar_base(base)
    total = round(dur_narracao + float(cfg["video"]["segura_final_s"]), 3)
    i_cta = _sfx.indice_cta(palavras, cfg["cta"]["gatilho"])
    ate = i_cta if (i_cta is not None and cfg["legenda"].get("esconder_no_cta", True)) else None
    cards = cartoes(palavras, int(cfg["legenda"]["palavras_por_cartao"]), ate)
    planos, cortes = linha_do_tempo(total, [c["t0"] for c in cards], an, cfg["video"], sem)
    t_cta = palavras[i_cta][1] if i_cta is not None else max(0.0, total - 3.0)
    preco = momento_preco(palavras, cfg["preco"]) if cri.get("preco") else None
    return {
        "id": cri["id"], "semente": sem, "total": total, "base": os.path.abspath(base),
        "planos": planos, "cortes": [round(c, 3) for c in cortes],
        "cartoes": cards, "cta": {"t": round(t_cta, 3), "texto": cfg["cta"]["texto"]},
        "preco": ({"t": round(preco[0], 3), "texto": preco[1]} if preco else None),
        "sfx": _sfx.plano(palavras, cortes, total, cfg["audio"], sem),
        "musica": musica_escolhida,
    }
