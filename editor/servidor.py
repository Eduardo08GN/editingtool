# -*- coding: utf-8 -*-
r"""SERVIDOR — a ferramenta por HTTP, para o painel (painel/dist). Padrao herdado do ow_agente
(agente/servidor.py, so' consulta): FastAPI em 127.0.0.1, senha da sessao em toda rota /api.

    python edt.py painel [--porta 8791] [--sem-janela]

Leitura                                     Acoes (POST)
  GET /api/estado                             /api/campanhas/importar  {nome, produto, texto}
  GET /api/campanhas                          /api/campanhas/{nome}/abrir
  GET /api/campanhas/{nome}                   /api/campanhas/{nome}/base     {caminho}
  GET /api/base/analisar?caminho=             /api/campanhas/{nome}/ajustes  {...}
  GET /api/midia?caminho=&t=                  /api/produzir  {campanha, ids?, refazer?}
  GET /api/miniatura?caminho=&w=&t=           /api/parar
                                              /api/abrir-pasta {caminho}
⛔ `?k=` (senha) tambem vale na URL: <video src> nao manda cabecalho. (`t` e' o tempo do quadro.)
⛔ Midia so' de dentro de campanhas/, musica/ e sfx/ — o servidor nao serve o disco inteiro.
"""
import hashlib, io, json, os, secrets, socket, threading, time
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import campanha as _camp, config, lote, montagem, musica, transicoes

PAINEL = os.path.join(config.RAIZ, "painel", "dist")
CACHE_MINI = os.path.join(config.CACHE_DIR, "miniaturas")
ESTADO_UI = os.path.join(config.CACHE_DIR, "painel.json")
RAIZES = [config.CAMPANHAS_DIR, os.path.join(config.RAIZ, "musica"), config.SFX_DIR]


# ── producao em segundo plano ─────────────────────────────────────────────────
class Produtor:
    """Um lote por vez. Guarda a etapa de cada criativo e o registro para o painel."""

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.parar = threading.Event()
        self.campanha = None
        self.etapas = {}             # id -> fila|narrando|renderizando|entregue|erro|parado
        self.registro = []           # [{hora, texto}]
        self.inicio = None

    def log(self, texto):
        with self.lock:
            self.registro.insert(0, {"hora": datetime.now().strftime("%H:%M"), "texto": str(texto)})
            del self.registro[300:]

    def etapa(self, cid, e):
        with self.lock: self.etapas[cid] = e

    @property
    def rodando(self):
        return bool(self.thread and self.thread.is_alive())

    def iniciar(self, nome, ids=None, refazer=False, workers=2):
        if self.rodando: raise HTTPException(409, "ja' existe uma producao rodando")
        camp = carregar(nome)
        if not camp.get("base"): raise HTTPException(400, "defina o video base da campanha antes de produzir")
        self.parar.clear(); self.campanha = nome; self.inicio = time.time()
        with self.lock: self.etapas = {}

        def rodar():
            try:
                r = lote.produzir(nome, camp["base"], set(ids) if ids else None, workers, None,
                                  log=self.log, refazer=refazer, etapa=self.etapa, parar=self.parar)
                self.log(f"producao terminou: {r['feitos']} entregue(s)" + (f", {len(r['erros'])} erro(s)" if r["erros"] else ""))
            except BaseException as e:                           # noqa: BLE001 (SystemExit inclusive)
                self.log(f"⚠ producao parou: {e}")
        self.thread = threading.Thread(target=rodar, daemon=True); self.thread.start()


PRODUTOR = Produtor()


# ── leitura do disco ──────────────────────────────────────────────────────────
def carregar(nome):
    """campanha.carregar, mas com erro HTTP legivel (o motor usa SystemExit, que a rota nao converte)."""
    try:
        return _camp.carregar(nome)
    except SystemExit as e:
        raise HTTPException(404, str(e))


def _ui():
    return config.ler_json(ESTADO_UI, {}) or {}


