# -*- coding: utf-8 -*-
"""MOTOR REMOTION — o MESMO plano.json, desenhado pelo Remotion (legenda e graficos animados).

Escolha por campanha em Ajustes (config "motor": "remotion" | "ffmpeg"). O Python continua sendo o
cerebro (narracao, alinhamento, cortes, SFX, musica, QA); este modulo so':
  1. traduz o plano.json em props do Remotion (tudo em QUADROS, inteiros, a 30 fps);
  2. monta uma pasta public PROPRIA do render (trechos dos planos, narracao, SFX, musica, fonte);
  3. chama `npx remotion render` e normaliza o audio a -14 LUFS (o mix do Remotion nao tem loudnorm).

⛔ Licoes da prova de conceito (2026-10-03):
  - a porta 3000 (padrao) estava ocupada por outro app da maquina: o render abriu a pagina ERRADA.
    Cada render pega uma porta livre propria (com trava: renders em paralelo nao disputam a mesma).
  - o Remotion copia a pasta public inteira a cada render: com clipes inteiros eram 676 MB por video.
    Agora vai so' o TRECHO de cada plano (cache em .cache/remotion_trechos) e a pasta e' do render
    (renders em paralelo nao apagam os arquivos uns dos outros).
"""
import hashlib, os, re, shutil, subprocess, threading, time

from . import campanha as _camp, config

DIR = os.path.join(config.RAIZ, "remotion")
FONTES = os.path.join(DIR, "public", "fonts")
CACHE_TRECHOS = os.path.join(config.CACHE_DIR, "remotion_trechos")
FPS = 30
_TRAVA_PORTA = threading.Lock()
_PORTAS_EM_USO = set()


def disponivel():
    return os.path.isdir(os.path.join(DIR, "node_modules", "@remotion", "cli"))


