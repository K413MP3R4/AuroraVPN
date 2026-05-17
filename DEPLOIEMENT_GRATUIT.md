# Déployer AuroraVPN **gratuitement**

> Trois voies sans dépenser un centime. Sécurité et perf comparables aux
> options payantes, plus quelques contraintes à connaître.

---

## Tableau comparatif

| Option | Coût | Pérennité | Performance | Difficulté |
|---|---|---|---|---|
| **Oracle Cloud Always Free** | 0 € à vie | Sans limite de temps | 4 vCPU ARM + 24 Go RAM, 10 To/mois | Moyenne |
| **Auto-hébergement (Pi / PC)** | 0 € (matériel déjà là) | Tant que la machine tourne | Limité par ton upload ADSL/Fibre | Moyenne+ |
| **Crédits trial payants** | 0 € pendant N jours | 30 j à 12 mois | Excellente | Facile |

**Recommandation** : **Oracle Cloud Always Free** est le meilleur compromis
pour un VPN personnel — c'est ce que ferait un développeur expérimenté.

---

## Option 1 — Oracle Cloud Always Free (★★★★★)

### Pourquoi c'est imbattable

Oracle propose **réellement gratuit à vie** (pas un trial qui expire) :

- **Soit 2 VM AMD** `VM.Standard.E2.1.Micro` (1 vCPU, 1 Go RAM chacune)
- **Soit 4 cœurs ARM Ampere A1** avec **jusqu'à 24 Go RAM** au total

→ Tu peux choisir la version ARM : c'est 4 cœurs + 6 Go par VM, ce qui est
**énorme** pour un VPN personnel. Largement de quoi tenir 50+ utilisateurs.

Plus :
- **10 To de bande passante sortante par mois** (le besoin moyen perso : 1-2 To)
- Datacenters européens : **Francfort, Marseille, Madrid, Stockholm**
- Adresse IPv4 publique fixe
- Tu peux créer **plusieurs serveurs gratuits** (1 par région)

### Étapes

#### 1.1 Créer un compte Oracle Cloud

1. Aller sur https://www.oracle.com/cloud/free/
2. **Start for free** → renseigner email, téléphone, **carte bancaire**
   (vérification d'identité uniquement, **aucun débit** si tu restes dans
   le tier gratuit). Une carte virtuelle Revolut ou N26 fonctionne.
3. Région d'inscription : choisir **Frankfurt** ou **Marseille** (UE/RGPD).
   ⚠️ Le choix est **définitif**, on ne peut plus le changer après.
4. Validation par téléphone (SMS).
5. Compte créé en ~10 minutes.

#### 1.2 Créer la VM Always Free

1. Console → **Compute** → **Instances** → **Create Instance**
2. Nom : `aurora-vpn-fr`
3. **Image** : `Canonical Ubuntu 22.04`
4. **Shape** :
   - Cliquer **Change shape** → **Ampere** → `VM.Standard.A1.Flex`
   - **Number of OCPUs** : 1 (suffisant pour le VPN)
   - **Amount of memory** : 6 Go
   - → tu vois "Always Free Eligible" en vert
5. **Networking** :
   - Garder VCN par défaut (Oracle en crée un)
   - **Assign a public IPv4 address** : OUI
6. **SSH key** :
   - **Generate SSH key pair for me** → télécharger la clé privée
     (`ssh-key-XXXX.key`) ET la clé publique
   - Stocker la clé privée dans `D:\Claude Code\AuroraVPN\oracle-vpn.key`
7. **Create**. Délai ~30 secondes.
8. Une fois "RUNNING", noter l'**IP publique** (ex : `141.94.123.45`).

#### 1.3 Ouvrir le port UDP 51820 (TRÈS IMPORTANT)

Oracle bloque **tout** le trafic entrant par défaut, même UDP. Il faut :

**A. Security List (firewall cloud)**

1. Instance → **Virtual cloud network** → cliquer le nom du VCN
2. **Security Lists** → cliquer celle par défaut
3. **Add Ingress Rules** :
   - Source CIDR : `0.0.0.0/0`
   - IP Protocol : `UDP`
   - Destination Port Range : `51820`
   - Description : `AuroraVPN WireGuard`
   - **Add Ingress Rules**

**B. iptables local (déjà géré par le script install_wireguard.sh)**

Le script v2 (mis à jour) détecte Oracle Cloud et insère les bonnes
règles iptables avant la règle `REJECT` par défaut. Aucune action manuelle
de ton côté.

