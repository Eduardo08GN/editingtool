# -*- coding: utf-8 -*-
"""Testes sem rede e sem ffmpeg:  python -m pytest tests  (ou: python tests/test_basico.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from editor import alinhar, campanha, legendas, montagem, musica, sfx

TXT = """Público 1 - Religioso (copys escolhidas)

1.1 Padre (20 s, sem preço)
Padre, quantas famílias saem da missa sem saber ensinar a fé aos filhos pequenos? Garanta o seu. Clique em saiba mais e confira.

1.2 Pastor (31 s, com preço)
Pastor, custa só dez reais.
Clique em saiba mais e confira.
"""


def test_importa_formato_do_time():
    c = campanha.importar_texto(TXT)
    assert [x["id"] for x in c["criativos"]] == ["1.1", "1.2"]
    assert c["criativos"][1]["preco"] and c["criativos"][1]["alvo_s"] == 31
    assert c["criativos"][1]["copy"].endswith("Clique em saiba mais e confira.")
    assert any("publico 1" in a for a in campanha.validar(c))       # so 2 criativos: avisa


def test_casar_texto_usa_grafia_da_copy():
    ouvidas = [("A", 0, .2), ("Bíblia", .2, .5), ("tem", .5, .7), ("70", .7, 1.0), ("cards", 1.0, 1.3)]
    pal, rel = alinhar.casar_texto(ouvidas, "A Bíblia tem setenta cards")
    assert [p[0] for p in pal] == ["A", "Bíblia", "tem", "setenta", "cards"]


def test_cartoes_equilibrados_sem_palavra_sozinha():
    ws = "você que conduz o batismo ou a apresentação de bebês ouve esse compromisso o tempo todo:".split()
    pal = [(w, i * .3, i * .3 + .25) for i, w in enumerate(ws)]
    tam = [len(c["palavras"]) for c in montagem.cartoes(pal, 3)]
    assert sum(tam) == len(ws) and min(tam) >= 2 and max(tam) <= 3


def test_preco_vira_selo():
    pal = [("custa", 0, .3), ("só", .3, .5), ("dez", .5, .7), ("reais.", .7, 1.0)]
    assert montagem.momento_preco(pal, {"gatilho": "reais"})[1] == "SÓ R$ 10"


def test_cta_e_destaque():
    pal = [("Garanta", 0, .3), ("o", .3, .4), ("seu.", .4, .6), ("Clique", .7, 1), ("em", 1, 1.1)]
    assert sfx.indice_cta(pal) == 3
    assert legendas.papel(["A", "B", "C"], 1, None, legendas.estilo(11)) == ["base", "realce", "base"]


def test_perfil_de_musica():
    assert musica.perfil({"angulo": "Padre", "publico": "Religioso", "copy": ""}) == "fe_emocional"
    assert musica.perfil({"angulo": "Rodinha", "publico": "Professoras", "copy": "turma"}) == "brincar_alegre"




def test_ajuste_de_velocidade_nao_linear():
    """MiniMax: dur ~ 1/speed^2.4 (medido). O ajuste tem de chegar perto do alvo sem passar do ponto."""
    from editor import tts
    natural = {"x": 24.22}
    chamadas = []
    original = tts.sintetizar
    tts.sintetizar = lambda texto, saida, cfg, v=None: (chamadas.append(v), natural["x"] / (float(v) ** 2.4))[1]
    try:
        cfg = {"velocidade": 1.0, "ajustar_duracao": True, "tolerancia_s": 1.5, "velocidade_min": 0.9, "velocidade_max": 1.2}
        r = tts.narrar("copy", 20, "x.wav", cfg)
        assert abs(r["duracao"] - 20) <= 1.5, r
        natural["x"] = 27.2; chamadas.clear()
        r = tts.narrar("copy", 30, "x.wav", cfg)
        assert abs(r["duracao"] - 30) <= 1.5 and r["velocidade"] < 1.0, r
    finally:
        tts.sintetizar = original


def test_razao_em_texto_longo():
    """Regressao: autojunk do difflib derrubava a razao em copy longa (>200 caracteres)."""
    copy = ("Paizão, você trabalha o dia inteiro e sente que não consegue ensinar sobre Deus aos seus filhos? "
            "A Bíblia do Bebê ajuda nisso em cinco minutinhos por noite: um card, uma passagem da Bíblia curtinha "
            "e uma brincadeira pra fazer juntos. Garante o seu. Clique em saiba mais e confira.")
    ouvido = copy.replace("Paizão", "Paisão").replace("cinco", "5")
    ouvidas = [(w, i * .3, i * .3 + .25) for i, w in enumerate(ouvido.split())]
    _, rel = alinhar.casar_texto(ouvidas, copy)
    assert rel["razao"] > 0.9, rel


def test_afinar_sfx_na_escala():
    """Pop afinado no tom da musica: cai numa nota da escala, nunca mais de meia oitava de distancia."""
    import math
    from editor import sfx
    for tom in [(0, "maior"), (9, "menor"), (5, "maior")]:
        for f0 in (180.0, 440.0, 753.7, 2304.1):
            for grau in (0, 1, 2):
                s = sfx.semitons_para_escala(f0, tom, grau)
                assert -6 <= s <= 6, (f0, tom, grau, s)
                nota = round(12 * math.log2(f0 / 261.63) + s - tom[0]) % 12
                assert nota in sfx.ESCALA[tom[1]], (f0, tom, grau, nota)
    assert sfx.semitons_para_escala(0, (0, "maior")) == 0.0 and sfx.semitons_para_escala(440, None) == 0.0


def test_cta_aceita_clica():
    """Copy do time fecha com "Clica no botao aqui embaixo": o CTA precisa ser achado (fecho e SFX)."""
    from editor import sfx
    pal = [("Garante", 0, 1), ("Clica", 1, 2), ("no", 2, 3), ("botão", 3, 4)]
    assert sfx.indice_cta(pal) == 1 and sfx.indice_cta(pal, "clique") == 1
    assert sfx.indice_cta([("clicar", 0, 1)]) is None

# ── mineracao (sem rede) ──────────────────────────────────────────────────────
def _ad(i, pid, dom, dias, alcance, corpo, termo="à imprimer", mercado="FR"):
    import datetime
    ini = (datetime.date(2026, 10, 9) - datetime.timedelta(days=dias)).isoformat()
    return {"id": str(i), "page_id": pid, "page_name": f"pag {pid}", "ad_delivery_start_time": ini, "eu_total_reach": alcance,
            "ad_creative_bodies": [corpo], "ad_creative_link_titles": ["Kit"], "ad_creative_link_captions": [dom],
            "languages": ["fr"], "_termo": termo, "_mercado": mercado}


def test_mineracao_agrupa_por_landing_e_filtra():
    import datetime
    from editor import mineracao
    hoje = datetime.date(2026, 10, 9)
    ads = [_ad(i, "1", "kit.com", 20 if i < 3 else 3, 1000, "PDF à imprimer, accès immédiat") for i in range(5)]
    ads += [_ad(10 + i, "2", "www.Creme.fr", 30, 9000, "Crème anti-âge, livraison offerte") for i in range(4)]
    ads += [_ad(20 + i, "3", "maigrir.fr", 30, 9000, "PDF pour maigrir de 10 kilos") for i in range(4)]
    g = mineracao.agrupar(ads, hoje)
    assert set(g) == {"kit.com", "creme.fr", "maigrir.fr"}           # dominio normalizado (sem www, minusculo)
    assert g["kit.com"]["n15"] == 3 and g["kit.com"]["alc"] == 5000 and g["kit.com"]["alc_novo"] == 2000
    cands = mineracao.candidatos(g)
    assert [c["chave"] for c in cands] == ["kit.com"]                 # fisico e proibido saem


def test_mineracao_buraco_e_nota():
    from editor import mineracao
    pag = {"paises_pct": {"ES": 87, "PT": 4, "FR": 1}, "idiomas": {"es": 100}}
    pres = mineracao.presenca(pag)
    assert pres == {"FR": 1, "DE": 0}
    base = {"alcance_ue": 500_000, "anuncios_15d": 40, "presenca": pres, "buraco": ["FR", "DE"], "digital": 1.0, "bandeiras": []}
    alta = mineracao.nota(base)
    assert alta >= 8
    assert mineracao.nota({**base, "bandeiras": ["isca"]}) <= alta - 4     # isca gratis derruba
    assert mineracao.nota({**base, "buraco": [], "presenca": {"FR": 60, "DE": 40}}) < alta


if __name__ == "__main__":  # noqa
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("OK", n)
