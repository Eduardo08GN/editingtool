# -*- coding: utf-8 -*-
r"""MINERACAO — garimpa ofertas de infoproduto escaladas na Europa pela API oficial da Biblioteca de
Anuncios da Meta. O objetivo: achar oferta grande num idioma e AUSENTE em frances/alemao (o "buraco").

    python edt.py minerar [--mercados FR,DE,PT] [--max 1000] [--finalistas 40]
    python edt.py minerar --rodada <id>            (retoma uma rodada parada / refaz a analise)

Pipeline (cada etapa grava em mineracao/rodadas/<id>/; rodar de novo retoma de onde parou):
  1. coleta   termos de config/mineracao.json, frase exata, anuncios ATIVOS no mercado → dados/<M>__<termo>.json
  2. grupos   agrupa por landing (dominio), soma o alcance real (eu_total_reach), tira fisico/proibido → candidatos.json
  3. medicao  top N: TODOS os anuncios ativos da pagina na UE + alcance por pais → paginas.json
  4. landing  so' GET (nunca preenche nada): titulo, precos, sinais de digital/fisico → landings.json
  5. ofertas  nota 0-10, buraco FR/DE, links da biblioteca e da landing → ofertas.json

⭐ A medida de escala e' o ALCANCE REAL na UE (pessoas), nao o numero de anuncios.
⭐ Portugal e' a vitrine dos operadores brasileiros dentro da UE: a API mostra o alcance deles.
⛔ A API so' devolve anuncio comercial veiculado na UE/Reino Unido (Brasil/EUA puros nao aparecem).
⛔ O token (META_TOKEN no .env) nunca vai para log, tela ou git.
"""
import collections, concurrent.futures as cf, datetime, glob, html as H, http.client, json, math, os, re, threading, time
import urllib.error, urllib.parse, urllib.request

from . import config

DIR = os.path.join(config.RAIZ, "mineracao")
RODADAS = os.path.join(DIR, "rodadas")
DECISOES = os.path.join(DIR, "decisoes.json")
BANCO = os.path.join(config.RAIZ, "config", "mineracao.json")
VERSAO = "v26.0"
PAUSA = 1.5
UE = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
      "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
CAMPOS_BUSCA = ("id,page_id,page_name,ad_delivery_start_time,ad_creative_bodies,ad_creative_link_titles,"
                "ad_creative_link_captions,languages,eu_total_reach")
CAMPOS_PAGINA = ("id,page_id,page_name,ad_delivery_start_time,eu_total_reach,languages,ad_creative_link_captions,"
                 "age_country_gender_reach_breakdown")
# presenca de cada mercado-alvo: paises (alcance) e idioma (anuncios)
ALVO = {"FR": (("FR", "LU"), "fr"), "DE": (("DE", "AT"), "de")}

GENERICOS = {"fb.me", "fb.com", "facebook.com", "m.facebook.com", "instagram.com", "wa.me", "api.whatsapp.com",
             "whatsapp.com", "m.me", "bit.ly", "linktr.ee", "youtube.com", "youtu.be", "apps.apple.com",
             "play.google.com", "itunes.apple.com", "tiktok.com", "google.com", "tapthe.link"}
LOJAS = {"amazon.fr", "amazon.de", "amazon.com", "amzn.to", "amzn.eu", "fnac.com", "thalia.de", "etsy.com"}

DIGITAL = re.compile(
    r"\bpdf\b|e-?books?\b|numérique|télécharg|à imprimer|imprimable|accès immédiat|accès à vie|par e-?mail|"
    r"formation en ligne|cours en ligne|download|herunterlad|zum ausdrucken|druckbar|sofortige[rn]? (?:zugriff|zugang)|"
    r"sofort-?zugang|videokurs|online-?kurs|ratgeber|vorlagen|arbeitsbl|kein abo|einmalzahlung|digitale[sn]? produkt|"
    r"acesso imediato|acesso vitalício|para imprimir|material digital|apostila|videoaulas|curso online|kit digital|"
    r"no seu e-?mail|templates?\b|planner|printable|instant access|fichier|prêt(?:e|es)? à imprimer|kein versand", re.I)
FISICO = re.compile(
    r"livraison|frais de port|expédi|livré|colis|en stock|versand(?!kosten)|lieferung|versandkostenfrei|auf lager|"
    r"portes grátis|envio grátis|portes incluídos|encomenda|loja física|nos magasins|im laden|"
    r"crème|creme|sérum|serum|parfum|gélules|kapseln|cápsulas|suplemento|complément alimentaire|nahrungsergänzung|"
    r"matelas|matratze|chaussures|schuhe|sapatos|vêtement|kleidung|roupas?\b|bijou|schmuck|joias?\b|"
    r"restaurant|hôtel|hotel|réservez|reserv|immobili|imobili|assurance|versicherung|seguro|crédit|kredit|crédito", re.I)
PROIBIDO = re.compile(
    r"minceur|maigrir|perte de poids|perdre du poids|\d+ ?kilos?|régime|ventre plat|graisse|abnehmen|gewicht verlieren|"
    r"bauchfett|diät|emagrec|perder peso|barriga|gordura|dieta|érection|erektion|ereção|testostéron|testosteron|prostat|"
    r"potenz|libido|revenus? passifs?|passives einkommen|renda extra|ganhar dinheiro|gagner de l'argent|geld verdienen|"
    r"zweite einkommensquelle|2\. standbein|crypto|krypto|cripto|trading|bourse|börse|aktien|forex|paris sportifs|"
    r"sportwetten|apostas|casino|dropshipping|afiliad|affiliate|\bmlm\b|investissement|investimento|geldanlage|"
    r"finanças pessoais|literacia financeira|finances personnelles|finanzielle freiheit", re.I)
