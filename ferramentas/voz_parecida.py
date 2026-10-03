# -*- coding: utf-8 -*-
"""Acha a voz MiniMax mais parecida com a narracao de um video/audio de referencia.

    python ferramentas/voz_parecida.py <video_ou_audio> [--texto "frase da copy"] [--todas]

Como funciona: estima o genero pelo tom (F0), sintetiza a MESMA frase com cada voz candidata
(cache em .cache/vozes_teste) e compara a "impressao digital" de voz (ECAPA, speechbrain).
Calibracao medida em 2026-10-03: mesma voz MiniMax com textos diferentes = 0,86; vozes
diferentes = ~0,44. Acima de ~0,70 e' a mesma voz; abaixo de ~0,50 a referencia NAO e' uma voz
de sistema da MiniMax (outra plataforma, voz clonada ou locutor real).
Precisa de: pip install torch speechbrain librosa   (custo MiniMax: ~170 caracteres por voz)
"""
import argparse, binascii, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from editor import config, tts  # noqa: E402

FEM = ("lady", "girl", "woman", "queen", "female", "narrator", "hostess", "girlfriend", "boss", "spirit", "instructor", "princess")


def main(argv):
    ap = argparse.ArgumentParser(); ap.add_argument("ref"); ap.add_argument("--texto")
    ap.add_argument("--todas", action="store_true", help="testa tambem vozes de outros idiomas falando portugues")
    a = ap.parse_args(argv)
    import numpy as np, librosa, torch
    from speechbrain.inference.speaker import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy

    wav = os.path.join(config.CACHE_DIR, "ref_voz.wav"); os.makedirs(config.CACHE_DIR, exist_ok=True)
    config.ffmpeg(["-i", a.ref, "-vn", "-ac", "1", "-ar", "16000", wav])
    y, sr = librosa.load(wav, sr=16000)
    f0, vf, _ = librosa.pyin(y[: sr * 30], fmin=60, fmax=400, sr=sr)
    f0 = float(np.nanmedian(f0[vf])) if vf.any() else 0
    feminina = f0 > 165
    print(f"tom mediano {f0:.0f} Hz -> voz {'feminina' if feminina else 'masculina'}")
    texto = a.texto or "Agora você pode dar a resposta na prática. São setenta cards com histórias e uma brincadeira em cada um."

    d = tts._post("/v1/get_voice", {"voice_type": "all"})
    cand = []
    for v in d.get("system_voice") or []:
        vid = v["voice_id"]; desc = (" ".join(v.get("description") or []) + " " + (v.get("voice_name") or "")).lower()
        if not a.todas and not vid.startswith("Portuguese_"): continue
        eh_fem = any(k in desc or k in vid.lower() for k in FEM)
        if eh_fem == feminina: cand.append(vid)
    print(f"{len(cand)} vozes candidatas")

    pasta = os.path.join(config.CACHE_DIR, "vozes_teste"); os.makedirs(pasta, exist_ok=True)
    enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir=os.path.join(config.CACHE_DIR, "ecapa"),
                                         run_opts={"device": "cpu"}, local_strategy=LocalStrategy.COPY)

    def emb(sig):
        with torch.no_grad(): e = enc.encode_batch(torch.tensor(sig).unsqueeze(0)).squeeze().numpy()
        return e / np.linalg.norm(e)
    R = emb(y)
    cfg = config.padrao()["tts"]
    res = []
    for vid in cand:
        mp3 = os.path.join(pasta, config.slug(vid + "_" + texto, 80) + ".mp3")
        if not os.path.exists(mp3):
            try: tts._minimax(texto, mp3, dict(cfg, voz=vid), 1.0)
            except tts.ErroTTS as e: print("  falhou", vid, e); continue
        s, _ = librosa.load(mp3, sr=16000)
        res.append((float(emb(s) @ R), vid))
    res.sort(reverse=True)
    for s, vid in res[:10]: print(f"  {s:.3f}  {vid}")
    if res and res[0][0] < 0.5:
        print("\nnenhuma voz de sistema bate (< 0,50): a referencia veio de outra plataforma, voz clonada ou locutor real.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