#### 1.4 Se connecter en SSH

Sur Windows (PowerShell) :

```powershell
# Permissions strictes sur la clé (sinon SSH refuse)
icacls "D:\Claude Code\AuroraVPN\oracle-vpn.key" /inheritance:r /grant:r "%username%:R"

# Connexion (l'utilisateur Ubuntu sur Oracle est "ubuntu", pas "root")
ssh -i "D:\Claude Code\AuroraVPN\oracle-vpn.key" ubuntu@141.94.123.45
```

#### 1.5 Lancer le provisioning

Sur le serveur :

```bash
# Telecharger ou coller install_wireguard.sh
nano install_wireguard.sh
# (coller le contenu, Ctrl+O Enter, Ctrl+X)
chmod +x install_wireguard.sh

# Lancer en root (Oracle utilise sudo)
sudo ./install_wireguard.sh mon-pc
```

Le script détecte automatiquement Oracle Cloud (`/etc/oci-hostname.conf`)
et insère les règles iptables nécessaires.

Récupérer le `.conf` comme expliqué dans `DEPLOIEMENT_SERVEUR.md` §5.

### Risques Oracle Cloud

- **Suppression pour inactivité** : si la VM n'utilise pas de CPU pendant
  7 jours, Oracle peut la "réclamer". Solution : un cron qui ping
  l'extérieur toutes les heures (`*/60 * * * * curl -s https://example.com >/dev/null`).
- **Compte fermé sans préavis** : Oracle a la réputation de fermer des
  comptes free tier sans explication. Sauvegarder ta config WireGuard
  (clés serveur + clients) régulièrement.
- **Performance ARM** : 99% des logiciels marchent. WireGuard est natif ARM
  (excellentes perf, parfois meilleures que x86).

---

## Option 2 — Auto-hébergement (Raspberry Pi / vieux PC)

### Le matériel suffit-il ?

