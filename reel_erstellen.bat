@echo off
setlocal
cd /d "%USERPROFILE%\rs-platform"

:: Neuesten Stand holen
git pull origin master --quiet

echo ============================================
echo  Instagram Reel erstellen
echo ============================================
echo.
set /p TICKER="Ticker eingeben (z.B. KLAC, MU, NVDA): "

:: Analyse pruefen
if not exist "analyses\%TICKER%.md" (
    echo.
    echo HINWEIS: Keine Analyse fuer %TICKER% gefunden.
    echo Bitte zuerst im Claude Code Chat eingeben:
    echo   Analysiere %TICKER%
    echo.
    pause
    exit /b 1
)

echo.
echo Generiere Slides + Cinematic Reel fuer %TICKER%...
echo (Pexels Stock-Footage + edge-tts Stimme aktiv)
echo.
python -m instagram.generate --analysis %TICKER%

echo.
echo ============================================
echo  Fertig! Output liegt unter:
echo  %USERPROFILE%\rs-platform\out\instagram\
echo ============================================
pause