# titulo da landing que entrega produto fisico (livro impresso personalizado, aparelho, pulseira)
FISICO_TITULO = re.compile(r"personnalisé|personalisiert|personalizado|\bband\b|bracelet|armband|montre|\buhr\b|gerät|appareil|"
                           r"aparelho|device|matelas|coussin|kissen", re.I)
ISCA = re.compile(r"gratuit|offert|kostenlos|gratis|grátis|\bfree\b|webinaire|webinar|masterclass|aula gratuita|"
                  r"workshop gratuito|\[0€\]|0 €", re.I)
ASSINATURA = re.compile(r"abonnement|abonnez|\babo\b|monatlich|pro monat|par mois|/mois|/monat|por mês|mensalidade|"
                        # ⛔ "app" sozinho nao: oferta "sem tela" cita o app como o inimigo ("em vez do app")
                        r"lern-app|app store|google play|baixe o app|télécharge[zr]? l'app|lade die app|test(?:e|ez) gratuitement|kostenlos testen|"
                        r"tage kostenlos|jours gratuits|essai gratuit|teste grátis|software|logiciel|plattform|plateforme|saas", re.I)
# curso de carreira, certificacao, mentoria, recrutamento: ticket alto e dificil de virar low ticket
FORMACAO = re.compile(r"certifica|zertifi|torna-te|tornar-se|devenir (?:coach|praticien|formateur|thérapeute|naturopathe)|"
                      r"\bwerde\b|ausbildung zu[mr]|weiterbildung|formação (?:profissional|certificada|completa)|curso profissional|"
                      r"mentoria|mentorat|coaching|jobgarantie|reconversion|bootcamp|recrut|einstellen|fahrer finden", re.I)
NAO_ASSINATURA = re.compile(r"pas d'abonnement|sans abonnement|kein abo|ohne abo|sem assinatura|sem mensalidade|zéro abonnement", re.I)


class Parado(Exception):
    """O operador pediu para parar."""


# ── banco de termos, rodadas e decisoes ──────────────────────────────────────
EXTRAS = os.path.join(DIR, "termos_extras.json")


def banco():
    return config.ler_json(BANCO) or {"mercados": {}, "termos": {}, "alvos": ["FR", "DE"]}


def termos_extras():
    """Termos que o operador digitou no painel (por mercado). Ficam fora do git, ao lado dos dados."""
    return config.ler_json(EXTRAS, {}) or {}


def banco_completo():
    """O banco do repositorio + os termos do operador (camada "extra", sem traducao)."""
    b = banco()
    ext = termos_extras()
    for m in b["mercados"]:
        ja = {t[0].lower() for t in b["termos"].get(m, [])}
        b["termos"].setdefault(m, [])
        b["termos"][m] = b["termos"][m] + [[t, "", "extra"] for t in ext.get(m, []) if t.lower() not in ja]
    return b


def _limpar_termo(t):
    return re.sub(r"\s+", " ", (t or "").strip().strip('"').strip("“”"))[:80]


def adicionar_extras(mercado, termos):
    if mercado not in banco()["mercados"]: raise SystemExit(f"mercado {mercado} nao existe")
    d = termos_extras(); lst = d.setdefault(mercado, [])
    novos = [x for x in dict.fromkeys(_limpar_termo(t) for t in termos) if x and x.lower() not in {y.lower() for y in lst}]
    lst += novos
    config.escrever_json(EXTRAS, d)
    return novos


def remover_extra(mercado, termo):
    d = termos_extras()
    d[mercado] = [t for t in d.get(mercado, []) if t != termo]
    config.escrever_json(EXTRAS, d)


def tem_token():
    return bool(os.environ.get("META_TOKEN"))


def _token():
    t = os.environ.get("META_TOKEN")
    if not t: raise SystemExit("falta o META_TOKEN no .env (token da Biblioteca de Anuncios da Meta)")
    return t


def _pasta(rid):
    return os.path.join(RODADAS, rid)


def meta(rid):
    return config.ler_json(os.path.join(_pasta(rid), "rodada.json"), {}) or {}


def salvar_meta(rid, **kw):
    m = meta(rid); m.update(kw); m["atualizada"] = datetime.datetime.now().isoformat(timespec="seconds")
    config.escrever_json(os.path.join(_pasta(rid), "rodada.json"), m)
    return m


def nova_rodada(mercados, max_por_termo=1000, finalistas=40, termos=None):
    """`termos` = {mercado: [termo, ...]} escolhidos no painel; sem ele, usa o banco inteiro dos mercados."""
    rid = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    os.makedirs(os.path.join(_pasta(rid), "dados"), exist_ok=True)
    if termos:
        termos = {m: [x for x in dict.fromkeys(_limpar_termo(t) for t in lst) if x] for m, lst in termos.items() if lst}
        mercados = [m for m in mercados if termos.get(m)]
    return salvar_meta(rid, id=rid, criada=datetime.datetime.now().isoformat(timespec="seconds"), mercados=list(mercados),
                       max_por_termo=int(max_por_termo), finalistas=int(finalistas), fase="coleta", status="rodando",
                       termos=termos or None)


def rodadas():
    out = []
    for p in sorted(glob.glob(os.path.join(RODADAS, "*", "rodada.json")), reverse=True):
        m = config.ler_json(p, {}) or {}
        ofs = config.ler_json(os.path.join(os.path.dirname(p), "ofertas.json"), []) or []
        m["ofertas"] = len(ofs)
        m["n_termos"] = sum(len(v) for v in (m.get("termos") or {}).values()) or None
        m.pop("termos", None)
        out.append(m)
    return out


