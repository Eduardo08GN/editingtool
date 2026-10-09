# editingtool — o MOTOR. Leia isto primeiro.

Você é o operador desta ferramenta para o time de low ticket. A pessoa entrega **um vídeo base**
e **o mapa de ângulos** (ou só o produto e os públicos). Você faz o resto e devolve 20+
criativos 9:16 prontos para subir na Meta, com legenda queimada, voz MiniMax, SFX e música.
A pessoa não é técnica: quem roda comando é você.

## O fluxo (siga nesta ordem)

1. **Pergunte só o que falta**, de uma vez:
   - produto e preço (ex.: "Bíblia do Bebê: 70 Cards Lúdicos", R$ 10);
   - o vídeo base (caminho do .mp4). Ele deve vir limpo: sem legenda e sem narração;
   - o mapa de ângulos pronto **ou** os públicos para você escrever as copys.
2. **Copys**: se a pessoa não mandou, escreva seguindo `docs/ANGULOS.md` (regra 5×5, tempos,
   preço, CTA). Salve em `campanhas/<nome>/copys.txt` no MESMO formato do exemplo
   `campanhas/biblia-do-bebe/copys.txt`.
3. **Importe e valide**:
   `python edt.py importar campanhas/<nome>/copys.txt --campanha <nome> --produto "..."`
   Se aparecer aviso de REGRA, corrija a copy (ou mostre à pessoa) antes de gastar TTS.
4. **Amostra antes do lote**: renderize 1 criativo e mostre à pessoa (SendUserFile, display render):
   `python edt.py amostra <nome> --base <video.mp4> --id 1.1`
5. **Lote**: com o ok, produza tudo:
   `python edt.py produzir <nome> --base <video.mp4> --workers 3`
6. **Entrega**: mande `campanhas/<nome>/saida/player.html` (grade por público, com avisos de QA)
   e diga onde estão os MP4: `campanhas/<nome>/saida/_entregues/`.
   Se algum criativo tiver aviso (fala divergente, CTA não ouvido, duração fora), mostre-o.

## A interface (o jeito normal de operar)