def _salvar_ui(**kw):
    d = _ui(); d.update(kw); config.escrever_json(ESTADO_UI, d)


def lista_campanhas():
    out = []
    if not os.path.isdir(config.CAMPANHAS_DIR): return out
    for d in sorted(os.listdir(config.CAMPANHAS_DIR)):
        c = config.ler_json(os.path.join(config.CAMPANHAS_DIR, d, "campanha.json"))
        if not c: continue
        saida = os.path.join(config.CAMPANHAS_DIR, d, "saida")
        prontos = 0
        for x in (os.listdir(saida) if os.path.isdir(saida) else []):
            qa = config.ler_json(os.path.join(saida, x, "qa.json")) or {}
            if qa.get("entregue") and os.path.exists(qa["entregue"]): prontos += 1   # so' conta video que EXISTE
        out.append({"nome": d, "produto": c.get("produto", ""), "criativos": len(c.get("criativos", [])), "prontos": prontos})
    return out


def detalhe_campanha(nome):
    camp = carregar(nome)
    saida = os.path.join(camp["_pasta"], "saida")
    cfg = config.padrao(camp.get("ajustes"))
    criativos = []
    for c in camp["criativos"]:
        pasta = os.path.join(saida, f"{c['id']}-{config.slug(c['angulo'], 30)}")
        qa = config.ler_json(os.path.join(pasta, "qa.json")) or {}
        plano = config.ler_json(os.path.join(pasta, "plano.json")) or {}
        entregue = qa.get("entregue") if qa.get("entregue") and os.path.exists(qa["entregue"]) else None
        if not entregue: qa, plano = {}, {}       # ⛔ relatorio de um video que nao existe mais nao vai para a tela
        etapa = PRODUTOR.etapas.get(c["id"]) if PRODUTOR.campanha == nome else None
        # ⭐ "erro"/"parado" da rodada nao escondem um video que existe (ex.: refeito depois pela linha de comando)
        if etapa in ("erro", "parado") and entregue: etapa = None
        if not etapa: etapa = "entregue" if entregue else "pendente"
        if etapa == "entregue" and qa.get("avisos"): etapa = "aviso"
        criativos.append({
            **{k: c[k] for k in ("id", "publico_n", "publico", "angulo", "alvo_s", "preco", "copy")},
            "etapa": etapa, "entregue": entregue, "duracao": qa.get("duracao"), "avisos": qa.get("avisos") or [],
            "musica": (qa.get("musica") or {}).get("titulo"), "voz": (qa.get("tts") or {}).get("velocidade"),
            "sfx": len(qa.get("sfx") or []), "modelo": plano.get("modelo"), "motor": qa.get("motor"),
            "zona_segura": qa.get("zona_segura") or [], "bpm": qa.get("bpm"), "motion": qa.get("motion") or [],
            "entrega": _entrega(qa.get("entrega")),
            "turbo": bool(qa.get("turbo") or (qa.get("motor") == "remotion" and qa.get("motion"))),
            "transicoes": [t["tipo"] for t in plano.get("transicoes", []) if t.get("tipo") != "seco"],
            "perfil_musica": musica.perfil(c), "pasta": pasta if os.path.isdir(pasta) else None,
        })
    base = camp.get("base")
    return {"nome": nome, "turbo_recursos": turbo_recursos(camp, cfg) if cfg.get("turbo") else [], "produto": camp.get("produto", ""), "pasta": camp["_pasta"], "base": base,
            "base_ok": bool(base and os.path.exists(base)), "regra": _camp.validar(camp), "criativos": criativos,
            "ajustes": camp.get("ajustes") or {}, "efetivo": {
                "voz": cfg["tts"]["voz"], "velocidade": cfg["tts"]["velocidade"], "modelo": cfg.get("modelo"),
                "motor": cfg.get("motor", "ffmpeg"), "motion_graphics": cfg["video"].get("motion_graphics") or {},
                "emojis": bool((cfg["video"].get("emojis") or {}).get("ativo")),
                "selos": bool((cfg["video"].get("selos") or {}).get("ativo")),
                "camera_lenta": bool((cfg["video"].get("camera_lenta") or {}).get("ativo")),
                "turbo": bool(cfg.get("turbo")),
                "musica": cfg["audio"].get("musica"), "sfx": cfg["audio"].get("sfx", True),
                "legenda_estilo": cfg["legenda"]["estilo"], "transicoes": cfg.get("transicoes", {})},
            "entregues_dir": os.path.join(saida, "_entregues"), "publicar": _pub_destino(camp)}


