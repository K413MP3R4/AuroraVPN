# =====================================================================
#  AuroraVPN - Provisionnement IKEv2 natif Windows (PowerShell)
#  Lancer en tant qu'Administrateur :
#    Set-ExecutionPolicy -Scope Process Bypass
#    .\ikev2_setup.ps1
# =====================================================================

param(
    [string]$ConnectionName  = "AuroraVPN",
    [string]$ServerAddress   = "vpn-fr-par-01.aurora.example.com",
    [ValidateSet("MachineCertificate","Eap","Pap")]
    [string]$AuthMethod      = "MachineCertificate",
    [bool]  $SplitTunnel     = $false
)

Write-Host "=== AuroraVPN - Configuration IPsec/IKEv2 ===" -ForegroundColor Cyan

# 1. Supprimer l'eventuelle connexion existante
$existing = Get-VpnConnection -Name $ConnectionName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Suppression de la connexion existante..." -ForegroundColor Yellow
    Remove-VpnConnection -Name $ConnectionName -Force
}

# 2. Creation de la connexion VPN
Write-Host "Creation de la connexion '$ConnectionName' vers $ServerAddress..." `
    -ForegroundColor Green

Add-VpnConnection `
    -Name                  $ConnectionName `
    -ServerAddress         $ServerAddress `
    -TunnelType            IKEv2 `
    -EncryptionLevel       Required `
    -AuthenticationMethod  $AuthMethod `
    -SplitTunneling        $SplitTunnel `
    -RememberCredential    $false `
    -PassThru | Out-Null

# 3. Application de la suite cryptographique (AES-GCM-256, ECP-384, PFS)
Write-Host "Application de la suite cryptographique forte..." -ForegroundColor Green

Set-VpnConnectionIPsecConfiguration `
    -ConnectionName                    $ConnectionName `
    -AuthenticationTransformConstants  GCMAES256 `
    -CipherTransformConstants          GCMAES256 `
    -EncryptionMethod                  GCMAES256 `
    -IntegrityCheckMethod              SHA384 `
    -DHGroup                           ECP384 `
    -PfsGroup                          ECP384 `
    -Force

# 4. Test de connexion immediate
Write-Host ""
Write-Host "Connexion en cours..." -ForegroundColor Cyan
rasdial $ConnectionName

# 5. Verifications
$state = (Get-VpnConnection -Name $ConnectionName).ConnectionStatus
Write-Host ""
Write-Host "Statut : $state" -ForegroundColor $(if ($state -eq "Connected") {"Green"} else {"Red"})

if ($state -eq "Connected") {
    Write-Host "Adresse IP publique :" -ForegroundColor Cyan
    Invoke-RestMethod -Uri "https://api.ipify.org?format=json"
}
