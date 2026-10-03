# -*- coding: utf-8 -*-
"""RENDER — o plano vira MP4 numa passada so' de ffmpeg (padrao herdado do ow_agente).

Video: cada plano entra como `-ss src -t dur -i base` (busca rapida, sem `split` gigante em
memoria) -> fps/escala/zoom/crop 9:16 -> concat -> [faixa borrada opcional] -> legendas
(`movie=` PNG + overlay enable=between) -> selo de preco -> pilula CTA + setas pulando.
Audio: narracao (+ respiro final) + musica (abaixa sob a voz via sidechain) + SFX (adelay) ->
amix -> loudnorm -14 LUFS (padrao de Reels/feed).
⛔ O audio original do base NUNCA entra: o base pode ter fala/legenda de outro criativo.
"""
import os, tempfile

from . import config, legendas


def _mov(caminho):
    """Caminho para o filtro movie=: barras normais, ':' escapado, entre aspas simples."""
    return "movie='" + os.path.abspath(caminho).replace("\\", "/").replace(":", "\\:") + "'"


def renderizar(plano, narracao_wav, saida, cfg, pasta_tmp=None):
    V, A, L = cfg["video"], cfg["audio"], cfg["legenda"]
    W, H, FPS = int(V["largura"]), int(V["altura"]), int(V["fps"])
    est = legendas.estilo(L["estilo"])
    tmp = pasta_tmp or tempfile.mkdtemp(prefix="edt_")
    os.makedirs(tmp, exist_ok=True)
    total = float(plano["total"])

    entradas, fil = [], []
    # ── video: planos ──
    for k, p in enumerate(plano["planos"]):
        entradas += ["-ss", f"{p['src']:.3f}", "-t", f"{p['dur'] + 0.2:.3f}", "-i", plano["base"]]
        z = float(p["zoom"]); zw, zh = int(round(W * z / 2) * 2), int(round(H * z / 2) * 2)
        fil.append(f"[{k}:v]fps={FPS},scale={zw}:{zh}:force_original_aspect_ratio=increase,crop={W}:{H},"
                   f"setsar=1,trim=duration={p['dur']:.3f},setpts=PTS-STARTPTS[p{k}]")
    n = len(plano["planos"])
    fil.append("".join(f"[p{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0[vc]")
    cur = "vc"
    faixas = V.get("borrar_faixa") or []
    if faixas and not isinstance(faixas[0], (list, tuple)): faixas = [faixas]
    for i, (a, b) in enumerate(faixas):          # ⭐ so' para base que ja' vem com texto queimado
        y0, hh = int(a * H) // 2 * 2, int((b - a) * H) // 2 * 2
        fil.append(f"[{cur}]split[bz{i}a][bz{i}b];[bz{i}b]crop={W}:{hh}:0:{y0},boxblur=28:3[bz{i}c];"
                   f"[bz{i}a][bz{i}c]overlay=0:{y0}[vb{i}]")
        cur = f"vb{i}"

    ov = 0

    def overlay(png, x, y, t0, t1, yexpr=None):
        nonlocal cur, ov
        ov += 1
        fil.append(f"{_mov(png)}[o{ov}]")
        ypos = yexpr if yexpr else str(int(y))
        fil.append(f"[{cur}][o{ov}]overlay={int(x)}:{ypos}:enable='between(t,{t0:.3f},{t1:.3f})'"
                   + (":eval=frame" if yexpr else "") + f"[v{ov}]")
        cur = f"v{ov}"

    # ── legendas ──
    cy = float(L["centro_y"]) * H
    cards = plano["cartoes"]
    for ci, c in enumerate(cards):
        prox = cards[ci + 1]["t0"] if ci + 1 < len(cards) else None
        for j, (t0, t1) in enumerate(c["tempos"]):
            if j + 1 < len(c["tempos"]): fim = c["tempos"][j + 1][0]
            else: fim = min(prox, t1 + 0.6) if prox is not None else t1 + 0.5
            fim = max(fim, t0 + 0.08)
            png = os.path.join(tmp, f"c{ci:03d}_{j}.png")
            w, h = legendas.png_cartao([p.strip(",.!?;:") for p in c["palavras"]], j, est["alt"] * H, png, W, int(W * 0.86),
                                       None, est)
            x = min(max(int(W / 2 - w / 2), int(W * 0.02)), int(W * 0.98) - w)
            overlay(png, x, cy - h / 2, t0, min(fim, plano["cta"]["t"]))

    # ── selo de preco ──
    if plano.get("preco"):
        png = os.path.join(tmp, "selo.png")
        w, h = legendas.png_selo(plano["preco"]["texto"], W, png)
        t0 = plano["preco"]["t"]
        overlay(png, W / 2 - w / 2, float(cfg["preco"]["centro_y"]) * H - h / 2, t0, min(t0 + 2.6, plano["cta"]["t"]))

    # ── CTA final ──
    tc = plano["cta"]["t"]
    png = os.path.join(tmp, "cta.png")
    w, h = legendas.png_cta(plano["cta"]["texto"], W, png)
    ycta = float(cfg["cta"]["centro_y"]) * H
    overlay(png, W / 2 - w / 2, ycta - h / 2, tc, total + 1)
    if cfg["cta"].get("setas", True):
        ps = os.path.join(tmp, "seta.png")
        sw, sh = legendas.png_seta(W, ps)
        yb = ycta - sh / 2 - int(H * 0.012)
        bounce = f"'{yb:.0f}+{int(H * 0.012)}*abs(sin(2*PI*1.7*(t-{tc:.3f})))'"
        gap = int(W * 0.04)
        overlay(ps, W / 2 - w / 2 - sw - gap, None, tc, total + 1, yexpr=bounce)
        overlay(ps, W / 2 + w / 2 + gap, None, tc, total + 1, yexpr=bounce)
    fil.append(f"[{cur}]format=yuv420p[vout]")

    # ── audio ──
    ia = n
    entradas += ["-i", narracao_wav]
    fil.append(f"[{ia}:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={total:.3f}[nar0]")
    mix = ["[nar]"]
    mus = plano.get("musica")
    if mus and A.get("musica"):
        im = ia + 1
        entradas += ["-stream_loop", "-1", "-i", mus["arquivo"]]
        fil.append("[nar0]asplit=2[nar][narsc]")
        fil.append(f"[{im}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
                   f"volume={float(A['musica_db']):.1f}dB,afade=t=in:d=0.4,afade=t=out:st={max(0, total - 0.9):.3f}:d=0.9[mus0]")
        fil.append(f"[mus0][narsc]sidechaincompress=threshold=0.02:ratio=4:attack=15:release=400:makeup=1[mus]")
        mix.append("[mus]")
        prox_in = im + 1
    else:
        fil[-1] = fil[-1].replace("[nar0]", "[nar]")
        prox_in = ia + 1
    for k, s in enumerate(plano.get("sfx") or []):
        entradas += ["-i", s["arquivo"]]
        ms = int(s["t"] * 1000); m = float(s["max_s"])
        fil.append(f"[{prox_in + k}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{m:.3f},asetpts=PTS-STARTPTS,"
                   f"afade=t=out:st={max(0, m - 0.2):.3f}:d=0.2,volume={s['db']:.1f}dB,adelay={ms}|{ms}[s{k}]")
        mix.append(f"[s{k}]")
    fil.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,"
               f"loudnorm=I={float(A['lufs']):.0f}:TP=-1.5:LRA=11,aresample=48000,atrim=0:{total:.3f}[aout]")

    script = os.path.join(tmp, "filtro.txt")
    with open(script, "w", encoding="utf-8") as f: f.write(";\n".join(fil))
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    args = entradas + ["-/filter_complex", script, "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
                       "-r", str(FPS), "-c:v", "libx264", "-preset", V.get("preset", "medium"), "-crf", str(V.get("crf", 19)),
                       "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", saida]
    r = config.ffmpeg(args)
    if r.returncode != 0 or not os.path.exists(saida) or os.path.getsize(saida) == 0:
        raise RuntimeError("render falhou: " + (r.stderr or "")[-1500:])
    return {"saida": saida, "duracao": round(config.duracao(saida), 2), "overlays": ov, "filtro": script}
