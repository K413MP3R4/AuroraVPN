@echo off
REM =====================================================================
REM  AuroraVPN - Activation du demarrage automatique avec Windows
REM
REM  Cree un raccourci dans le dossier Demarrage de l'utilisateur courant.
REM  AuroraVPN se lancera (et se connectera, selon vos parametres) a chaque
REM  ouverture de session Windows.
REM
REM  Lancement standard, pas besoin d'Administrateur (raccourci utilisateur).
REM =====================================================================

setlocal
cd /d "%~dp0"
title AuroraVPN - Installation demarrage Windows

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
"$startup=[Environment]::GetFolderPath('Startup');" ^
"$shell=New-Object -ComObject WScript.Shell;" ^
"$lnk=$shell.CreateShortcut((Join-Path $startup 'AuroraVPN.lnk'));" ^
"$lnk.TargetPath=(Join-Path (Get-Location) 'AuroraVPN.bat');" ^
"$lnk.WorkingDirectory=(Get-Location).Path;" ^
"$iconPath=(Join-Path (Get-Location) 'assets\aurora.ico');" ^
"if (Test-Path $iconPath) { $lnk.IconLocation=$iconPath };" ^
"$lnk.WindowStyle=7;" ^
"$lnk.Description='AuroraVPN - lancement automatique';" ^
"$lnk.Save();" ^
"Write-Host 'Raccourci cree : ' (Join-Path $startup 'AuroraVPN.lnk')"

if errorlevel 1 (
    echo.
    echo [ERREUR] Creation du raccourci echouee.
    pause
    exit /b 1
)

echo.
echo === Demarrage automatique active ===
echo.
echo AuroraVPN se lancera a chaque ouverture de session Windows.
echo Pour le desactiver, lancez : Desinstaller_Demarrage_Windows.cmd
echo.
pause
exit /b 0
