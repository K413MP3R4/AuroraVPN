# Avoir un vrai VPN sans payer **et sans carte bancaire**

> Trois voies réalistes. La 1ʳᵉ est la seule où tu possèdes vraiment ton
> serveur. Les 2 autres utilisent des services tiers gratuits et solides.

---

## Diagnostic rapide : laquelle pour toi ?

```
                    Tu as un Raspberry Pi ou un vieux PC ?
                                    │
                ┌───────────────────┴───────────────────┐
                ▼ OUI                                  ▼ NON
        ┌────────────────┐                  ┌────────────────────┐
        │  Auto-heberger │                  │ Tu veux ton propre │
        │  chez toi (§1) │                  │  serveur ?         │
        │  GRATUIT A VIE │                  └─────────┬──────────┘
        └────────────────┘                            │
                                          ┌───────────┴───────────┐
                                          ▼ OUI                  ▼ NON
                                  ┌──────────────────┐  ┌──────────────────┐
                                  │ Pas possible     │  │ ProtonVPN Free   │
                                  │ sans carte +     │  │      (§2)        │
                                  │ sans matos.      │  │ Suisse, illimite │
                                  │ Achete un Pi     │  │ 3 pays           │
                                  │ d'occasion ~25 € │  └──────────────────┘
                                  └──────────────────┘             ou
                                                          ┌──────────────────┐
                                                          │  Tailscale Free  │
                                                          │      (§3)        │
                                                          │  Mesh entre tes  │
                                                          │  appareils       │
                                                          └──────────────────┘
```

---

## Option 1 — Auto-hébergement (la seule façon d'avoir TON serveur sans carte)

### Pré-requis

- **Une machine qui tourne 24/24** chez toi :
  - Raspberry Pi 3B+ ou 4 (idéal, 5W, silencieux)
  - Un vieux PC, mini-PC, NAS Synology/QNAP
  - Ton ordinateur de bureau (si tu le laisses allumé en permanence)
- **Une connexion Internet** chez toi (que tu as déjà)
- **Un accès admin à ton routeur** (pour le port forwarding)
- ⚠️ **PAS de CGNAT** : test sur https://am.i.behind.nat-or-cgnat.com ou
  compare l'IP affichée par https://ifconfig.me avec l'IP WAN de ton routeur.
  Si elles diffèrent → CGNAT → tu dois passer par un relais (cf. §1.5).

### 1.1 Si tu n'as PAS de matériel

Avant de renoncer :

- **Demander autour de toi** : 90% des gens ont un vieux PC ou laptop au placard
- **Leboncoin / Vinted** : Raspberry Pi 3B+ d'occasion ~20-30 €, Pi 4 ~40-60 €
- **Reconditionné** : mini-PC ex-entreprise sur https://backmarket.fr ~50-100 €
- **Récupération** : déchetterie, asso "Repair Café", parents/amis

Ces ~30 € sont un investissement à vie (5-10 ans de service VPN gratuit).

### 1.2 Installation (Raspberry Pi → exemple type)

1. Télécharger **Raspberry Pi Imager** : https://www.raspberrypi.com/software/
2. Flasher **Raspberry Pi OS Lite (64-bit)** sur une carte microSD ≥ 8 Go
3. Dans les **réglages avancés** d'Imager (icône ⚙) :
   - Nom d'hôte : `aurora-pi`
   - SSH activé, ton utilisateur (ex `aurora`) + mot de passe ou clé
   - Wi-Fi configuré OU branchement Ethernet (préféré, plus fiable)
4. Insérer la carte, brancher l'alimentation
5. Trouver l'IP locale : sur Windows `arp -a | findstr aurora-pi`
   ou via la page admin du routeur (liste des appareils connectés)

### 1.3 Installer WireGuard

```bash
ssh aurora@192.168.1.42   # remplace par l'IP de ton Pi

# Coller le script install_wireguard.sh
nano install_wireguard.sh
# (coller le contenu depuis D:\Claude Code\AuroraVPN\server_setup\)
# Ctrl+O Enter pour sauvegarder, Ctrl+X pour quitter
chmod +x install_wireguard.sh

sudo ./install_wireguard.sh mon-pc
```

