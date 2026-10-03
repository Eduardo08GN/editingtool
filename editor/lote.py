# -*- coding: utf-8 -*-
"""LOTE — produz os criativos de uma campanha: TTS -> alinhamento -> plano -> render -> entrega.

Estado em disco, idempotente (licao do ow_agente): cada criativo tem sua pasta em
`campanhas/<nome>/saida/<id>-<angulo>/` com narracao.wav, plano.json, final.mp4 e qa.json.
Rodar de novo pula o que ja' esta' pronto e igual; mudou copy/voz/base/config, refaz.
Entregues: `campanhas/<nome>/saida/_entregues/P<pub>_<id>_<angulo>_<dur>s.mp4` + player.html.
"""
import hashlib, json, os, shutil, threading, traceback
from concurrent.futures import ThreadPoolExecutor

from . import alinhar, campanha as _camp, config, montagem, musica, player, render, tts

_LOCK_WHISPER = threading.Lock()


def _hash(*partes):
    return hashlib.sha1(json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]


def conferir(cri, rel, info_tts, dur_final):
    """QA: avisos que a pessoa precisa ver antes de subir o criativo."""
    av = []
    if rel.get("razao", 0) < 0.85: av.append(f"fala divergente da copy (similaridade {rel.get('razao')})")
    if rel.get("extras", 0) > 2: av.append(f"TTS falou {rel['extras']} palavra(s) a mais")
    if "clique" not in rel.get("ouvido", "").lower(): av.append("CTA 'clique em saiba mais' nao foi ouvido")
    if abs(info_tts["duracao"] - cri["alvo_s"]) > 4:
        av.append(f"narracao {info_tts['duracao']}s vs alvo {cri['alvo_s']}s")
    return av


def produzir_um(camp, cri, base, cfg, usadas_musica, log=print, refazer=False):
    pasta = os.path.join(camp["_pasta"], "saida", f"{cri['id']}-{config.slug(cri['angulo'], 30)}")
    os.makedirs(pasta, exist_ok=True)
    wav = os.path.join(pasta, "narracao.wav")
    final = os.path.join(pasta, "final.mp4")
    est = config.ler_json(os.path.join(pasta, "qa.json")) or {}
    st = os.stat(base)
    h = _hash(cri["copy"], cri["alvo_s"], cfg, base, st.st_size, int(st.st_mtime))
    if not refazer and est.get("hash") == h and os.path.exists(final) and est.get("entregue") and os.path.exists(est["entregue"]):
        log(f"[{cri['id']}] ja' pronto — pulando"); return est

    log(f"[{cri['id']}] narracao ({cfg['tts']['provedor']}: {cfg['tts']['voz']})")
    info = tts.narrar(cri["copy"], cri["alvo_s"], wav, cfg["tts"])
    with _LOCK_WHISPER:
        palavras, rel = alinhar.alinhar(wav, cri["copy"], cfg["whisper"])
    mus = None
    if cfg["audio"].get("musica") == "auto":
        mus = musica.escolher(cri, usadas_musica.get(cri["publico_n"], set()), montagem.semente(cri["id"], camp.get("nome", "")),
                              minimo_s=info["duracao"] + 1)
        if mus: usadas_musica.setdefault(cri["publico_n"], set()).add(os.path.basename(mus["arquivo"]))
    elif cfg["audio"].get("musica"):
        mus = {"arquivo": cfg["audio"]["musica"], "titulo": os.path.basename(cfg["audio"]["musica"]), "perfil": "fixa"}
    plano = montagem.planejar(cri, palavras, info["duracao"], base, cfg, camp.get("nome", ""), mus)
    config.escrever_json(os.path.join(pasta, "plano.json"), plano)
    log(f"[{cri['id']}] render {plano['total']}s, {len(plano['planos'])} planos, {len(plano['sfx'])} sfx, "
        f"musica: {mus['titulo'] if mus else '-'}")
    r = render.renderizar(plano, wav, final, cfg, pasta_tmp=os.path.join(pasta, "_tmp"))
    entregues = os.path.join(camp["_pasta"], "saida", "_entregues")
    os.makedirs(entregues, exist_ok=True)
    nome = f"P{cri['publico_n']}_{cri['id']}_{config.slug(cri['angulo'], 30)}_{int(round(r['duracao']))}s.mp4"
    destino = os.path.join(entregues, nome)
    shutil.copyfile(final, destino)
    qa = {"hash": h, "id": cri["id"], "publico": cri["publico"], "angulo": cri["angulo"], "alvo_s": cri["alvo_s"],
          "preco": cri["preco"], "copy": cri["copy"], "duracao": r["duracao"], "tts": info, "alinhamento": rel,
          "musica": mus, "sfx": [{"t": s["t"], "cat": s["categoria"], "motivo": s["motivo"]} for s in plano["sfx"]],
          "avisos": conferir(cri, rel, info, r["duracao"]), "final": final, "entregue": destino}
    config.escrever_json(os.path.join(pasta, "qa.json"), qa)
    shutil.rmtree(os.path.join(pasta, "_tmp"), ignore_errors=True)
    log(f"[{cri['id']}] OK -> {nome}" + (f"  AVISOS: {'; '.join(qa['avisos'])}" if qa["avisos"] else ""))
    return qa