| Matériel | OK pour VPN perso ? | Note |
|---|---|---|
| Raspberry Pi 3B+ / 4 | Oui (jusqu'à ~100 Mbps) | Idéal, 5W, silencieux |
| Vieux laptop / desktop | Oui | Sur-dimensionné, consomme +ressources |
| NAS Synology / QNAP | Oui (paquet WireGuard officiel) | Encore plus simple |
| Mini PC chinois (~50 €) | Oui | Très bon ratio |

### Pré-requis ISP

⚠️ **Vérifie d'abord que tu n'es pas en CGNAT** (Carrier-Grade NAT).
Si tu es derrière du CGNAT, ton routeur n'a pas d'IP publique directement
accessible. Test :

```
Va sur https://am.i.behind.a.nat.com   (ou)
Compare l'IP affichée par https://ifconfig.me
Avec celle visible sur la page admin de ton routeur (interface WAN).
Si elles sont DIFFERENTES → CGNAT → tu dois passer par un relais (cf. §2.5).
```

Si IP identiques (= pas de CGNAT), tu peux continuer.

### 2.1 Installer le système

#### Raspberry Pi

1. Télécharger **Raspberry Pi Imager** : https://www.raspberrypi.com/software/
2. Flasher **Raspberry Pi OS Lite (64-bit)** sur la carte SD
3. Pré-configurer : nom d'hôte `aurora-pi`, SSH activé, ton utilisateur, ta clé SSH
4. Insérer la carte, brancher RJ45 (Wi-Fi possible mais moins fiable)
5. Trouver son IP locale : `arp -a | findstr aurora-pi`

#### Vieux PC

Installer **Ubuntu Server 22.04** (1 Go RAM suffit). Désactiver l'écran de veille.

### 2.2 Provisioning WireGuard

Identique au script standard. SSH :

```bash
ssh aurora@<IP-locale>
wget https://raw.githubusercontent.com/<repo>/install_wireguard.sh
chmod +x install_wireguard.sh
sudo ./install_wireguard.sh mon-pc
```

### 2.3 Port forwarding sur le routeur

Trouver la page admin du routeur (généralement `192.168.0.1`, `192.168.1.1`,
`192.168.1.254`, etc.). Connecter avec admin/mot-de-passe.

Section habituelle : **NAT / Port Forwarding / Redirection de ports**

- Nom : `WireGuard`
- Protocole : `UDP`
- Port externe : `51820`
- IP interne : IP locale du Pi/PC (ex `192.168.1.50`)
- Port interne : `51820`
- → Sauvegarder + redémarrer le routeur

Astuce : réserver l'IP locale du serveur (**DHCP Reservation**) pour qu'elle
ne change jamais.

### 2.4 DNS dynamique (DuckDNS, FreeDNS, No-IP)

Ton IP publique change probablement (sauf abonnement IP fixe). Solution :
un nom de domaine dynamique qui pointe toujours sur ton IP du moment.

**Recommandation : DuckDNS** (gratuit, open source, ultra simple) :

1. https://www.duckdns.org → se connecter avec Google/Twitter/GitHub
2. Créer un sous-domaine : `monvpn.duckdns.org` (gratuit, instantané)
3. Copier ton token
4. Sur le serveur Pi/PC :

```bash
mkdir -p ~/duckdns && cd ~/duckdns
cat > duck.sh <<EOF
echo url="https://www.duckdns.org/update?domains=monvpn&token=<TON_TOKEN>&ip=" \
  | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod 700 duck.sh
./duck.sh   # premier test (le log doit contenir "OK")

# Cron toutes les 5 minutes
crontab -l 2>/dev/null > mycron
echo "*/5 * * * * /home/aurora/duckdns/duck.sh >/dev/null 2>&1" >> mycron
crontab mycron && rm mycron
```

5. Modifier le `.conf` client : remplacer l'IP par `monvpn.duckdns.org:51820`
   et réimporter dans AuroraVPN.

### 2.5 Si tu es en CGNAT

Solutions de contournement :

- **Demander une IPv4 publique** à ton FAI (souvent gratuit chez Free, Orange,
  payant ~3 €/mois chez d'autres). Appel téléphonique, demander "désactivation
  du CGNAT" ou "passage en IPv4 full-stack".
- **Cloudflare Tunnel** (gratuit) : crée un tunnel sortant vers Cloudflare
  qui expose ton service. WireGuard sur UDP ne marche pas sur Cloudflare
  Tunnel (qui est HTTP), donc nécessite SSH/HTTP. Plutôt complexe pour VPN.
- **Tailscale Funnel / ngrok** : pour exposer un port UDP, ngrok payant, ce
  qui défait l'intérêt "gratuit".
- **Passer chez un FAI sans CGNAT** : Free (IPv4 full), Bouygues fibre.

### Limites de l'auto-hébergement

- **Upload limité** : ton VPN est plafonné à l'**upload** de ton accès Internet
  (ADSL 1 Mbps = 1 Mbps max VPN ; fibre 500/500 = beaucoup mieux).
- **Géolocalisation** : ton IP "VPN" est ton IP maison → tu ne déplaces pas
  ta localisation, juste tu chiffres le trafic entre tes appareils et chez toi.
- **Quota mensuel** : si ton FAI a un quota (rare en fibre, encore courant
  en 4G/Starlink), le VPN compte dedans.
- **Couper le courant chez toi = VPN coupé partout**.

---

## Option 3 — Crédits trial payants

Pas gratuit à vie, mais 0 € pendant la période :

| Provider | Crédit offert | Validité | Note |
|---|---|---|---|
| DigitalOcean | 200 $ | 60 jours | Suffit largement |
| Vultr | 100 $ | 14-30 jours | Court mais utilisable |
| Linode (Akamai) | 100 $ | 60 jours | Bon |
| Hetzner | Parfois 20 € via parrainage | 1 mois | Cherche un code parrainage |
| Scaleway | 100 € | 1 mois | Souvent renouvelable |

Utilisation : carte bancaire requise, débitée après expiration si tu ne
résilies pas. **Mettre un rappel calendrier** la veille de l'expiration.

Recommandé : DigitalOcean (200 $ / 60 j) si tu veux **tester sans risque
ni engagement**. Tu y mets ton serveur, tu valides que ça marche, et tu
migres vers Oracle Always Free avant l'expiration.

---

## Tableau final : pour qui ?

| Profil | Choix recommandé |
|---|---|
| Débutant, jamais touché à un VPS | **Oracle Always Free** (option 1) |
| Geek, déjà un Raspberry Pi à la maison | **Auto-hébergement** (option 2) |
| Veut tester rapidement, sans paperasse Oracle | **DigitalOcean trial** puis migration |
| Ne veut RIEN payer même en validation CB | **Auto-hébergement** ou demander à un ami de prêter un coin de VPS |

---

## Suite

Une fois ton serveur en place (peu importe l'option), reprendre
`DEPLOIEMENT_SERVEUR.md` à partir du §5 (récupération du `.conf` et
import dans AuroraVPN).

Bonne route 🚀
