# editingtool

Editor automático de criativos para a operação de low ticket. Recebe **um vídeo base** e o
**mapa de ângulos** (25 copys) e devolve 25 vídeos **9:16** com:

- narração gerada pela **MiniMax** (voz padrão `Portuguese_ChattyGirl`);
- **legenda queimada** palavra a palavra, com a palavra falada em amarelo;
- cortes casados com a voz e zoom punch-in;
- **selo de preço** quando a copy fala o valor;
- **CTA "SAIBA MAIS"** com setas no fim;
- **SFX** do pool do time, escolhidos por palavra-chave e por corte;
- **música** da Meta Sound Collection escolhida pelo clima de cada ângulo;
- áudio normalizado em −14 LUFS.

Quem opera é o Claude Code: leia o [`CLAUDE.md`](CLAUDE.md), que é o motor. Detalhes técnicos estão em
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) e a regra das copys em [`docs/ANGULOS.md`](docs/ANGULOS.md).

## Instalação

```bash
pip install -r requirements.txt
```

1. Copie `.env.example` para `.env` e preencha `MINIMAX_API_KEY`.
2. Tenha o ffmpeg no PATH (ou indique-o em `FFMPEG` / `FFPROBE` no `.env`).
3. Baixe o pool de SFX com `python edt.py sfx sync` (vai para `sfx/pool/`, fora do git).
4. Coloque as faixas da Meta Sound Collection em `musica/biblioteca/`, com os nomes de
   `musica/catalogo.json`. Elas ficam fora do git porque a licença vale só nos apps da Meta.

## Motor de render

O padrão é o **Remotion**: legenda, título, selo e CTA animados. Ele precisa do Node.js, e a ferramenta instala o que precisa em `remotion/` sozinha na primeira vez. Em **Ajustes** dá para voltar ao motor original (ffmpeg), que é mais rápido.

## Interface

Dê dois cliques em `EditingTool.cmd` (ou rode `python edt.py painel`). A janela abre com o painel da campanha:
- produzir e parar;
- progresso;
- os criativos organizados por público.

Pela interface também dá para criar campanhas e ajustar voz, modelo, transições, música e SFX.

A aba **Mineração** garimpa ofertas de infoproduto escaladas na Europa pela API oficial da Biblioteca de Anúncios da Meta
(precisa do `META_TOKEN` no `.env`). A tabela traz a nota, o link da biblioteca, a landing, o alcance real na UE, os anúncios
com 15+ dias, os países e o "buraco" (francês ou alemão) de cada oferta. Pelo terminal: `python edt.py minerar`.

## Uso rápido

```bash
python edt.py importar campanhas/biblia-do-bebe/copys.txt --campanha biblia-do-bebe
python edt.py amostra biblia-do-bebe --base base.mp4 --id 1.1
python edt.py produzir biblia-do-bebe --base base.mp4 --workers 3
```

A saída fica em `campanhas/<nome>/saida/`:
- `_entregues/*.mp4`
- `player.html` (revisão)
- `relatorio.json`

Cada criativo tem também a própria pasta, com `plano.json` e `qa.json`.

## Créditos de terceiros

- **Emojis animados**: [Google Noto Animated Emoji](https://googlefonts.github.io/noto-emoji-animation/), licença CC BY 4.0, via `@remotion/animated-emoji`. Baixados sob demanda para `.cache/emojis`.
- **Câmera lenta por IA**: [rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) (MIT), modelo RIFE v4.6. Baixado na primeira vez para `.cache/ferramentas`.
- **Alinhamento fino da legenda**: modelo MMS_FA da Meta via `torchaudio` (alinhamento forçado wav2vec2 + CTC, a técnica do WhisperX).