def nome_rodada(m):
    c = (m.get("criada") or "")[:10]
    return m.get("nome") or (f"Mineração {c[8:10]}/{c[5:7]}" if c else "Mineração")


def excluir_rodada(rid):
    """Hard delete da pasta da rodada (anuncios, medicoes, ofertas). As decisoes do operador ficam."""
    import shutil
    pasta = os.path.realpath(_pasta(rid))
    if not rid or os.path.dirname(pasta) != os.path.realpath(RODADAS) or not os.path.isdir(pasta):
        raise SystemExit("rodada nao existe")
    if MINERADOR.rodando and MINERADOR.rodada == rid: raise SystemExit("essa rodada esta' rodando: pare antes de excluir")
    shutil.rmtree(pasta)


def ofertas_todas():
    """Todas as rodadas numa lista so': a mesma oferta (dominio) aparece uma vez, com o dado mais novo
    e sem perder o que so' a rodada antiga tinha (ex.: nicho e concorrentes da planilha do socio)."""
    juntas = {}
    for m in sorted(rodadas(), key=lambda r: r.get("criada") or ""):
        nome = nome_rodada(m)
        for o in config.ler_json(os.path.join(_pasta(m["id"]), "ofertas.json"), []) or []:
            velha = juntas.get(o["chave"])
            if velha:
                o = {**velha, **{k: v for k, v in o.items() if v not in (None, "", [], {})}}
                o["fontes"] = list(dict.fromkeys((velha.get("fontes") or []) + [nome]))
                if velha.get("nota_planilha") is not None: o["nota_planilha"] = velha["nota_planilha"]
            else:
                o["fontes"] = [nome]
            juntas[o["chave"]] = o
    dec = decisoes()
    out = sorted(juntas.values(), key=lambda o: (-o["nota"], -o.get("alcance_ue", 0)))
    for o in out: o["decisao"] = dec.get(o["chave"]) or {}
    return out


def decisoes():
    return config.ler_json(DECISOES, {}) or {}


def decidir(chave, **kw):
    """Guarda a decisao do operador por OFERTA (dominio): vale em todas as rodadas."""
    d = decisoes(); e = d.setdefault(chave, {})
    for k, v in kw.items():
        if k not in ("status", "nota", "obs", "nicho"): continue
        if v is None or v == "": e.pop(k, None)
        else: e[k] = v
    e["quando"] = datetime.datetime.now().isoformat(timespec="seconds")
    if not any(k in e for k in ("status", "nota", "obs", "nicho")): d.pop(chave, None)
    config.escrever_json(DECISOES, d)
    return d.get(chave)


def ofertas(rid):
    ofs = config.ler_json(os.path.join(_pasta(rid), "ofertas.json"), []) or []
    dec = decisoes()
    nome = nome_rodada(meta(rid))
    for o in ofs: o["decisao"] = dec.get(o["chave"]) or {}; o.setdefault("fontes", [nome])
    return ofs


# ── API da Meta ───────────────────────────────────────────────────────────────
def _esperar(s, parar):
    if parar is None: time.sleep(s); return
    if parar.wait(s): raise Parado()


def _chamar(url, parar=None):
    for tentativa in range(8):
        if parar is not None and parar.is_set(): raise Parado()
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", "replace")
            try: err = json.loads(corpo)["error"]
            except Exception: err = {"message": corpo[:200]}
            if err.get("code") in (1, 2, 4, 17, 32, 613) or err.get("is_transient"):
                _esperar(90 * (tentativa + 1), parar); continue
            if err.get("code") == 190: raise RuntimeError("o token da Meta expirou ou e' invalido (troque o META_TOKEN no .env)")
            raise RuntimeError(f"API da Meta: {err.get('message')} (code {err.get('code')})")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException):
            _esperar(15, parar)          # ⛔ rede caindo no meio da resposta (IncompleteRead): tenta de novo
    raise RuntimeError("a API da Meta nao respondeu depois de varias tentativas")


def _url(params):
    return f"https://graph.facebook.com/{VERSAO}/ads_archive?" + urllib.parse.urlencode(dict(params, access_token=_token()))


def buscar(termo, paises, maximo=1000, parar=None):
    url = _url({"search_terms": termo, "search_type": "KEYWORD_EXACT_PHRASE", "ad_active_status": "ACTIVE",
                "ad_reached_countries": json.dumps(paises), "fields": CAMPOS_BUSCA, "limit": "250"})
    ads = []
    while url and len(ads) < maximo:
        r = _chamar(url, parar)
        ads += r.get("data", [])
        url = r.get("paging", {}).get("next")
        _esperar(PAUSA, parar)
    return ads


def anuncios_da_pagina(pid, parar=None, maximo=1500):
    url = _url({"search_page_ids": json.dumps([pid]), "search_terms": "''", "ad_active_status": "ACTIVE",
                "ad_reached_countries": json.dumps(UE), "fields": CAMPOS_PAGINA, "limit": "100"})
    ads = []
    while url and len(ads) < maximo:
        r = _chamar(url, parar)
        ads += r.get("data", [])
        url = r.get("paging", {}).get("next")
        _esperar(1.0, parar)
    return ads


def biblioteca(pid, pais="ALL"):
    return ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=" + pais +
            f"&view_all_page_id={pid}&search_type=page&media_type=all")


