# Déploiement d'un vrai serveur AuroraVPN

> Guide pas-à-pas pour louer un VPS, y installer WireGuard via le script
> de provisioning, puis importer la configuration dans AuroraVPN Windows.

---

## 1. Choisir un hébergeur

Tableau comparatif des hébergeurs **éprouvés et abordables** pour un VPN
personnel (1-5 utilisateurs) :

| Hébergeur | VPS le moins cher | Bande passante incluse | Localisation suggérée | Note |
|---|---|---|---|---|
| **Hetzner Cloud** | CX22 — 3.79 €/mois | 20 To/mois | Falkenstein (DE), Nuremberg (DE), Helsinki (FI) | Excellent prix/performance |
| **OVH VPS** | Starter — 3.50 €/mois | 100 Mbps illimité | Gravelines (FR), Strasbourg (FR) | Bon pour utilisateurs FR |
| **DigitalOcean** | Basic — 4 $/mois | 500 Go/mois | Amsterdam, NY, SF, Bangalore, Sydney | Interface très claire |
| **Vultr** | Cloud Compute — 3.50 $/mois | 1 To/mois | 30+ régions | Très bonne couverture mondiale |
| **Scaleway** | Stardust — 4 €/mois | 100 Go/mois | Paris, Amsterdam | Cocorico, jurisdiction FR |
| **Contabo** | VPS S — 4.99 €/mois | 32 To/mois | DE, US, UK, JP, SG | Beaucoup de RAM/CPU pour le prix |

**Recommandation pour la confidentialité** : Hetzner (DE) ou Scaleway (FR/NL)
si tu veux rester en UE/RGPD. Mullvad-style : tu peux louer chez plusieurs
fournisseurs et changer régulièrement.

**Configuration minimale requise** : 1 vCPU, 1 Go RAM, 10 Go disque,
Ubuntu 22.04 LTS ou Debian 12.

---

## 2. Créer le VPS

### Exemple avec Hetzner Cloud

1. Compte sur https://www.hetzner.com/cloud (~5 min, ~10 €/mois budget initial).
2. **Add Server** → emplacement Falkenstein → image **Ubuntu 22.04**.
3. Type **CX22** (3.79 €/mois).
4. **SSH Keys** : ajouter ta clé publique SSH (ou récupérer le mot de passe root par email).
5. Nom : `aurora-vpn-de1` (par exemple).
6. **Create & Buy**. Délai d'allocation : ~30 secondes.
7. Note l'IP publique IPv4 affichée (ex : `49.12.123.45`).

### Exemple avec OVH

1. Compte sur https://www.ovhcloud.com/fr/vps/.
2. **VPS Starter** → datacenter Gravelines → distribution **Ubuntu 22.04 Server**.
3. Pas de panel web (Ubuntu only).
4. Valider la commande. Délai : 5-15 minutes.
5. Réception par email du mot de passe root + IP publique.

---

## 3. Se connecter en SSH

Sur ton **Windows** (PowerShell ou Terminal) :

```powershell
ssh root@49.12.123.45
# (remplace 49.12.123.45 par l'IP de ton VPS)
```

Première connexion : taper `yes` pour accepter l'empreinte, puis le mot
de passe root. Si tu as configuré une clé SSH, pas de mot de passe.

---

## 4. Provisionner WireGuard (1 seule commande)

Une fois connecté en SSH sur le serveur :

```bash
# Telecharger le script de provisioning
wget https://raw.githubusercontent.com/<TON_REPO>/AuroraVPN/main/server_setup/install_wireguard.sh
chmod +x install_wireguard.sh

# Lancer (installation + creation du 1er client "mon-pc")
./install_wireguard.sh mon-pc
```

> Si tu n'as pas encore publié AuroraVPN sur GitHub, copie le script à
> la main : sur Windows, ouvre `D:\Claude Code\AuroraVPN\server_setup\install_wireguard.sh`,
> puis sur le serveur fais `nano install_wireguard.sh`, colle le contenu, sauvegarde (Ctrl+O Enter, Ctrl+X).

Durée totale : **~60-90 secondes**.

Le script :
1. Installe les paquets `wireguard wireguard-tools iptables qrencode curl`
2. Génère les clés serveur (Curve25519)
3. Configure `wg0` sur `10.66.66.1/24` (UDP 51820)
4. Active le `net.ipv4.ip_forward`
5. Pose les règles iptables NAT MASQUERADE
6. Ouvre le port firewall (ufw/firewalld/iptables)
7. Démarre le service `wg-quick@wg0` au boot
8. **Crée le 1er client** `mon-pc` et affiche le fichier `.conf` + QR code.

À la fin, tu vois dans le terminal :

```
=== Client mon-pc cree ===
Fichier de configuration :
    /etc/wireguard/clients/mon-pc/mon-pc.conf
```

---

## 5. Récupérer le fichier `.conf` sur ton Windows

### Option A : copier-coller via SSH

Sur ton **Windows** (PowerShell) :

```powershell
scp root@49.12.123.45:/etc/wireguard/clients/mon-pc/mon-pc.conf "D:\Claude Code\AuroraVPN\mon-pc.conf"
```

### Option B : afficher et copier-coller manuellement

Sur le **serveur** :

```bash
cat /etc/wireguard/clients/mon-pc/mon-pc.conf
```

