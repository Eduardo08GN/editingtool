# -*- coding: utf-8 -*-
"""MOTOR REMOTION (prova de conceito, 2026-10-03) — o MESMO plano.json, desenhado pelo Remotion.

    python edt.py remotion <campanha> --id 1.5

O Python continua sendo o cerebro (narracao, alinhamento, cortes, SFX, musica, QA). Este modulo so':
  1. traduz o plano.json em props do Remotion (tudo em QUADROS, inteiros, a 30 fps);
  2. poe os arquivos (clipes, narracao, SFX, musica) em remotion/public/assets por HARD LINK
     (nada de copiar 700 MB; o Remotion so' le' arquivos de public/);
  3. chama `npx remotion render`, normaliza o audio a -14 LUFS (o mix do Remotion nao tem loudnorm)
     e grava saida/<criativo>/final_remotion.mp4 — a entrega oficial (ffmpeg) NAO e' tocada.
"""
import hashlib, json, os, shutil, time

from . import campanha as _camp, config

DIR = os.path.join(config.RAIZ, "remotion")
PUBLIC = os.path.join(DIR, "public")
FPS = 30


def _asset(caminho):
    """Hard link (ou copia) do arquivo em public/assets; devolve o caminho relativo para staticFile()."""
    ext = os.path.splitext(caminho)[1].lower()
    nome = hashlib.sha1(os.path.abspath(caminho).encode()).hexdigest()[:14] + ext
    dest = os.path.join(PUBLIC, "assets", nome)
    if not os.path.exists(dest) or os.path.getsize(dest) != os.path.getsize(caminho):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest): os.remove(dest)
        try: os.link(caminho, dest)
        except OSError: shutil.copyfile(caminho, dest)
    return f"assets/{nome}"


def _trecho(arq, ini, dur, cfg):
    """⭐ So' o pedaco do clipe que o plano usa, ja' em 1080x1920 a 30 fps (cache por conteudo).
    Antes o Remotion copiava 676 MB de clipes inteiros para o bundle a CADA render."""
    W, H = int(cfg["video"]["largura"]), int(cfg["video"]["altura"])
    st = os.stat(arq)
    chave = hashlib.sha1(f"{os.path.abspath(arq)}|{st.st_size}|{int(st.st_mtime)}|{ini:.3f}|{dur:.3f}|{W}x{H}".encode()).hexdigest()[:16]
    dest = os.path.join(PUBLIC, "assets", f"trecho_{chave}.mp4")
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        r = config.ffmpeg(["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", arq, "-an", "-vf",
                           f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
                           "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", dest])
        if r.returncode != 0: raise RuntimeError("nao consegui cortar o trecho: " + (r.stderr or "")[-300:])
    return f"assets/{os.path.basename(dest)}"


def _limpar_assets(manter):
    """Tira de public/assets o que este render nao usa (o Remotion copia a pasta inteira)."""
    pasta = os.path.join(PUBLIC, "assets")
    for n in os.listdir(pasta) if os.path.isdir(pasta) else []:
        if f"assets/{n}" not in manter:
            try: os.remove(os.path.join(pasta, n))
            except OSError: pass


def _db(v):
    return round(10 ** (float(v) / 20.0), 4)