Durée : **60-90 secondes**. À la fin, tu vois le `.conf` à récupérer.

### 1.4 Port forwarding sur ton routeur

Connecte-toi à la page admin de ton routeur (en général `192.168.1.1`,
`192.168.0.1`, ou `192.168.1.254`). Pour les box françaises :

| Box | Adresse admin | Section |
|---|---|---|
| Freebox | http://mafreebox.freebox.fr | Paramètres → Gestion des ports |
| Livebox (Orange) | http://192.168.1.1 | Réseau → NAT/PAT |
| Bbox (Bouygues) | http://192.168.1.254 | Services de la Bbox → Redirection de ports |
| SFR Box | http://192.168.1.1 | Réseau → NAT |

Créer une règle :
- **Protocole** : UDP
- **Port externe** : 51820
- **IP interne** : celle du Pi (ex 192.168.1.42)
- **Port interne** : 51820

Penser à **réserver l'IP** locale du Pi (DHCP Reservation) pour qu'elle ne change pas.

### 1.5 IP dynamique = DuckDNS gratuit

Ton IP publique change probablement chaque jour. Solution gratuite :

1. https://www.duckdns.org → login Google/Twitter/GitHub
2. Créer `monvpn.duckdns.org` (instantané)
3. Copier ton token (sera affiché en haut)
4. Sur le Pi :