def _pub_destino(camp):
    from . import publicar as _p
    return _p.destino(camp)


def _entrega(e):
    """Resultado do QA de entrega para a tela (a folha so' vai se o arquivo existir)."""
    if not e: return None
    return {"falhas": e.get("falhas") or [], "avisos": e.get("avisos") or [], "lufs": e.get("lufs"), "pico": e.get("pico"),
            "folha": e["folha"] if e.get("folha") and os.path.exists(e["folha"]) else None}


def turbo_recursos(camp, cfg):
    """O que o Modo Turbo liga nesta campanha, e se cada recurso e' pertinente aqui (com o motivo)."""
    import re as _re
    from . import motor_remotion
    rem = motor_remotion.disponivel()
    produto = camp.get("produto") or ""
    tem_num = bool(_re.search(r":\s*\d+\s+\S", produto))
    bib = os.path.join(config.RAIZ, "musica", "biblioteca")
    tem_mus = os.path.isdir(bib) and bool(os.listdir(bib))
    pesos = (cfg.get("transicoes") or {}).get("pesos") or {}
    estilo = "cartoon" if "iris" in pesos else "editor"
    return [
        {"id": "remotion", "nome": "Motor Remotion", "ativo": rem, "nota": "" if rem else "falta o Node.js nesta maquina: usa o motor atual"},
        {"id": "gancho", "nome": "Gancho animado", "ativo": tem_num and rem,
         "nota": "" if tem_num else "o nome do produto nao tem numero para contar"},
        {"id": "fecho", "nome": "Cartao de fecho", "ativo": rem, "nota": ""},
        {"id": "blur", "nome": "Motion blur", "ativo": True, "nota": "so' nas transicoes animadas"},
        {"id": "batida", "nome": "Corte na batida", "ativo": tem_mus, "nota": "" if tem_mus else "sem biblioteca de musica"},
        {"id": "musica", "nome": "Musica automatica", "ativo": tem_mus, "nota": "" if tem_mus else "sem biblioteca de musica"},
        {"id": "sfx", "nome": "SFX no pico", "ativo": True, "nota": ""},
        {"id": "emojis", "nome": "Emojis animados", "ativo": True, "nota": "nas palavras-chave"},
        {"id": "selos", "nome": "Selos de confianca", "ativo": True, "nota": "garantia, WhatsApp, compra segura"},
        {"id": "recorte", "nome": "Musica recortada sob a voz", "ativo": True, "nota": ""},
        {"id": "lenta", "nome": "Camera lenta por IA", "ativo": True, "nota": "clipe curto nao congela"},
        {"id": "transicoes", "nome": f"70% com transicao ({estilo})", "ativo": True, "nota": ""},
    ]


def analisar_base(caminho):
    if not caminho or not os.path.exists(caminho): raise HTTPException(404, "caminho nao existe")
    an = montagem.analisar_base(caminho)
    return {"pasta": an["pasta"], "clipes": len(an["clipes"]), "duracao": round(an["duracao"], 1),
            "arquivos": [{"nome": os.path.basename(c["arquivo"]), "caminho": c["arquivo"], "duracao": round(c["duracao"], 1)}
                         for c in an["clipes"]]}


