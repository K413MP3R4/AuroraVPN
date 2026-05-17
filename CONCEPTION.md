# AuroraVPN — Document de conception technique

**Version** : 1.0
**Date** : 13 mai 2026
**Plateforme cible** : Windows 10 (1809+) / Windows 11
**Statut** : Conception complète prête pour développement

---

## 1. Résumé exécutif

AuroraVPN est un logiciel VPN Windows pensé pour combiner la **rigueur d'un produit entreprise** (IPsec/IKEv2 site-à-site) et la **simplicité d'un produit grand-public moderne** (WireGuard mono-clic). L'interface est compacte (460×720 px), sombre, avec accents violet (#8B5CF6) et cyan (#22D3EE), inspirée de l'ergonomie d'un dashboard premium sans copier la marque ni le logo de Proton VPN ou de tout autre produit.

L'architecture est modulaire : un moteur central orchestre trois backends de protocole (WireGuard, IKEv2, OpenVPN) et un gestionnaire de sécurité applique transversalement les protections (kill switch WFP, DNS chiffré, anti-fuite IPv6/WebRTC, PFS, hybride post-quantique).

---

## 2. Objectifs produit

| # | Objectif | Mesure de succès |
|---|---|---|
| O1 | VPN « un clic » par défaut sécurisé | < 3 s du clic à l'état CONNECTÉ |
| O2 | Suite cryptographique de niveau entreprise | AES-GCM-256, ECP-384, PFS, X.509 |
| O3 | Latence faible (cas grand-public) | WireGuard sélectionné automatiquement quand possible |
| O4 | Compatibilité réseaux restrictifs | Fallback OpenVPN TCP/443 + obfuscation |
| O5 | Préparation post-quantique | Hybride classique + ML-KEM (Kyber) optionnel |
| O6 | Aucun journal sensible | No-log architecture, journal local minimal |
| O7 | Distribution simple | Exécutable Windows autonome (~30-50 Mo) |

---

## 3. Architecture logicielle

### 3.1 Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                    AuroraVPNApp (UI / Tk)                   │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │ Status card  │  │ Action btn   │  │ Info grid    │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
│   ┌──────────────┐  ┌──────────────┐                        │
│   │ Protocol sel │  │ Security pan │                        │
│   └──────────────┘  └──────────────┘                        │
└────────┬────────────────────────────────────┬───────────────┘
         │ on_state_change()                  │ status (R/W)
         ▼                                    ▼
┌─────────────────────────┐         ┌────────────────────────┐
│       VPNEngine         │         │   SecurityManager      │
│  - state machine        │◄────────┤  - kill switch (WFP)   │
│  - server selection     │         │  - DNS DoH/DoT         │
│  - protocol selection   │         │  - leak protection     │
└────────┬────────────────┘         │  - PFS / post-quantum  │
         │                          │  - split tunneling     │
         ▼                          │  - tracker blocking    │
