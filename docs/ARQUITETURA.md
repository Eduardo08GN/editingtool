# Arquitetura

## Linha mestra

1. **Claude como orquestrador com um documento-motor.** A ideia veio do vídeo de referência sobre
   automação no estilo "engine". Nada aqui se conecta ao Higgsfield.
   - O `CLAUDE.md` é o motor: o Claude Code lê o arquivo e pergunta só o que falta.
   - Depois roda o pipeline inteiro sozinho.
2. **Engenharia herdada do `ow_agente`**, usado só para consulta (nada foi alterado lá):
   - ffmpeg numa passada só;
   - legenda em PNG (Pillow) sobreposta com `overlay enable=between`;
   - a grafia da copy aplicada sobre os tempos do whisper;
   - estado em disco idempotente;
   - um QA que avisa em vez de falhar calado.

## Pipeline de um criativo

```
copy (campanha.json)
  │  tts.narrar ─────────── MiniMax T2A v2 (speech-2.6-hd, Portuguese_ChattyGirl)
  │                           · cache por conteúdo (.cache/tts)
  │                           · ajusta a velocidade (0,9–1,2) se sair longe do tempo-alvo
  ▼
narracao.wav (48 kHz, sem silêncio nas pontas)
  │  alinhar.alinhar ────── faster-whisper small (palavra a palavra) + casar_texto (grafia da copy)
  ▼
palavras [(texto, t0, t1)]
  │  montagem.planejar ──── cartões de legenda (equilibrados, nunca atravessam frase)
  │                         cortes casados com o início dos cartões (1,6–3,4 s)
  │                         planos do vídeo base (rotação por semente + zoom punch-in)
  │                         selo de preço · CTA no "clique" · SFX por regra · música por perfil
  ▼
plano.json  (dados puros: dá para conferir sem renderizar)
  │  render.renderizar ──── 1 ffmpeg: planos → concat → legendas/selo/CTA (+ setas pulando)
  │                         áudio: voz + música (sidechain) + SFX (adelay) → loudnorm −14 LUFS
  ▼
final.mp4 (1080×1920, 30 fps, H.264 CRF 19, AAC 192k)  →  _entregues/  +  player.html
```

## Módulos

| arquivo | papel |
|---|---|
| `edt.py` | CLI |
| `editor/config.py` | `.env`; `config/padrao.json` mais os `ajustes` da campanha mais as variáveis `EDT_*`; `run()` do ffmpeg |
| `editor/campanha.py` | importa o mapa de ângulos (texto) e valida a regra 5×5 |
| `editor/tts.py` | MiniMax T2A v2 (com retry e cache), Kokoro local como reserva, lista de vozes |
| `editor/alinhar.py` | whisper (faster-whisper ou whisper.cpp) e `casar_texto` |
| `editor/legendas.py` | 11 estilos (o 11 LOWTICKET é o padrão), pílula CTA, seta, selo de preço |
| `editor/montagem.py` | análise do base (cortes de cena), cartões, linha do tempo, plano |
| `editor/sfx.py` | regras de SFX (abertura, gatilho por palavra, CTA, cortes) e sync do Drive |
| `editor/musica.py` | perfil emocional do criativo e escolha da faixa sem repetir no público |
| `editor/render.py` | o grafo do ffmpeg |
| `editor/lote.py` | orquestra a campanha: paralelo entre públicos, idempotente, QA |
| `editor/player.py` | página de revisão |

## Por que cada decisão

- **Plano separado do render:** dá para testar regras sem ffmpeg e refazer só o render.
- **`-ss/-t` por plano em vez de `split`:** a busca é rápida e o ffmpeg não guarda frames em memória.
- **Corte no início do cartão:** a troca de imagem acompanha a troca de frase, como numa edição feita à mão.
- **Último plano fixo no fim do base:** é onde costuma estar o "money shot" (o leque de cards).
- **Música em sequência dentro do público e em paralelo entre públicos:** o resultado é
  determinístico e 5 criativos do mesmo conjunto nunca repetem a faixa.
- **Selo de preço automático:** quando a voz diz "reais", o número anterior vira **SÓ R$ N**.
- **Loudnorm em −14 LUFS:** é o padrão de Reels e do feed, então nenhum criativo sai mais baixo que os outros.

## Pool de recursos (todos gratuitos)

| tipo | fonte | licença |
|---|---|---|
| SFX | Drive do time (`sfx/catalogo.json`): 16 liberados, 21 bloqueados (memes e marcas) | uso livre; bloqueados por risco no Rights Manager |
| música | Meta Sound Collection, 40 faixas instrumentais (`musica/catalogo.json`) | livre em apps da Meta, inclusive anúncios |
| fontes | Montserrat, Poppins, Anton, Bebas, Archivo, Luckiest Guy (`fontes/`) | OFL / Apache 2.0 |
| voz | MiniMax (pago); Kokoro-82M local, Apache 2.0, só para teste | — |
| transcrição | faster-whisper / whisper.cpp locais | MIT |

Para ampliar o pool: Pixabay (SFX e música, comercial sem crédito), Freesound **somente CC0**,
Mixkit, Kenney (CC0) e Sonniss GDC bundle. Evite BBC SFX (não comercial) e qualquer fonte que
exija crédito.
