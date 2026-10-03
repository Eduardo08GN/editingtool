# -*- coding: utf-8 -*-
"""TTS — a narracao de cada criativo. MiniMax T2A v2 (principal), Kokoro local (teste/reserva).

⭐ A COPY E' SAGRADA: o texto vai para o TTS exatamente como esta' na campanha.
⭐ CACHE POR CONTEUDO: mesma copy + mesma voz + mesma velocidade = mesmo arquivo, sem pagar de novo.
⭐ AJUSTE DE DURACAO: se a narracao sair longe do tempo-alvo da copy, re-sintetiza UMA vez com a
   velocidade corrigida, dentro de [velocidade_min, velocidade_max] — voz acelerada demais soa
   robo; e' melhor um criativo 3 s mais longo do que uma voz de esquilo.
"""
import binascii, hashlib, http.client, json, os, time, urllib.error, urllib.request

from . import config

TTS_CACHE = os.path.join(config.CACHE_DIR, "tts")
ERROS_TEMPORARIOS = (1000, 1001, 1002, 1039)


class ErroTTS(Exception):
    pass


def _host():
    return os.environ.get("MINIMAX_HOST", "https://api.minimax.io").rstrip("/")


def _post(caminho, corpo, timeout=180):
    chave = os.environ.get("MINIMAX_API_KEY")
    if not chave: raise ErroTTS("MINIMAX_API_KEY ausente (coloque no .env da raiz da ferramenta)")
    req = urllib.request.Request(_host() + caminho, data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + chave, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def listar_vozes(filtro="portug"):
    d = _post("/v1/get_voice", {"voice_type": "all"})
    out = []
    for tipo in ("system_voice", "voice_cloning", "voice_generation"):
        for v in d.get(tipo) or []:
            txt = json.dumps(v, ensure_ascii=False).lower()
            if not filtro or filtro.lower() in txt:
                out.append({"tipo": tipo, "voice_id": v.get("voice_id"), "nome": v.get("voice_name") or "",
                            "desc": " ".join(v.get("description") or [])})
    return out


def _minimax(texto, saida_mp3, cfg, velocidade):
    corpo = {"model": cfg["modelo"], "text": texto, "stream": False,
             "language_boost": cfg.get("idioma") or "Portuguese",
             "voice_setting": {"voice_id": cfg["voz"], "speed": round(float(velocidade), 3), "vol": 1.0, "pitch": 0},
             "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3", "channel": 1}}
    if cfg.get("emocao"): corpo["voice_setting"]["emotion"] = cfg["emocao"]
    if cfg.get("pronuncia"): corpo["pronunciation_dict"] = {"tone": list(cfg["pronuncia"])}
    ultimo = None
    for tent in range(5):
        try:
            r = _post("/v1/t2a_v2", corpo)
        except urllib.error.HTTPError as e:
            ultimo = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 504): time.sleep(4 * (tent + 1)); continue
            break
        # ⛔ 2026-10-03 (criativo 2.3): a MiniMax fechou a conexao sem resposta (RemoteDisconnected, que e'
        #    ConnectionError e NAO URLError) e o criativo morreu na 1a tentativa. Queda de rede = tenta de novo.
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as e:
            ultimo = f"{type(e).__name__}: {e}"; time.sleep(3 * (tent + 1)); continue
        st = (r.get("base_resp") or {}).get("status_code")
        if st == 0 and (r.get("data") or {}).get("audio"):
            with open(saida_mp3, "wb") as f: f.write(binascii.unhexlify(r["data"]["audio"]))
            return r.get("extra_info") or {}
        ultimo = r.get("base_resp")
        if st in ERROS_TEMPORARIOS: time.sleep(4 * (tent + 1)); continue
        break
    raise ErroTTS(f"MiniMax falhou: {ultimo}")


def _kokoro(texto, saida_wav, cfg, velocidade):
    """Reserva LOCAL e gratis (Apache 2.0): `pip install kokoro soundfile`. Vozes pt-BR: pf_dora, pm_alex, pm_santa."""
    try:
        from kokoro import KPipeline
        import numpy as np, soundfile as sf
    except Exception as e:                                      # noqa: BLE001
        raise ErroTTS("Kokoro nao instalado (pip install kokoro soundfile): " + str(e))
    pipe = KPipeline(lang_code="p")
    voz = cfg.get("voz_kokoro") or "pf_dora"
    partes = [a for _, _, a in pipe(texto, voice=voz, speed=float(velocidade))]
    sf.write(saida_wav, np.concatenate(partes), 24000)
    return {}