┌─────────────────────────┐         └────────────────────────┘
│        Backends         │
│  ┌──────────────────┐   │           ┌────────────────────┐
│  │ WireGuardBackend │───┼──────────►│ wireguard.exe      │
│  └──────────────────┘   │           └────────────────────┘
│  ┌──────────────────┐   │           ┌────────────────────┐
│  │ IKEv2Backend     │───┼──────────►│ rasdial.exe / RAS  │
│  └──────────────────┘   │           └────────────────────┘
│  ┌──────────────────┐   │           ┌────────────────────┐
│  │ OpenVPNBackend   │───┼──────────►│ openvpn.exe        │
│  └──────────────────┘   │           └────────────────────┘
└─────────────────────────┘
```

### 3.2 Modules

| Module | Rôle | Fichier |
|---|---|---|
| Interface | Composition CustomTkinter, événements, animations | `main.py` |
| Moteur | Machine d'états, sélection serveur/protocole | `vpn_engine.py` |
| Backends | Pilotes spécifiques WG / IKEv2 / OpenVPN | `vpn_engine.py` (mêmes fichier) |
| Sécurité | Kill switch, DNS, PFS, post-quantique, etc. | `security.py` |
| Configurations | Modèles `.conf`, `.ovpn`, scripts PowerShell | `config_examples/` |
| Build | Script PyInstaller de production | `build_windows.bat` |

### 3.3 Séparation des responsabilités

- **Interface** : aucun appel système direct ; ne fait que lire/écrire du moteur via callbacks.
- **Moteur** : ignore tout détail UI ; expose `connect()`, `disconnect()`, `state`, `on_state_change`.
- **Backends** : encapsulent strictement un protocole ; même contrat (`is_available`, `connect`, `disconnect`).
- **Sécurité** : transversale ; chaque protection est un toggle indépendant qui applique sa règle système.

---

## 4. Interface utilisateur

### 4.1 Charte graphique

| Rôle | Couleur | Hex |
|---|---|---|
| Fond principal | Noir profond | `#0B0B14` |
| Carte / panneau | Anthracite | `#15151F` |
| Panneau secondaire | Anthracite clair | `#1E1E2C` |
| Bordure | Gris violet | `#2A2A3A` |
| Texte principal | Blanc cassé | `#E5E7EB` |
| Texte secondaire | Gris bleuté | `#8B8B9C` |
| Accent principal | Violet | `#8B5CF6` |
| Accent hover | Violet sombre | `#6D28D9` |
| Accent secondaire | Cyan | `#22D3EE` |
| État connecté | Vert | `#34D399` |
| Avertissement | Ambre | `#FBBF24` |
| Erreur / kill switch | Rouge | `#EF4444` |

Police : **Segoe UI** (native Windows) en 9–18 pt.
Coins arrondis : 8 px (cartes), 12 px (gros boutons / panneaux principaux).
Bordures : 1 px `#2A2A3A`, sans ombre portée (look plat moderne).

### 4.2 Disposition de la fenêtre principale

```
┌───────────────────────────────────────────────────────┐
│  ●  AuroraVPN                                    [⚙] │
│     Tunnel chiffré · Confidentialité · Performance    │
├───────────────────────────────────────────────────────┤
│  ●  Connecté                              00:14:23    │
│     Tunnel actif et chiffré                           │
├───────────────────────────────────────────────────────┤
│                                                       │
│              ╔═══════════════════════════╗            │
│              ║       DÉCONNECTER         ║            │
│              ╚═══════════════════════════╝            │
│                                                       │
├───────────────────────────────────────────────────────┤
│  🌐 SERVEUR              🔑 IP PUBLIQUE               │
│  France · Paris          185.10.20.30                 │
│                                                       │
│  🔒 PROTOCOLE            ⚡ LATENCE / DÉBIT           │
│  WireGuard               22 ms / 380 Mb/s             │
├───────────────────────────────────────────────────────┤
│  PROTOCOLE                                            │
│  [ Auto ][ WireGuard ][ IKEv2 ][ OpenVPN ]            │
│  💡 Recommandé : WireGuard (latence faible…)          │
├───────────────────────────────────────────────────────┤
│  SÉCURITÉ                                             │
│  ● Kill Switch          ● DNS chiffré (DoH)           │
│  ● Anti-fuite           ● Perfect Forward Secrecy     │
│  ○ Hybride post-quantique  ○ Split tunneling          │
├───────────────────────────────────────────────────────┤
│  [ Auto ▾ ]                              [ Serveurs ] │
└───────────────────────────────────────────────────────┘
```

### 4.3 États visuels

| État moteur | Pastille | Bouton | Sous-titre |
|---|---|---|---|
| `DISCONNECTED` | gris fixe | violet « CONNECTER » | « Aucun tunnel actif » |
| `CONNECTING` | cyan pulsant | gris « ANNULER » | « Négociation des clés en cours » |
| `CONNECTED` | vert pulsant | gris « DÉCONNECTER » | « Tunnel actif et chiffré » |
| `ERROR` | rouge fixe | violet « RÉESSAYER » | message d'erreur |

### 4.4 Fenêtres secondaires

- **Paramètres** (420×520) : 9 toggles (kill switch, DNS, anti-fuite, PFS, post-quantique, split, reconnexion auto, Wi-Fi public auto, blocage trackers).
- **Serveurs** (420×520) : liste défilable, latence en cyan, bouton « Sélectionner » par ligne.

---

## 5. Choix de protocoles

### 5.1 Tableau comparatif

