# -*- coding: utf-8 -*-
"""QA DE ENTREGA — confere o MP4 final antes de ele sair (ideia do motion-graphics-skills, MIT).

Uma passada de decodificacao procura o que o operador nao pode receber:
  - trecho CONGELADO (imagem parada >= 0,5 s)            -> falha
  - quadro PRETO (>= 0,15 s)                             -> falha
  - "pipoco": um quadro isolado diferente dos vizinhos   -> falha
  - SILENCIO no audio (>= 1,2 s)                          -> aviso
  - loudness fora de -14 LUFS (+-1,5) / pico > -1 dBTP    -> aviso
  - formato que celular nao toca liso                     -> falha (formato.py ja' corrige antes)
E gera a FOLHA DE CONTATO (12 quadros) que o painel mostra no detalhe do criativo.
⛔ 2026-10-04: 2.4 e 3.3 chegaram ao operador "travando"; esta conferencia existe para que o proximo
   defeito desse tipo seja pego aqui, e nao no WhatsApp dele.
"""
import os, re

from . import config, formato


def pipocos(arq, limiar=14.0):
    """Instantes (s) de quadros isolados que destoam dos vizinhos. Miniatura cinza 54x96: rapido."""
    import numpy as np
    w, h = 54, 96
    raw = config.run([config.FFMPEG, "-v", "error", "-i", arq, "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                     capture_output=True).stdout
    q = np.frombuffer(raw, np.uint8)
    n = len(q) // (w * h)
    if n < 3: return []
    f = q[: n * w * h].reshape(n, h, w).astype(np.float32)
    d_ant = np.abs(f[1:-1] - f[:-2]).mean(axis=(1, 2))
    d_seg = np.abs(f[2:] - f[1:-1]).mean(axis=(1, 2))
    d_viz = np.abs(f[2:] - f[:-2]).mean(axis=(1, 2))
    fps = config.probe(arq).get("fps") or 30
    idx = np.where((d_ant > limiar) & (d_seg > limiar) & (d_viz < 0.35 * np.minimum(d_ant, d_seg)))[0]
    return [round(float(i + 1) / fps, 2) for i in idx]


def conferir(arq, pasta, lufs_alvo=-14.0, log=None):
    """{'falhas': [...], 'avisos': [...], 'folha': caminho, 'lufs': x, 'pico': y}"""
    dur = config.duracao(arq)
    fil = ("[0:v]split=3[a][b][c];"
           "[a]freezedetect=n=-60dB:d=0.5,nullsink;"
           "[b]blackdetect=d=0.15:pix_th=0.06,nullsink;"
           "[c]null[vout];"
           "[0:a]asplit[x][y];[x]silencedetect=n=-50dB:d=1.2,anullsink;[y]ebur128=peak=true[aout]")
    # ⛔ todo grafo precisa de ao menos uma saida: os ramos que so' medem terminam em nullsink, e o ultimo
    #    de video e o de audio vao para o "-f null" (sem isso o ffmpeg recusa e a conferencia passava calada)
    r = config.run([config.FFMPEG, "-hide_banner", "-nostats", "-i", arq, "-filter_complex", fil,
                    "-map", "[vout]", "-map", "[aout]", "-f", "null", "-"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    err = r.stderr or ""
    if r.returncode != 0:
        raise RuntimeError("a conferencia de entrega nao rodou: " + err[-400:])
    falhas, avisos = [], []

    for ini, d in zip(re.findall(r"freeze_start: ([0-9.]+)", err), re.findall(r"freeze_duration: ([0-9.]+)", err)):
        falhas.append(f"imagem congelada em {float(ini):.1f}s por {float(d):.1f}s")
    for ini, d in re.findall(r"black_start:([0-9.]+) black_end:[0-9.]+ black_duration:([0-9.]+)", err):
        falhas.append(f"tela preta em {float(ini):.1f}s por {float(d):.2f}s")

    # pipoco: um quadro diferente do ANTERIOR e do SEGUINTE, enquanto anterior e seguinte se parecem.
    # (corte seco muda e fica; transicao muda aos poucos; pipoco vai e volta em 1 quadro)
    for t in pipocos(arq):
        falhas.append(f"pipoco (1 quadro estranho) em {t:.2f}s")

    for ini, d in zip(re.findall(r"silence_start: ([0-9.]+)", err), re.findall(r"silence_duration: ([0-9.]+)", err)):
        if float(ini) < dur - 1.5:                          # o respiro do fim nao conta
            avisos.append(f"silencio em {float(ini):.1f}s por {float(d):.1f}s")
    m_i = re.findall(r"I:\s+(-?[0-9.]+) LUFS", err)
    m_p = re.findall(r"Peak:\s+(-?[0-9.]+) dBFS", err)
    lufs = float(m_i[-1]) if m_i else None
    pico = float(m_p[-1]) if m_p else None
    if lufs is not None and abs(lufs - lufs_alvo) > 1.5: avisos.append(f"volume {lufs:.1f} LUFS (alvo {lufs_alvo:.0f})")
    if pico is not None and pico > -0.5: avisos.append(f"pico de audio {pico:.1f} dBTP (pode distorcer)")
    if not formato.ok(arq): falhas.append(f"formato {formato.inspecionar(arq)['pix_fmt']} (celular pode travar)")

    folha = os.path.join(pasta, "qa_folha.jpg")
    passo = max(dur / 12.0, 0.1)
    config.ffmpeg(["-i", arq, "-vf", f"fps=1/{passo:.3f},scale=180:-2,tile=6x2:padding=4:color=0x0E1B1A",
                   "-frames:v", "1", "-q:v", "4", folha])
    if log and (falhas or avisos):
        log("   QA de entrega: " + "; ".join(falhas + avisos))
    return {"falhas": falhas, "avisos": avisos, "folha": folha if os.path.exists(folha) else None,
            "lufs": lufs, "pico": pico}


def versao_whatsapp(arq, destino):
    """Copia LEVE para revisar pelo WhatsApp (720p, ~2,5 Mbps, formato de celular). Nunca vai para o repo."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    r = config.ffmpeg(["-i", arq, "-vf", "scale=720:1280:flags=lanczos,format=yuv420p",
                       "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "2500k", "-bufsize", "5000k",
                       "-profile:v", "main", "-level", "3.1", "-pix_fmt", "yuv420p", "-color_range", "tv", "-g", "60",
                       "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", destino])
    if r.returncode != 0 or not os.path.exists(destino):
        raise RuntimeError("versao leve falhou: " + (r.stderr or "")[-300:])
    return destino
