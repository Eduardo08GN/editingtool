# -*- coding: utf-8 -*-
"""SFX — o plano de efeitos sonoros de cada criativo, a partir das PALAVRAS e dos CORTES.

⭐ Regras (sfx/catalogo.json):
  1. abertura: um "revelar"/"transicao" em t=0 (gancho).
  2. gatilhos: palavra da copy -> categoria (deus/fe -> angelical, brincadeira -> brinquedo,
     minutinhos -> tempo, reais -> pop...). Cada categoria toca no maximo N vezes.
  3. CTA: um "pop" quando a narracao chega no "clique".
  4. cortes: whoosh em parte dos cortes de cena (um sim, um nao).
  5. respiro: nada a menos de `sfx_espaco_min_s` de outro SFX; prioridade na ordem acima.
⛔ So' arquivo com "liberado": true entra (meme/marca fica fora — Rights Manager da Meta).
⭐ Variacao: a semente do criativo escolhe QUAL arquivo de cada categoria, para os 25 criativos
   nao soarem iguais.
"""
import io, json, os, random, unicodedata

from . import config

CATALOGO = os.path.join(config.SFX_DIR, "catalogo.json")
DRIVE_PASTA = "https://drive.google.com/drive/folders/1HCqd9TRGvktSj5T6Kd2V4DzzZA05sVq1"


PICOS = os.path.join(config.CACHE_DIR, "sfx_picos.json")
ENTRADA_MAX = 0.6        # ate' quanto do "embalo" antes do pico entra (o resto do comeco do arquivo e' cortado)


def pico(arquivo):
    """Segundos do arquivo ate' o ponto mais alto (o "impacto"), com cache.
    ⭐ 2026-10-03 (tecnica do awesome-opus5-5-videos): o SFX entra para que o PICO, e nao o inicio do
    arquivo, caia no evento. Medido: o whoosh tem o pico em 0,51 s — antes ele chegava meio segundo atrasado."""
    import subprocess, numpy as np
    st = os.stat(arquivo); chave = f"{os.path.abspath(arquivo)}|{st.st_size}|{int(st.st_mtime)}"
    cache = config.ler_json(PICOS, {}) or {}
    if chave in cache: return cache[chave]
    raw = config.run([config.FFMPEG, "-v", "error", "-i", arquivo, "-t", "4", "-ac", "1", "-ar", "8000", "-f", "f32le", "-"],
                     capture_output=True).stdout
    a = np.abs(np.frombuffer(raw, np.float32))
    env = np.convolve(a, np.ones(80) / 80, "same") if len(a) > 80 else a
    t = round(float(np.argmax(env)) / 8000, 3) if len(env) else 0.0
    cache[chave] = t; config.escrever_json(PICOS, cache)
    return t


def janela(arquivo, max_s):
    """(inicio_no_arquivo, duracao): um pouco de embalo antes do pico e a cauda depois dele."""
    pk = pico(arquivo)
    entrada = min(pk, ENTRADA_MAX)
    cauda = max(0.4, float(max_s) - pk)
    return round(pk - entrada, 3), round(entrada + cauda, 3), entrada


FREQS = os.path.join(config.CACHE_DIR, "sfx_freqs.json")
PROC = os.path.join(config.CACHE_DIR, "sfx_proc")
ESCALA = {"maior": [0, 2, 4, 5, 7, 9, 11], "menor": [0, 2, 3, 5, 7, 8, 10]}
AFINAVEIS = {"pop", "brinquedo", "fofo"}        # sons com nota clara; whoosh/impacto/revelar nao se afinam


def freq_dominante(arquivo):
    """Frequencia (Hz) mais forte logo depois do pico do som (o "tom" dele), com cache."""
    import numpy as np
    st = os.stat(arquivo); chave = f"{os.path.abspath(arquivo)}|{st.st_size}|{int(st.st_mtime)}"
    cache = config.ler_json(FREQS, {}) or {}
    if chave in cache: return cache[chave]
    raw = config.run([config.FFMPEG, "-v", "error", "-i", arquivo, "-t", "4", "-ac", "1", "-ar", "22050", "-f", "f32le", "-"],
                     capture_output=True).stdout
    a = np.frombuffer(raw, np.float32)
    ini = int(pico(arquivo) * 22050); trecho = a[ini: ini + 2048]
    f = 0.0
    if len(trecho) > 256:
        esp = np.abs(np.fft.rfft(trecho * np.hanning(len(trecho))))
        fr = np.fft.rfftfreq(len(trecho), 1 / 22050)
        ok = (fr > 150) & (fr < 4000)
        if ok.any(): f = float(fr[ok][np.argmax(esp[ok])])
    cache[chave] = round(f, 1); config.escrever_json(FREQS, cache)
    return cache[chave]