| Critère | IPsec/IKEv2 | WireGuard | OpenVPN |
|---|---|---|---|
| Suite par défaut | AES-GCM-256, SHA-384, ECP-384 | ChaCha20-Poly1305, Curve25519 | AES-256-GCM, TLS 1.3 |
| PFS | Oui (DH éphémère) | Oui (handshake Noise) | Oui (TLS) |
| Latence d'établissement | ~600 ms | ~150 ms | ~1500 ms |
| Débit (1 Gbps test) | ~870 Mbps | ~940 Mbps | ~520 Mbps |
| Traversée NAT | NAT-T (UDP 4500) | UDP standard | UDP/TCP |
| Mobilité (changement de réseau) | Excellent (MOBIKE) | Excellent (handshake léger) | Moyen (reconnexion) |
| Support natif Windows | ✅ (RAS) | ❌ (binaire externe) | ❌ (binaire externe) |
| Cipher post-quantique | Draft IETF | Couche PSK ML-KEM | TLS 1.3 X25519MLKEM768 |
| Cas d'usage idéal | Site-à-site, entreprise | Cloud, mobile, simple | Compatibilité extrême |

### 5.2 Algorithme de sélection automatique

```
fonction selectionner_protocole(serveur, contexte):
    si contexte == "réseau hostile":
        retourner OPENVPN  (TCP 443, obfuscation)
    si contexte == "entreprise" ou "site-à-site":
        retourner IKEV2
    si serveur.supporte_wireguard et wireguard_dispo():
        retourner WIREGUARD
    si serveur.supporte_ikev2:
        retourner IKEV2
    retourner OPENVPN
```

### 5.3 Recommandations par défaut

- **Protocole d'entrée** : `Auto` → WireGuard pour la plupart des utilisateurs.
- **Profil entreprise** : forcer IKEv2 + authentification certificat machine X.509.
- **Profil mobile / Wi-Fi public** : WireGuard avec `PersistentKeepalive=25`.

---

## 6. Sécurité

### 6.1 Cipher suites par défaut

#### IPsec/IKEv2
```
IKE SA   : AES-GCM-256 / SHA-384 / ECP-384
ESP      : AES-GCM-256
PFS      : ECP-384 (DH group 20)
Auth     : Certificat X.509 machine (RSA-3072 ou ECDSA-P-384)
NAT-T    : UDP 4500
```

#### WireGuard
```
DH       : Curve25519
AEAD     : ChaCha20-Poly1305
Hash     : BLAKE2s
KDF      : HKDF
PSK      : optionnel (renforcement post-quantique léger)
```

#### OpenVPN
```
Data ch. : AES-256-GCM (+ ChaCha20-Poly1305 fallback)
Control  : TLS 1.3, TLS_AES_256_GCM_SHA384
HMAC     : tls-crypt v2 (anti-DPI)
```

### 6.2 Kill Switch (Windows Filtering Platform)

Au montage du tunnel, AuroraVPN crée un filtre WFP `block all outbound` avec exceptions :
- Trafic vers l'endpoint VPN (IP + port)
- Trafic via l'interface VPN (`luid` du tunnel)
- (Optionnel) trafic LAN local si l'utilisateur autorise

Au démontage, le filtre **reste actif tant que l'utilisateur n'a pas désactivé le kill switch** : aucune fuite possible même en cas de crash du processus.

### 6.3 DNS chiffré

- Forçage des DNS : `1.1.1.1`, `9.9.9.9` (configurable).
- DoH activé via `netsh dns set encryption server=...` (Windows 11) ou résolveur interne (Windows 10).
- Filtre WFP bloque tout UDP 53 sortant hors tunnel (anti-DNS leak).

### 6.4 Anti-fuite IPv6 / WebRTC

- IPv6 : interface IPv6 du tunnel ou désactivation via WFP `permit ipv6 only via tun`.
- WebRTC : impossible à bloquer côté OS (couche navigateur). L'UI affiche une alerte
  invitant l'utilisateur à activer le blocage WebRTC dans son navigateur.
- Vérification active toutes les 30 s : test DNS + comparaison IP publique reçue avec IP attendue du serveur VPN.

### 6.5 Hybride post-quantique (optionnel)

