# AuroraVPN — v4

> **Tu débutes ?** Commence par `GUIDE_DEBUTANT.md` — tout est expliqué
> pas à pas, avec les commandes prêtes à copier-coller.
>
> **Pour un vrai serveur VPN, trois guides selon ton budget** :
> - `DEPLOIEMENT_SANS_CARTE.md` — **0 €, AUCUNE carte bancaire** (auto-hébergement
>   Pi/PC, ProtonVPN Free, Tailscale)
> - `DEPLOIEMENT_GRATUIT.md` — gratuit avec carte (Oracle Cloud Always Free,
>   crédits trial)
> - `DEPLOIEMENT_SERVEUR.md` — payant (Hetzner ~4 €/mois, OVH, DigitalOcean)
>
> **Au premier lancement** de `AuroraVPN.bat`, un **assistant de configuration**
> s'ouvre et te guide en 3 clics : ProtonVPN Free / import d'un .conf existant /
> créer son propre serveur. Tu peux le rouvrir n'importe quand avec le
> bouton **?** dans l'en-tête de la fenêtre principale.

Logiciel VPN moderne pour Windows : interface compacte sombre violet/cyan,
moteur multi-protocoles (IPsec/IKEv2, WireGuard, OpenVPN), kill switch,
DNS chiffré, anti-fuite IPv6/WebRTC, sélection automatique du protocole,
**system tray**, **persistance des préférences**, et **mode VPN réel**
opt-in avec élévation UAC automatique.

> Inspiré de l'ergonomie d'un dashboard VPN premium, sans copier la marque
> ni le logo d'aucun produit existant.

---

## Lancement rapide

### Pré-requis

- Windows 10 (1809+) ou Windows 11
- Python 3.10 ou supérieur (https://python.org)
- Droits administrateur **uniquement** pour le mode VPN réel
  (kill switch firewall, configuration RAS, IPsec, DNS, IPv6)

### Installation et lancement (mode démo)

Dans le dossier `D:\Claude Code\AuroraVPN` :

```bat
python -m pip install -r requirements.txt
python main.py
```

Aucune élévation requise en démo — l'UI est entièrement testable sans
toucher au système.

### Compilation en exécutable Windows

```bat
build_windows.bat
```

Génère `dist\AuroraVPN.exe` (~40-60 Mo, autonome). Le binaire embarque le
manifeste UAC `requireAdministrator` : Windows demandera l'élévation au
premier lancement.

---

## Architecture

```
AuroraVPN/
|-- main.py              # UI + Dashboard + raccourcis clavier + tray + i18n
|-- vpn_engine.py        # Moteur + backends WG / IKEv2 / OpenVPN / Loopback
|-- security.py          # Kill switch (arm/disarm safe), DNS, IPv6, leak monitor
|-- config.py            # Persistance JSON (%APPDATA%\AuroraVPN)
|-- utils.py             # IP publique, ping, single-instance, logs, UAC
|-- features.py          # Multi-hop, Tor over VPN, Threat Protection,
|                        # LeakTester, VpnAccelerator, Notifier
|-- widgets_extra.py     # WorldMap, SpeedChart, LeakTestPanel
|-- dns_resolver.py      # Mini-resolveur DNS local (NXDOMAIN sinkhole)
|-- i18n.py              # Internationalisation FR/EN
|-- locales/
|   |-- fr.json
|   |-- en.json
|-- tests/               # pytest (config, engine, security, features, ...)
|   |-- conftest.py
|   |-- test_*.py
|-- pytest.ini
|-- make_icon.py         # Generation de l'icone .ico (lance par build)
|-- app.manifest         # Manifeste UAC requireAdministrator + DPI
|-- requirements.txt
|-- build_windows.bat
|-- config_examples/
|   |-- aurora.conf      # Modele WireGuard
|   |-- aurora.ovpn      # Modele OpenVPN (TLS 1.3 + AES-256-GCM)
|   |-- ikev2_setup.ps1  # Script PowerShell IKEv2 (AES-GCM-256/ECP-384/PFS)
|-- README.md
|-- CONCEPTION.md
|-- JURIDICTION.md       # Strategie Suisse + RAM-only + audit no-logs
```

---

## Nouveautes de la v2

### Interface

- **Hero animé** : disque central avec halos concentriques pulsants,
  la couleur reflète l'état (violet/gris au repos, cyan en cours,
  vert connecté, rouge en erreur).
