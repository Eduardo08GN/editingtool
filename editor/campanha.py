# -*- coding: utf-8 -*-
"""CAMPANHA — o mapa de angulos (texto) vira `campanha.json`, e a regra da operacao e' conferida.

Formato de entrada (o mesmo que o time ja' escreve):

    Público 1 - Religioso (copys escolhidas)
    1.1 Padre (20 s, sem preço)
    <a narracao, em uma ou mais linhas>
    1.2 Pastor (31 s, com preço)
    ...

⭐ A COPY E' SAGRADA: o texto importado e' exatamente o que vai para o TTS e para a legenda.
A ferramenta confere a regra (tempos, preco, CTA) e AVISA; quem corrige a copy e' a pessoa.
"""
import io, os, re

from . import config

RX_PUBLICO = re.compile(r"^\s*P[úu]blico\s+(\d+)\s*[-–:]\s*(.+?)\s*(\(.*\))?\s*$", re.I)
RX_CRIATIVO = re.compile(r"^\s*(\d+)\.(\d+)\s+(.+?)\s*\(\s*(\d+)\s*s\s*,\s*(com|sem)\s+pre[çc]o\s*\)\s*$", re.I)

PALAVRAS_POR_S = 2.6      # medido no criativo de referencia: 95 palavras narradas em ~37 s (pt-BR)
CLASSES = (20, 30, 40)
REGRA_POR_PUBLICO = {20: 2, 30: 2, 40: 1}
PRECO_POR_PUBLICO = 2
CTA_FRASE = "clique em saiba mais e confira"


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", t).split()


def palavras(copy):
    return len([w for w in copy.split() if any(c.isalnum() for c in w)])


def estimar_s(copy):
    return round(palavras(copy) / PALAVRAS_POR_S, 1)


def classe(seg):
    return min(CLASSES, key=lambda c: abs(c - seg))


def importar_texto(txt, produto=""):
    """Texto do mapa de angulos -> dict da campanha."""
    criativos, pub_n, pub_nome, atual = [], None, "", None
    linhas_produto = []
    for linha in txt.splitlines():
        m_pub, m_cri = RX_PUBLICO.match(linha), RX_CRIATIVO.match(linha)
        if m_pub:
            pub_n, pub_nome, atual = int(m_pub.group(1)), m_pub.group(2).strip(), None
            continue
        if m_cri:
            atual = {"id": f"{m_cri.group(1)}.{m_cri.group(2)}",
                     "publico_n": int(m_cri.group(1)),
                     "publico": pub_nome if pub_n == int(m_cri.group(1)) else f"Publico {m_cri.group(1)}",
                     "angulo": m_cri.group(3).strip(), "alvo_s": int(m_cri.group(4)),
                     "preco": m_cri.group(5).lower() == "com", "copy": ""}
            criativos.append(atual)
            continue
        if atual is not None and linha.strip() and not linha.strip().startswith("---"):
            atual["copy"] = (atual["copy"] + " " + linha.strip()).strip()
        elif pub_n is None and linha.strip() and not criativos:
            linhas_produto.append(linha.strip())
    if not produto and linhas_produto:
        cand = [l for l in linhas_produto if len(l) < 80 and not l.endswith(":")]
        produto = cand[0] if cand else ""
    return {"produto": produto, "criativos": criativos, "ajustes": {}}


def validar(camp):
    """Lista de avisos (strings). Vazia = campanha dentro da regra."""
    av = []
    cri = camp.get("criativos") or []
    if not cri: return ["nenhum criativo encontrado"]
    ids = [c["id"] for c in cri]
    if len(set(ids)) != len(ids): av.append("ids repetidos: " + ", ".join(sorted({i for i in ids if ids.count(i) > 1})))
    por_pub = {}
    for c in cri:
        por_pub.setdefault(c["publico_n"], []).append(c)
        est = estimar_s(c["copy"])
        if abs(est - c["alvo_s"]) > max(4, c["alvo_s"] * 0.2):
            av.append(f"{c['id']}: copy estimada em {est}s para alvo de {c['alvo_s']}s ({palavras(c['copy'])} palavras)")
        if " ".join(_norm(CTA_FRASE)) not in " ".join(_norm(c["copy"])):
            av.append(f"{c['id']}: sem o CTA '{CTA_FRASE}'")
        fala_preco = "reais" in _norm(c["copy"])
        if c["preco"] and not fala_preco: av.append(f"{c['id']}: marcado COM preco mas a copy nao fala o preco")
        if not c["preco"] and fala_preco: av.append(f"{c['id']}: marcado SEM preco mas a copy fala 'reais'")
    for n, lst in sorted(por_pub.items()):
        cont = {k: 0 for k in CLASSES}
        for c in lst: cont[classe(c["alvo_s"])] += 1
        if len(lst) != 5: av.append(f"publico {n}: {len(lst)} criativos (regra: 5)")
        if cont != REGRA_POR_PUBLICO:
            av.append(f"publico {n}: duracoes {cont[20]}x20 {cont[30]}x30 {cont[40]}x40 (regra: 2x20 2x30 1x40)")
        np_ = sum(1 for c in lst if c["preco"])
        if np_ != PRECO_POR_PUBLICO: av.append(f"publico {n}: {np_} com preco (regra: {PRECO_POR_PUBLICO})")
    return av


def pasta(nome):
    return os.path.join(config.CAMPANHAS_DIR, config.slug(nome, 60))


def carregar(nome_ou_pasta):
    p = nome_ou_pasta if os.path.isdir(nome_ou_pasta) else pasta(nome_ou_pasta)
    camp = config.ler_json(os.path.join(p, "campanha.json"))
    if not camp: raise SystemExit(f"campanha nao encontrada: {p}\\campanha.json (rode `edt importar` antes)")
    camp["_pasta"] = p
    return camp


def importar(arquivo_txt, nome, produto=""):
    txt = io.open(arquivo_txt, encoding="utf-8").read()
    camp = importar_texto(txt, produto)
    p = pasta(nome)
    os.makedirs(p, exist_ok=True)
    antigo = config.ler_json(os.path.join(p, "campanha.json")) or {}
    camp["nome"] = nome
    camp["ajustes"] = antigo.get("ajustes") or {}        # ⛔ reimportar a copy nao apaga os ajustes da campanha
    if antigo.get("base"): camp["base"] = antigo["base"]
    config.escrever_json(os.path.join(p, "campanha.json"), camp)
    io.open(os.path.join(p, "copys.txt"), "w", encoding="utf-8").write(txt)
    return camp, p


def resumo(camp):
    linhas = []
    for c in camp["criativos"]:
        linhas.append(f"  {c['id']:<5} {c['publico'][:22]:<22} {c['angulo'][:34]:<34} alvo {c['alvo_s']:>2}s "
                      f"~{estimar_s(c['copy']):>4}s  {'R$' if c['preco'] else '  '}")
    return "\n".join(linhas)