L'option suit l'approche **classique + ML-KEM** recommandée par le NIST :
- IKEv2 : draft `draft-ietf-ipsecme-ikev2-pq-auth` + extensions.
- WireGuard : couche PSK rotative dérivée d'un échange ML-KEM périodique.
- TLS 1.3 (OpenVPN) : groupe `X25519MLKEM768` (déjà supporté par OpenSSL 3.5+).

Tant que les piles ne sont pas matures, l'option reste **désactivée par défaut** ; la suite classique (Curve25519 / ECP-384) reste utilisée et garantit une sécurité forte.

### 6.6 Architecture sans journaux

- Aucun log applicatif ne contient l'IP cible, l'URL visitée, le DNS résolu.
- Le journal local conserve seulement : horodatage de connexion/déconnexion, durée, protocole, code d'erreur. Rotation 7 jours.
- Aucune télémétrie réseau sortante.

---

## 7. Flux de connexion

### 7.1 Diagramme de séquence

```
Utilisateur     UI (Tk)        VPNEngine        Backend         OS Windows
    │              │                │                │                │
    │ clic CONNECT │                │                │                │
    │─────────────►│                │                │                │
    │              │ connect()      │                │                │
    │              │───────────────►│                │                │
    │              │                │ état:CONNECTING│                │
    │              │◄───────────────│                │                │
    │              │ pulse cyan     │                │                │
    │              │                │ select_server()│                │
    │              │                │ select_proto() │                │
    │              │                │ backend.connect│                │
    │              │                │───────────────►│                │
    │              │                │                │ rasdial / WG   │
    │              │                │                │───────────────►│
    │              │                │                │                │ tunnel
    │              │                │                │◄───────────────│ établi
    │              │                │◄───────────────│                │
    │              │                │ état:CONNECTED │                │
    │              │◄───────────────│                │                │
    │              │ pulse vert     │                │                │
    │              │ compteur ↑     │                │                │
    │              │                │                │                │
    │              │                │ SecurityMgr    │                │
    │              │                │ .apply_kill_sw │                │
    │              │                │───────────────►│ WFP filter add │
    │              │                │                │                │
```

### 7.2 États et transitions

```
       ┌─────────────────┐
       │  DISCONNECTED   │◄──────────┐
       └────────┬────────┘           │
                │ connect()          │ disconnect()
                ▼                    │
       ┌─────────────────┐           │
       │   CONNECTING    │           │
       └────────┬────────┘           │
        success │      failure       │
                ▼                    │
       ┌─────────────────┐    ┌──────┴───────┐
       │   CONNECTED     │    │    ERROR     │
       └────────┬────────┘    └──────┬───────┘
                │ disconnect()        │ reconnect /
                └─────────────────────┘ ack
```

---

## 8. Modes prédéfinis

| Mode | Protocole | Kill switch | DNS chiffré | Split | PFS | Post-Q |
|---|---|---|---|---|---|---|
| Auto | Auto | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sécurité max | IKEv2 | ✅ | ✅ | ❌ | ✅ | ✅ |
| Vitesse max | WireGuard | ✅ | ✅ | ❌ | ✅ | ❌ |
| Streaming | WireGuard | ✅ | ✅ | ✅ | ✅ | ❌ |
| Entreprise | IKEv2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Réseau hostile | OpenVPN | ✅ | ✅ | ❌ | ✅ | ✅ |

---

## 9. Exemple de configuration

### 9.1 WireGuard (`aurora.conf`)

```ini
[Interface]
PrivateKey = <CLE_PRIVEE_CLIENT>
Address    = 10.66.66.2/32, fd66:66:66::2/128
DNS        = 1.1.1.1, 9.9.9.9, 2606:4700:4700::1111
MTU        = 1420
Table      = auto

[Peer]
PublicKey           = <CLE_PUBLIQUE_SERVEUR>
PresharedKey        = <PSK_OPTIONNELLE>
Endpoint            = vpn-fr-par-01.aurora.example.com:51820
AllowedIPs          = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

### 9.2 IKEv2 (PowerShell)

```powershell
Add-VpnConnection -Name "AuroraVPN" `
  -ServerAddress "vpn.aurora.example.com" `
  -TunnelType IKEv2 -EncryptionLevel Required `
  -AuthenticationMethod MachineCertificate

Set-VpnConnectionIPsecConfiguration -ConnectionName "AuroraVPN" `
  -AuthenticationTransformConstants GCMAES256 `
  -CipherTransformConstants GCMAES256 `
  -EncryptionMethod GCMAES256 `
  -IntegrityCheckMethod SHA384 `
  -DHGroup ECP384 -PfsGroup ECP384 -Force

