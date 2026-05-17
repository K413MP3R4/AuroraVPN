@echo off
REM =====================================================================
REM  AuroraVPN - Launcher one-click "rien a faire"
REM  Double-cliquez sur ce fichier : l'app se lance et se connecte seule.
REM =====================================================================

setlocal
cd /d "%~dp0"
title AuroraVPN - Demarrage

REM ----- 1. Verifier Python -----
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERREUR] Python n'est pas installe ou pas dans le PATH.
    echo         Telechargez Python 3.10+ sur https://python.org
    echo         Cochez "Add python.exe to PATH" pendant l'installation.
    echo.
    pause
    exit /b 1
)

REM ----- 2. Installer les dependances si necessaire (premier lancement) -----
python -c "import customtkinter, PIL, pystray, plyer" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Premier lancement : installation des dependances...
    echo (Patientez 30-60 secondes, une seule fois.)
    echo.
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERREUR] Installation des dependances echouee.
        pause
        exit /b 1
    )
    echo.
    echo Dependances installees.
)

REM ----- 3. Pre-configurer pour auto-connexion zero-clic -----
REM Active : connexion automatique au demarrage + mode loopback (test
REM sans serveur distant) + reduction dans la zone de notification.
python -c "from config import UserConfig; c=UserConfig.load(); c.auto_connect_on_start=True; c.loopback_mode=True; c.minimize_to_tray=True; c.save(); print('Configuration : auto-connexion activee.')"

REM ----- 4. Lancer en arriere-plan (sans fenetre console) -----
where pythonw >nul 2>nul
if errorlevel 1 (
    echo Lancement avec python.exe (console visible).
    start "" python main.py
) else (
    echo Lancement silencieux avec pythonw.exe.
    start "" pythonw main.py
)

REM ----- 5. Termine -----
echo.
echo AuroraVPN se lance et se connectera automatiquement.
echo Vous pouvez fermer cette fenetre.
timeout /t 3 >nul
exit /b 0
