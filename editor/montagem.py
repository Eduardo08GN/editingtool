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
def _analisar_arquivo(arq):
    """{'arquivo','duracao','w','h','fps','cortes'} com cache ao lado do arquivo."""
    cache = arq + ".analise.json"
    st = os.stat(arq); chave = f"{st.st_size}|{int(st.st_mtime)}"
    d = config.ler_json(cache)
    if d and d.get("chave") == chave: return d
    info = config.probe(arq)
    r = config.run([config.FFMPEG, "-hide_banner", "-i", arq, "-an", "-vf",
                    "scale=320:-2,select='gt(scene,0.30)',showinfo", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    cortes = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr or "")]
    d = {"chave": chave, "arquivo": os.path.abspath(arq), "duracao": info["duracao"], "w": info.get("w"),
         "h": info.get("h"), "fps": info.get("fps"), "cortes": cortes}
    config.escrever_json(cache, d)
    return d


EXT_VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".webm")


def _ordem_natural(nome):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", nome)]


def analisar_base(base):
    """Base = UM video ou uma PASTA de clipes (2026-10-03: o operador entrega 17 clipes soltos).
    Devolve {'pasta': bool, 'clipes': [analise de cada clipe, em ordem natural], 'duracao': soma}."""
    if os.path.isdir(base):
        arqs = sorted((f for f in os.listdir(base) if f.lower().endswith(EXT_VIDEO) and ".limpo." not in f),
                      key=_ordem_natural)
        if not arqs: raise SystemExit(f"nenhum video na pasta base: {base}")
        clipes = [_analisar_arquivo(os.path.join(base, f)) for f in arqs]
        return {"pasta": True, "clipes": clipes, "duracao": sum(c["duracao"] for c in clipes)}
    c = _analisar_arquivo(base)
    return {"pasta": False, "clipes": [c], "duracao": c["duracao"], "cortes": c["cortes"]}


def janela(an, cfg_v):
    """(ini, fim) do trecho UTIL do base. `video.janela_base` corta pontas (ex.: um fim com CTA antigo)."""
    j = cfg_v.get("janela_base") or [0.0, an["duracao"]]
    ini = max(0.0, float(j[0])); fim = min(an["duracao"], float(j[1]) if j[1] else an["duracao"])
    return ini, fim


def pecas_do_base(an, alvo=2.6, ini=0.0, fim=None):
    """Divide UM clipe em pecas: corta nos cortes de cena e quebra trechos longos em ~alvo s."""
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
IMA_BATIDA_S = 0.14
FOLGA_CLIPE = 0.3         # imagem que o plano precisa alem do proprio tempo (meias-transicoes)       # o corte so' "pula" para a batida se ela estiver a ate' isto da troca de frase


def linha_do_tempo(total, inicios_cartao, an, cfg_v, sem, batidas=None):
    """[{'dur','src','zoom'}] cobrindo `total` s.
    ⭐ Com `batidas` (grade da musica): entre as trocas de frase possiveis, prefere a que esta' mais perto
    de uma batida e, se a batida estiver a ate' IMA_BATIDA_S, o corte vai PARA a batida — a fala continua
    casada com a imagem e a edicao ganha o ritmo da musica."""
    rng = random.Random(sem)
    mn, mx = float(cfg_v["plano_min_s"]), float(cfg_v["plano_max_s"])
    bt = sorted(batidas or [])

    def perto(x):
        if not bt: return None, 9.0
        import bisect
        i = bisect.bisect_left(bt, x)
        viz = [b for b in bt[max(0, i - 1):i + 1]]
        b = min(viz, key=lambda b: abs(b - x)); return b, abs(b - x)

    cortes, t = [], 0.0
    cand = sorted(c for c in inicios_cartao if c > mn * 0.9)
    while total - t > mx:
        ok = [c for c in cand if t + mn <= c <= t + mx]
        if ok and bt:
            ok = sorted(ok, key=lambda c: perto(c)[1])[:2]
            nxt = rng.choice(ok)
            b, d = perto(nxt)
            if b is not None and d <= IMA_BATIDA_S and b - t >= mn * 0.85: nxt = b
        elif ok:
            nxt = rng.choice(ok[:3])
        else:
            nxt = t + (mn + mx) / 2
            b, d = perto(nxt)
            if b is not None and d <= 0.5: nxt = b
        if total - nxt < mn: break
        cortes.append(round(nxt, 3)); t = nxt
    marcas = [0.0] + cortes + [total]
    duracoes = [b - a for a, b in zip(marcas, marcas[1:])]

    # ⭐ FONTES: cada clipe vira uma lista de pecas; o video percorre os clipes NA ORDEM DA HISTORIA
    #    (imprimir -> recortar -> cards -> mesa), comecando num ponto diferente por criativo.
    #    Arquivo unico = as pecas dele fazem o papel de clipes (comportamento antigo).
    if an.get("pasta"):
        grupos = [[(c["arquivo"], a, b) for a, b in pecas_do_base(c)] for c in an["clipes"]]
        ultimo_clipe = an["clipes"][-1]
    else:
        c = an["clipes"][0]; ini, D = janela(c, cfg_v)
        grupos = [[(c["arquivo"], a, b)] for a, b in pecas_do_base(c, ini=ini, fim=D)]
        ultimo_clipe = dict(c, duracao=D)
    dur_clipe = {}
    for g in grupos:
        for arq, a, b in g: dur_clipe[arq] = max(dur_clipe.get(arq, 0), b)
    zooms = list(cfg_v.get("zooms") or [1.0])
    z0 = rng.randrange(len(zooms))
    nG = len(grupos)
    ordem = list(range(nG))
    if cfg_v.get("ordem") == "embaralhada": rng.shuffle(ordem)
    else:
        ini_g = rng.randrange(nG); ordem = [(ini_g + k) % nG for k in range(nG)]
    fixo_final = cfg_v.get("ultimo_plano_fixo", True)
    if fixo_final and an.get("pasta"):          # o clipe final fica reservado para o fecho
        ordem = [g for g in ordem if grupos[g][0][0] != ultimo_clipe["arquivo"]] or ordem
    planos, cursor = [], 0
    for k, d in enumerate(duracoes):
        if k == len(duracoes) - 1 and fixo_final:
            arq = ultimo_clipe["arquivo"]
            planos.append({"arquivo": arq, "dur": round(d, 3), "src": round(max(0.0, ultimo_clipe["duracao"] - d - 0.15), 3),
                           "zoom": zooms[(z0 + k) % len(zooms)]}); continue
        escolha = None
        for tent in range(len(ordem)):
            g = grupos[ordem[(cursor + tent) % len(ordem)]]
            # peca que caiba o plano inteiro; senao, qualquer trecho do clipe com folga
            # ⛔ 2026-10-04 (4.1): o plano usa imagem tambem na meia-transicao antes e depois do corte;
            #    sem esta folga, um plano no fim de um clipe curto congelava ~0,13 s
            boas = [p for p in g if p[2] - p[1] >= d + FOLGA_CLIPE]
            if boas: escolha = rng.choice(boas); cursor += tent + 1; break
            if dur_clipe[g[0][0]] >= d + 2 * FOLGA_CLIPE:
                arq = g[0][0]; a = rng.uniform(FOLGA_CLIPE, dur_clipe[arq] - d - FOLGA_CLIPE); escolha = (arq, a, a + d); cursor += tent + 1; break
        if escolha is None:          # nenhum clipe comporta: usa o mais longo
            arq = max(dur_clipe, key=dur_clipe.get); escolha = (arq, 0.0, dur_clipe[arq])
        arq, a, b = escolha
        folga = (b - a) - d
        src = a + (rng.uniform(0, folga) if folga > 0 else 0.0)
        src = max(min(FOLGA_CLIPE, max(0.0, dur_clipe[arq] - d)), min(src, dur_clipe[arq] - d - FOLGA_CLIPE))
        planos.append({"arquivo": arq, "dur": round(d, 3), "src": round(src, 3), "zoom": zooms[(z0 + k) % len(zooms)]})
    return planos, cortes