def preparar():
    """Instala as dependencias do Remotion na primeira vez (npm install em remotion/)."""
    if disponivel(): return
    npm = "npm.cmd" if os.name == "nt" else "npm"
    r = config.run([npm, "install", "--no-audit", "--no-fund"], cwd=DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not disponivel():
        raise RuntimeError("nao consegui instalar o Remotion (precisa do Node.js): " + (r.stderr or r.stdout or "")[-600:])


def _ligar(origem, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest): return
    try: os.link(origem, dest)                    # hard link: nada de copiar o arquivo
    except OSError: shutil.copyfile(origem, dest)


def _asset(caminho, pub):
    ext = os.path.splitext(caminho)[1].lower()
    nome = hashlib.sha1(os.path.abspath(caminho).encode()).hexdigest()[:14] + ext
    _ligar(caminho, os.path.join(pub, "assets", nome))
    return f"assets/{nome}"


def _trecho(arq, ini, dur, cfg, pub):
    """So' o pedaco do clipe que o plano usa, ja' em 1080x1920 a 30 fps (cache por conteudo)."""
    W, H = int(cfg["video"]["largura"]), int(cfg["video"]["altura"])
    st = os.stat(arq)
    chave = hashlib.sha1(f"{os.path.abspath(arq)}|{st.st_size}|{int(st.st_mtime)}|{ini:.3f}|{dur:.3f}|{W}x{H}".encode()).hexdigest()[:16]
    cache = os.path.join(CACHE_TRECHOS, f"{chave}.mp4")
    if not os.path.exists(cache):
        os.makedirs(CACHE_TRECHOS, exist_ok=True)
        tmp = cache + f".{os.getpid()}.{threading.get_ident()}.mp4"
        r = config.ffmpeg(["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", arq, "-an", "-vf",
                           f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
                           "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp])
        if r.returncode != 0: raise RuntimeError("nao consegui cortar o trecho: " + (r.stderr or "")[-300:])
        os.replace(tmp, cache)
    _ligar(cache, os.path.join(pub, "assets", f"trecho_{chave}.mp4"))
    return f"assets/trecho_{chave}.mp4"


def _db(v):
    return round(10 ** (float(v) / 20.0), 4)


def motion_graphics(props, plano, produto, gancho=True, fecho=True):
    """Gancho animado (contador 0..N + rotulo que vira o titulo) e cartao de fecho (CTA).
    O numero e o rotulo saem do nome do produto: "Biblia do Bebe: 70 Cards Ludicos" -> 70 / CARDS LUDICOS."""
    nome, _, resto = (produto or "").partition(":")
    m = re.match(r"\s*(\d+)\s+(.+)", resto or "")
    if gancho and m:
        props["gancho"] = {"numero": m.group(1), "rotulo": m.group(2).strip().upper(), "frames": 54,
                           "tituloY": props["layout"]["tituloY"]}
        if props.get("titulo"): props["titulo"]["from"] = max(props["titulo"]["from"], 54 - 6)   # o titulo nasce da pilula
    if not fecho: return props
    fim = props["cta"]["from"]
    linhas = [l for l in (props["titulo"]["linhas"] if props.get("titulo") else [nome.strip(), resto.strip()]) if l]
    props["fecho"] = {"from": fim, "linhas": [l.upper().rstrip(":") for l in linhas] or ["SAIBA MAIS"], "cta": props["cta"]["texto"]}
    props["cards"] = [dict(c, to=min(c["to"], fim)) for c in props["cards"] if c["from"] < fim]
    if props.get("titulo"): props["titulo"]["to"] = min(props["titulo"]["to"], fim)
    return props


def montar_props(plano, wav, cfg, pub):
    f = lambda t: int(round(float(t) * FPS))
    total = f(plano["total"])
    planos = plano["planos"]
    trans = plano.get("transicoes") or []
    cortes = [0]; acc = 0.0
    for p in planos[:-1]: acc += p["dur"]; cortes.append(f(acc))
    cortes.append(total)
    # meia-transicao em cada corte (seco = 0: corte direto); quadros pares para dividir ao meio
    durs = [0] + [0 if t.get("tipo") == "seco" else max(2, int(round(t["dur"] * FPS / 2)) * 2) for t in trans] + [0]
    shots = []
    for k, p in enumerate(planos):
        h0, h1 = durs[k] // 2, durs[k + 1] // 2
        frames = (cortes[k + 1] - cortes[k]) + h0 + h1
        ini = max(0.0, float(p["src"]) - h0 / FPS)
        shots.append({"src": _trecho(p.get("arquivo") or plano["base"], ini, frames / FPS + 0.3, cfg, pub), "trim": 0,
                      "frames": frames, "zoom": float(p.get("zoom", 1.0))})
    transicoes = [{"tipo": t.get("tipo", "seco"), "xfade": t.get("xfade", ""), "frames": durs[k + 1]} for k, t in enumerate(trans)]
    L = plano.get("layout") or {}
    t_cta = f(plano["cta"]["t"])
    esconde = L.get("esconder_legenda_no_cta", True)
    cards, cs = [], plano["cartoes"]
    for i, c in enumerate(cs):
        ini = [f(a) for a, _b in c["tempos"]]
        fim_ult = f(c["tempos"][-1][1])
        prox = f(cs[i + 1]["t0"]) if i + 1 < len(cs) else None
        fim = min(prox, fim_ult + f(0.6)) if prox is not None else fim_ult + f(0.5)
        if esconde: fim = min(fim, t_cta)
        if fim > ini[0]:
            cards.append({"words": [w.strip(",.!?;:") for w in c["palavras"]], "starts": ini, "from": ini[0], "to": fim})
    a = cfg["audio"]
    sfx = [{"src": _asset(s["arquivo"], pub), "from": f(s["t"]), "frames": max(1, f(s["max_s"])), "trim": f(s.get("inicio_arquivo", 0)),
            "volume": min(1.0, _db(s["db"]))}
           for s in plano.get("sfx") or []]
    musica = None
    if plano.get("musica") and a.get("musica"):
        musica = {"src": _asset(plano["musica"]["arquivo"], pub), "volume": _db(a.get("musica_db", -23)) * 1.8}
    return {
        "fps": FPS, "width": int(cfg["video"]["largura"]), "height": int(cfg["video"]["altura"]), "totalFrames": total,
        "pushIn": float(cfg["video"].get("push_in", 0.045)), "shots": shots, "transicoes": transicoes, "cards": cards,
        "motionBlur": ({"amostras": int(cfg["video"]["motion_blur"].get("amostras", 6)),
                        "obturador": float(cfg["video"]["motion_blur"].get("obturador", 220))}
                       if (cfg["video"].get("motion_blur") or {}).get("ativo") else None),
        "layout": {"legendaY": float(L.get("legenda_y", cfg["legenda"]["centro_y"])), "ctaY": float(L.get("cta_y", cfg["cta"]["centro_y"])),
                   "tituloY": float(L.get("titulo_y", 0.15)), "seloY": float(L.get("selo_y", cfg["preco"]["centro_y"]))},
        "cta": {"from": t_cta, "texto": plano["cta"]["texto"]},
        "preco": {"from": f(plano["preco"]["t"]), "texto": plano["preco"]["texto"]} if plano.get("preco") else None,
        "titulo": {"linhas": plano["titulo"]["linhas"], "from": f(plano["titulo"]["t0"]), "to": f(plano["titulo"]["t1"])} if plano.get("titulo") else None,
        "narracao": _asset(wav, pub), "musica": musica, "sfx": sfx,
        "fala": [[c["from"], c["to"]] for c in cards],          # a musica abaixa por baixo da voz
    }


def _reservar_porta():
    from .servidor import porta_livre
    with _TRAVA_PORTA:
        p = 3310
        while True:
            p = porta_livre(p)
            if p not in _PORTAS_EM_USO: _PORTAS_EM_USO.add(p); return p
            p += 1


def renderizar_plano(plano, wav, saida, cfg, pasta, log=print, rotulo="", produto=None, gancho=True, fecho=True):
    """Desenha o plano no Remotion e grava `saida` (mp4 com audio a -14 LUFS). Devolve o relatorio."""
    preparar()
    pub = os.path.join(pasta, "_remotion_public")
    shutil.rmtree(pub, ignore_errors=True)
    os.makedirs(os.path.join(pub, "fonts"), exist_ok=True)
    for n in os.listdir(FONTES): _ligar(os.path.join(FONTES, n), os.path.join(pub, "fonts", n))
    props = montar_props(plano, wav, cfg, pub)
    if produto is not None and (gancho or fecho): props = motion_graphics(props, plano, produto, gancho, fecho)
    arq_props = os.path.join(pasta, "remotion_props.json")
    config.escrever_json(arq_props, props)
    bruto = os.path.join(pasta, "_remotion_bruto.mp4")
    log_arq = os.path.join(pasta, "remotion.log")
    npx = "npx.cmd" if os.name == "nt" else "npx"
    # ⭐ CPU dividida entre os renders paralelos do lote (cada Remotion abre varios navegadores)
    conc = max(2, (os.cpu_count() or 4) // max(1, int(cfg.get("_workers", 2))))
    porta = _reservar_porta()
    t0 = time.time()
    try:
        with open(log_arq, "w", encoding="utf-8", errors="replace") as lf:
            r = config.run([npx, "remotion", "render", "src/index.ts", "Criativo", bruto, f"--props={arq_props}",
                            f"--public-dir={pub}", "--codec=h264", "--crf=19", f"--concurrency={conc}", f"--port={porta}"],
                           cwd=DIR, stdout=lf, stderr=lf, stdin=subprocess.DEVNULL)
    finally:
        with _TRAVA_PORTA: _PORTAS_EM_USO.discard(porta)
    if r.returncode != 0 or not os.path.exists(bruto):
        txt = open(log_arq, encoding="utf-8", errors="replace").read()
        txt = chr(10).join(l for l in txt.splitlines() if "Copying public dir" not in l and "Bundling" not in l)
        raise RuntimeError(f"remotion falhou (log em {log_arq}): " + txt[-2000:])
    t_render = time.time() - t0
    rr = config.ffmpeg(["-i", bruto, "-c:v", "copy", "-af", f"loudnorm=I={cfg['audio']['lufs']}:TP=-1.5:LRA=11,aresample=48000",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida])
    if rr.returncode != 0: raise RuntimeError("loudnorm falhou: " + (rr.stderr or "")[-500:])
    os.remove(bruto)
    shutil.rmtree(pub, ignore_errors=True)              # os trechos ficam no cache; a pasta do render sai
    log(f"{rotulo}remotion: {len(props['cards'])} cartoes, render em {t_render:.0f}s")
    return {"saida": saida, "duracao": round(config.duracao(saida), 2), "segundos_render": round(t_render, 1), "motor": "remotion"}


def renderizar(nome, cid, log=print, motion=False):
    """Linha de comando: desenha no Remotion um criativo que ja' tem plano (saida: final_remotion.mp4)."""
    camp = _camp.carregar(nome)
    cri = next((c for c in camp["criativos"] if c["id"] == cid), None)
    if not cri: raise SystemExit(f"criativo {cid} nao existe")
    pasta = os.path.join(camp["_pasta"], "saida", f"{cri['id']}-{config.slug(cri['angulo'], 30)}")
    plano = config.ler_json(os.path.join(pasta, "plano.json"))
    if not plano: raise SystemExit(f"{cid} ainda nao tem plano.json: produza o criativo antes")
    cfg = config.padrao(camp.get("ajustes"))
    saida = os.path.join(pasta, "final_motion.mp4" if motion else "final_remotion.mp4")
    return renderizar_plano(plano, os.path.join(pasta, "narracao.wav"), saida, cfg, pasta, log, rotulo=f"[{cid}] ",
                            produto=(camp.get("produto") or "") if motion else None)