def produzir(nome_camp, base=None, so=None, workers=2, ajustes=None, log=print, refazer=False):
    camp = _camp.carregar(nome_camp)
    base = base or camp.get("base")
    if not base or not os.path.exists(base): raise SystemExit(f"video base nao encontrado: {base!r} (use --base)")
    if camp.get("base") != os.path.abspath(base):
        camp_disco = config.ler_json(os.path.join(camp["_pasta"], "campanha.json"))
        camp_disco["base"] = os.path.abspath(base)
        config.escrever_json(os.path.join(camp["_pasta"], "campanha.json"), camp_disco)
    aj = dict(camp.get("ajustes") or {})
    for k, v in (ajustes or {}).items():
        if isinstance(v, dict): aj.setdefault(k, {}).update(v)
        else: aj[k] = v
    cfg = config.padrao(aj)
    alvo = [c for c in camp["criativos"] if not so or c["id"] in so]
    if not alvo: raise SystemExit("nenhum criativo selecionado")
    log(f"campanha '{camp.get('nome')}': {len(alvo)} criativo(s), base {os.path.basename(base)}, {workers} em paralelo")
    usadas, res, erros = {}, [], []
    # ⭐ a escolha de musica depende da ordem (nao repetir no publico): sequencial por publico
    #    garante o mesmo resultado em toda rodada; o paralelismo e' entre publicos.
    por_pub = {}
    for c in alvo: por_pub.setdefault(c["publico_n"], []).append(c)

    def roda_publico(lst):
        out = []
        for c in lst:
            try: out.append(produzir_um(camp, c, base, cfg, usadas, log, refazer))
            except Exception as e:                              # noqa: BLE001
                erros.append((c["id"], str(e)[-600:])); log(f"[{c['id']}] ERRO: {e}")
                traceback.print_exc()
        return out

    with ThreadPoolExecutor(max(1, int(workers))) as ex:
        for out in ex.map(roda_publico, por_pub.values()): res.extend(out)
    todos = [config.ler_json(os.path.join(camp["_pasta"], "saida", d, "qa.json"))
             for d in sorted(os.listdir(os.path.join(camp["_pasta"], "saida"))) if not d.startswith("_")]
    todos = [t for t in todos if t]
    html = player.gerar(camp, todos)
    config.escrever_json(os.path.join(camp["_pasta"], "saida", "relatorio.json"),
                         {"campanha": camp.get("nome"), "feitos": len(res), "erros": erros, "criativos": todos})
    return {"feitos": len(res), "erros": erros, "player": html}
