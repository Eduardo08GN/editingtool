# -*- coding: utf-8 -*-
"""CONFIG — caminhos, .env, padroes da campanha e o `run()` unico para ffmpeg/ffprobe.

⭐ Um lugar so' para ler configuracao: `padrao()` junta config/padrao.json + o bloco `ajustes`
da campanha + variaveis de ambiente (EDT_*). Quem desenha/monta recebe o dict pronto.
"""
import io, json, os, subprocess, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES_DIR = os.path.join(RAIZ, "fontes")
CAMPANHAS_DIR = os.path.join(RAIZ, "campanhas")
SFX_DIR = os.path.join(RAIZ, "sfx")
SFX_POOL = os.path.join(SFX_DIR, "pool")
CACHE_DIR = os.path.join(RAIZ, ".cache")
PADRAO_JSON = os.path.join(RAIZ, "config", "padrao.json")


def carregar_env(caminho=None):
    """Le .env (KEY=VALUE) sem dependencia externa. Variavel ja' definida no ambiente vence."""
    caminho = caminho or os.path.join(RAIZ, ".env")
    if not os.path.exists(caminho): return
    for linha in io.open(caminho, encoding="utf-8"):
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha: continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


carregar_env()

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")


def run(cmd, **kw):
    """subprocess.run sem abrir janela no Windows."""
    if os.name == "nt":
        kw.setdefault("creationflags", 0x08000000)          # CREATE_NO_WINDOW
    return subprocess.run(cmd, **kw)


def ffmpeg(args, **kw):
    kw.setdefault("capture_output", True); kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8"); kw.setdefault("errors", "replace")
    return run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y"] + list(args), **kw)


def probe(path):
    r = run([FFPROBE, "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", path], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    out = {"duracao": float(d.get("format", {}).get("duration") or 0)}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and "w" not in out:
            n, _, den = (s.get("r_frame_rate") or "30/1").partition("/")
            out.update(w=int(s["width"]), h=int(s["height"]), fps=float(n) / float(den or 1))
        if s.get("codec_type") == "audio": out["audio"] = True
    return out


def duracao(path):
    return probe(path)["duracao"]


def padrao(ajustes=None):
    """Config efetiva: config/padrao.json < ajustes da campanha < EDT_* do ambiente."""
    cfg = json.load(io.open(PADRAO_JSON, encoding="utf-8"))
    for k, v in (ajustes or {}).items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict): cfg[k].update(v)
        else: cfg[k] = v
    amb = {"EDT_VOZ": ("tts", "voz"), "EDT_TTS": ("tts", "provedor"), "EDT_MODELO": ("tts", "modelo"),
           "EDT_LEGENDA": ("legenda", "estilo")}
    for env, (sec, chave) in amb.items():
        if os.environ.get(env): cfg[sec][chave] = os.environ[env]
    if cfg.get("turbo"): aplicar_turbo(cfg)
    return cfg


def aplicar_turbo(cfg):
    """⭐ MODO TURBO (pedido do operador, 2026-10-04): liga todos os recursos tops, QUANDO pertinentes.
    O que e' "pertinente" e' decidido na hora de cada criativo, nao aqui:
      - gancho animado so' aparece se o nome do produto tiver um numero para contar (motor_remotion);
      - musica automatica so' toca se a biblioteca tiver faixa; corte na batida so' com musica;
      - sem Node/Remotion na maquina, o lote cai no motor atual e AVISA (lote.produzir).
    ⛔ NAO mexe no ESTILO das transicoes (pesos: cartoon na Biblia, editor nas outras) nem na voz/copy:
       turbo e' "mais recurso", nao "outra cara"."""
    cfg["motor"] = "remotion"
    v = cfg["video"]
    v["motion_graphics"] = {"gancho": True, "fecho": True}
    # ⛔ 2026-10-05: o motion blur da camera (CameraMotionBlur, 6 amostras) desenhava cada quadro de transicao
    #    6 vezes e mais que DOBRAVA o render (81 s -> 35 s em 300 quadros sem ele). As transicoes ja' tem
    #    borrao de movimento proprio (chicote, corte na curva, giro): o turbo nao liga mais o blur da camera.
    v["emojis"] = dict(v.get("emojis") or {}, ativo=True)
    v["selos"] = dict(v.get("selos") or {}, ativo=True)
    v["camera_lenta"] = dict(v.get("camera_lenta") or {}, ativo=True)
    v["cortar_na_batida"] = True
    cfg["audio"]["sfx"] = True
    if os.path.isdir(os.path.join(RAIZ, "musica", "biblioteca")) and os.listdir(os.path.join(RAIZ, "musica", "biblioteca")):
        cfg["audio"]["musica"] = "auto"
    t = cfg.setdefault("transicoes", {})
    t["proporcao"] = max(float(t.get("proporcao", 0.6)), 0.7)
    return cfg


def slug(txt, n=40):
    import re, unicodedata
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:n] or "x"


def escrever_json(path, obj):
    """Escrita atomica: estado em disco nunca fica pela metade."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def ler_json(path, padrao_=None):
    try: return json.load(io.open(path, encoding="utf-8"))
    except Exception: return padrao_


if hasattr(sys.stdout, "reconfigure"):
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
