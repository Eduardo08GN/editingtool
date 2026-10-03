# -*- coding: utf-8 -*-
"""LIMPAR — apaga legenda queimada de um video base (para quando so' existe o criativo pronto).

⭐ Apaga SO' as letras da legenda, nao uma faixa inteira (a tarja borrada atrapalhava o video —
   pedido do operador em 2026-10-03). Como:
   1. OCR (rapidocr) numa faixa da tela, a cada `passo` quadros;
   2. fica so' com texto NO ESTILO DE LEGENDA: caixa alta, letra grande (>= 3% da altura) e
      contorno preto grosso — o texto impresso no PRODUTO (cards, rotulos) nao entra;
   3. mascara = uniao das deteccoes vizinhas (a legenda dura varios quadros) -> cv2.inpaint.
⛔ E' remendo: o ideal continua sendo receber o base limpo (sem legenda e sem narracao).
"""
import os, subprocess

from . import config


def _filtra(res, fr, y0, H):
    import cv2, numpy as np
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    caixas = []
    for box, txt, _sc in (res or []):
        b = np.array(box, dtype=np.float32); b[:, 1] += y0
        h = b[:, 1].max() - b[:, 1].min()
        letras = [c for c in txt if c.isalpha()]
        if h < 0.030 * H or not letras or sum(c.isupper() for c in letras) / len(letras) < 0.8: continue
        x0, x1 = int(max(0, b[:, 0].min())), int(b[:, 0].max()); ya, yb = int(b[:, 1].min()), int(b[:, 1].max())
        reg = hsv[ya:yb, x0:x1]
        if reg.size == 0: continue
        escuro = (reg[..., 2] < 50).mean()                                   # contorno preto grosso
        claro = ((reg[..., 2] > 200) & ((reg[..., 1] < 70) | ((reg[..., 0] > 18) & (reg[..., 0] < 38)))).mean()
        if escuro > 0.10 and claro > 0.10: caixas.append(b.astype(np.int32))
    return caixas


def limpar_base(base, saida=None, faixa=(0.55, 0.86), passo=3, fps=30, log=print):
    import cv2, numpy as np
    from rapidocr_onnxruntime import RapidOCR
    saida = saida or os.path.splitext(base)[0] + ".limpo.mp4"
    if os.path.exists(saida) and os.path.getmtime(saida) > os.path.getmtime(base): return saida
    ocr = RapidOCR()
    cap = cv2.VideoCapture(base)
    fps_in = cap.get(cv2.CAP_PROP_FPS) or fps
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    pula = max(1, int(round(fps_in / fps)))
    quadros = []
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok: break
        if i % pula == 0: quadros.append(fr)
        i += 1
    cap.release()
    y0, y1 = int(faixa[0] * H), int(faixa[1] * H)
    det = {}
    for k in range(0, len(quadros), passo):
        res, _ = ocr(quadros[k][y0:y1])
        det[k] = _filtra(res, quadros[k], y0, H)
        if k % (passo * 60) == 0: log(f"   limpando base: {k}/{len(quadros)} quadros")
    proc = subprocess.Popen([config.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "15", "-preset", "medium",
                             "-pix_fmt", "yuv420p", saida], stdin=subprocess.PIPE,
                            creationflags=0x08000000 if os.name == "nt" else 0)
    ker = np.ones((17, 17), np.uint8)
    for k, fr in enumerate(quadros):
        ref = k - k % passo
        caixas = det.get(ref, []) + det.get(ref - passo, []) + det.get(ref + passo, [])
        if caixas:
            m = np.zeros((H, W), np.uint8)
            for c in caixas: cv2.fillPoly(m, [c], 255)
            fr = cv2.inpaint(fr, cv2.dilate(m, ker), 7, cv2.INPAINT_TELEA)
        proc.stdin.write(fr.tobytes())
    proc.stdin.close(); proc.wait()
    if proc.returncode != 0 or not os.path.exists(saida): raise RuntimeError("limpeza do base falhou")
    log(f"   base limpo: {saida}")
    return saida