def busca_biblioteca(termo, pais):
    return ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=" + pais +
            "&q=" + urllib.parse.quote(f'"{termo}"') + "&search_type=keyword_exact_phrase&media_type=all")


# ── 1. coleta ─────────────────────────────────────────────────────────────────
def _arq_termo(rid, mercado, termo):
    return os.path.join(_pasta(rid), "dados", f"{mercado}__{config.slug(termo, 60)}.json")


def coletar(rid, log=print, parar=None, prog=None):
    m, b = meta(rid), banco_completo()
    if m.get("termos"):                                   # ⭐ termos escolhidos no painel para esta rodada
        b["termos"] = {mc: [[t, "", ""] for t in lst] for mc, lst in m["termos"].items()}
    mercados = [x for x in m.get("mercados", []) if x in b["termos"]]
    total = sum(len(b["termos"][x]) for x in mercados)
    feitos = [0]
    lock = threading.Lock()

    def avancar():
        with lock:
            feitos[0] += 1
            if prog: prog(feitos[0], total)

    def um_mercado(mc):
        paises = b["mercados"][mc]["paises"]
        for termo, _pt, _camada in b["termos"][mc]:
            arq = _arq_termo(rid, mc, termo)
            if os.path.exists(arq): avancar(); continue
            try:
                ads = buscar(termo, paises, m.get("max_por_termo", 1000), parar)
            except RuntimeError as e:
                log(f"⚠ [{mc}] {termo}: {e}"); avancar()
                if "token" in str(e): raise
                continue
            for a in ads: a["_termo"], a["_mercado"] = termo, mc
            os.makedirs(os.path.dirname(arq), exist_ok=True)
            with open(arq + ".tmp", "w", encoding="utf-8") as f: json.dump(ads, f, ensure_ascii=False)
            os.replace(arq + ".tmp", arq)
            log(f"[{mc}] {termo}: {len(ads)} anúncios"); avancar()

    if prog: prog(0, total)
    with cf.ThreadPoolExecutor(max(1, len(mercados))) as ex:        # um mercado por vez em cada fio
        for f in [ex.submit(um_mercado, mc) for mc in mercados]: f.result()


# ── 2. grupos por landing ─────────────────────────────────────────────────────
def _dominio(ad):
    for c in ad.get("ad_creative_link_captions") or []:
        c = re.sub(r"^https?://", "", (c or "").strip().lower()).split("/")[0]
        c = re.sub(r"^www\.", "", c)
        if "." in c and " " not in c and c not in GENERICOS: return c
    return None


def _dias(ad, hoje):
    ini = (ad.get("ad_delivery_start_time") or "")[:10]
    return (hoje - datetime.date.fromisoformat(ini)).days if ini else 0


def agrupar(ads, hoje=None):
    """Anuncios → grupos por landing com alcance, persistencia e cara de digital. Funcao pura (testavel)."""
    hoje = hoje or datetime.date.today()
    dom_pag = collections.defaultdict(collections.Counter)
    for a in ads:
        d = _dominio(a)
        if d: dom_pag[a["page_id"]][d] += 1
    grupos = {}
    for a in ads:
        d = _dominio(a) or (dom_pag[a["page_id"]].most_common(1)[0][0] if dom_pag[a["page_id"]] else None)
        chave = d or f"pagina:{a['page_id']}"
        g = grupos.setdefault(chave, {"chave": chave, "dominio": d, "paginas": collections.Counter(), "nomes": {},
                                      "n": 0, "n15": 0, "alc": 0, "alc_novo": 0, "max_dias": 0,
                                      "mercados": collections.Counter(), "idiomas": collections.Counter(),
                                      "corpos": collections.Counter(), "titulos": collections.Counter(),
                                      "termos": collections.Counter(), "dig": 0, "fis": 0, "proib": 0, "isca": 0,
                                      "assin": 0, "form": 0, "textos": []})
        dd, r = _dias(a, hoje), a.get("eu_total_reach") or 0
        g["paginas"][a["page_id"]] += 1; g["nomes"][a["page_id"]] = a.get("page_name") or "?"
        g["n"] += 1; g["alc"] += r; g["max_dias"] = max(g["max_dias"], dd)
        if dd >= 15: g["n15"] += 1
        else: g["alc_novo"] += r
        for mc in a.get("_mercados") or [a.get("_mercado")]: g["mercados"][mc] += 1
        for t in a.get("_termos") or [f"{a.get('_mercado')}:{a.get('_termo')}"]: g["termos"][t] += 1
        for l in a.get("languages") or []: g["idiomas"][l] += 1
        corpo = re.sub(r"\s+", " ", " ".join(a.get("ad_creative_bodies") or [])).strip()
        tit = " | ".join(dict.fromkeys(t for t in (a.get("ad_creative_link_titles") or []) if t))
        if corpo: g["corpos"][corpo[:140]] += 1
        if tit: g["titulos"][tit[:120]] += 1
        txt = corpo + " " + tit
        g["dig"] += bool(DIGITAL.search(txt)); g["fis"] += bool(FISICO.search(txt)); g["proib"] += bool(PROIBIDO.search(txt))
        g["isca"] += bool(ISCA.search(tit + " " + corpo[:250]))
        g["assin"] += bool(ASSINATURA.search(NAO_ASSINATURA.sub(" ", txt)))
        g["form"] += bool(FORMACAO.search(txt) or re.match(r"(formation|formacao|school|akademie)\.", d or ""))
        if corpo and len(g["textos"]) < 3 and corpo[:60] not in [x[:60] for x in g["textos"]]: g["textos"].append(corpo[:400])
    return grupos


