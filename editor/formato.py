# -*- coding: utf-8 -*-
"""FORMATO — todo video entregue sai no formato que celular toca liso (Reels/Stories/WhatsApp).

⛔ 2026-10-04: o operador viu 2.4 e 3.3 "travando no meio" no celular. O arquivo era perfeito no PC
   (sem quadro congelado, sem buraco de tempo); o problema era a COR em faixa cheia (`yuvj420p`, o
   formato de JPEG) que o Remotion gravava. Player de celular engasga com isso. Padrao agora:
   H.264 High, `yuv420p`, faixa de TV, bt709, GOP de 2 s, faststart.
"""
import json, os

from . import config


def inspecionar(arq):
    r = config.run([config.FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
                    "stream=pix_fmt,color_range,profile", "-of", "json", arq], capture_output=True, text=True)
    s = (json.loads(r.stdout or "{}").get("streams") or [{}])[0]
    return {"pix_fmt": s.get("pix_fmt"), "color_range": s.get("color_range"), "profile": s.get("profile")}


def ok(arq):
    i = inspecionar(arq)
    return i["pix_fmt"] == "yuv420p" and i.get("color_range") in (None, "tv", "unknown")


def garantir(arq, log=None):
    """Se o video nao estiver no padrao de celular, regrava NO LUGAR (audio copiado). Devolve True se mexeu."""
    if ok(arq): return False
    tmp = arq + ".fmt.mp4"
    r = config.ffmpeg(["-i", arq, "-vf", "scale=in_range=auto:out_range=tv,format=yuv420p",
                       "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-profile:v", "high", "-level", "4.1",
                       "-pix_fmt", "yuv420p", "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709",
                       "-color_trc", "bt709", "-g", "60", "-c:a", "copy", "-movflags", "+faststart", tmp])
    if r.returncode != 0 or not os.path.exists(tmp):
        raise RuntimeError("nao consegui regravar no formato de celular: " + (r.stderr or "")[-400:])
    os.replace(tmp, arq)
    if log: log(f"   formato: {os.path.basename(arq)} regravado em yuv420p (faixa de TV)")
    return True