def miniatura(caminho, largura=360, t=None):
    """JPEG pequeno: de imagem, redimensiona; de video, tira o quadro em `t` s (padrao: 30% do video)."""
    st = os.stat(caminho)
    chave = hashlib.sha1(f"{os.path.realpath(caminho)}|{st.st_size}|{st.st_mtime_ns}|{largura}|{t}".encode()).hexdigest()
    destino = os.path.join(CACHE_MINI, chave + ".jpg")
    if os.path.exists(destino): return destino
    os.makedirs(CACHE_MINI, exist_ok=True)
    if caminho.lower().endswith((".mp4", ".mov", ".m4v", ".webm", ".mkv")):
        tt = t if t is not None else max(0.0, config.duracao(caminho) * 0.3)
        config.ffmpeg(["-ss", f"{tt:.2f}", "-i", caminho, "-frames:v", "1", "-vf", f"scale={largura}:-2", "-q:v", "4", destino])
    else:
        from PIL import Image
        with Image.open(caminho) as im:
            im = im.convert("RGB"); im.thumbnail((largura, largura * 4)); im.save(destino, "JPEG", quality=82)
    if not os.path.exists(destino): raise HTTPException(500, "nao consegui gerar a miniatura")
    return destino


def dentro(caminho):
    real = os.path.realpath(caminho)
    return any(real.startswith(os.path.realpath(r) + os.sep) for r in RAIZES)


# ── app ───────────────────────────────────────────────────────────────────────
class Importar(BaseModel):
    nome: str
    produto: str = ""
    texto: str


class Base(BaseModel):
    caminho: str


class Produzir(BaseModel):
    campanha: str
    ids: list = []
    refazer: bool = False
    workers: int = 2


class Caminho(BaseModel):
    caminho: str


