@echo off
REM =====================================================================
REM  AuroraVPN - Desactivation du demarrage automatique avec Windows
REM
REM  Supprime le raccourci AuroraVPN.lnk du dossier Demarrage utilisateur.
REM =====================================================================

setlocal
title AuroraVPN - Desinstallation demarrage Windows

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
"$shortcut=Join-Path ([Environment]::GetFolderPath('Startup')) 'AuroraVPN.lnk';" ^
"if (Test-Path -LiteralPath $shortcut) { Remove-Item -LiteralPath $shortcut -Force; Write-Host 'Raccourci supprime.' } else { Write-Host 'Aucun raccourci de demarrage trouve.' }"

echo.
echo AuroraVPN ne demarrera plus automatiquement avec Windows.
echo.
pause
exit /b 0