def montar_props(plano, wav, cfg):
    f = lambda t: int(round(float(t) * FPS))
    total = f(plano["total"])
    planos = plano["planos"]; n = len(planos)
    trans = plano.get("transicoes") or []
    # cortes em quadros e meia-transicao de cada corte (seco = 0: corte direto)
    cortes = [0]; acc = 0.0
    for p in planos[:-1]: acc += p["dur"]; cortes.append(f(acc))
    cortes.append(total)
    durs = [0] + [0 if t.get("tipo") == "seco" else max(2, int(round(t["dur"] * FPS / 2)) * 2) for t in trans] + [0]
    shots = []
    for k, p in enumerate(planos):
        h0, h1 = durs[k] // 2, durs[k + 1] // 2
        frames = (cortes[k + 1] - cortes[k]) + h0 + h1
        ini = max(0.0, float(p["src"]) - h0 / FPS)
        shots.append({"src": _trecho(p.get("arquivo") or plano["base"], ini, frames / FPS + 0.3, cfg), "trim": 0,
                      "frames": frames, "zoom": float(p.get("zoom", 1.0))})
    transicoes = [{"tipo": t.get("tipo", "seco"), "xfade": t.get("xfade", ""), "frames": durs[k + 1]} for k, t in enumerate(trans)]
    L = plano.get("layout") or {}
    t_cta = f(plano["cta"]["t"])
    esconde = L.get("esconder_legenda_no_cta", True)
    cards = []
    cs = plano["cartoes"]
    for i, c in enumerate(cs):
        ini = [f(a) for a, _b in c["tempos"]]
        fim_ult = f(c["tempos"][-1][1])
        prox = f(cs[i + 1]["t0"]) if i + 1 < len(cs) else None
        fim = min(prox, fim_ult + f(0.6)) if prox is not None else fim_ult + f(0.5)
        if esconde: fim = min(fim, t_cta)
        if fim > ini[0]:
            cards.append({"words": [w.strip(",.!?;:") for w in c["palavras"]], "starts": ini, "from": ini[0], "to": fim})
    a = cfg["audio"]
    sfx = [{"src": _asset(s["arquivo"]), "from": f(s["t"]), "frames": max(1, f(s["max_s"])), "volume": min(1.0, _db(s["db"]))}
           for s in plano.get("sfx") or []]
    musica = None
    if plano.get("musica") and a.get("musica"):
        musica = {"src": _asset(plano["musica"]["arquivo"]), "volume": _db(a.get("musica_db", -23)) * 1.8}
    fala = [[c["from"], c["to"]] for c in cards]          # janelas de fala: a musica abaixa por baixo delas
    return {
        "fps": FPS, "width": int(cfg["video"]["largura"]), "height": int(cfg["video"]["altura"]), "totalFrames": total,
        "pushIn": float(cfg["video"].get("push_in", 0.045)), "shots": shots, "transicoes": transicoes, "cards": cards,
        "layout": {"legendaY": float(L.get("legenda_y", cfg["legenda"]["centro_y"])), "ctaY": float(L.get("cta_y", cfg["cta"]["centro_y"])),
                   "tituloY": float(L.get("titulo_y", 0.15)), "seloY": float(L.get("selo_y", cfg["preco"]["centro_y"]))},
        "cta": {"from": t_cta, "texto": plano["cta"]["texto"]},
        "preco": {"from": f(plano["preco"]["t"]), "texto": plano["preco"]["texto"]} if plano.get("preco") else None,
        "titulo": {"linhas": plano["titulo"]["linhas"], "from": f(plano["titulo"]["t0"]), "to": f(plano["titulo"]["t1"])} if plano.get("titulo") else None,
        "narracao": _asset(wav), "musica": musica, "sfx": sfx, "fala": fala,
    }


def renderizar(nome, cid, log=print):
    camp = _camp.carregar(nome)
    cri = next((c for c in camp["criativos"] if c["id"] == cid), None)
    if not cri: raise SystemExit(f"criativo {cid} nao existe")
    pasta = os.path.join(camp["_pasta"], "saida", f"{cri['id']}-{config.slug(cri['angulo'], 30)}")
    plano = config.ler_json(os.path.join(pasta, "plano.json"))
    if not plano: raise SystemExit(f"{cid} ainda nao tem plano.json: produza com o motor ffmpeg antes")
    cfg = config.padrao(camp.get("ajustes"))
    props = montar_props(plano, os.path.join(pasta, "narracao.wav"), cfg)
    usados = {s["src"] for s in props["shots"]} | {s["src"] for s in props["sfx"]} | {props["narracao"]}
    if props.get("musica"): usados.add(props["musica"]["src"])
    _limpar_assets(usados)
    arq_props = os.path.join(pasta, "remotion_props.json")
    config.escrever_json(arq_props, props)
    bruto = os.path.join(pasta, "_remotion_bruto.mp4")
    saida = os.path.join(pasta, "final_remotion.mp4")
    log(f"[{cid}] remotion: {len(props['shots'])} planos, {len(props['cards'])} cartoes, {props['totalFrames']} quadros")
    t0 = time.time()
    npx = "npx.cmd" if os.name == "nt" else "npx"
    # ⛔ 2026-10-03: a porta 3000 (padrao do Remotion) estava ocupada por outro app da maquina (site Next.js)
    #    e o render abriu a pagina ERRADA. Sempre uma porta livre propria.
    from .servidor import porta_livre
    porta = porta_livre(3310)
    log_arq = os.path.join(pasta, "remotion.log")
    with open(log_arq, "w", encoding="utf-8", errors="replace") as lf:
        r = config.run([npx, "remotion", "render", "src/index.ts", "Criativo", bruto, f"--props={arq_props}",
                        "--codec=h264", "--crf=19", "--concurrency=50%", f"--port={porta}"],
                       cwd=DIR, stdout=lf, stderr=lf, stdin=__import__("subprocess").DEVNULL)
    if r.returncode != 0 or not os.path.exists(bruto):
        txt = open(log_arq, encoding="utf-8", errors="replace").read()
        txt = chr(10).join(l for l in txt.splitlines() if "Copying public dir" not in l)
        raise RuntimeError("remotion falhou (log em " + log_arq + "): " + txt[-2500:])
    t_render = time.time() - t0
    rr = config.ffmpeg(["-i", bruto, "-c:v", "copy", "-af", f"loudnorm=I={cfg['audio']['lufs']}:TP=-1.5:LRA=11,aresample=48000",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida])
    if rr.returncode != 0: raise RuntimeError("loudnorm falhou: " + (rr.stderr or "")[-500:])
    os.remove(bruto)
    log(f"[{cid}] remotion OK em {t_render:.0f}s -> {saida}")
    return {"saida": saida, "segundos_render": round(t_render, 1), "duracao": round(config.duracao(saida), 2)}
