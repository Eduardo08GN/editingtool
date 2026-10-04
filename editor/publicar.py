# -*- coding: utf-8 -*-
"""PUBLICAR — manda os criativos entregues para o repositorio do time no GitHub.

    python edt.py publicar <campanha> [--repo URL] [--pasta "caminho/dentro/do/repo"]

⭐ Organizacao: a do TIME. Em 2026-10-04 o Lucas reorganizou o repo low-ticket na estrutura PLANA
   (uma pasta por publico, sem pasta por angulo) e a ferramenta, sem saber, recriou as pastas por angulo
   e duplicou tudo. Padrao agora ("estrutura" no campanha.json):
     plana      <pasta>/Publico 2 - Mães e avós/Publico 2 - Avó, legado 26seg.mp4
     por_angulo <pasta>/Publico 2 - Mães e avós/2.4 - Avó, legado/Publico 2 - Avó, legado 26seg.mp4
   A versao nova de um angulo SUBSTITUI a anterior (mesmo publico e angulo, qualquer duracao).
⛔ No fim do lote publica SO' os criativos daquele lote (`ids`): o que o time apagou do repo nao volta.
⭐ Clone esparso e parcial em .cache/publicar/: so' a pasta de destino e' baixada (o repo do time
   tem PDFs, paginas e audios que a ferramenta nao precisa).
⛔ So' toca arquivos DENTRO das pastas de angulo que ela mesma cria. O resto do repo (inclusive
   videos que o time colocou a mao em <pasta>/) fica intacto.
⛔ Repo e pasta ficam gravados no campanha.json ("publicar"): a proxima vez e' so' o comando.
"""
import os, re, shutil, subprocess

from . import campanha as _camp, config

PROIBIDO = re.compile(r'[<>:"/\\|?*]+')


def _nome(t):
    return PROIBIDO.sub("-", (t or "").strip()).strip(" .-") or "sem-nome"


def _git(args, cwd, log=None):
    r = config.run(["git"] + args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} falhou: {(r.stderr or r.stdout).strip()[-600:]}")
    return r.stdout.strip()


def destino_relativo(cri, segundos, estrutura="plana"):
    pub = f"Publico {cri['publico_n']} - {_nome(cri['publico'])}"
    arq = f"Publico {cri['publico_n']} - {_nome(cri['angulo'])} {int(round(segundos))}seg.mp4"
    if estrutura == "por_angulo":
        return os.path.join(pub, f"{cri['id']} - {_nome(cri['angulo'])}"), arq
    return pub, arq


def _versoes_antigas(pasta, cri, novo):
    """Arquivos do MESMO publico e angulo (qualquer duracao) na pasta, exceto o novo."""
    rx = re.compile(rf"^Publico {cri['publico_n']} - {re.escape(_nome(cri['angulo']))} \d+seg\.mp4$", re.I)
    return [n for n in (os.listdir(pasta) if os.path.isdir(pasta) else []) if rx.match(n) and n != novo]


def publicar(nome, repo=None, pasta=None, log=print, ids=None):
    camp = _camp.carregar(nome)
    arq_camp = os.path.join(camp["_pasta"], "campanha.json")
    salvo = config.ler_json(arq_camp)
    pub = dict(salvo.get("publicar") or {})
    if repo: pub["repo"] = repo
    if pasta: pub["pasta"] = pasta
    pub.setdefault("estrutura", "plana")
    if not pub.get("repo") or not pub.get("pasta"):
        raise SystemExit("diga o repo e a pasta na primeira vez: --repo <url> --pasta \"pasta/dentro/do/repo\"")
    salvo["publicar"] = pub; config.escrever_json(arq_camp, salvo)

    url = pub["repo"].rstrip("/")
    if not url.endswith(".git"): url += ".git"
    m = re.search(r"github\.com[/:]([^/]+)/([^/.]+)", url)
    clone = os.path.join(config.CACHE_DIR, "publicar", f"{m.group(1)}-{m.group(2)}" if m else config.slug(url))
    alvo_rel = pub["pasta"].replace("\\", "/").strip("/")

    if not os.path.isdir(os.path.join(clone, ".git")):
        os.makedirs(os.path.dirname(clone), exist_ok=True)
        log(f"publicar: clonando {url} (so' a pasta de destino)")
        _git(["clone", "--filter=blob:none", "--sparse", url, clone], cwd=os.path.dirname(clone))
    # ⛔ 2026-10-03: o caminho de "2.3 - Mãe, ensinar a fé desde cedo/..." passou de 260 caracteres e o git
    #    do Windows recusou o arquivo ("Filename too long"). Caminho longo liga no clone da ferramenta.
    _git(["config", "core.longpaths", "true"], cwd=clone)
    _git(["sparse-checkout", "set", "--no-cone", f"/{alvo_rel}/"], cwd=clone)
    ramo = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=clone)
    _git(["pull", "--ff-only", "origin", ramo], cwd=clone)

    base = os.path.join(clone, *alvo_rel.split("/"))
    enviados = []
    for cri in camp["criativos"]:
        if ids is not None and cri["id"] not in ids: continue
        pasta_cri = os.path.join(camp["_pasta"], "saida", f"{cri['id']}-{config.slug(cri['angulo'], 30)}")
        qa = config.ler_json(os.path.join(pasta_cri, "qa.json")) or {}
        origem = qa.get("entregue")
        if not origem or not os.path.exists(origem): continue
        sub, arq = destino_relativo(cri, qa.get("duracao") or 0, pub["estrutura"])
        d = os.path.join(base, sub)
        os.makedirs(d, exist_ok=True)
        for velho in _versoes_antigas(d, cri, arq):  # a versao nova do angulo substitui a anterior
            os.remove(os.path.join(d, velho))
        dest = os.path.join(d, arq)
        if not (os.path.exists(dest) and os.path.getsize(dest) == os.path.getsize(origem)):
            shutil.copyfile(origem, dest)
        enviados.append(os.path.join(sub, arq))

    if not enviados: raise SystemExit("nenhum criativo entregue para publicar")
    _git(["add", "--all", "--", alvo_rel], cwd=clone)
    mudou = _git(["status", "--porcelain", "--", alvo_rel], cwd=clone)
    if not mudou:
        log("publicar: o repo ja' tem estes videos — nada para enviar")
        return {"enviados": 0, "total": len(enviados), "repo": pub["repo"], "pasta": alvo_rel}
    n = len([l for l in mudou.splitlines() if l.strip()])
    quais = "" if ids is None else " (" + ", ".join(sorted(ids)) + ")"
    msg = (f"Criativos {camp.get('produto') or nome}: {len(enviados)} video(s){quais} (EditingTool)\n\n"
           "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    _git(["commit", "-m", msg], cwd=clone)
    log(f"publicar: enviando {n} alteracao(oes) para o GitHub")
    _git(["push", "origin", ramo], cwd=clone)
    sha = _git(["rev-parse", "--short", "HEAD"], cwd=clone)
    log(f"publicar: OK — {len(enviados)} videos em {alvo_rel} (commit {sha})")
    return {"enviados": n, "total": len(enviados), "commit": sha, "repo": pub["repo"], "pasta": alvo_rel}
