@echo off
cd /d "%~dp0backend"
echo RS Platform Backend starten...
echo.
pip install -r requirements.txt -q
echo.
echo Backend laeuft auf: http://localhost:8000
echo App oeffnen:        http://localhost:8000
echo API-Doku:           http://localhost:8000/docs
echo.
echo CTRL+C zum Beenden.
echo.
uvicorn main:app --reload --host 127.0.0.1 --port 8000