def criar_app(token, hosts):
    app = FastAPI(title="editingtool", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def portao(request: Request, call_next):
        host = (request.headers.get("host") or "").split(":")[0]
        if host not in hosts: return JSONResponse({"erro": "host"}, status_code=403)       # DNS rebinding
        if request.url.path.startswith("/api/"):
            dado = request.headers.get("x-edt-token") or request.query_params.get("k")
            if not dado or not secrets.compare_digest(dado, token):
                return JSONResponse({"erro": "senha"}, status_code=401)
        try:
            return await call_next(request)
        except SystemExit as e:          # ⛔ o motor avisa erro de uso com SystemExit (BaseException): vira 400 legivel
            return JSONResponse({"erro": str(e)}, status_code=400)

    @app.get("/api/estado")
    def estado():
        ui = _ui()
        aberta = ui.get("campanha")
        if aberta and not os.path.isdir(_camp.pasta(aberta)): aberta = None
        return {"campanha": aberta, "campanhas": lista_campanhas(), "rodando": PRODUTOR.rodando,
                "produzindo": PRODUTOR.campanha if PRODUTOR.rodando else None, "parando": PRODUTOR.parar.is_set(),
                "etapas": PRODUTOR.etapas, "registro": PRODUTOR.registro[:40],
                "minimax": bool(os.environ.get("MINIMAX_API_KEY")), "transicoes": sorted(transicoes.CATALOGO),
                "cartoon": list(transicoes.CARTOON)}

    @app.get("/api/campanhas")
    def campanhas():
        return lista_campanhas()

    @app.get("/api/campanhas/{nome}")
    def campanha(nome: str):
        return detalhe_campanha(nome)

    @app.post("/api/campanhas/{nome}/abrir")
    def abrir(nome: str):
        carregar(nome); _salvar_ui(campanha=nome); return {"ok": True}

    @app.post("/api/campanhas/importar")
    def importar(b: Importar):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(b.texto); tmp = f.name
        try:
            camp, pasta = _camp.importar(tmp, b.nome, b.produto)
        finally:
            os.remove(tmp)
        nome = os.path.basename(pasta); _salvar_ui(campanha=nome)
        return {"nome": nome, "criativos": len(camp["criativos"]), "regra": _camp.validar(camp)}

    @app.post("/api/campanhas/{nome}/base")
    def base(nome: str, b: Base):
        info = analisar_base(b.caminho)
        p = os.path.join(_camp.pasta(nome), "campanha.json")
        c = config.ler_json(p); c["base"] = os.path.abspath(b.caminho); config.escrever_json(p, c)
        return info

    @app.get("/api/base/analisar")
    def get_base(caminho: str):
        return analisar_base(caminho)

    @app.post("/api/campanhas/{nome}/ajustes")
    async def ajustes(nome: str, request: Request):
        novo = await request.json()
        p = os.path.join(_camp.pasta(nome), "campanha.json")
        c = config.ler_json(p); aj = c.setdefault("ajustes", {})
        if isinstance(novo.get("publicar"), dict):          # destino no GitHub mora fora de "ajustes"
            c.setdefault("publicar", {}).update(novo.pop("publicar"))
        for k, v in novo.items():
            if isinstance(v, dict): aj.setdefault(k, {}).update(v)
            elif v is None: aj.pop(k, None)
            else: aj[k] = v
        config.escrever_json(p, c)
        return {"ok": True, "ajustes": aj}

    @app.post("/api/produzir")
    def produzir(b: Produzir):
        PRODUTOR.iniciar(b.campanha, b.ids or None, b.refazer, b.workers)
        return {"ok": True}

    @app.post("/api/publicar")
    def post_publicar(b: Caminho):
        """b.caminho = nome da campanha. Roda em segundo plano; o resultado aparece na atividade."""
        if PRODUTOR.rodando: raise HTTPException(409, "espere a producao terminar para publicar")
        from . import publicar as _pub
        carregar(b.caminho)
        def rodar():
            try: _pub.publicar(b.caminho, log=PRODUTOR.log)
            except BaseException as e:                       # noqa: BLE001
                PRODUTOR.log(f"⚠ publicar falhou: {e}")
        threading.Thread(target=rodar, daemon=True).start()
        return {"ok": True}

    @app.post("/api/nova-narracao")
    async def nova_narracao(request: Request):
        """Outra leitura da MiniMax para UM criativo (o ouvido do operador achou a entonacao ruim)."""
        b = await request.json()
        camp = carregar(b["campanha"])
        cri = next((c for c in camp["criativos"] if c["id"] == b["id"]), None)
        if not cri: raise HTTPException(404, "criativo nao existe")
        pasta = os.path.join(camp["_pasta"], "saida", f"{cri['id']}-{config.slug(cri['angulo'], 30)}")
        arq = os.path.join(pasta, "tts_take.json")
        take = int((config.ler_json(arq) or {}).get("take", 0)) + 1
        os.makedirs(pasta, exist_ok=True); config.escrever_json(arq, {"take": take})
        PRODUTOR.iniciar(b["campanha"], [cri["id"]], refazer=True, workers=1)
        PRODUTOR.log(f"[{cri['id']}] nova narracao pedida (leitura {take})")
        return {"ok": True, "take": take}

    @app.post("/api/parar")
    def parar():
        PRODUTOR.parar.set(); PRODUTOR.log("parada pedida: termina o criativo atual e para")
        return {"ok": True}

    @app.post("/api/abrir-pasta")
    def abrir_pasta(b: Caminho):
        alvo = b.caminho if os.path.isdir(b.caminho) else os.path.dirname(b.caminho)
        if not dentro(os.path.join(alvo, "x")) and not os.path.isdir(alvo): raise HTTPException(404, "pasta nao existe")
        if os.name == "nt": os.startfile(alvo)                   # noqa: S606 (abre o Explorer na pasta)
        return {"ok": True}

    @app.get("/api/midia")
    def midia(caminho: str):
        if not (os.path.isfile(caminho) and dentro(caminho)): raise HTTPException(404, "midia fora das pastas da ferramenta")
        return FileResponse(caminho)

    @app.get("/api/miniatura")
    def mini(caminho: str, w: int = 360, t: float = None):
        if not os.path.isfile(caminho): raise HTTPException(404, "arquivo nao existe")
        return FileResponse(miniatura(caminho, max(80, min(w, 1080)), t), media_type="image/jpeg",
                            headers={"Cache-Control": "max-age=86400"})

    if os.path.isdir(PAINEL):
        @app.get("/{resto:path}")
        def spa(resto: str):
            alvo = os.path.realpath(os.path.join(PAINEL, resto))
            if resto and alvo.startswith(os.path.realpath(PAINEL)) and os.path.isfile(alvo): return FileResponse(alvo)
            return FileResponse(os.path.join(PAINEL, "index.html"))
    return app


def porta_livre(preferida):
    for p in [preferida] + list(range(preferida + 1, preferida + 20)):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0: return p
    raise SystemExit("nenhuma porta livre")


PERFIL_JANELA = os.path.join(config.CACHE_DIR, "janela_edge")


def fechar_janelas():
    """Fecha as janelas da ferramenta abertas antes. ⛔ 2026-10-05: cada reinicio abria mais uma janela
    (o operador ficou com 4). A janela roda num perfil PROPRIO do Edge (--user-data-dir), entao da' para
    achar e fechar so' ela, sem tocar no Edge normal do operador."""
    if os.name != "nt": return
    import subprocess
    alvo = PERFIL_JANELA.replace("'", "''")
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' OR Name='chrome.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{alvo}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}")
    config.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    # ⛔ abrir antes de o Edge antigo terminar de fechar = a janela nova "some" (o perfil ainda esta' preso)
    import time
    for _ in range(40):
        r = config.run(["powershell", "-NoProfile", "-Command",
                        f"(Get-CimInstance Win32_Process -Filter \"Name='msedge.exe' OR Name='chrome.exe'\" | "
                        f"Where-Object {{ $_.CommandLine -like '*{alvo}*' }}).Count"], capture_output=True, text=True)
        if (r.stdout or "0").strip() in ("", "0"): break
        time.sleep(0.25)
    time.sleep(0.5)