def candidatos(grupos):
    out = []
    for g in grupos.values():
        n = g["n"]
        if n < 3 or (g["dominio"] or "") in LOJAS: continue
        dig, fis, proib = g["dig"] / n, g["fis"] / n, g["proib"] / n
        if dig < 0.25 or fis > max(0.15, dig / 2) or proib > 0.15: continue
        dup = g["corpos"].most_common(1)[0][1] if g["corpos"] else 0
        score = (math.log10(g["alc"] + 10) * 10 + math.log10(g["alc_novo"] + 10) * 4
                 + min(g["n15"], 40) * 0.4 + min(dup, 30) * 0.2)
        out.append({"chave": g["chave"], "dominio": g["dominio"], "score": round(score, 1), "alcance": g["alc"],
                    "anuncios": n, "anuncios_15d": g["n15"], "max_dias": g["max_dias"], "dup_max": dup,
                    "digital": round(dig, 2), "isca": round(g["isca"] / n, 2), "assinatura": round(g["assin"] / n, 2),
                    "formacao": round(g["form"] / n, 2),
                    "paginas": [{"id": pid, "nome": g["nomes"][pid], "anuncios": k} for pid, k in g["paginas"].most_common(3)],
                    "mercados": dict(g["mercados"]), "idiomas": dict(g["idiomas"].most_common(6)),
                    "titulos": [t for t, _ in g["titulos"].most_common(4)], "textos": g["textos"],
                    "termos": [t for t, _ in g["termos"].most_common(8)]})
    out.sort(key=lambda c: -c["score"])
    return out


def ler_anuncios(rid):
    """Todos os anuncios coletados na rodada, sem repetir (um anuncio achado por varios termos guarda todos)."""
    ads = {}
    for f in glob.glob(os.path.join(_pasta(rid), "dados", "*.json")):
        for a in config.ler_json(f, []) or []:
            b = ads.setdefault(a["id"], a)
            b.setdefault("_termos", set()).add(f"{a.get('_mercado')}:{a.get('_termo')}")
            b.setdefault("_mercados", set()).add(a.get("_mercado"))
    return list(ads.values())


# ── 3. medicao da pagina inteira ──────────────────────────────────────────────
def medir_pagina(ids, parar=None, hoje=None):
    hoje = hoje or datetime.date.today()
    t = {"n": 0, "n15": 0, "alc": 0, "alc15": 0, "max_dias": 0, "paises": collections.Counter(),
         "idiomas": collections.Counter(), "nomes": set()}
    for pid in dict.fromkeys(ids):
        for a in anuncios_da_pagina(pid, parar):
            d, r = _dias(a, hoje), a.get("eu_total_reach") or 0
            t["n"] += 1; t["alc"] += r; t["max_dias"] = max(t["max_dias"], d); t["nomes"].add(a.get("page_name") or "?")
            if d >= 15: t["n15"] += 1; t["alc15"] += r
            for l in a.get("languages") or []: t["idiomas"][l] += 1
            for b in a.get("age_country_gender_reach_breakdown") or []:
                t["paises"][b.get("country")] += sum((x.get("male") or 0) + (x.get("female") or 0) + (x.get("unknown") or 0)
                                                     for x in b.get("age_gender_breakdowns") or [])
    soma = sum(t["paises"].values()) or 1
    return {"anuncios": t["n"], "anuncios_15d": t["n15"], "alcance_ue": t["alc"], "alcance_15d": t["alc15"],
            "max_dias": t["max_dias"], "nomes": sorted(t["nomes"]),
            "paises_pct": {k: round(v * 100 / soma) for k, v in t["paises"].most_common(8)},
            "idiomas": dict(t["idiomas"].most_common(8))}


def medir(rid, cands, n, log=print, parar=None, prog=None):
    arq = os.path.join(_pasta(rid), "paginas.json")
    pags = config.ler_json(arq, {}) or {}
    alvo = [c for c in cands if c["isca"] < 0.4 and c.get("formacao", 0) < 0.3 and c.get("assinatura", 0) < 0.3][:n]
    for i, c in enumerate(alvo, 1):
        if prog: prog(i - 1, len(alvo))
        if c["chave"] in pags: continue
        try:
            pags[c["chave"]] = medir_pagina([p["id"] for p in c["paginas"]], parar)
        except RuntimeError as e:
            log(f"⚠ medicao de {c['chave']}: {e}")
            if "token" in str(e): raise
            continue
        config.escrever_json(arq, pags)
        p = pags[c["chave"]]
        log(f"medida: {c['chave']} · {p['alcance_ue']:,} pessoas · {p['anuncios']} anúncios".replace(",", "."))
    if prog: prog(len(alvo), len(alvo))
    return pags


# ── 4. landing (so' leitura) ──────────────────────────────────────────────────
# ⛔ "R$ 426" nao e' dolar: real fica fora do preco (vira so' a bandeira Operador BR)
PRECO = re.compile(r"(?:€|EUR|US\$|(?<![R\w])\$)\s?(\d{1,4}(?:[.,]\d{1,2})?)|(\d{1,4}(?:[.,]\d{1,2})?)\s?(?:€|EUR|USD|\$)")
FISICO_LP = re.compile(r"livraison (?!immédiate)|frais de port|versandkosten|lieferzeit|portes|envio pelos correios|shipping", re.I)


