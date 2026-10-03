# -*- coding: utf-8 -*-
"""ALINHAR — o tempo de cada palavra da narracao, com a GRAFIA da copy.

O whisper da' o TEMPO; a copy da' a GRAFIA ("setenta", nao "70"; "Bíblia do Bebê", nao "Bebé").
`casar_texto` foi portado do ow_agente (motor/montar.py), onde ja' estava provado: o portao mede
LETRA e nao palavra, e palavra que o TTS falou a mais fica fora da legenda.

Motores: faster-whisper (padrao, modelo `small` ja' no cache do HF) ou whisper.cpp
(`WHISPER_CPP_DIR`, ex.: C:/Users/edlut/ogtools/tools/whisper).
"""
import difflib, json, os

from . import config

_MODELO = {}


def _faster(wav, modelo, idioma, dica):
    from faster_whisper import WhisperModel
    if modelo not in _MODELO:
        _MODELO[modelo] = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = _MODELO[modelo].transcribe(wav, language=idioma, word_timestamps=True, beam_size=5,
                                         initial_prompt=(dica or "")[:400], vad_filter=False)
    return [(w.word.strip(), float(w.start), float(w.end)) for s in segs for w in (s.words or []) if w.word.strip()]


def _whispercpp(wav, modelo, idioma, dica):
    base = os.environ.get("WHISPER_CPP_DIR", r"C:/Users/edlut/ogtools/tools/whisper")
    exe = os.path.join(base, "Release", "whisper-cli.exe")
    mdl = os.path.join(base, "models", f"ggml-{modelo}.bin")
    out = wav + ".wcpp"
    config.run([exe, "-m", mdl, "-l", idioma, "-ml", "1", "-sow", "-ojf", "-of", out, "--prompt", (dica or "")[:300], wav],
               capture_output=True)
    d = json.load(open(out + ".json", encoding="utf-8"))
    return [(s["text"].strip(), s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000)
            for s in d["transcription"] if s["text"].strip()]


def ouvir(wav, cfg, dica=""):
    """[(palavra, t0, t1)] do audio, com cache ao lado do wav."""
    cache = wav + ".palavras.json"
    chave = f"{os.path.getsize(wav)}|{os.path.getmtime(wav)}|{cfg['motor']}|{cfg['modelo']}"
    d = config.ler_json(cache)
    if d and d.get("chave") == chave: return [tuple(x) for x in d["palavras"]]
    fn = _whispercpp if cfg.get("motor") == "whispercpp" else _faster
    try:
        pal = fn(wav, cfg["modelo"], cfg["idioma"], dica)
    except ImportError:
        pal = _whispercpp(wav, cfg["modelo"], cfg["idioma"], dica)
    config.escrever_json(cache, {"chave": chave, "palavras": pal})
    return pal


def _cmp(p):
    import unicodedata
    p = unicodedata.normalize("NFKD", (p or "").lower()).encode("ascii", "ignore").decode()
    return "".join(ch for ch in p if ch.isalnum())


def casar_texto(ouvidas, esperado):
    """Poe a GRAFIA esperada sobre os TEMPOS ouvidos. Devolve (palavras, relatorio).

    Diferenca para o ow_agente: palavra da copy que o whisper NAO ouviu (tag 'delete') entra com
    tempo interpolado entre as vizinhas — aqui o audio veio da propria copy via TTS, entao a
    palavra FOI dita; omitir da legenda seria buraco na tela."""
    exp = [w for w in (esperado or "").split() if w.strip()]
    if not exp or not ouvidas: return list(ouvidas), {"razao": 0.0, "trocas": 0, "extras": 0, "faltas": 0}
    A, B = [_cmp(w) for w in exp], [_cmp(w[0]) for w in ouvidas]
    razao = difflib.SequenceMatcher(None, " ".join(A), " ".join(B)).ratio()
    rel = {"razao": round(razao, 3), "trocas": 0, "extras": 0, "faltas": 0}
    if razao < 0.70:
        return list(ouvidas), rel
    fora = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag == "equal":
            for d in range(i2 - i1): fora.append((exp[i1 + d], ouvidas[j1 + d][1], ouvidas[j1 + d][2]))
        elif tag == "replace":
            t0, t1 = ouvidas[j1][1], ouvidas[j2 - 1][2]; n = max(1, i2 - i1); passo = (t1 - t0) / n
            for d in range(i2 - i1):
                fora.append((exp[i1 + d], t0 + d * passo, t0 + (d + 1) * passo)); rel["trocas"] += 1
        elif tag == "insert":
            rel["extras"] += j2 - j1
        elif tag == "delete":
            t0 = fora[-1][2] if fora else (ouvidas[0][1] if ouvidas else 0.0)
            t1 = ouvidas[j1][1] if j1 < len(ouvidas) else t0 + 0.25 * (i2 - i1)
            t1 = max(t1, t0 + 0.12 * (i2 - i1)); passo = (t1 - t0) / (i2 - i1)
            for d in range(i2 - i1):
                fora.append((exp[i1 + d], t0 + d * passo, t0 + (d + 1) * passo)); rel["faltas"] += 1
    return fora, rel


def alinhar(wav, copy, cfg):
    ouvidas = ouvir(wav, cfg, dica=copy)
    palavras, rel = casar_texto(ouvidas, copy)
    rel["ouvido"] = " ".join(w[0] for w in ouvidas)
    return palavras, rel
