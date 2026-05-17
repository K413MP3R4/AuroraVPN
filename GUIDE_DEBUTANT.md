# Guide complet débutant — AuroraVPN

> Écrit pour quelqu'un qui n'a JAMAIS touché à un VPN ou à un serveur.
> Si tu butes sur un mot, regarde le **lexique** à la fin.

---

## Avant tout : c'est quoi un VPN ?

Imagine que tu envoies une carte postale. **N'importe qui sur le trajet
peut la lire** : ton facteur, ton FAI, l'État, des hackers.

Un VPN, c'est mettre la carte postale dans une **enveloppe scellée**
avant de l'envoyer. Personne en chemin ne peut la lire. Seule la personne
qui reçoit (le serveur VPN) peut l'ouvrir et la transmettre à
destination.

**Conséquences** :
- Ton fournisseur Internet ne voit plus ce que tu fais (juste que tu
  parles à un serveur VPN).
- Les sites web voient l'IP du serveur VPN, pas la tienne (= tu sembles
  être ailleurs).
- Sur un Wi-Fi public (café, aéroport), personne ne peut espionner.

Pour fonctionner, un VPN a besoin de **DEUX choses** :

```
   TON ORDINATEUR                              UN SERVEUR
   (avec un client                             (qui chiffre/déchiffre
    comme AuroraVPN)        ←──tunnel──→        et fait le relais)
```

**AuroraVPN, c'est uniquement le client (ton côté).** Pour le serveur, tu
as 3 choix expliqués ci-dessous.

---

## Les 3 voies, du plus simple au plus libre

### 🟢 Voie 1 : ProtonVPN Free (le plus simple, marche dans 5 minutes)

Si tu veux **juste être protégé maintenant** et que tu te fiches de
"posséder" ton VPN, c'est la meilleure option.

**Ce que tu vas faire** :
1. Créer un compte gratuit sur ProtonVPN (suisse, sérieux, vraiment gratuit)
2. Installer leur application
3. Cliquer "Connecter"

C'est tout. Pas de serveur à créer, pas de carte bancaire, illimité à vie.

**Inconvénients** : tu n'utilises pas AuroraVPN (c'est leur app), tu n'as
que 3 pays au choix (Pays-Bas, USA, Japon), et tu ne possèdes pas le serveur.

#### Étapes

1. Va sur https://protonvpn.com/fr/free-vpn
2. Clique **"Get Proton VPN Free"** ou **"Créer un compte gratuit"**
3. Renseigne ton **email** et un **mot de passe**. **Pas besoin de carte.**
4. Tu reçois un email de confirmation → clique le lien.
5. Sur le site Proton, clique **"Télécharger"** → choisir **Windows**.
6. Lance le fichier `.exe` téléchargé, accepte l'installation.
7. Ouvre **Proton VPN**, connecte-toi avec ton email/mot de passe.
8. Clique le gros bouton **"Connexion rapide"**.
9. ✅ Tu es protégé. Vérifie sur https://ifconfig.me : ton IP a changé.

---

### 🟡 Voie 2 : Importer un fichier `.conf` que tu as déjà

Si quelqu'un t'a donné un fichier WireGuard `.conf` (un ami, ton travail,
un VPN payant qui propose ses configs), c'est très rapide.

**Ce que tu vas faire** :
1. Récupérer le fichier `.conf`
2. Lancer une commande pour l'importer dans AuroraVPN
3. Lancer AuroraVPN

#### Étapes