- **Bouton CONNECTER** géant, plus haut, plus lisible.
- **Trio d'info** compact (Serveur · Latence · Protocole).
- **Sélecteur de protocole segmenté** + recommandation contextuelle.
- **Panneau Protections** sur 2 lignes / 3 colonnes (6 toggles d'un coup d'œil).
- **Footer** avec IP publique en direct + Mode + Serveurs.
- **System tray** (zone de notification Windows) : clic droit → Afficher /
  Connecter / Quitter. Fermer la fenêtre minimise dans le tray.

### Robustesse

- **Persistance** des préférences dans `%APPDATA%\AuroraVPN\config.json`.
  Toutes les modifications sont sauvegardées immédiatement.
- **Single instance** : un seul AuroraVPN à la fois (mutex fichier).
- **Logs rotatifs quotidiens** dans `%APPDATA%\AuroraVPN\logs\` (7 jours).
- **Fermeture propre** : déconnexion automatique avant exit, sauvegarde,
  release du mutex.
- **Détection de fuite** en thread d'arrière-plan : compare l'IP publique
  réelle à celle attendue toutes les 30 s, avertissement dans l'UI si
  mismatch.

### Mode réel (opt-in)

Dans **Paramètres → AVANCÉ**, deux toggles distincts :

1. **Connexion VPN réelle** — active les vrais appels :
   - WireGuard : `wireguard.exe /installtunnelservice`
   - IKEv2 : provisionnement RAS via PowerShell + `rasdial`
   - OpenVPN : `openvpn.exe --config`
2. **Sécurité réelle** — active les vrais filtres :
   - Kill switch : `New-NetFirewallRule -Direction Outbound -Action Block`
   - DNS chiffré : `Set-DnsClientServerAddress` + `netsh dns set encryption`
   - IPv6 : désactivation via `Disable-NetAdapterBinding ms_tcpip6`
   - Split tunneling : `Set-VpnConnection -SplitTunneling`

Les deux toggles nécessitent les droits Administrateur. Sans élévation,
les opérations sont silencieusement ignorées (et journalisées).

### Mesures réelles

- **IP publique** récupérée via `api.ipify.org` (puis fallback `icanhazip.com`).
- **Latence** mesurée via ping ICMP réel sur l'endpoint du serveur.
- Affichées en direct dans le footer dès la connexion.

---

## Intégration des protocoles sur Windows

### IPsec/IKEv2 (recommandé entreprise / site-à-site)

Cipher suite par défaut : **AES-GCM-256 / SHA-384 / ECP-384 / PFS**.
Provisionnement automatique en mode réel ; voir aussi
`config_examples/ikev2_setup.ps1` pour faire ça à la main.

### WireGuard (recommandé moderne / cloud)

Installer le client officiel : https://www.wireguard.com/install/
Modèle de configuration : `config_examples/aurora.conf`
(ChaCha20-Poly1305, Curve25519, AllowedIPs `0.0.0.0/0, ::/0`).

En mode réel, AuroraVPN écrit le fichier `.conf` dans
`C:\ProgramData\AuroraVPN\aurora.conf` puis appelle
`wireguard.exe /installtunnelservice`.

### OpenVPN (compatibilité maximale)

Installer OpenVPN 2.6+ : https://openvpn.net/community-downloads/
Configuration : `config_examples/aurora.ovpn`
(TLS 1.3, AES-256-GCM, `tls-crypt`, fallback TCP 443).

---

## Sécurité par défaut

| Protection | Activé |
|---|---|
| Kill Switch (firewall) | Oui |
| DNS chiffré (DoH) | Oui |
| Anti-fuite IPv6 + leak monitor | Oui |
| Perfect Forward Secrecy | Oui |
| Hybride post-quantique (ML-KEM) | Désactivé (expérimental) |
| Split tunneling | Désactivé |
| Reconnexion automatique | Oui |
| Connexion auto sur Wi-Fi public | Oui |
| Blocage trackers / malware | Oui |
| Réduire dans le tray | Oui |
| Démarrer minimisé | Non |

---

## Modes prédéfinis

| Mode | Protocole | Politique |
|---|---|---|
| Auto | Auto | Tout activé, choix dynamique |
| Sécurité max | IKEv2 | AES-GCM-256, PFS, post-quantique, kill switch |
| Vitesse max | WireGuard | Latence minimale |
| Streaming | WireGuard | Latence minimale, split tunneling |
| Entreprise | IKEv2 | Site-à-site, certificats, post-quantique |
| Réseau hostile | OpenVPN | TCP 443, anti-DPI |

---

## Emplacements de fichiers utilisés

| Quoi | Où |
|---|---|
| Préférences utilisateur | `%APPDATA%\AuroraVPN\config.json` |
| Logs | `%APPDATA%\AuroraVPN\logs\aurora.log` (rotation 7j) |
| Configuration WireGuard générée | `C:\ProgramData\AuroraVPN\aurora.conf` |
| Configuration OpenVPN attendue | `C:\ProgramData\AuroraVPN\aurora.ovpn` |
| Connexion RAS Windows | nom `AuroraVPN` (Panneau de config → VPN) |
| Mutex single-instance | `%TEMP%\AuroraVPN.lock` |

---

## Compilation et distribution

```bat
build_windows.bat
```

Étapes effectuées :

1. `pip install -r requirements.txt`
2. `python make_icon.py` → `assets\aurora.ico` (multi-tailles 16/32/48/64/128/256)
3. `pyinstaller --onefile --windowed --manifest app.manifest --uac-admin --icon assets\aurora.ico ...`
4. Sortie : `dist\AuroraVPN.exe`

---

## Dépannage

- **« Une autre instance est en cours »** : supprimer `%TEMP%\AuroraVPN.lock`.
- **Le bouton CONNECTER reste violet en mode réel** : vérifier que
  WireGuard ou OpenVPN est installé, ou utiliser IKEv2 (natif Windows).
- **Le système tray n'apparaît pas** : `pip install pystray Pillow`.
- **DNS toujours fuyant** : activer aussi le Kill switch (ils se complètent).
- **Connexion réelle refuse de partir** : relancer en tant qu'Administrateur,
  ou désactiver « Connexion VPN réelle » pour rester en démo.

---

## Nouveautés v4

### Tests unitaires

Suite `pytest` couvrant tous les modules clés. Lancer :

```bat
python -m pip install pytest
python -m pytest -v
```

Couverture : `tests/test_config.py`, `tests/test_features.py`,
`tests/test_security.py`, `tests/test_utils.py`, `tests/test_vpn_engine.py`,
`tests/test_dns_resolver.py`, `tests/test_i18n.py`. Aucun test ne nécessite
les droits Administrateur — tout passe en mode démo.

### Détection automatique du serveur le plus rapide

Au démarrage (toggle `auto_ping_on_start`), AuroraVPN ping en parallèle
les 12 serveurs du catalogue avec un `ThreadPoolExecutor` (8 workers,
timeout 3 s). Les latences réelles remplacent les valeurs catalogue, et
`_select_best_server` choisit le moins chargé / plus rapide.

### Mode loopback (VPN simulé localhost)

Toggle Paramètres → AVANCÉ → "Mode loopback". Active un nouveau backend
`LoopbackBackend` qui ouvre un vrai socket UDP sur `127.0.0.1` et permet
de tester le cycle complet connect → CONNECTED → disconnect avec un
endpoint réel, sans serveur distant. Indispensable pour démonstrations,
QA et validation CI/CD.

### Mini-résolveur DNS local

Module `dns_resolver.py` : serveur UDP léger (port 5353 par défaut, 53
si admin) qui forward toutes les requêtes vers `1.1.1.1` et bloque par
NXDOMAIN les domaines présents dans la blocklist Threat Protection.
Active la protection DNS *de bout en bout*. Pour pointer Windows DNS
sur le résolveur :

```powershell
Set-DnsClientServerAddress -InterfaceAlias "Ethernet" -ServerAddresses "127.0.0.1"
```

(à adapter selon votre interface ; pour utiliser le port 53 plutôt que 5353,
lancer AuroraVPN en tant qu'Administrateur).

### Internationalisation FR / EN

Module `i18n.py` + fichiers `locales/fr.json` et `locales/en.json`.
Auto-détection de la langue système au démarrage, switcher dans
Paramètres → LANGUE. Pour ajouter une langue : copier `en.json`,
traduire les valeurs, sauvegarder en `xx.json`, redémarrer.

Usage côté code :

```python
from i18n import _, set_language
set_language("en")
print(_("btn_connect"))   # -> "CONNECT"
```

---

## Nouveautés v3

### Tableau de bord avancé (bouton "Tableau de bord" dans le footer)

Six onglets accessibles d'un clic :

- **Carte** — carte du monde stylisée avec pins serveurs cliquables. La couleur du pin reflète la latence (vert < 60 ms, ambre < 150 ms, rouge au-delà).
- **Stats** — graphique en direct latence (cyan) + débit (violet) sur les 60 dernières secondes.
- **Tests** — bouton "LANCER LE TEST" qui vérifie en parallèle votre IP publique vs IP attendue, vos DNS système, votre IPv6, et rappelle la limite WebRTC.
- **Multi-hop** — Double VPN : choisissez un serveur d'entrée et un serveur de sortie distincts pour cascader les tunnels.
- **Tor** — Tor over VPN (lance `tor.exe` si Tor Browser est installé, configure le SOCKS5 sur 127.0.0.1:9150).
- **Threat** — protection anti-pubs / trackers / malware basée sur la liste StevenBlack/hosts (mise à jour hebdomadaire). Stats temps réel : requêtes vérifiées + domaines bloqués.

### Notifications Windows natives

Toasts via `plyer` à chaque changement d'état (connexion, déconnexion, erreur, fuite détectée, multi-hop activé, Tor démarré, etc.). Désactivable dans les Paramètres.

### Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Ctrl+K` | Connecter / déconnecter |
| `Ctrl+M` | Ouvrir le tableau de bord |
| `Ctrl+L` | Ouvrir la liste des serveurs |
| `F5` | Rafraîchir l'IP publique |

