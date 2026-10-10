@echo off
REM Abre a interface do EditingTool (janela propria). Feche a janela preta para encerrar.
cd /d "%~dp0"
REM Atualiza a ferramenta e as mineracoes compartilhadas pelo time (so' avanca, nunca apaga nada local).
where git >/dev/null 2>/dev/null && (
  echo Atualizando o EditingTool...
  git pull --ff-only --quiet 2>/dev/null || echo Nao deu para atualizar agora: abrindo a versao que ja esta aqui.
)
python edt.py painel