def ler_landing(url):
    """GET da landing (nunca preenche nada): titulo, precos, se parece digital. Sem rede: {'erro': ...}."""
    if not url.startswith("http"): url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36",
                                                   "Accept-Language": "fr,de,pt;q=0.8"})
        with urllib.request.urlopen(req, timeout=20) as r:
            h = r.read(3_000_000).decode("utf-8", "replace"); final = r.url
    except Exception as e:                                       # noqa: BLE001
        return {"url": url, "erro": str(e)[:120]}
    titulo = H.unescape((re.search(r"<title[^>]*>([^<]*)", h) or [None, ""])[1]).strip()
    t = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[\s\S]*?</\1>", " ", h))))
    valores = []
    for m in PRECO.finditer(t):
        v = (m.group(1) or m.group(2) or "").replace(",", ".")
        try: f = float(v)
        except ValueError: continue
        if 1 <= f <= 2000: valores.append(f)
    precos = list(dict.fromkeys(re.findall(r"(?:€|US\$|\$|R\$)\s?\d+[.,]?\d*|\d+[.,]?\d*\s?(?:€|\$)", t)))[:8]
    tipico = sorted(valores)[len(valores) // 2] if valores else None     # o preco que mais aparece pesa mais que a ancora
    return {"url": url, "final": final, "titulo": titulo[:140], "precos": precos,
            "preco_min": min(valores) if valores else None, "preco_tipico": tipico, "brl": "R$" in t,
            "digital": len(DIGITAL.findall(t)), "fisico": len(FISICO_LP.findall(t)), "vazia": len(t) < 400}


def checar_landings(rid, chaves, log=print, parar=None):
    arq = os.path.join(_pasta(rid), "landings.json")
    lps = config.ler_json(arq, {}) or {}
    faltam = [k for k in chaves if k not in lps and not k.startswith("pagina:")]
    with cf.ThreadPoolExecutor(8) as ex:
        for k, r in zip(faltam, ex.map(ler_landing, faltam)):
            if parar is not None and parar.is_set(): raise Parado()
            lps[k] = r
    config.escrever_json(arq, lps)
    if faltam: log(f"{len(faltam)} landing(s) lidas")
    return lps


# ── 5. ofertas com nota ───────────────────────────────────────────────────────
def presenca(p):
    """% do mercado-alvo na pagina: o maior entre o alcance nos paises dele e a fatia de anuncios no idioma dele."""
    tot_id = sum(p.get("idiomas", {}).values()) or 1
    return {m: max(sum(p.get("paises_pct", {}).get(x, 0) for x in paises),
                   round(p.get("idiomas", {}).get(lang, 0) * 100 / tot_id))
            for m, (paises, lang) in ALVO.items()}


def nota(o):
    """0-10: escala real (40%), persistencia (20%), buraco FR/DE (25%), cara de digital (15%), menos as bandeiras."""
    escala = min(1.0, max(0.0, (math.log10(o["alcance_ue"] + 1) - 4.0) / 2.6))       # 10 mil → 0 · ~4 mi → 1
    persist = min(o["anuncios_15d"], 40) / 40
    buraco = 1.0 if o["buraco"] else (0.4 if min(o["presenca"].values() or [100]) < 20 else 0.0)
    n = 10 * (0.40 * escala + 0.20 * persist + 0.25 * buraco + 0.15 * o["digital"])
    # ⭐ o alvo e' low ticket a €10: o que nao vira low ticket cai para o fim da lista (mas fica visivel)
    pen = {"isca": 5, "fisico": 5, "assinatura": 4, "formacao": 4, "ticket_alto": 4, "novo": 1}
    n -= sum(pen.get(f, 0) for f in o["bandeiras"])
    return round(max(0.0, min(10.0, n)) * 2) / 2


def montar_ofertas(rid, cands, pags, lps, hoje=None):
    hoje = hoje or datetime.date.today()
    out, vistas = [], set()
    for c in cands:
        p = pags.get(c["chave"])
        if not p or not p.get("anuncios"): continue
        if c["paginas"][0]["id"] in vistas: continue        # mesma pagina com dois dominios (.fr/.be): uma oferta so'
        vistas.add(c["paginas"][0]["id"])
        lp = lps.get(c["chave"]) or {}
        pres = presenca(p)
        bandeiras = []
        if p["anuncios_15d"] == 0: bandeiras.append("novo")
        if p["alcance_ue"] > 50_000 and (p["alcance_ue"] - p["alcance_15d"]) / p["alcance_ue"] > 0.4: bandeiras.append("escalando")
        if c["isca"] >= 0.4: bandeiras.append("isca")
        tit_lp = lp.get("titulo") or ""
        if c["assinatura"] >= 0.3 or ASSINATURA.search(NAO_ASSINATURA.sub(" ", tit_lp)): bandeiras.append("assinatura")
        if c.get("formacao", 0) >= 0.3: bandeiras.append("formacao")
        if (lp.get("fisico", 0) >= 3 and lp["fisico"] > lp.get("digital", 0)) or FISICO_TITULO.search(tit_lp): bandeiras.append("fisico")
        if PROIBIDO.search(tit_lp): continue
        if (lp.get("preco_tipico") or lp.get("preco_min") or 0) > 60: bandeiras.append("ticket_alto")
        if lp.get("brl"): bandeiras.append("operador_br")
        pid = c["paginas"][0]["id"]
        titulo = (c["titulos"][0].split(" | ")[0] if c["titulos"] else "") or lp.get("titulo") or c["paginas"][0]["nome"]
        o = {"chave": c["chave"], "oferta": titulo, "titulo_landing": lp.get("titulo") or "",
             "anunciante": ", ".join(dict.fromkeys(x["nome"] for x in c["paginas"])),
             "biblioteca": biblioteca(pid), "bibliotecas": [{"nome": x["nome"], "url": biblioteca(x["id"])} for x in c["paginas"]],
             "landing": lp.get("final") or (f"https://{c['dominio']}" if c["dominio"] else None), "landing_erro": lp.get("erro"),
             "origem": sorted(c["mercados"], key=lambda k: -c["mercados"][k]),
             "variacoes": [{"termo": t.split(":", 1)[1], "mercado": t.split(":", 1)[0]} for t in c["termos"]],
             "alcance_ue": p["alcance_ue"], "alcance_15d": p["alcance_15d"], "anuncios": p["anuncios"],
             "anuncios_15d": p["anuncios_15d"], "max_dias": p["max_dias"],
             "rodando_desde": (hoje - datetime.timedelta(days=p["max_dias"])).isoformat(),
             "paises_pct": p["paises_pct"], "idiomas": p["idiomas"], "presenca": pres,
             "buraco": [m for m, v in pres.items() if v < 5], "precos": lp.get("precos") or [], "preco_min": lp.get("preco_min"),
             "digital": c["digital"], "bandeiras": bandeiras, "textos": c["textos"], "titulos": c["titulos"]}
        o["nota"] = nota(o)
        out.append(o)
    out.sort(key=lambda o: (-o["nota"], -o["alcance_ue"]))
    return out


# ── importar a planilha de garimpo do time (Planilha de Ofertas.html / dados-*.js) ──
def ler_planilha(texto):
    """dados-frances.js / dados-brasil.js (window.OFERTAS["fr"] = [...]) ou um JSON com a lista."""
    texto = texto.strip()
    if texto.startswith("["): return json.loads(texto)
    m = re.search(r"=\s*(\[[\s\S]*\])\s*;?\s*$", texto)
    if not m: raise SystemExit("nao achei a lista de ofertas no arquivo (esperava window.OFERTAS[...] = [...])")
    return json.loads(m.group(1))


def _host(url):
    h = re.sub(r"^https?://", "", (url or "").strip().lower()).split("/")[0]
    return re.sub(r"^www\.", "", h)


def importar_planilha(itens, nome="Garimpo do sócio", criada=None, log=print, parar=None):
    """Vira uma rodada: cada oferta da planilha e' medida pela API (alcance real, paises, 15+ dias) e a landing
    e' lida. Nota, nicho, concorrentes, variacoes e observacoes da planilha ficam como estao."""
    criada = criada or datetime.datetime.now().isoformat(timespec="seconds")
    rid = criada[:10] + "_planilha-" + config.slug(nome, 24)
    os.makedirs(_pasta(rid), exist_ok=True)
    salvar_meta(rid, id=rid, criada=criada, nome=nome, tipo="planilha", mercados=["FR"], fase="medicao", status="rodando")
    try:
        return _importar_planilha(rid, itens, nome, log, parar)
    except BaseException as e:                                       # noqa: BLE001
        salvar_meta(rid, status="erro", erro=str(e)[:300]); raise


def _importar_planilha(rid, itens, nome, log, parar):
    arq_p = os.path.join(_pasta(rid), "paginas.json")
    pags = config.ler_json(arq_p, {}) or {}
    hoje, out = datetime.date.today(), []
    for it in itens:
        pid = (re.search(r"view_all_page_id=(\d+)", it.get("biblioteca") or "") or [None, None])[1]
        chave = _host(it.get("landing")) or (f"pagina:{pid}" if pid else config.slug(it.get("oferta", "?"), 40))
        p = pags.get(chave)
        if p is None and pid and tem_token():
            try:
                p = pags[chave] = medir_pagina([pid], parar); config.escrever_json(arq_p, pags)
                log(f"medida: {it.get('oferta')} · {p['alcance_ue']:,} pessoas".replace(",", "."))
            except RuntimeError as e:
                log(f"⚠ medicao de {it.get('oferta')}: {e}"); p = None
        p = p or {"anuncios": it.get("ativos_total") or 0, "anuncios_15d": it.get("ativos_15d") or 0, "alcance_ue": 0,
                  "alcance_15d": 0, "max_dias": 0, "paises_pct": {}, "idiomas": {}}
        lp = ler_landing(it["landing"]) if it.get("landing") else {}
        pres = presenca(p)
        dias_planilha = (hoje - datetime.date.fromisoformat(it["rodando_desde"])).days if it.get("rodando_desde") else 0
        max_dias = max(p.get("max_dias") or 0, dias_planilha)
        bandeiras = (["novo"] if p["anuncios_15d"] == 0 else []) + (["operador_br"] if lp.get("brl") else [])
        obs = " ".join(x for x in (it.get("por_que"), it.get("observacao")) if x)
        o = {"chave": chave, "oferta": it.get("oferta") or chave, "titulo_landing": lp.get("titulo") or "",
             "anunciante": it.get("anunciante") or "", "biblioteca": it.get("biblioteca") or (biblioteca(pid) if pid else ""),
             "bibliotecas": [{"nome": it.get("anunciante") or "página", "url": it.get("biblioteca")}] if it.get("biblioteca") else [],
             "landing": it.get("landing"), "landing_erro": lp.get("erro"), "origem": ["FR"],
             "variacoes": [{"termo": x["termo"], "mercado": "FR"} for x in it.get("pesquisar") or [] if x.get("termo")],
             "alcance_ue": p["alcance_ue"], "alcance_15d": p.get("alcance_15d", 0), "anuncios": p["anuncios"],
             "anuncios_15d": p["anuncios_15d"], "max_dias": max_dias,
             "rodando_desde": it.get("rodando_desde") or (hoje - datetime.timedelta(days=max_dias)).isoformat(),
             "paises_pct": p.get("paises_pct", {}), "idiomas": p.get("idiomas", {}), "presenca": pres,
             "buraco": [m for m, v in pres.items() if v < 5] if p.get("paises_pct") else [],
             "precos": [it["preco"]] if it.get("preco") else lp.get("precos") or [], "preco_min": lp.get("preco_min"),
             "digital": 1.0, "bandeiras": bandeiras, "textos": [], "titulos": [],
             "nicho": it.get("nicho") or "", "formato": it.get("formato") or "", "observacao": obs,
             "concorrentes": [{"nome": c.get("nome"), "url": c.get("link"), "obs": c.get("obs")} for c in it.get("concorrentes") or []],
             "n_concorrentes": it.get("concorrentes_fr"), "anuncios_fr": it.get("anuncios_fr"), "anuncios_fr_15d": it.get("anuncios_fr_15d"),
             "esforco": it.get("esforco"), "aceitacao": it.get("aceitacao_fr"), "adaptacao": it.get("adaptacao"),
             "paises_alvo": it.get("paises_alvo"), "nota_planilha": it.get("nota")}
        # ⭐ a nota da tabela e' a automatica (medida hoje, como as outras rodadas); a da planilha fica ao lado.
        #    Sem medicao (sem token), vale a da planilha.
        o["nota"] = nota(o) if o["alcance_ue"] or it.get("nota") is None else float(it["nota"])
        out.append(o)
    out.sort(key=lambda o: (-o["nota"], -o["alcance_ue"]))
    config.escrever_json(os.path.join(_pasta(rid), "ofertas.json"), out)
    salvar_meta(rid, fase="pronta", status="pronta")
    log(f"planilha importada: {len(out)} ofertas em '{nome}'")
    return rid, out


# ── a rodada inteira ──────────────────────────────────────────────────────────
def analisar(rid, log=print, parar=None, fase=None, prog=None):
    """Etapas 2-5 (sem coletar). Retoma: pagina ja' medida e landing ja' lida nao repetem."""
    fase = fase or (lambda f: None)
    fase("grupos")
    cands = candidatos(agrupar(ler_anuncios(rid)))
    config.escrever_json(os.path.join(_pasta(rid), "candidatos.json"), cands[:400])
    log(f"{len(cands)} grupos com cara de produto digital")
    fase("medicao")
    pags = medir(rid, cands, meta(rid).get("finalistas", 40), log, parar, prog)
    fase("landing")
    lps = checar_landings(rid, [c["chave"] for c in cands if c["chave"] in pags], log, parar)
    fase("ofertas")
    ofs = montar_ofertas(rid, cands, pags, lps)
    config.escrever_json(os.path.join(_pasta(rid), "ofertas.json"), ofs)
    log(f"rodada pronta: {len(ofs)} ofertas ranqueadas")
    return ofs


def rodar(rid, log=print, parar=None, fase=None, prog=None):
    fase = fase or (lambda f: None)
    fase("coleta")
    coletar(rid, log, parar, prog)
    return analisar(rid, log, parar, fase, prog)


class Minerador:
    """Uma mineracao por vez, em segundo plano, com registro e progresso para o painel."""

    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.parar = threading.Event()
        self.rodada = None
        self.fase = None
        self.progresso = {"feitos": 0, "total": 0}
        self.registro = []

    def log(self, texto):
        with self.lock:
            self.registro.insert(0, {"hora": datetime.datetime.now().strftime("%H:%M"), "texto": str(texto)})
            del self.registro[200:]

    @property
    def rodando(self):
        return bool(self.thread and self.thread.is_alive())

    def _fase(self, f):
        self.fase = f; self.progresso = {"feitos": 0, "total": 0}
        salvar_meta(self.rodada, fase=f)

    def _prog(self, feitos, total):
        self.progresso = {"feitos": feitos, "total": total}

    def iniciar(self, rid, coletar_antes=True):
        if self.rodando: raise RuntimeError("ja' existe uma mineracao rodando")
        if coletar_antes: _token()
        self.parar.clear(); self.rodada = rid
        salvar_meta(rid, status="rodando", erro=None)

        def correr():
            try:
                (rodar if coletar_antes else analisar)(rid, self.log, self.parar, self._fase, self._prog)
                salvar_meta(rid, status="pronta", fase="pronta"); self.fase = "pronta"
            except Parado:
                salvar_meta(rid, status="parada"); self.log("mineracao parada: retome quando quiser")
            except BaseException as e:                               # noqa: BLE001 (SystemExit inclusive)
                salvar_meta(rid, status="erro", erro=str(e)[:300]); self.log(f"⚠ mineracao parou: {e}")
        self.thread = threading.Thread(target=correr, daemon=True); self.thread.start()

    def importar(self, itens, nome):
        """Planilha → rodada, em segundo plano (mede cada pagina na API)."""
        if self.rodando: raise RuntimeError("ja' existe uma mineracao rodando")
        self.parar.clear(); self.rodada = None; self.fase = "medicao"; self.progresso = {"feitos": 0, "total": len(itens)}

        def correr():
            try:
                rid, _ = importar_planilha(itens, nome, log=self.log, parar=self.parar)
                self.rodada = rid; self.fase = "pronta"
            except BaseException as e:                               # noqa: BLE001
                self.log(f"⚠ importacao parou: {e}")
        self.thread = threading.Thread(target=correr, daemon=True); self.thread.start()


MINERADOR = Minerador()