def _limpar(entrada, saida_wav):
    """48 kHz mono, sem silencio no comeco/fim (o corte do video depende da ultima palavra)."""
    filtro = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
              "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.12,areverse")
    r = config.ffmpeg(["-i", entrada, "-af", filtro, "-ar", "48000", "-ac", "1", saida_wav])
    if r.returncode != 0 or not os.path.exists(saida_wav):
        raise ErroTTS("ffmpeg nao converteu a narracao: " + (r.stderr or "")[-300:])


def sintetizar(texto, saida_wav, cfg, velocidade=None):
    """Gera (ou reaproveita do cache) a narracao limpa em `saida_wav`. Devolve a duracao em s."""
    velocidade = float(velocidade or cfg.get("velocidade") or 1.0)
    prov = cfg.get("provedor") or "minimax"
    if prov == "minimax" and not cfg.get("voz"):
        raise ErroTTS("nenhuma voz definida (config tts.voz ou EDT_VOZ). Liste com: python edt.py vozes")
    chave = hashlib.sha1(json.dumps([prov, cfg.get("modelo"), cfg.get("voz"), cfg.get("voz_kokoro"), cfg.get("emocao"),
                                     cfg.get("pronuncia"), round(velocidade, 3), texto], ensure_ascii=False).encode()).hexdigest()[:16]
    os.makedirs(TTS_CACHE, exist_ok=True)
    cache_wav = os.path.join(TTS_CACHE, chave + ".wav")
    if not os.path.exists(cache_wav):
        bruto = os.path.join(TTS_CACHE, chave + (".mp3" if prov == "minimax" else ".raw.wav"))
        (_minimax if prov == "minimax" else _kokoro)(texto, bruto, cfg, velocidade)
        _limpar(bruto, cache_wav)
    os.makedirs(os.path.dirname(os.path.abspath(saida_wav)), exist_ok=True)
    import shutil
    shutil.copyfile(cache_wav, saida_wav)
    return config.duracao(saida_wav)


# ⛔ MEDIDO em 2026-10-03 (25 criativos): o `speed` da MiniMax NAO e' linear. Duracao ~ 1/speed^k
# com k ~ 2,4 (24,2 s a 1,0 viraram 16,0 s a 1,2 — e nao 20 s). Corrigir com a regra linear
# passava do ponto nos dois sentidos. Agora: chute com k=2,4 e, se ainda fora, secante com o k medido.
EXPOENTE_SPEED = 2.4


def narrar(texto, alvo_s, saida_wav, cfg):
    """Narracao ajustada ao alvo (ate' 3 sinteses). Devolve {'duracao', 'velocidade', 'tentativas'}."""
    import math
    vmin, vmax = float(cfg["velocidade_min"]), float(cfg["velocidade_max"])
    tol = float(cfg.get("tolerancia_s", 1.5))
    v = float(cfg.get("velocidade") or 1.0)
    pontos = [(v, sintetizar(texto, saida_wav, cfg, v))]
    if not cfg.get("ajustar_duracao") or not alvo_s:
        return {"duracao": round(pontos[0][1], 2), "velocidade": v, "tentativas": 1}
    k = EXPOENTE_SPEED
    while abs(pontos[-1][1] - alvo_s) > tol and len(pontos) < 3:
        if len(pontos) >= 2:
            (va, da), (vb, db) = pontos[-2], pontos[-1]
            if abs(math.log(vb / va)) > 1e-3 and da > 0 and db > 0:
                k = min(max(math.log(da / db) / math.log(vb / va), 0.8), 4.0)
        vb, db = pontos[-1]
        nv = min(max(vb * (db / float(alvo_s)) ** (1.0 / k), vmin), vmax)
        if abs(nv - vb) < 0.01: break
        pontos.append((nv, sintetizar(texto, saida_wav, cfg, nv)))
    # fica com a tentativa mais perto do alvo (e garante que o wav em disco e' ela)
    vbest, dbest = min(pontos, key=lambda p: abs(p[1] - alvo_s))
    if (vbest, dbest) != pontos[-1]: sintetizar(texto, saida_wav, cfg, vbest)
    return {"duracao": round(dbest, 2), "velocidade": round(vbest, 3), "tentativas": len(pontos)}
