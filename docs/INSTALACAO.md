# Instalar o EditingTool num PC novo (guia para o agente)

Você é um agente (Claude Code ou parecido) instalando o **EditingTool** no Windows de uma pessoa do time de
low ticket. A pessoa **não é técnica**: quem roda os comandos é você. Siga as etapas em ordem, confira cada
uma antes de passar para a próxima e, no fim, entregue a ferramenta aberta e funcionando.

- **Repositório:** https://github.com/Eduardo08GN/editingtool (público, branch `main`)
- **Dono da ferramenta:** Eduardo. A pessoa que você está ajudando é sócia dele.
- **O que a ferramenta faz:**
  - **criativos:** recebe um vídeo base e as copys e devolve criativos 9:16 prontos para a Meta, com legenda, voz MiniMax, SFX e música;
  - **aba Mineração:** garimpa ofertas de infoproduto escaladas na Europa pela Biblioteca de Anúncios da Meta.
- Depois de instalada, o manual de operação é o `CLAUDE.md` na raiz do repositório.

## Regras (valem do começo ao fim)

- ⛔ **Nunca** coloque chave ou token em commit, em log, em mensagem de chat ou na linha de comando. Eles moram só no
  arquivo `.env` da pasta da ferramenta, que já está no `.gitignore`.
- ⛔ **Não faça `git push`** nem commit no repositório: ele é do Eduardo. Aqui é só clonar e, depois, `git pull` para atualizar.
- ⛔ Antes de instalar programas (Git, Python, ffmpeg, Node), diga à pessoa o que vai instalar e espere o ok.
- Não mude código da ferramenta para "fazer funcionar". Se algo quebrar, pare e explique o erro à pessoa.

## Etapa 1 — Conferir o que já existe

Rode e anote o que falta:

```powershell
git --version
python --version      # precisa ser 3.10 ou mais novo (o Eduardo usa 3.12)
ffmpeg -version
node --version        # precisa ser 20 ou mais novo
```

Instale só o que faltar (com o ok da pessoa), pelo `winget`:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id Gyan.FFmpeg -e
winget install --id OpenJS.NodeJS.LTS -e
```

Depois de instalar, **abra um terminal novo**, para o PATH atualizar, e rode a conferência de novo.

- Se `python` abrir a Microsoft Store, use `py` no lugar de `python` em todos os comandos.
- O ffmpeg precisa responder no terminal. Se não responder, você vai indicar o caminho dele no `.env` na Etapa 4.

## Etapa 2 — Baixar a ferramenta

Use uma pasta **fora do OneDrive** e com caminho curto:

```powershell
git config --global core.longpaths true
cd $HOME
git clone https://github.com/Eduardo08GN/editingtool.git
cd editingtool
```

A pasta da ferramenta passa a ser `C:\Users\<usuario>\editingtool`. Daqui em diante, rode tudo de dentro dela.

## Etapa 3 — Dependências do Python

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Recomendado:** deixa a legenda mais precisa. Baixa uns 200 MB; se a internet for ruim, pode pular.

```powershell
python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**Pré-baixar o motor de render** (Remotion). A ferramenta faria isso sozinha no primeiro vídeo, mas assim já fica pronto:

```powershell
cd remotion; npm install; cd ..
```

O painel já vem compilado (`painel/dist`), então **não** precisa rodar `npm` dentro de `painel/`.

## Etapa 4 — Chaves no `.env`

```powershell
Copy-Item .env.example .env
```

Abra o `.env` no Bloco de Notas (`notepad .env`) e peça para a **pessoa colar** os valores. Ela mesma digita; você
não deve receber nem repetir a chave no chat.