Dois cliques em **`EditingTool.cmd`** (ou `python edt.py painel`) abre a janela:
**Painel** (produzir/parar, progresso, atividade, criativos por publico) · **Criativos** (filtros,
player, refazer um so') · **Nova campanha** (colar o mapa de angulos, escolher a pasta de clipes) ·
**Ajustes** da campanha (voz, modelo 1/2/alternar, estilo de transicao, musica, SFX) · **Mineracao**
(garimpa ofertas de infoproduto escaladas na Europa; veja a secao abaixo).
Codigo: `editor/servidor.py` (FastAPI, so' 127.0.0.1, senha por sessao) + `painel/` (React/Vite;
`npm run build` gera `painel/dist`, que vai no git para ninguem precisar de Node).

## Motor de render (Ajustes → "Motor de render")

- **Remotion** (padrao desde 2026-10-03, o operador achou "bem melhor"): legenda com a palavra falada
  pulando, titulo/selo/CTA animados com mola, transicoes cartoon. `remotion/` (Node; a ferramenta roda
  `npm install` sozinha na primeira vez). ~2-3 min por criativo.
- **Atual (ffmpeg)**: o original, ~1 min por criativo.
Os dois leem o MESMO `plano.json` (cortes, voz, musica, SFX). Licenca do Remotion: gratis ate' 3 pessoas
no time; acima disso, plano "Automators" (US$ 0,01/render, minimo US$ 100/mes).

## Mineracao de ofertas (aba Mineracao)

Antes do criativo vem a oferta. A aba **Mineracao** garimpa, pela API oficial da Biblioteca de Anuncios da Meta,
ofertas de infoproduto **escaladas** num idioma e **ausentes em frances/alemao** (o "buraco"), para o time recriar a €10.
Codigo: `editor/mineracao.py` · termos: `config/mineracao.json` (cada termo com a traducao em portugues e a camada) ·
dados: `mineracao/rodadas/<id>/` (fora do git) · decisoes do operador: `mineracao/decisoes.json` (por dominio, valem em todas as rodadas).

- **Escala = alcance real na UE** (`eu_total_reach`, pessoas), somado por landing; nao o numero de anuncios.
- **Termos de direct response**, nao de nicho: prova de escala ("déjà plus de", "bereits über"), mecanismo unico
  ("astuce de 10 secondes", "Oma-Trick", "la bible du"), entrega digital, funil (quiz/VSL), chamada de publico, sazonal.
- **Portugal (PT) e' a vitrine dos operadores brasileiros dentro da UE**: a API mostra o alcance deles.
- Etapas (rodar de novo retoma): coleta → grupos por landing → medicao da pagina inteira (top N, alcance por pais)
  → landing (so' GET, nunca preenche nada) → ranking com nota 0-10 e bandeiras (Escalando, Novo, Operador BR,
  Isca gratis, Assinatura/app, Fisico?, Ticket alto).
- Nota = escala 40% + persistencia (anuncios 15+ dias) 20% + buraco FR/DE 25% + cara de digital 15%, menos as bandeiras.
  E' triagem: o operador abre biblioteca e landing (botoes da tabela, abrem no navegador padrao) e aprova/descarta.
- **Painel:** "Nova mineracao" mostra os termos por mercado e camada (liga/desliga, com a traducao) e aceita termos
  digitados (ficam em `mineracao/termos_extras.json`) · "Importar planilha" traz o `dados-*.js` da Planilha de Ofertas
  do socio (cada oferta e' medida na API; nota/nicho/concorrentes da planilha ficam) · "Todas as rodadas" junta tudo
  por dominio · lixeira exclui uma rodada (com confirmacao; as decisoes ficam).
- ⛔ A API so' devolve anuncio comercial veiculado na UE/Reino Unido. Oferta que roda so' no Brasil/EUA nao aparece.
- ⛔ `META_TOKEN` mora no `.env` (nunca em log, tela, commit ou linha de comando). Token vencido = erro "code 190": troque no `.env`.

## Onde ficam os videos

`campanhas/<nome>/saida/_entregues/P<n>-<publico>/<id>-<angulo>/P<n>_<id>_<angulo>_<dur>s.mp4`
— uma pasta por angulo; variacoes futuras do mesmo angulo caem nela.

## Comandos

| para quê | comando |
|---|---|
| importar mapa de ângulos | `python edt.py importar <txt> --campanha <nome>` |
| conferir a regra | `python edt.py validar <nome>` |
| 1 criativo | `python edt.py amostra <nome> --base <mp4> --id 2.3` |
| vários / todos | `python edt.py produzir <nome> --base <mp4> [--so 1.1,2.3] [--workers 3]` |
| ver a música que cada um usaria | `python edt.py musica <nome>` |
| listar vozes MiniMax | `python edt.py vozes --filtro portug` |
| estado do pool de SFX / baixar do Drive | `python edt.py sfx` / `python edt.py sfx sync` |
| refazer o player | `python edt.py player <nome>` |
| achar a voz MiniMax mais parecida com um vídeo | `python ferramentas/voz_parecida.py <video_ou_audio>` |
| garimpar ofertas (FR, DE e Portugal) | `python edt.py minerar [--mercados FR,DE,PT] [--finalistas 40]` |
| retomar uma rodada / refazer a análise | `python edt.py minerar --rodada <id>` |
| importar a planilha de garimpo do sócio | `python edt.py minerar --importar-planilha <dados-frances.js> [--nome "..."]` |

Base com texto queimado (só em emergência): `--borrar-faixa 0.63:0.80` borra a faixa;
`--janela 0:33` usa só esse trecho do base (ex.: para fugir de um CTA antigo no fim).

## Regras que não se quebram

- ⛔ **A copy é sagrada.** O texto da campanha vai literal para o TTS e para a legenda. Não
  "melhore" copy aprovada; se achar erro, pergunte.
- ⛔ **Áudio do base nunca entra.** O base pode ter fala de outro criativo.
- ⛔ **SFX só do pool liberado** (`sfx/catalogo.json`, `liberado: true`). Meme de filme/jogo/marca
  fica bloqueado: o Rights Manager da Meta derruba o anúncio.
- ⛔ **Música só da biblioteca** (`musica/`, Meta Sound Collection): livre em FB/IG, inclusive
  em anúncio, e **somente** na Meta. Criativo para TikTok/YouTube precisa de outra trilha.
- ⛔ **Nunca** comite `.env` (chave MiniMax e token da Meta), vídeos, áudios, `campanhas/*/saida/` ou `mineracao/`.
- A voz padrão é `Portuguese_ChattyGirl` (`config/padrao.json` → `tts.voz`). Trocar por
  campanha: bloco `ajustes` do `campanha.json` (ex.: `{"tts": {"voz": "..."}}`).
- Mudou copy, voz, base ou config? Rode de novo: o lote refaz só o que mudou.
