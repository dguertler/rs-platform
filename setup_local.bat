@echo off
setlocal

set REPO_URL=https://github.com/dguertler/rs-platform.git
set TARGET_DIR=%USERPROFILE%\rs-platform

echo ============================================
echo  RS-Platform Setup
echo ============================================

:: Pruefen ob git vorhanden
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Git ist nicht installiert.
    echo Download: https://git-scm.com/download/win
    pause
    exit /b 1
)

:: Pruefen ob Python vorhanden
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Python ist nicht installiert.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Repo klonen oder aktualisieren
if exist "%TARGET_DIR%\.git" (
    echo Repo gefunden — aktualisiere auf neuesten Stand...
    cd /d "%TARGET_DIR%"
    git pull origin master
) else (
    echo Klone Repo nach %TARGET_DIR%...
    git clone %REPO_URL% "%TARGET_DIR%"
    cd /d "%TARGET_DIR%"
)

:: Python-Abhaengigkeiten installieren
echo.
echo Installiere Python-Abhaengigkeiten...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt -r instagram/requirements.txt

:: Pexels API Key abfragen
echo.
echo ============================================
echo  Pexels API Key (fuer Stock-Footage)
echo  Leer lassen = ueberspringen
echo ============================================
set /p PEXELS_KEY="Pexels API Key eingeben: "

if not "%PEXELS_KEY%"=="" (
    :: Key dauerhaft als User-Umgebungsvariable setzen
    setx PEXELS_API_KEY "%PEXELS_KEY%" >nul
    echo Pexels API Key gesetzt.
)

echo.
echo ============================================
echo  Fertig! Repo liegt unter:
echo  %TARGET_DIR%
echo.
echo  Analyse erstellen (Beispiel):
echo  cd %TARGET_DIR%
echo  python -m instagram.generate --analysis KLAC
echo ============================================
pause
