@echo off
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python niet gevonden. Installeer Python 3.11 of hoger.
    pause
    exit /b 1
)

if not exist "venv" (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Venv aanmaken mislukt.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Requirements installeren mislukt.
    pause
    exit /b 1
)

streamlit run src/main.py
if %errorlevel% neq 0 (
    echo Streamlit starten mislukt.
    pause
    exit /b 1
)