def abrir_janela(url):
    """UMA janela de aplicativo (Edge/Chrome em modo app, perfil proprio); sem eles, o navegador padrao."""
    import shutil, subprocess, webbrowser
    fechar_janelas()
    for exe in (shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", shutil.which("chrome"),
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if exe and os.path.exists(exe):
            subprocess.Popen([exe, f"--app={url}", "--window-size=1440,900", f"--user-data-dir={PERFIL_JANELA}",
                              "--no-first-run", "--no-default-browser-check"]); return
    webbrowser.open(url)


def ja_aberta():
    """URL do painel se ja' houver um servidor da ferramenta rodando (e respondendo), senao None."""
    import urllib.request
    d = config.ler_json(os.path.join(config.CACHE_DIR, "painel_api.json")) or {}
    if not d.get("porta"): return None
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{d['porta']}/api/estado", headers={"X-EDT-Token": d.get("token", "")})
        with urllib.request.urlopen(req, timeout=2) as r:
            return d.get("url") if r.status == 200 else None
    except Exception:                                            # noqa: BLE001
        return None


def rodar(porta=8791, janela=True):
    import uvicorn
    # ⭐ instancia UNICA: se a ferramenta ja' esta' rodando, so' traz a janela de volta (nao abre outra)
    url = ja_aberta()
    if url:
        print(f"a ferramenta ja' esta' aberta: {url}")
        if janela: abrir_janela(url)
        return
    porta = porta_livre(porta)
    token = secrets.token_urlsafe(18)
    app = criar_app(token, {"127.0.0.1", "localhost"})
    url = f"http://127.0.0.1:{porta}/#t={token}"
    config.escrever_json(os.path.join(config.CACHE_DIR, "painel_api.json"), {"porta": porta, "token": token, "url": url})
    print(f"painel: {url}")
    if janela: threading.Timer(1.0, abrir_janela, args=(url,)).start()
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning")