def semitons_para_escala(f0, tom, grau=0):
    """Quantos semitons levam f0 ate' a nota da escala (grau 0 = a mais perto; 1, 2... = notas acima na escala)."""
    import math
    if not f0 or not tom: return 0.0
    tonica, modo = tom
    nota = 12 * math.log2(f0 / 261.63) - tonica                 # semitons acima da tonica (Do4 = 261,63 Hz)
    graus = ESCALA.get(modo, ESCALA["maior"])
    cand = [o * 12 + g for o in range(-3, 4) for g in graus]
    perto = min(cand, key=lambda c: abs(c - nota))
    i = cand.index(perto) + grau * 2                            # grau 1 = uma terca acima (2 notas da escala)
    alvo = cand[min(max(i, 0), len(cand) - 1)]
    s = alvo - nota
    while s > 6: s -= 12                                        # nunca mais de meia oitava: soaria outro som
    while s < -6: s += 12
    return round(s, 2)


def processar(arquivo, fator):
    """O som tocado `fator` vezes mais rapido (e agudo). 1.0 = o original. Cache em .cache/sfx_proc."""
    if abs(fator - 1.0) < 0.01: return arquivo
    import hashlib
    st = os.stat(arquivo)
    chave = hashlib.sha1(f"{os.path.abspath(arquivo)}|{st.st_size}|{int(st.st_mtime)}|{fator:.4f}".encode()).hexdigest()[:16]
    dest = os.path.join(PROC, f"{chave}.wav")
    if not os.path.exists(dest):
        os.makedirs(PROC, exist_ok=True)
        r = config.ffmpeg(["-i", arquivo, "-af", f"aresample=48000,asetrate={48000 * fator:.1f},aresample=48000", "-ac", "2", dest])
        if r.returncode != 0: return arquivo
    return dest


def som(arq, meta, evento, categoria, motivo, base_db, fator=1.0):
    """Uma entrada de SFX com o PICO no evento, ja' com o fator (afinacao/velocidade) aplicado."""
    ini_arq, dur, entrada = janela(arq, meta.get("max_s", 1.0))
    if abs(fator - 1.0) >= 0.01:
        arq = processar(arq, fator)
        ini_arq, dur, entrada = ini_arq / fator, dur / fator, entrada / fator
    inicio = evento - entrada
    if inicio < 0: ini_arq, dur, inicio = ini_arq - inicio, dur + inicio, 0.0
    return {"t": round(inicio, 3), "evento": round(evento, 3), "arquivo": arq, "inicio_arquivo": round(ini_arq, 3),
            "db": base_db + float(meta.get("db", 0)), "max_s": round(max(0.1, dur), 3), "categoria": categoria,
            "motivo": motivo, "fator": round(fator, 3)}


def avulso(categoria, evento, motivo, cfg_audio, semente, tom=None, grau=0, db_extra=0.0):
    """Um som de uma categoria do pool num instante (para o gancho e o fecho animados)."""
    import random
    disp = disponiveis()
    lst = disp.get(categoria) or []
    if not lst: return None
    arq, meta = random.Random(semente).choice(lst)
    fator = 1.0
    if categoria in AFINAVEIS and tom:
        fator = 2 ** (semitons_para_escala(freq_dominante(arq), tom, grau) / 12)
    e = som(arq, meta, evento, categoria, motivo, float(cfg_audio.get("sfx_db", -11)) + db_extra, fator)
    return e


def catalogo():
    return json.load(io.open(CATALOGO, encoding="utf-8"))


def _norm(p):
    p = unicodedata.normalize("NFKD", (p or "").lower()).encode("ascii", "ignore").decode()
    return "".join(c for c in p if c.isalnum())


def disponiveis(cat=None):
    """{categoria: [(arquivo_abs, meta)]} so' com liberados que existem no pool."""
    out = {}
    for nome, meta in cat_or(cat)["arquivos"].items():
        p = os.path.join(config.SFX_POOL, nome)
        if meta.get("liberado") and os.path.exists(p):
            out.setdefault(meta["cat"], []).append((p, meta))
    return out


def cat_or(cat):
    return cat if cat is not None else catalogo()


