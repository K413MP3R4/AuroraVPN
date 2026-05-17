@echo off
REM =====================================================================
REM  AuroraVPN - Compilation en .exe Windows (avec UAC + icone)
REM  Sortie : dist\AuroraVPN.exe
REM =====================================================================

echo.
echo === AuroraVPN - Construction du paquet Windows ===
echo.

REM 1. Verifier Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python n'est pas dans le PATH.
    echo         Installez Python 3.10+ depuis https://python.org
    pause
    exit /b 1
)

REM 2. Installer les dependances
echo [1/4] Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERREUR] Echec installation dependances.
    pause
    exit /b 1
)

REM 3. Generer l'icone
echo.
echo [2/4] Generation de l'icone aurora.ico...
python make_icon.py
if errorlevel 1 (
    echo [AVERTISSEMENT] Generation icone echouee, on continue sans.
    set ICON_FLAG=
) else (
    set ICON_FLAG=--icon assets\aurora.ico
)

REM 4. Compilation PyInstaller (avec manifest UAC + icone)
echo.
echo [3/4] Compilation PyInstaller...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name AuroraVPN ^
    --manifest app.manifest ^
    --uac-admin ^
    --collect-all customtkinter ^
    --hidden-import=pystray._win32 ^
    --hidden-import=PIL ^
    %ICON_FLAG% ^
    main.py

if errorlevel 1 (
    echo [ERREUR] Compilation echouee.
    pause
    exit /b 1
)

REM 5. Termine
echo.
echo [4/4] Termine.
echo Executable genere : dist\AuroraVPN.exe
echo.
echo Note : au lancement, Windows demandera l'elevation UAC car
echo        l'application a besoin des privileges Administrateur
echo        pour gerer les tunnels VPN, le firewall et les DNS.
echo.
pause
