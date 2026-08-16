@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Gadget Terminal - サイトを更新して公開
echo ============================================
echo.
set "MSG="
set /p MSG="変更内容のメモ (何も入れずEnterでもOK): "
if "%MSG%"=="" set "MSG=更新"
echo.
echo [1/4] 変更をまとめています...
git add .
echo [2/4] 記録しています...
git commit -m "%MSG%"
echo [3/4] GitHub側の変更を取り込んでいます...
git pull --rebase
echo [4/4] 送信しています...
git push
echo.
if errorlevel 1 (
  echo ********************************************
  echo   エラーが出ました。
  echo   この画面をコピーして Claude に貼ってください。
  echo ********************************************
) else (
  echo ============================================
  echo   完了しました。
  echo   3分ほどで https://gadgetterminal.com/ に反映されます。
  echo ============================================
)
echo.
pause