def plano(palavras, cortes, total, cfg_audio, semente, cat=None, transicoes=None, tom=None):
    """[{'t','arquivo','db','max_s','motivo'}] ordenado por tempo."""
    cat = cat_or(cat)
    disp = disponiveis(cat)
    if not disp or not cfg_audio.get("sfx", True): return []
    rng = random.Random(semente)
    espaco = float(cfg_audio.get("sfx_espaco_min_s", 1.4))
    base_db = float(cfg_audio.get("sfx_db", -11))

    def pega(categoria):
        lst = disp.get(categoria) or []
        return rng.choice(lst) if lst else None

    cand = []      # (prioridade, t, categoria, motivo[, duracao do movimento])
    for c in cat.get("abertura") or []:
        if c in disp: cand.append((0, 0.0, c, "abertura")); break
    i_cta = indice_cta(palavras)
    if i_cta is not None and cat.get("cta") in disp:
        cand.append((1, palavras[i_cta][1], cat["cta"], "cta"))
    usados = {}
    fim_fala = palavras[i_cta][1] if i_cta is not None else total
    for w, t0, _t1 in palavras:
        n = _norm(w)
        for c, g in cat.get("gatilhos", {}).items():
            if c.startswith("_") or c not in disp: continue
            if n in g["palavras"] and usados.get(c, 0) < g.get("vezes", 1) and t0 < fim_fala:
                usados[c] = usados.get(c, 0) + 1
                cand.append((3, t0, c, f"palavra '{w}'"))
    if transicoes:
        # ⭐ o whoosh casa com a transicao ANIMADA (nao com corte seco); o respiro minimo entre SFX
        #    mantem a densidade que o operador aprovou em 2026-10-03 (~1 a cada 4 s)
        efeitos = [t for t in transicoes if t.get("sfx") and 0.5 < t["t"] < fim_fala - 0.3]
        for k, tr in enumerate(efeitos):
            c = tr["sfx"] if tr["sfx"] in disp else cat.get("cortes")
            if c in disp:      # ⭐ transicao animada tem prioridade sobre palavra-chave (2026-10-03)
                cand.append((2, tr["t"], c, f"transicao {tr['tipo']}", float(tr.get("dur", 0.3))))
    elif cat.get("cortes") in disp:
        for k, tc in enumerate(cortes):
            if k % 3 == 0 and 0.5 < tc < fim_fala - 0.3:
                cand.append((3, tc, cat["cortes"], "corte"))

    aceitos = []
    vezes = {}
    for item in sorted(cand, key=lambda x: (x[0], x[1])):
        pri, t, c, motivo = item[:4]
        mov = item[4] if len(item) > 4 else None
        if any(abs(t - a["evento"]) < espaco for a in aceitos): continue      # respiro medido entre EVENTOS
        esc = pega(c)
        if not esc: continue
        arq, meta = esc
        k = vezes.get(c, 0); vezes[c] = k + 1
        # ⭐ (motion-graphics-skills) 1) som com nota afinado na musica; repeticoes sobem na escala
        #    (tonica, terca, quinta); 2) whoosh com o tamanho do movimento; 3) outros variam um pouco
        if c in AFINAVEIS and tom:
            fator = 2 ** (semitons_para_escala(freq_dominante(arq), tom, k % 3) / 12)
        elif mov and c == "transicao":                     # so' whoosh se estica/encolhe
            _i, _d, entrada0 = janela(arq, meta.get("max_s", 1.0))
            fator = min(1.45, max(0.85, entrada0 / max(0.15, mov * 1.6)))
        else:
            fator = 2 ** ([0, 1, -1, 2, -2][k % 5] / 12)
        aceitos.append(som(arq, meta, t, c, motivo, base_db, fator))
    return sorted(aceitos, key=lambda a: a["t"])


def indice_cta(palavras, gatilho="clique"):
    """Indice da palavra que abre o CTA final ("Clique em saiba mais..."), procurando do fim."""
    # ⭐ 2026-10-05: copy do time fecha com "Clica no botao aqui embaixo" — o CTA nao era achado
    alvos = {_norm(gatilho), "clique", "clica", "toque", "toca", "aperte", "aperta"}
    for i in range(len(palavras) - 1, -1, -1):
        if _norm(palavras[i][0]) in alvos: return i
    return None


def sync():
    """Baixa a pasta do Drive para sfx/pool/ (precisa de `pip install gdown`)."""
    try:
        import gdown
    except ImportError:
        raise SystemExit("instale o gdown: pip install gdown  (ou baixe a pasta manualmente para sfx/pool/)\n" + DRIVE_PASTA)
    os.makedirs(config.SFX_POOL, exist_ok=True)
    gdown.download_folder(DRIVE_PASTA, output=config.SFX_POOL, quiet=False, remaining_ok=True)
    return relatorio()


def relatorio():
    cat = catalogo(); linhas = []
    for nome, meta in sorted(cat["arquivos"].items(), key=lambda x: (not x[1].get("liberado"), x[1]["cat"])):
        tem = os.path.exists(os.path.join(config.SFX_POOL, nome))
        linhas.append(f"  {'OK ' if meta.get('liberado') else 'BLQ'} {'   ' if tem else 'FALTA'} {meta['cat']:<12} {nome}"
                      + (f"   ({meta.get('motivo')})" if not meta.get("liberado") else ""))
    soltos = sorted(set(os.listdir(config.SFX_POOL)) - set(cat["arquivos"])) if os.path.isdir(config.SFX_POOL) else []
    for s in soltos: linhas.append(f"  ??? novo         {s}   (sem entrada no catalogo: nao entra em video)")
    return "\n".join(linhas)