```bash
mkdir -p ~/duckdns && cd ~/duckdns
cat > duck.sh <<'EOF'
echo url="https://www.duckdns.org/update?domains=monvpn&token=TON_TOKEN&ip=" \
  | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod 700 duck.sh
./duck.sh   # test : doit afficher "OK"

# Auto toutes les 5 min
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/aurora/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

5. Dans le `.conf` client, remplacer l'IP par `monvpn.duckdns.org:51820`,
   puis réimporter avec `import_wireguard_config.py`.

### 1.6 Si tu es en CGNAT (très courant en 4G, Starlink, certains FAI)

Le port forwarding ne suffit pas car ton routeur n'a pas une vraie IP publique.

**Solutions gratuites** :
- **Demander à ton FAI** la sortie du CGNAT : appelle le support, demande
  "passage en IPv4 full-stack". Souvent gratuit chez Free (oui) et Orange,
  parfois payant chez les autres.
- **Tailscale** (option 3) : contourne complètement le CGNAT car c'est un
  mesh qui établit les connexions à travers ses serveurs NAT-traversal.

---

## Option 2 — ProtonVPN Free (vrai VPN, vrais serveurs, vrai zéro €)

### Quand l'utiliser

Si tu n'as **pas de matériel** et tu veux juste **un VPN qui marche
maintenant**, ProtonVPN Free est la seule option crédible :

- ✅ Gratuit à vie
- ✅ **Aucune carte demandée** (juste un email)
- ✅ Société **suisse** (LPD/RGPD), audit no-logs publié
- ✅ **Bande passante illimitée** sur le tier gratuit (unique sur le marché)
- ✅ Open source côté client
- ✅ Kill switch, DNS chiffré, IPv6 leak protection
- ⚠️ **3 pays seulement** sur le free : Pays-Bas, États-Unis, Japon
- ⚠️ Vitesse plus lente que le payant (priorité aux clients premium)
- ⚠️ **Pas de streaming Netflix** sur le free (mais marche pour usage normal)

### Étapes

1. https://protonvpn.com/fr/free-vpn → **Créer un compte gratuit**
2. Email + mot de passe (avec ou sans Proton Mail, peu importe)
3. Validation email
4. Télécharger le **client officiel Windows** :
   https://protonvpn.com/fr/download-windows
5. Installer, se connecter avec son compte
6. Cliquer sur **Quick Connect**. Voilà. Tu es protégé.

### Pourquoi pas avec AuroraVPN ?

ProtonVPN ne distribue PAS les configs WireGuard brutes sur le tier
gratuit, donc on ne peut pas les importer dans AuroraVPN. **Tu utiliseras
leur client à la place du nôtre.** Pas de honte : c'est un excellent
client, parmi les meilleurs.

Tu peux garder AuroraVPN pour ton apprentissage / démonstration et
utiliser ProtonVPN Free pour la protection quotidienne réelle.

### Alternatives gratuites équivalentes (sans carte)

- **Windscribe Free** — 10 Go/mois, 11 pays, Canadien
- **TunnelBear Free** — 2 Go/mois, 47 pays, propriété McAfee
- **Hide.me Free** — 10 Go/mois, 8 pays

ProtonVPN reste le meilleur : c'est le seul **illimité** gratuit.

---

## Option 3 — Tailscale Free (ton propre mesh VPN)

### C'est quoi

Tailscale est un VPN **mesh** basé sur WireGuard. Au lieu d'avoir un
serveur central, **chacun de tes appareils** (PC, téléphone, Pi, serveur
distant) devient un nœud dans un réseau privé chiffré entre eux.

- ✅ Gratuit pour usage personnel (jusqu'à **100 appareils**, **3 utilisateurs**)
- ✅ **Aucune carte** (login Google/Microsoft/GitHub/Apple)
- ✅ Marche **derrière CGNAT** sans config réseau
- ✅ Aussi sécurisé que WireGuard (c'est la même base)
- ✅ Setup en **5 minutes**
- ⚠️ **Pas exactement la même chose** qu'un VPN traditionnel : tu te
  connectes à TES PROPRES appareils. Pour "changer ton IP publique", tu
  dois désigner un de tes appareils comme **exit node** (= un appareil
  qui a une connexion Internet, par exemple ton PC à la maison).
- ⚠️ Le **coordination server** est chez Tailscale (open source si tu veux
  voir : `headscale` est l'alternative self-hosted).

### Cas d'usage idéaux

- Accéder à ton PC fixe depuis ton laptop en déplacement (comme un retour
  à la maison)
- Partager des fichiers entre tes appareils sans Internet
- Faire passer ton trafic du laptop au travers de ton PC maison (exit node)
  → équivalent VPN "je me connecte à mon Internet depuis ailleurs"

### Étapes

1. https://tailscale.com/download → installer le client Windows
2. Cliquer **Sign in** → connexion Google ou autre (pas de carte)
3. Installer Tailscale sur un **second appareil** (PC, Pi, téléphone)
4. Tu vois tes 2 appareils dans la même icône réseau. Ils peuvent
   communiquer entre eux via des IPs `100.x.x.x`.
5. **Pour usage VPN exit node** :
   - Sur ton PC fixe à la maison (ou Pi) :
     ```bash
     sudo tailscale up --advertise-exit-node
     ```
   - Sur l'admin web Tailscale : approuver l'exit node
   - Sur ton laptop : `tailscale up --exit-node=mon-pc-fixe`
   - Tout ton trafic Internet sort par ton PC fixe → IP publique = celle de chez toi

---

## Tableau récap

| Besoin | Choix |
|---|---|
| Je veux MON serveur et j'ai du matériel | Option 1 (auto-héberger) |
| Je veux MON serveur mais pas de matériel | Achète un Pi d'occasion 30 €, puis option 1 |
| Je veux juste une protection VPN maintenant | Option 2 (ProtonVPN Free) |
| Je veux relier mes appareils entre eux + exit node | Option 3 (Tailscale) |
| Je veux conjuguer AuroraVPN + un vrai serveur | Option 1 uniquement (les autres ne donnent pas de .conf WireGuard) |

---

## Mon conseil concret pour toi

1. **Tu as un PC sous la main ?** → Option 1, en mettant ton PC fixe ou
   un mini-PC en serveur. Coût zéro absolu.
2. **Tu n'as rien et pas envie d'acheter** → Option 2 (ProtonVPN Free) en
   complément d'AuroraVPN qui reste un beau projet à montrer / tester.
3. **Tu veux apprendre + connecter tous tes appareils** → Option 3
   (Tailscale) en plus du reste.

Tu peux même **combiner** : Tailscale entre tes appareils + ProtonVPN
Free pour cacher ton IP publique vis-à-vis de l'extérieur, le tout 100%
gratuit sans carte.

Bon courage 🚀
