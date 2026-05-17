@echo off
REM =====================================================================
REM  AuroraVPN - Desactiver l'auto-connexion
REM  Lancez ce script si vous voulez reprendre la main sur les boutons.
REM =====================================================================

setlocal
cd /d "%~dp0"
title AuroraVPN - Reinitialisation

python -c "from config import UserConfig; c=UserConfig.load(); c.auto_connect_on_start=False; c.loopback_mode=False; c.save(); print('Auto-connexion desactivee. Mode loopback desactive.')"

echo.
echo Au prochain lancement, AuroraVPN attendra que vous cliquiez sur CONNECTER.
echo.
pause
exit /b 0