# ── transicoes ────────────────────────────────────────────────────────────────
def transicoes(cortes, cfg_t, sem):
    from . import transicoes as _tr
    return _tr.sortear(cortes, cfg_t, sem)


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
def planejar(cri, palavras, dur_narracao, base, cfg, campanha="", musica_escolhida=None, campanha_produto=""):
    sem = semente(cri["id"], campanha)
    an = analisar_base(base)
    total = round(dur_narracao + float(cfg["video"]["segura_final_s"]), 3)
    mod_cfg = cfg.get("modelo", "1")
    modelo = str((int(cri["id"].split(".")[-1]) % 2) + 1) if mod_cfg == "alternar" else str(mod_cfg)
    M = (cfg.get("modelos") or {}).get(modelo, {})
    i_cta = _sfx.indice_cta(palavras, cfg["cta"]["gatilho"])
    esconde = M.get("esconder_legenda_no_cta", cfg["legenda"].get("esconder_no_cta", True))
    ate = i_cta if (i_cta is not None and esconde) else None
    cards = cartoes(palavras, int(cfg["legenda"]["palavras_por_cartao"]), ate)
    grade_bt, bpm = None, None
    if musica_escolhida and cfg["video"].get("cortar_na_batida", True):
        try:
            from . import musica as _mus
            bpm, grade_bt = _mus.grade(musica_escolhida["arquivo"], musica_escolhida.get("dur_s") or 60, total)
        except Exception as e:                               # noqa: BLE001 — sem batida, corta so' pela fala
            print(f"   batida: nao consegui analisar a musica ({e}); cortando so' pela fala")
    planos, cortes = linha_do_tempo(total, [c["t0"] for c in cards], an, cfg["video"], sem, grade_bt)
    t_cta = palavras[i_cta][1] if i_cta is not None else max(0.0, total - 3.0)
    preco = momento_preco(palavras, cfg["preco"]) if cri.get("preco") else None
    trans = transicoes(cortes, cfg["transicoes"], sem) if cfg.get("transicoes") else []
    titulo = None
    if M.get("titulo"):
        txt = cfg.get("titulo_texto") or ""
        linhas = [l.strip() for l in txt.split(chr(10))] if txt else []
        if not linhas and campanha_produto:
            a, _, b = campanha_produto.partition(":")
            linhas = [a.strip() + (":" if b else ""), b.strip()] if b else [a.strip()]
        if linhas:
            lim = float(M.get("titulo_ate_frac", 0.62)) * total
            fim = min([c for c in cortes if c >= lim] or [lim])
            titulo = {"linhas": linhas, "t0": 0.0, "t1": round(min(fim, t_cta), 3)}
    return {
        "id": cri["id"], "semente": sem, "total": total, "base": os.path.abspath(base),
        "modelo": modelo, "layout": M, "titulo": titulo, "bpm": bpm,
        "planos": planos, "cortes": [round(c, 3) for c in cortes],
        "cartoes": cards, "cta": {"t": round(t_cta, 3), "texto": cfg["cta"]["texto"]},
        "preco": ({"t": round(preco[0], 3), "texto": preco[1]} if preco else None),
        "transicoes": trans,
        "sfx": _sfx.plano(palavras, cortes, total, cfg["audio"], sem, transicoes=trans),
        "musica": musica_escolhida,
    }