rasdial "AuroraVPN"
```

### 9.3 OpenVPN (`aurora.ovpn`)

Voir le fichier `config_examples/aurora.ovpn` (TLS 1.3, AES-256-GCM, `tls-crypt`, fallback TCP 443).

---

## 10. Distribution

### 10.1 Compilation

```bat
build_windows.bat
```

Produit `dist\AuroraVPN.exe` autonome (~30-50 Mo) avec PyInstaller.

### 10.2 Pré-requis runtime utilisateur

- Windows 10 1809+ ou Windows 11.
- Pour le mode IKEv2 : aucun (pile native Windows).
- Pour WireGuard : installer le client officiel WireGuard (https://www.wireguard.com).
- Pour OpenVPN : installer OpenVPN 2.6+ (https://openvpn.net).

### 10.3 Élévation administrateur

Le binaire doit demander UAC élévation au démarrage (manifeste `requireAdministrator`) pour pouvoir :
- Créer / supprimer des connexions RAS (IKEv2).
- Installer / désinstaller des services WireGuard.
- Appliquer / retirer des filtres WFP (kill switch).
- Modifier les routes IP (split tunneling).

---

## 11. Points d'extension futurs

| Évolution | Intérêt |
|---|---|
| VPN over QUIC / HTTP/3 / MASQUE CONNECT-IP | Traverser des réseaux qui bloquent UDP/TCP non-443 |
| Mode obfuscation Shadowsocks / Cloak | Rendre le trafic VPN indistinguable d'HTTPS |
| Architecture Zero Trust / SASE | Politiques d'accès par identité utilisateur + posture device |
| Multi-hop VPN (cascade 2 serveurs) | Augmenter l'anonymat (entrée + sortie séparées) |
| Tableau de bord santé tunnel | Latence, jitter, perte de paquets, MOS-like |
| Export / import sécurisé de profils | Partage chiffré de configurations entre postes |

---

## 12. Justification des choix techniques

| Choix | Pourquoi |
|---|---|
| **Python + CustomTkinter** | Développement rapide, look moderne natif Windows, packaging PyInstaller simple, large communauté |
| **Backends séparés** | Chaque protocole évolue indépendamment ; on peut ajouter un 4ᵉ backend (QUIC) sans modifier le moteur |
| **Pile RAS Windows pour IKEv2** | Pas de driver tiers à installer, certifié WHQL, MOBIKE natif |
| **wireguard.exe officiel** | Implémentation de référence, kernel-level driver signé, performances maximales |
| **WFP plutôt que `netsh advfirewall`** | API native, granularité fine, pas de course avec d'autres règles utilisateur |
| **Hybride post-quantique en option** | Trade-off : standards encore mouvants en 2025-2026 ; l'utilisateur peut activer dès qu'il en a besoin sans casser la compatibilité |
| **Sélection auto WG > IKEv2 > OpenVPN** | Performance maximale par défaut, fallback compat extrême |
| **Aucun log sensible** | Conformité RGPD, pas de subpoena utile, confiance utilisateur |

---

## 13. Annexes

- `main.py` — code source UI (~520 lignes).
- `vpn_engine.py` — code source moteur (~330 lignes).
- `security.py` — code source sécurité (~150 lignes).
- `config_examples/aurora.conf` — modèle WireGuard.
- `config_examples/aurora.ovpn` — modèle OpenVPN.
- `config_examples/ikev2_setup.ps1` — script PowerShell IKEv2.
- `build_windows.bat` — script de compilation .exe.
- `README.md` — documentation utilisateur.

---

*Document généré dans le cadre du projet AuroraVPN — palette violet/cyan, design original ne reprenant ni la marque ni les éléments propriétaires d'aucun produit existant.*