1. Place le fichier `.conf` quelque part de simple, par exemple le bureau
   ou directement dans `D:\Claude Code\AuroraVPN\`.
2. Installe WireGuard officiel (le moteur, AuroraVPN le pilote) :
   https://www.wireguard.com/install/ → télécharge l'installeur Windows,
   double-clic, accepte UAC.
3. Ouvre **PowerShell en tant qu'Administrateur** :
   - Clique sur le menu **Démarrer**
   - Tape **"PowerShell"**
   - **Clic droit** sur "Windows PowerShell" → **"Exécuter en tant qu'administrateur"**
   - Accepte l'UAC.
4. Dans la fenêtre PowerShell, tape :

   ```powershell
   cd "D:\Claude Code\AuroraVPN"
   python import_wireguard_config.py "C:\Users\TonNom\Desktop\fichier.conf" --name "Mon Serveur"
   ```

   (Remplace le chemin par celui de ton fichier `.conf` réel.)
5. Le script imprime "Termine" → ferme PowerShell.
6. Double-clique sur `AuroraVPN.bat`.
7. Windows demande l'élévation (UAC) → Accepte.
8. AuroraVPN se lance, se connecte automatiquement au vrai serveur.
9. ✅ Vérifie sur https://ifconfig.me que ton IP a changé.

---

### 🔵 Voie 3 : Créer ton propre serveur VPN (le plus libre)

Là tu deviens **vraiment indépendant**. C'est ce qu'utilisent les vrais
fans de vie privée. Tu loues ou récupères une machine, tu y installes
WireGuard, et c'est **ton VPN à toi pour toujours**.

Tu as 2 sous-choix selon ce que tu possèdes :

#### 🔵.A — Sur ta machine à la maison (le plus gratuit)

**Pré-requis** :
- Une machine que tu peux laisser **allumée tout le temps** :
  - Un Raspberry Pi (très bien, 5W, silencieux, ~30 € d'occasion)
  - Un vieux PC qui dort dans un placard
  - Ton PC fixe si tu le laisses toujours allumé
- Une **connexion Internet** (la tienne)
- Vérifier que **ton FAI n'est pas en CGNAT** (sinon ça ne marche pas
  depuis l'extérieur — voir DEPLOIEMENT_SANS_CARTE.md §1.6)

**Ce que tu vas faire** :
1. Installer Linux sur la machine (Ubuntu Server ou Raspberry Pi OS)
2. Te connecter en SSH depuis ton Windows
3. Lancer le script `install_wireguard.sh` qui fait tout
4. Configurer le port forwarding sur ton routeur
5. Récupérer le fichier `.conf` et l'importer dans AuroraVPN

##### Étape par étape (cas Raspberry Pi)

**A. Préparer la carte microSD**

1. Procure-toi une **carte microSD ≥ 8 Go** et un **lecteur** pour la
   brancher sur ton PC.
2. Télécharge **Raspberry Pi Imager** : https://www.raspberrypi.com/software/
3. Lance-le, choisis :
   - **CHOOSE DEVICE** : ton modèle de Pi
   - **CHOOSE OS** : Raspberry Pi OS (Other) → **Raspberry Pi OS Lite (64-bit)**
   - **CHOOSE STORAGE** : ta microSD
4. Avant de cliquer **"NEXT"** → **"EDIT SETTINGS"** :
   - Hostname : `aurora-pi`
   - **Enable SSH** : OUI, avec **mot de passe** (plus simple pour débuter)
   - Username : `aurora`, Password : choisis-en un solide
   - Configure Wireless LAN si pas de Ethernet : ton SSID + mot de passe Wi-Fi
   - Locale : ton fuseau horaire
5. **WRITE** → attendre ~10 minutes que ça flashe.

**B. Premier démarrage du Pi**

1. Insère la microSD dans le Pi.
2. Branche **éthernet** (préféré) ou laisse le Wi-Fi (si configuré).
3. Branche l'alimentation. Voyant rouge fixe + vert qui clignote = OK.
4. Attends ~1 minute le temps qu'il démarre.
5. Trouve son **IP locale** :
   - Soit dans ta box (page admin → liste des appareils, cherche
     `aurora-pi`)
   - Soit sur Windows, dans PowerShell :
     ```powershell
     arp -a | findstr "192.168"
     ```
     Et essaie de te connecter à chaque IP en ssh.

**C. Se connecter en SSH**

Sur Windows, ouvre **PowerShell** (pas besoin d'admin) :

```powershell
ssh aurora@192.168.1.42
```

(Remplace `192.168.1.42` par l'IP du Pi.)

Tape **"yes"** à la première connexion, puis le mot de passe que tu as
choisi à l'étape A4.

Tu es maintenant **dans** le Pi. Le prompt change : `aurora@aurora-pi:~ $`

**D. Coller et lancer le script d'installation**

Toujours sur le Pi (via SSH) :

```bash
nano install_wireguard.sh
```

Une fenêtre éditeur s'ouvre. **Maintenant, sur ton Windows** :
1. Ouvre l'Explorateur, va dans `D:\Claude Code\AuroraVPN\server_setup\`
2. Ouvre `install_wireguard.sh` avec le Bloc-notes
3. **Ctrl+A** (tout sélectionner), **Ctrl+C** (copier)

**Reviens dans la fenêtre PowerShell** où tu es connecté au Pi :
1. **Clic droit** dans la fenêtre PowerShell → ça colle automatiquement
   (ou Ctrl+Shift+V selon la version)
2. **Ctrl+O** (lettre O), **Enter** → sauvegarde
3. **Ctrl+X** → quitte l'éditeur

Tu es de retour au prompt. Lance :

```bash
chmod +x install_wireguard.sh
sudo ./install_wireguard.sh mon-pc
```

Il te demande le mot de passe `aurora` (celui de l'étape A4).

Le script tourne 60-90 secondes. À la fin :
- Tu vois en gros : `=== Client mon-pc cree ===`
- Le chemin du fichier : `/etc/wireguard/clients/mon-pc/mon-pc.conf`
- Un QR code dans le terminal (pour l'app mobile WireGuard si tu veux
  brancher ton téléphone aussi).

**E. Port forwarding sur ta box**

WireGuard tourne sur le Pi, MAIS personne ne peut s'y connecter de
l'extérieur tant que tu n'as pas dit à ta box : "le trafic UDP qui
arrive sur le port 51820, envoie-le au Pi".

Ouvre un navigateur, va sur la page admin de ta box :

| Box | Adresse |
|---|---|
| Freebox | http://mafreebox.freebox.fr |
| Livebox | http://192.168.1.1 |
| Bbox | http://192.168.1.254 |
| SFR Box | http://192.168.1.1 |
| Autre | regarde l'autocollant au dos de la box |

Connecte-toi (login/mot de passe sur l'autocollant si tu n'as jamais changé).

Cherche **"Redirection de ports"** ou **"NAT/PAT"** ou **"Gestion des ports"**.
Ajoute une règle :
- Protocole : **UDP**
- Port externe : **51820**
- IP interne : celle du Pi (192.168.1.42)
- Port interne : **51820**

Sauvegarde, redémarre la box si demandé.

**Astuce importante** : dans la section **DHCP**, réserve l'IP du Pi pour
qu'elle ne change jamais (sinon le port forwarding pointera dans le vide
au prochain reboot).

**F. (Optionnel mais recommandé) DuckDNS pour suivre ton IP qui change**

Ton IP publique (celle que voit l'extérieur) change probablement chaque
jour. Solution gratuite : **DuckDNS**.

1. https://www.duckdns.org → login Google ou autre
2. Crée `monvpnaurora.duckdns.org` (mets un nom unique)
3. Note ton **token** (en haut de la page)
4. Sur le Pi :

   ```bash
   mkdir -p ~/duckdns && cd ~/duckdns
   nano duck.sh
   ```

   Colle :
   ```bash
   echo url="https://www.duckdns.org/update?domains=monvpnaurora&token=TON_TOKEN_ICI&ip=" | curl -k -o ~/duckdns/duck.log -K -
   ```

   Remplace `monvpnaurora` et `TON_TOKEN_ICI` par tes vrais valeurs.
   Sauvegarde (Ctrl+O Enter, Ctrl+X).

   ```bash
   chmod 700 duck.sh
   ./duck.sh
   cat duck.log     # doit afficher OK
   (crontab -l 2>/dev/null; echo "*/5 * * * * /home/aurora/duckdns/duck.sh >/dev/null 2>&1") | crontab -
   ```

5. **Modifie le `.conf` client** : ouvre-le (`sudo nano /etc/wireguard/clients/mon-pc/mon-pc.conf`)
   et remplace la ligne `Endpoint = 81.123.45.67:51820` par
   `Endpoint = monvpnaurora.duckdns.org:51820`. Sauvegarde.

**G. Rapatrier le `.conf` sur Windows**

Sur Windows, dans PowerShell :

```powershell
scp aurora@192.168.1.42:/etc/wireguard/clients/mon-pc/mon-pc.conf "D:\Claude Code\AuroraVPN\mon-pc.conf"
```

(Ou affiche-le sur le Pi avec `sudo cat /etc/wireguard/clients/mon-pc/mon-pc.conf`,
copie-colle dans un nouveau fichier Bloc-notes sur Windows, sauvegarde
en `.conf`.)

**H. Importer dans AuroraVPN**

PowerShell **en tant qu'Administrateur** :

```powershell
cd "D:\Claude Code\AuroraVPN"
python import_wireguard_config.py mon-pc.conf --name "Chez moi"
```

**I. Lancer**

Installe WireGuard officiel s'il n'est pas déjà installé :
https://www.wireguard.com/install/

Double-clique sur `AuroraVPN.bat`. Accepte UAC. C'est connecté.

✅ Test final : https://ifconfig.me → tu dois voir **l'IP publique de
chez toi** (celle de la box), pas une autre. Ça veut dire que ton trafic
passe par TON serveur à toi. 🎉

---

#### 🔵.B — Sur Oracle Cloud (gratuit mais demande une carte pour vérification)

Si tu **acceptes finalement de donner une CB pour la vérification** (sans
débit, juste de l'identité), Oracle te donne **gratuitement à vie** un
serveur en Allemagne avec 4 cœurs ARM et 24 Go RAM. C'est beaucoup mieux
qu'un Raspberry Pi.

Procédure complète dans `DEPLOIEMENT_GRATUIT.md` — c'est le même
principe (script `install_wireguard.sh` puis `import_wireguard_config.py`),
juste avec une machine dans le cloud au lieu d'une chez toi.

---

## Connecter AuroraVPN une fois tout configuré

Une fois que l'import est fait (voie 2 ou voie 3), c'est très simple :

1. **Double-clique sur `AuroraVPN.bat`** (dans `D:\Claude Code\AuroraVPN\`)
2. Windows demande UAC → Accepte
3. La fenêtre AuroraVPN s'ouvre
4. Si tu as activé l'auto-connexion (par défaut quand tu utilises le
   launcher), elle se connecte toute seule au bout de 800 ms
5. Sinon, clique sur **CONNECTER** (gros bouton violet au milieu)

Tu vois :
- L'orb passe gris → cyan pulsant (en cours) → vert pulsant (connecté)
- Le footer affiche l'**IP publique** : celle de ton serveur, pas la tienne
- Le compteur de durée démarre
- Notification Windows en bas à droite : "Tunnel actif"

Pour **déconnecter** : clic sur le même bouton (devenu "DÉCONNECTER").

---

## Démarrage automatique avec Windows

Si tu veux qu'AuroraVPN se lance et se connecte à chaque démarrage de
Windows, double-clique une seule fois sur **`Installer_Demarrage_Windows.cmd`**.

Pour le désactiver : **`Desinstaller_Demarrage_Windows.cmd`**.

---

## Erreurs courantes et solutions

| Erreur | Cause probable | Solution |
|---|---|---|
| "Python n'est pas reconnu" | Python pas installé ou pas dans le PATH | Installe Python 3.10+ : https://python.org → coche "Add to PATH" pendant l'install |
| "Permission denied" en SSH | Mauvais nom utilisateur ou mot de passe | Re-vérifie l'utilisateur (`aurora` pour Pi, `ubuntu` pour Oracle, `root` ailleurs) et le mot de passe |
| "Connection refused" en SSH | Le serveur n'est pas démarré ou IP fausse | Refais la procédure pour trouver l'IP locale du Pi |
| AuroraVPN.bat se ferme tout seul | wireguard.exe pas installé ou pas admin | Installe WireGuard officiel, relance en admin |
| "Could not start tunnel" | Port forwarding pas bon, ou CGNAT | Vérifie la règle sur la box, teste le CGNAT |
| Mon IP ne change pas après connexion | Le tunnel n'est pas vraiment monté | Regarde `wg show` sur le serveur, le `latest handshake` doit être récent |
| Internet coupé après connexion | Le tunnel a remplacé la route par défaut mais le serveur ne fait pas le NAT | Sur le serveur, vérifie `sudo iptables -t nat -L POSTROUTING` |

---

## Lexique pour débutant

| Mot | Signification simple |
|---|---|
| **VPN** | Tunnel chiffré entre ton appareil et un serveur ailleurs. |
| **Client** | L'app sur ton appareil (ex: AuroraVPN). |
| **Serveur** | La machine au bout du tunnel (chez toi, dans le cloud, etc.). |
| **WireGuard** | Le "moteur" qui fait le chiffrement (rapide, moderne, open source). |
| **IP publique** | L'adresse visible de toi sur Internet (que tout le monde voit). |
| **CGNAT** | Quand ton FAI te met derrière un gros NAT partagé → tu n'as pas d'IP publique directe. |
| **SSH** | Connexion à distance sécurisée à un serveur Linux (terminal). |
| **Port forwarding** | Règle sur ta box qui dit "le trafic externe sur tel port, envoie-le à telle machine interne". |
| **DDNS** (Dynamic DNS) | Nom de domaine qui suit ton IP qui change (DuckDNS, etc.). |
| **UAC** | "User Account Control" Windows. La fenêtre bleue qui demande "Voulez-vous que cette app modifie votre PC ?" |
| **`.conf`** | Fichier texte WireGuard avec les clés et l'adresse du serveur. |
| **PowerShell** | Terminal Windows. Comme l'invite de commandes mais plus moderne. |
| **Raspberry Pi** | Mini-ordinateur de la taille d'une carte bancaire (~30-80 €). |
| **Ubuntu** | Distribution Linux populaire, utilisée par défaut sur Oracle/Hetzner. |
| **Cron** | Système Linux qui exécute des tâches automatiquement à intervalles réguliers. |

---

## Récap visuel des fichiers d'aide

| Fichier | Pour |
|---|---|
| **Ce guide** (`GUIDE_DEBUTANT.md`) | Commencer de zéro |
| `DEPLOIEMENT_SANS_CARTE.md` | Détails des 3 voies gratuites sans CB |
| `DEPLOIEMENT_GRATUIT.md` | Oracle Cloud (carte requise mais 0 €) |
| `DEPLOIEMENT_SERVEUR.md` | Hébergeurs payants (Hetzner, OVH, etc.) |
| `JURIDICTION.md` | Pour faire ça en société (avancé) |
| `CONCEPTION.md` | La doc technique du projet |
| `README.md` | Vue d'ensemble |

---

Tu peux poser n'importe quelle question en m'écrivant. Bon courage 🚀
