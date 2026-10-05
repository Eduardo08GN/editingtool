# -*- coding: utf-8 -*-
"""CAMERA LENTA por IA — quando o plano pede mais tempo do que o trecho do clipe tem, em vez de
congelar a imagem (o defeito do 4.1) ou pular para um clipe fora da ordem da historia, o trecho
e' desacelerado com quadros NOVOS inventados pelo RIFE (rife-ncnn-vulkan, MIT).

O RIFE roda via Vulkan: funciona na Radeon da maquina (sem CUDA). Na primeira vez o pacote oficial
(github.com/nihui/rife-ncnn-vulkan, release 20221029) e' baixado para .cache/ferramentas.
Sem RIFE (ou se ele falhar), cai num "lento simples" do ffmpeg (quadros repetidos): pior, mas nunca congela.
O resultado vai para .cache/camera_lenta (cache por conteudo): o mesmo plano nao e' recalculado.
"""
import glob, hashlib, os, shutil, tempfile, zipfile

from . import config

FERRAMENTAS = os.path.join(config.CACHE_DIR, "ferramentas")
PACOTE = "rife-ncnn-vulkan-20221029-windows"
URL = f"https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/{PACOTE}.zip"
EXE = os.path.join(FERRAMENTAS, PACOTE, "rife-ncnn-vulkan.exe")
CACHE = os.path.join(config.CACHE_DIR, "camera_lenta")
FPS = 30


def disponivel():
    return os.path.exists(EXE)


def preparar(log=print):
    """Baixa o RIFE na primeira vez (~430 MB, com todos os modelos)."""
    if disponivel(): return EXE
    import urllib.request
    os.makedirs(FERRAMENTAS, exist_ok=True)
    zipf = os.path.join(FERRAMENTAS, "rife.zip")
    log("camera lenta: baixando o RIFE (so' na primeira vez, ~430 MB)")
    urllib.request.urlretrieve(URL, zipf + ".parcial"); os.replace(zipf + ".parcial", zipf)
    with zipfile.ZipFile(zipf) as z: z.extractall(FERRAMENTAS)
    os.remove(zipf)
    return EXE


def _lento_simples(arq, ini, dur, fator, W, H, dest):
    return config.ffmpeg(["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", arq, "-an", "-vf",
                          f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
                          f"setpts={fator:.4f}*PTS,fps={FPS}",
                          "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p", dest])


def gerar(arq, ini, dur, fator, cfg_v, log=print):
    """MP4 1080x1920@30 com o trecho [ini, ini+dur] do clipe tocando `fator` vezes mais devagar.
    Devolve (caminho, metodo) com metodo "rife" ou "simples"."""
    W, H = int(cfg_v["largura"]), int(cfg_v["altura"])
    modelo = (cfg_v.get("camera_lenta") or {}).get("modelo", "rife-v4.6")
    st = os.stat(arq)
    chave = hashlib.sha1(f"{os.path.abspath(arq)}|{st.st_size}|{int(st.st_mtime)}|{ini:.3f}|{dur:.3f}|{fator:.4f}|{W}x{H}|{modelo}"
                         .encode()).hexdigest()[:16]
    os.makedirs(CACHE, exist_ok=True)
    for metodo in ("rife", "simples"):
        p = os.path.join(CACHE, f"{chave}_{metodo}.mp4")
        if os.path.exists(p): return p, metodo
    dest = os.path.join(CACHE, f"{chave}_rife.mp4")
    tmp = tempfile.mkdtemp(prefix="edt_lenta_")
    try:
        preparar(log)
        ent, sai = os.path.join(tmp, "ent"), os.path.join(tmp, "sai")
        os.makedirs(ent); os.makedirs(sai)
        r = config.ffmpeg(["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", arq, "-an", "-vf",
                           f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1",
                           os.path.join(ent, "%08d.png")])
        n_ent = len(glob.glob(os.path.join(ent, "*.png")))
        if r.returncode != 0 or n_ent < 2: raise RuntimeError("nao consegui extrair os quadros")
        n_sai = int(round(n_ent * fator))
        exe_dir = os.path.dirname(EXE)
        cmd = [EXE, "-i", ent, "-o", sai, "-n", str(n_sai), "-m", os.path.join(exe_dir, modelo), "-f", "%08d.png"]
        r = config.run(cmd, capture_output=True, cwd=exe_dir)
        if len(glob.glob(os.path.join(sai, "*.png"))) < n_sai * 0.95:          # GPU recusou: tenta na CPU
            shutil.rmtree(sai); os.makedirs(sai)
            r = config.run(cmd + ["-g", "-1"], capture_output=True, cwd=exe_dir)
        if len(glob.glob(os.path.join(sai, "*.png"))) < n_sai * 0.95:
            raise RuntimeError("RIFE nao gerou os quadros: " + str(getattr(r, "stderr", b""))[-200:])
        r = config.ffmpeg(["-framerate", str(FPS), "-i", os.path.join(sai, "%08d.png"), "-c:v", "libx264", "-crf", "14",
                           "-preset", "veryfast", "-pix_fmt", "yuv420p", "-color_range", "tv", dest + ".tmp.mp4"])
        if r.returncode != 0: raise RuntimeError("nao consegui montar o video lento")
        os.replace(dest + ".tmp.mp4", dest)
        return dest, "rife"
    except Exception as e:                                       # noqa: BLE001 — nunca derruba o criativo
        log(f"   camera lenta: RIFE indisponivel ({str(e)[:160]}); usando lento simples")
        dest = os.path.join(CACHE, f"{chave}_simples.mp4")
        _lento_simples(arq, ini, dur, fator, W, H, dest)
        return dest, "simples"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