Copier le contenu, sur Windows ouvrir un nouveau fichier `mon-pc.conf`,
coller, sauvegarder dans `D:\Claude Code\AuroraVPN\`.

---

## 6. Importer dans AuroraVPN

Sur **Windows**, dans le dossier `D:\Claude Code\AuroraVPN` :

```powershell
# Lancer PowerShell en tant qu'Administrateur (clic droit → "Exécuter en tant qu'administrateur")
cd "D:\Claude Code\AuroraVPN"
python import_wireguard_config.py mon-pc.conf --name "Allemagne - Falkenstein"
```

Effet :
- Copie le fichier dans `C:\ProgramData\AuroraVPN\aurora.conf` (lecture restreinte aux admins).
- Met à jour `%APPDATA%\AuroraVPN\config.json` :
  - `real_subprocess = True`
  - `loopback_mode = False`
  - `real_endpoint_host = 49.12.123.45`

---

## 7. Installer le client WireGuard officiel

AuroraVPN orchestre `wireguard.exe` mais ne l'embarque pas (driver kernel signé).

```
https://www.wireguard.com/install/
```

Télécharger l'installeur Windows, l'exécuter, accepter UAC. Aucun
redémarrage requis.

---

## 8. Lancer AuroraVPN

Double-cliquer sur `AuroraVPN.bat`. Avec `real_subprocess=True` et le
manifeste UAC, Windows demande l'élévation. Accepter.

L'app :
1. Charge la config
2. Détecte que `real_subprocess=True` et `loopback_mode=False`
3. Active le backend `WireGuardBackend`
4. Écrit `aurora.conf` dans le dossier ProgramData (déjà fait par l'import)
5. Lance `wireguard.exe /installtunnelservice C:\ProgramData\AuroraVPN\aurora.conf`
6. WireGuard établit le tunnel
7. AuroraVPN passe en CONNECTÉ, mesure la latence réelle (ping vers `49.12.123.45`), récupère l'IP publique
8. **L'IP publique affichée dans le footer est maintenant celle de ton serveur Allemagne** → ton trafic est réellement protégé.

---

## 9. Vérifier que ça fonctionne

Sur Windows, dans un navigateur :
- https://api.ipify.org → doit afficher `49.12.123.45` (ton serveur), pas ton IP FAI.
- https://browserleaks.com/ip → doit montrer Allemagne / Hetzner.

Sur le serveur (en SSH) :
```bash
wg show
```
Doit montrer ton peer (`mon-pc`) avec `latest handshake` récent et des octets transférés.

---

## 10. Ajouter d'autres appareils (téléphone, autre PC...)

Sur le serveur :

```bash
./add_client.sh telephone
```

QR code affiché → scanner depuis l'app WireGuard mobile (iOS/Android). Le
nouvel appareil se connecte au même serveur, avec sa propre IP `10.66.66.3`.

Pour un autre Windows, recopier le `.conf` et lancer `import_wireguard_config.py`.

---

## 11. Démarrage automatique avec Windows

Sur ton Windows :

```bat
Installer_Demarrage_Windows.cmd
```

→ Crée un raccourci dans le dossier `Démarrage` utilisateur. AuroraVPN
se lance à chaque login Windows. Combiné avec `auto_connect_on_start=True`
(déjà activé par `AuroraVPN.bat`), tu es VPN-connecté **dès l'allumage**.

Pour désactiver :

```bat
Desinstaller_Demarrage_Windows.cmd
```

---

## 12. Maintenance du serveur

### Mises à jour de sécurité (1×/mois)

```bash
ssh root@49.12.123.45
apt update && apt upgrade -y
reboot
```

WireGuard repart tout seul au boot grâce à `systemctl enable wg-quick@wg0`.

### Voir qui est connecté

```bash
wg show wg0
```

### Révoquer un client (perdu/volé)

```bash
# Liste les peers
wg show wg0
# Retire le peer (remplacer <PUBKEY> par la cle publique du client a revoquer)
wg set wg0 peer <PUBKEY> remove
wg-quick save wg0
# Supprime aussi son dossier client
rm -rf /etc/wireguard/clients/<nom>
```

### Sauvegarde de la config

```bash
tar -czf wg-backup-$(date +%F).tar.gz /etc/wireguard
scp wg-backup-*.tar.gz user@autre-machine:/backup/
```

---

## 13. Pour aller plus loin

- **DNS interne anti-pubs** : lancer un Pi-hole sur le serveur, le pointer
  comme DNS dans les `.conf` clients à la place de `1.1.1.1`.
- **Multi-serveurs** : louer 3-5 VPS différentes localisations, importer
  chaque `.conf` dans AuroraVPN, l'app les fait apparaître comme "serveurs"
  dans la liste (édition manuelle du catalogue dans `vpn_engine.py`).
- **Monitoring** : installer `vnstat` (bande passante) ou `prometheus-node-exporter`.
- **Haute disponibilité** : 2 serveurs derrière un DNS round-robin ou
  un load balancer DNS (gandi.net, Cloudflare gratuits).
- **Juridiction Suisse** : voir `JURIDICTION.md` pour le passage en SA
  + serveurs RAM-only.

---

## Annexe : variables d'environnement du script

Tu peux personnaliser `install_wireguard.sh` :

```bash
WG_PORT=443 WG_DNS="9.9.9.9, 8.8.8.8" ./install_wireguard.sh mon-pc
```

| Variable | Défaut | Description |
|---|---|---|
| `WG_INTERFACE` | `wg0` | Nom de l'interface WireGuard |
| `WG_PORT` | `51820` | Port UDP d'écoute (utiliser 443 pour bypass certains FAI) |
| `WG_SUBNET` | `10.66.66.0/24` | Réseau interne du tunnel |
| `WG_SERVER_IP` | `10.66.66.1` | IP du serveur dans le tunnel |
| `WG_DNS` | `1.1.1.1, 9.9.9.9` | Serveurs DNS poussés aux clients |