### Accélérateur VPN

Tuning automatique de la pile réseau Windows quand activé : MTU 1420 (optimal WireGuard), CUBIC congestion control, autotuning RWIN normal. Réduit la perte de paquets sur 4G et Wi-Fi saturés.

### Multi-hop / Double VPN

Cascade entrée → sortie : votre trafic passe par deux serveurs successifs. L'IP source vue de chacun n'est jamais la vôtre. Ajoute 30-80 ms de latence mais isole complètement le trafic. Configurez la route dans l'onglet Multi-hop du tableau de bord.

### Tor over VPN

Une fois activé (et Tor Browser installé), AuroraVPN démarre `tor.exe` en arrière-plan (SOCKS5 127.0.0.1:9150). Configurez votre navigateur sur ce proxy pour bénéficier du double anonymat (FAI ne voit que le VPN, sortie via Tor change d'IP en permanence).

### Threat Protection

Au premier lancement, télécharge la liste StevenBlack/hosts (~150 000 domaines). Renouvellement automatique tous les 7 jours. Stocké dans `%APPDATA%\AuroraVPN\blocklist.txt`. Pour activer le blocage DNS effectif, lancer le résolveur DNS interne (à brancher sur le port 53 local — phase suivante).

### Juridiction Suisse

Document complet `JURIDICTION.md` : pourquoi la Suisse, comment monter une Sàrl, déployer des serveurs RAM-only PXE, organiser un audit no-logs externe (Cure53 / Securitum / PwC), publier un transparency report.

---

## Crédits techniques

- Interface : CustomTkinter (Tom Schimansky, MIT)
- System tray : pystray (Moses Palmér, LGPL)
- Notifications natives : plyer (LGPL)
- Génération d'icônes : Pillow (PIL Software License)
- WireGuard : Jason A. Donenfeld (GPLv2)
- OpenVPN : OpenVPN Inc. (GPLv2)
- IPsec/IKEv2 : pile native Windows