| variável | para quê | de onde vem |
|---|---|---|
| `MINIMAX_API_KEY` | voz dos criativos | conta na MiniMax (https://platform.minimax.io → API Keys). O Eduardo diz se ela usa a conta dele ou uma própria. |
| `META_TOKEN` | aba Mineração | token próprio da pessoa. Veja os passos abaixo. |
| `FFMPEG` / `FFPROBE` | só se o ffmpeg não responder no terminal | caminho completo, ex.: `C:/ffmpeg/bin/ffmpeg.exe` |

**Como a pessoa gera o `META_TOKEN`:**
1. Confirmar a identidade em https://www.facebook.com/ID (exigência da Meta para usar a API da Biblioteca de Anúncios).
2. Em https://developers.facebook.com criar um app. O tipo "Outro"/"Business" serve.
3. Abrir o Graph API Explorer (https://developers.facebook.com/tools/explorer), escolher o app e gerar um **token de usuário**.
4. Esse token vence em poucas horas. Para durar uns 60 dias, use o Depurador de Token de Acesso
   (https://developers.facebook.com/tools/debug/accesstoken) e clique em "Estender token de acesso".
5. Colar o token estendido no `.env`, na linha `META_TOKEN=`.

Se a pessoa ainda não tiver o token, siga sem ele. Só a aba Mineração fica parada, e o resto funciona.

## Etapa 5 — SFX e músicas (ficam fora do git)

**SFX.** Baixa do Drive do time, cerca de 7 MB:

```powershell
python edt.py sfx sync
python edt.py sfx          # os liberados devem aparecer como "OK", sem "FALTA"
```

**Músicas** (Meta Sound Collection, 40 faixas, cerca de 16 MB):
- O Eduardo manda o arquivo **`musica-biblioteca.zip`**. Extraia o conteúdo em `musica\biblioteca\` (as 40 faixas direto nessa pasta, sem subpasta):
  ```powershell
  Expand-Archive -Path "<caminho>\musica-biblioteca.zip" -DestinationPath musica\biblioteca -Force
  (Get-ChildItem musica\biblioteca -File).Count      # deve dar 40
  ```
- Os nomes dos arquivos têm que bater com `musica/catalogo.json`. Não renomeie nada.
- ⛔ Não baixe música de outro lugar: a licença dessas faixas vale só nos apps da Meta, e a ferramenta escolhe a música pelo catálogo.

## Etapa 6 — Conferir e abrir

```powershell
python tests/test_basico.py          # todas as linhas devem começar com "OK"
python edt.py vozes --filtro portug  # lista vozes = a chave da MiniMax funciona
```

Abra a ferramenta com dois cliques em **`EditingTool.cmd`** ou com `python edt.py painel`. Ela abre uma janela própria do
Edge, e uma janela preta fica aberta atrás: é o servidor, e fechar a janela preta encerra a ferramenta.

Confira na janela:
- a barra lateral tem **Painel, Criativos, Nova campanha, Ajustes e Mineração**;
- embaixo, à esquerda, aparece "MiniMax conectada";
- na aba **Mineração**, se o `META_TOKEN` foi colado, o botão "Nova mineração" abre o formulário sem o aviso de token faltando.

Crie um atalho na Área de Trabalho, para a pessoa abrir sozinha depois:

```powershell
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\EditingTool.lnk")
$lnk.TargetPath = (Resolve-Path .\EditingTool.cmd).Path
$lnk.WorkingDirectory = (Get-Location).Path
$lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,115"
$lnk.Save()
```

**Teste opcional da Mineração** (só com token; leva alguns minutos e só lê dados):

```powershell
python edt.py minerar --mercados PT --max 100 --finalistas 5
```

## Etapa 7 — Explicar à pessoa (curto)

- **Abrir:** atalho "EditingTool" na Área de Trabalho. **Fechar:** fechar a janela preta.
- **Atualizar quando o Eduardo avisar:** feche a janela preta, rode `git pull` na pasta da ferramenta e abra de novo.
  Se a janela mostrar a versão antiga, aperte **Ctrl+F5**.
- **Para operar** (criar campanha, produzir criativos, minerar ofertas), basta pedir a um agente na pasta da ferramenta:
  ele lê o `CLAUDE.md` e conduz o resto.

## Problemas comuns

| sintoma | causa e solução |
|---|---|
| `ffmpeg` não encontrado | Abra um terminal novo depois de instalar. Se continuar, coloque `FFMPEG=` e `FFPROBE=` com o caminho completo no `.env`. |
| `No module named fastapi` (ou outro) | Rode de novo `python -m pip install -r requirements.txt` com o mesmo `python` que abre a ferramenta. |
| O painel abre sem a aba Mineração | Versão antiga em cache: aperte Ctrl+F5 na janela. Se continuar, rode `git pull` e confira o `git log -1`. |
| "Falta a chave da MiniMax" | `MINIMAX_API_KEY` vazia ou errada no `.env`. Feche a janela preta e abra a ferramenta de novo depois de corrigir. |
| A Mineração dá erro "code 190" | O token da Meta venceu. Gere outro (Etapa 4) e troque no `.env`. |
| A Mineração dá erro de identidade/permissão | A pessoa ainda não confirmou a identidade em facebook.com/ID. |
| A janela não abre | Rode `python edt.py painel` no terminal e abra no navegador o endereço que aparecer. |
| Erro de caminho longo no clone | `git config --global core.longpaths true` e clone de novo numa pasta curta, como `C:\editingtool`. |
