# -*- coding: utf-8 -*-
"""MIXAGEM — a musica "recortada" sob a voz (voiceover carve; ideia do HyperFrames, Apache-2.0).

Antes a musica INTEIRA abaixava quando a voz falava: a trilha "murchava" o video quase todo.
Agora a trilha e' dividida em 3 bandas (grave / meio / agudo) e so' o MEIO — onde a voz mora,
~300 Hz a ~3,8 kHz — e' comprimido pela propria narracao (sidechain). O grave e o brilho continuam:
a musica segue sendo musica, e a voz fica mais clara do que com o abaixamento geral.
O resultado e' um WAV do tamanho do video (cache por conteudo), usado pelos dois motores.
"""
import hashlib, os

from . import config

CACHE = os.path.join(config.CACHE_DIR, "musica_esculpida")


def esculpir(musica, narracao, total, cfg_a, log=print):
    """WAV estereo 48 kHz com `total` s da musica (em loop), volume da trilha ja' aplicado e o meio
    recortado sob a voz. None se falhar (o motor volta para o abaixamento antigo)."""
    c = (cfg_a.get("recorte_voz") or {})
    if c.get("ativo") is False: return None
    corte_baixo, corte_alto = float(c.get("de_hz", 300)), float(c.get("ate_hz", 3800))
    forca = float(c.get("forca", 10))                                  # razao do compressor no meio
    st_m, st_n = os.stat(musica), os.stat(narracao)
    chave = hashlib.sha1(f"{musica}|{st_m.st_size}|{int(st_m.st_mtime)}|{narracao}|{st_n.st_size}|{int(st_n.st_mtime)}|"
                         f"{total:.3f}|{cfg_a.get('musica_db', -23)}|{corte_baixo}|{corte_alto}|{forca}".encode()).hexdigest()[:16]
    os.makedirs(CACHE, exist_ok=True)
    dest = os.path.join(CACHE, f"{chave}.wav")
    if os.path.exists(dest): return dest
    T = f"{total:.3f}"
    fil = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{T},asetpts=PTS-STARTPTS,"
           f"volume={float(cfg_a.get('musica_db', -23)):.1f}dB,"
           f"afade=t=in:d=0.4,afade=t=out:st={max(0.0, total - 0.9):.3f}:d=0.9,"
           f"acrossover=split={corte_baixo:.0f} {corte_alto:.0f}:order=4th[gr][me][ag];"
           f"[1:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={T}[voz];"
           # so' o meio responde a voz; ataque curto (a palavra nao "pisa" na musica), soltura media
           f"[me][voz]sidechaincompress=threshold=0.012:ratio={forca:.1f}:attack=8:release=280:knee=3:makeup=1[mer];"
           f"[gr][mer][ag]amix=inputs=3:normalize=0,atrim=0:{T}[out]")
    r = config.ffmpeg(["-stream_loop", "-1", "-i", musica, "-i", narracao, "-filter_complex", fil,
                       "-map", "[out]", "-c:a", "pcm_s16le", dest + ".tmp.wav"])
    if r.returncode != 0 or not os.path.exists(dest + ".tmp.wav"):
        log(f"   recorte da musica falhou; usando o abaixamento antigo ({(r.stderr or '')[-160:]})")
        return None
    os.replace(dest + ".tmp.wav", dest)
    return dest
