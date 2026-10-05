# -*- coding: utf-8 -*-
"""LOTE — produz os criativos de uma campanha: TTS -> alinhamento -> plano -> render -> entrega.

Estado em disco, idempotente (licao do ow_agente): cada criativo tem sua pasta em
`campanhas/<nome>/saida/<id>-<angulo>/` com narracao.wav, plano.json, final.mp4 e qa.json.
Rodar de novo pula o que ja' esta' pronto e igual; mudou copy/voz/base/config, refaz.
Entregues: `campanhas/<nome>/saida/_entregues/P<pub>_<id>_<angulo>_<dur>s.mp4` + player.html.
"""
import hashlib, json, os, shutil, threading, traceback
from concurrent.futures import ThreadPoolExecutor

from . import alinhar, campanha as _camp, config, formato, montagem, musica, player, qa_entrega, render, tts

_LOCK_WHISPER = threading.Lock()


def _hash(*partes):
    return hashlib.sha1(json.dumps(partes, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:12]


# Zona segura de Reels/Stories da Meta (2026: unificada): topo ~14%, base ~35%, laterais ~6%
ZONA_TOPO, ZONA_BASE = 0.14, 0.65


def zona_segura(plano, cfg):
    """Informativo (nao e' aviso): o que do texto cai onde o app da Meta desenha a interface por cima."""
    L = plano.get("layout") or {}
    itens = [("legenda", float(L.get("legenda_y", cfg["legenda"]["centro_y"]))),
             ("CTA", float(L.get("cta_y", cfg["cta"]["centro_y"])))]
    if plano.get("titulo"): itens.append(("título", float(L.get("titulo_y", 0.15))))
    if plano.get("preco"): itens.append(("selo de preço", float(L.get("selo_y", cfg["preco"]["centro_y"]))))
    out = []
    for nome, y in itens:
        if y > ZONA_BASE: out.append(f"{nome} a {round(y * 100)}% da altura: no Reels a interface cobre de {round(ZONA_BASE * 100)}% para baixo")
        elif y < ZONA_TOPO + 0.03: out.append(f"{nome} a {round(y * 100)}% da altura: encosta na faixa do topo (até {round(ZONA_TOPO * 100)}%)")
    return out


def conferir(cri, rel, info_tts, dur_final):
    """QA: avisos que a pessoa precisa ver antes de subir o criativo."""
    av = []
    if rel.get("razao", 0) < 0.85: av.append(f"fala divergente da copy (similaridade {rel.get('razao')})")
    if rel.get("extras", 0) > 2: av.append(f"TTS falou {rel['extras']} palavra(s) a mais")
    # o CTA da copy ("clique"/"clica"/"toque"...) precisa ter sido ouvido na narracao
    from . import sfx as _sfx
    if _sfx.indice_cta([(w, 0, 0) for w in rel.get("ouvido", "").split()]) is None:
        av.append("CTA (clique/clica em ...) nao foi ouvido na narracao")
    if abs(info_tts["duracao"] - cri["alvo_s"]) > 4:
        av.append(f"narracao {info_tts['duracao']}s vs alvo {cri['alvo_s']}s")
    return av


def produzir_um(camp, cri, base, cfg, usadas_musica, log=print, refazer=False, etapa=None):
    etapa = etapa or (lambda _id, _e: None)
    # ⭐ ajustes de UM criativo (ex.: 2026-10-05, o 1.1 das variacoes vira mini VSL da landing e nao leva o
    #    cartao de fecho/SAIBA MAIS). Valem por cima da campanha E do Turbo.
    if cri.get("ajustes"):
        cfg = config.mesclar(cfg, cri["ajustes"])
        log(f"[{cri['id']}] ajustes deste criativo: {cri['ajustes'].get('_por_que') or list(cri['ajustes'])}")
    pasta = os.path.join(camp["_pasta"], "saida", f"{cri['id']}-{config.slug(cri['angulo'], 30)}")
    os.makedirs(pasta, exist_ok=True)
    wav = os.path.join(pasta, "narracao.wav")
    final = os.path.join(pasta, "final.mp4")
    est = config.ler_json(os.path.join(pasta, "qa.json")) or {}
    if os.path.isdir(base):
        assin = sorted((f, os.path.getsize(os.path.join(base, f))) for f in os.listdir(base))
    else:
        st = os.stat(base); assin = [st.st_size, int(st.st_mtime)]
    h = _hash(cri["copy"], cri["alvo_s"], {k: v for k, v in cfg.items() if not k.startswith("_")}, base, assin)
    if not refazer and est.get("hash") == h and os.path.exists(final) and est.get("entregue") and os.path.exists(est["entregue"]):
        log(f"[{cri['id']}] ja' pronto — pulando"); return est

    etapa(cri["id"], "narrando")
    # ⭐ TAKE da narracao: 0 = a de sempre; "Nova narracao" no painel soma 1 (arquivo tts_take.json)
    arq_take = os.path.join(pasta, "tts_take.json")
    take = int((config.ler_json(arq_take) or {}).get("take", 0))
    log(f"[{cri['id']}] narracao ({cfg['tts']['provedor']}: {cfg['tts']['voz']}" + (f", take {take}" if take else "") + ")")
    info = tts.narrar(cri["copy"], cri["alvo_s"], wav, dict(cfg["tts"], take=take))
    with _LOCK_WHISPER:
        palavras, rel = alinhar.alinhar(wav, cri["copy"], cfg["whisper"])
    # ⭐ voz ARRASTADA (2026-10-04, 4.1): pede outra leitura, ate' 2 vezes, e fica com a melhor
    ruins = alinhar.esticadas(palavras)
    melhor = (len(ruins), take)
    for extra in range(int(cfg["tts"].get("novas_leituras", 2))):
        if not ruins: break
        log(f"[{cri['id']}] voz arrastou {', '.join(f'{w!r} ({d}s)' for w, _a, d in ruins)} - pedindo outra leitura")
        take += 1
        info = tts.narrar(cri["copy"], cri["alvo_s"], wav, dict(cfg["tts"], take=take))
        with _LOCK_WHISPER:
            palavras, rel = alinhar.alinhar(wav, cri["copy"], cfg["whisper"])
        ruins = alinhar.esticadas(palavras)
        if len(ruins) < melhor[0]: melhor = (len(ruins), take)
    if take != melhor[1]:                               # a ultima nao foi a melhor: volta para ela (vem do cache)
        take = melhor[1]
        info = tts.narrar(cri["copy"], cri["alvo_s"], wav, dict(cfg["tts"], take=take))
        with _LOCK_WHISPER:
            palavras, rel = alinhar.alinhar(wav, cri["copy"], cfg["whisper"])
        ruins = alinhar.esticadas(palavras)
    config.escrever_json(arq_take, {"take": take})
    mus = None
    if cfg["audio"].get("musica") == "auto":
        mus = musica.escolher(cri, usadas_musica.get(cri["publico_n"], set()), montagem.semente(cri["id"], camp.get("nome", "")),
                              minimo_s=info["duracao"] + 1)
        if mus: usadas_musica.setdefault(cri["publico_n"], set()).add(os.path.basename(mus["arquivo"]))
    elif cfg["audio"].get("musica"):
        mus = {"arquivo": cfg["audio"]["musica"], "titulo": os.path.basename(cfg["audio"]["musica"]), "perfil": "fixa"}
    plano = montagem.planejar(cri, palavras, info["duracao"], base, cfg, camp.get("nome", ""), mus, camp.get("produto", ""))
    config.escrever_json(os.path.join(pasta, "plano.json"), plano)
    etapa(cri["id"], "renderizando")
    log(f"[{cri['id']}] render ({cfg.get('motor', 'ffmpeg')}) {plano['total']}s, {len(plano['planos'])} planos, {len(plano['sfx'])} sfx, "
        f"musica: {mus['titulo'] if mus else '-'}")
    # ⭐ MOTOR (Ajustes da campanha): "remotion" = legenda e graficos animados; "ffmpeg" = o original, mais rapido
    if cfg.get("motor") == "remotion":
        from . import motor_remotion
        mg = cfg["video"].get("motion_graphics") or {}
        r = motor_remotion.renderizar_plano(plano, wav, final, cfg, pasta, log, rotulo=f"[{cri['id']}] ",
                                            produto=camp.get("produto") or "", gancho=bool(mg.get("gancho")), fecho=bool(mg.get("fecho")))
        r["motion"] = [k for k in ("gancho", "fecho") if mg.get(k)]
    else:
        r = render.renderizar(plano, wav, final, cfg, pasta_tmp=os.path.join(pasta, "_tmp"))
        r["motor"] = "ffmpeg"
    # ⭐ saida organizada por PUBLICO e ANGULO (pedido do operador, 2026-10-03):
    #    _entregues/P1-religioso/1.5-equipe-de-batismo/<arquivo>.mp4 — variacoes futuras do angulo caem ali
    entregues = os.path.join(camp["_pasta"], "saida", "_entregues",
                             f"P{cri['publico_n']}-{config.slug(cri['publico'], 30)}",
                             f"{cri['id']}-{config.slug(cri['angulo'], 40)}")
    os.makedirs(entregues, exist_ok=True)
    nome = f"P{cri['publico_n']}_{cri['id']}_{config.slug(cri['angulo'], 30)}_{int(round(r['duracao']))}s.mp4"
    destino = os.path.join(entregues, nome)
    prefixo = f"P{cri['publico_n']}_{cri['id']}_"
    for velho in os.listdir(entregues):           # entrega anterior do mesmo criativo (outra duracao no nome)
        if velho.startswith(prefixo) and velho != nome: os.remove(os.path.join(entregues, velho))
    shutil.copyfile(final, destino)
    formato.garantir(final, log)
    # ⭐ QA de entrega (congelado, preto, pipoco, silencio, volume, formato) + folha de contato
    entrega = qa_entrega.conferir(final, pasta, float(cfg["audio"].get("lufs", -14)), log)
    qa = {"hash": h, "narracao_take": take, "voz_arrastada": ruins, "formato": formato.inspecionar(final)["pix_fmt"],
          "motor": r.get("motor", "ffmpeg"), "motion": r.get("motion", []), "turbo": bool(cfg.get("turbo")), "id": cri["id"], "publico": cri["publico"], "angulo": cri["angulo"], "alvo_s": cri["alvo_s"],
          "preco": cri["preco"], "copy": cri["copy"], "duracao": r["duracao"], "tts": info, "alinhamento": rel,
          "musica": mus, "sfx": [{"t": s["t"], "cat": s["categoria"], "motivo": s["motivo"]} for s in plano["sfx"]],
          "avisos": conferir(cri, rel, info, r["duracao"]) + ([f"voz arrastada em {', '.join(w for w, _a, _d in ruins)}: use Nova narracao"]
                                                               if ruins else []) + entrega["falhas"],
          "entrega": entrega, "zona_segura": zona_segura(plano, cfg),
          "bpm": plano.get("bpm"), "final": final, "entregue": destino}
    config.escrever_json(os.path.join(pasta, "qa.json"), qa)
    shutil.rmtree(os.path.join(pasta, "_tmp"), ignore_errors=True)
    etapa(cri["id"], "entregue")
    log(f"[{cri['id']}] OK -> {nome}" + (f"  AVISOS: {'; '.join(qa['avisos'])}" if qa["avisos"] else ""))
    return qa


def produzir(nome_camp, base=None, so=None, workers=2, ajustes=None, log=print, refazer=False, etapa=None, parar=None):
    etapa = etapa or (lambda _id, _e: None)
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
    # o motor Remotion divide a CPU entre os renders que rodam AO MESMO TEMPO: no maximo um por publico
    # (refazer 1 criativo usa a maquina toda, em vez de metade)
    _alvo = [c for c in camp["criativos"] if not so or c["id"] in so]
    cfg["_workers"] = max(1, min(int(workers), len({c["publico_n"] for c in _alvo}) or 1))
    if cfg.get("motor") == "remotion":
        from . import motor_remotion
        try:
            motor_remotion.preparar()                   # instala o Remotion na primeira vez, antes de gastar narracao
        except Exception as e:                          # noqa: BLE001
            if not cfg.get("turbo"): raise
            cfg["motor"] = "ffmpeg"                     # turbo e' "o melhor POSSIVEL": sem Node, segue no motor atual
            log(f"⚠ turbo: Remotion indisponivel nesta maquina ({str(e)[:120]}); usando o motor atual")
    if cfg.get("turbo"): log("turbo ligado: Remotion, motion graphics, emojis, selos, camera lenta, corte na batida, musica recortada e SFX no pico")
    alvo = [c for c in camp["criativos"] if not so or c["id"] in so]
    if not alvo: raise SystemExit("nenhum criativo selecionado")
    for c in alvo: etapa(c["id"], "fila")
    log(f"campanha '{camp.get('nome')}': {len(alvo)} criativo(s), base {os.path.basename(base)}, {workers} em paralelo")
    usadas, res, erros = {}, [], []
    # ⭐ a escolha de musica depende da ordem (nao repetir no publico): sequencial por publico
    #    garante o mesmo resultado em toda rodada; o paralelismo e' entre publicos.
    por_pub = {}
    for c in alvo: por_pub.setdefault(c["publico_n"], []).append(c)

    def roda_publico(lst):
        out = []
        for c in lst:
            if parar is not None and parar.is_set():
                etapa(c["id"], "parado"); continue
            try: out.append(produzir_um(camp, c, base, cfg, usadas, log, refazer, etapa))
            except Exception as e:                              # noqa: BLE001
                etapa(c["id"], "erro")
                erros.append((c["id"], str(e)[-600:])); log(f"[{c['id']}] ERRO: {e}")
                traceback.print_exc()
        return out

    with ThreadPoolExecutor(max(1, int(workers))) as ex:
        for out in ex.map(roda_publico, por_pub.values()): res.extend(out)
    todos = [config.ler_json(os.path.join(camp["_pasta"], "saida", d, "qa.json"))
             for d in sorted(os.listdir(os.path.join(camp["_pasta"], "saida"))) if not d.startswith("_")]
    todos = [t for t in todos if t]
    html = player.gerar(camp, todos)
    # ⭐ PUBLICAR AUTOMATICO (pedido do operador, 2026-10-03): campanha com destino no GitHub manda os
    #    entregues para o repo do time assim que o lote termina. "auto": false no campanha.json desliga.
    pub = (config.ler_json(os.path.join(camp["_pasta"], "campanha.json")) or {}).get("publicar") or {}
    if res and pub.get("repo") and pub.get("pasta") and pub.get("auto", True) and not (parar is not None and parar.is_set()):
        try:
            from . import publicar as _pub
            _pub.publicar(nome_camp, log=log, ids={q["id"] for q in res})     # so' o que ESTE lote produziu
        except BaseException as e:                              # noqa: BLE001 — publicar nunca derruba o lote
            log(f"⚠ publicar no GitHub falhou (os videos estao salvos; tente 'Enviar para o GitHub'): {e}")
    config.escrever_json(os.path.join(camp["_pasta"], "saida", "relatorio.json"),
                         {"campanha": camp.get("nome"), "feitos": len(res), "erros": erros, "criativos": todos})
    return {"feitos": len(res), "erros": erros, "player": html}
