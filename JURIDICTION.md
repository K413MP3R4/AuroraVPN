# AuroraVPN — Juridiction Suisse, serveurs RAM-only, audit no-logs

> Document stratégique : pourquoi la Suisse, comment monter une infra
> conforme, comment déclencher un audit no-logs externe et comment
> communiquer dessus. Complément du `CONCEPTION.md`.

---

## 1. Pourquoi une juridiction Suisse

| Critère | Suisse | États-Unis | Royaume-Uni | France |
|---|---|---|---|---|
| Loi sur la conservation obligatoire des données réseau | **Non** (FAI uniquement, pas les VPN) | Patriot Act | IPA 2016 | LCEN |
| Obligation de logs pour fournisseur VPN | **Non** | Variable | Oui (data retention) | 1 an |
| Adhésion 5/9/14 Eyes | **Non** | 5 Eyes | 5 Eyes | 9 Eyes |
| Force du secret professionnel (LPD/RGPD) | LPD 2023 + RGPD si EU | CCPA/HIPAA | UK GDPR | RGPD |
| Confiance utilisateur perçue | **Très élevée** | Moyenne | Faible | Moyenne |

La Suisse combine trois propriétés rares : **pas d'obligation de logs**
pour les fournisseurs de communication anonymisée, **pas d'appartenance**
aux alliances de renseignement *Eyes*, et la **LPD 2023** alignée RGPD.
ProtonVPN et plusieurs concurrents l'ont choisie pour ces raisons.

---

## 2. Étapes pour établir une entité Suisse

### 2.1 Forme juridique

- **GmbH (Sàrl)** : capital minimum 20 000 CHF, gestion souple, idéal pour démarrer.
- **AG (SA)** : capital 100 000 CHF (50 000 libérés), nécessaire pour lever des fonds.

Recommandation pour un VPN début 2026 : **Sàrl** dans le canton de Zoug, Genève ou Vaud.

### 2.2 Banque, domiciliation, RC

1. Réserver le nom au Registre du Commerce cantonal.
2. Ouvrir un compte de capital bloqué (Postfinance, Raiffeisen, BCV...).
3. Déposer les statuts chez un notaire.
4. Inscription au RC.
5. Immatriculation TVA (si CA > 100 000 CHF).
6. Adhésion à l'AVS et à la LPP pour les salariés.

Coût total typique : 3 000 à 8 000 CHF, délai 4 à 8 semaines.

### 2.3 Conformité LPD 2023

- Nommer un **DPO** (Data Protection Officer) si traitement de données sensibles à grande échelle.
- Tenir un **registre des traitements** (art. 12 LPD).
- Notifier les violations de données au PFPDT sous 72 h.
- Pas d'obligation de RGPD si vous n'avez pas d'utilisateurs UE — mais
  comme le marché cible est mondial, autant adopter RGPD comme socle commun.

### 2.4 Convention avec les utilisateurs

CGU + politique de confidentialité doivent indiquer noir sur blanc :
- la **juridiction Suisse exclusive**,
- les **données minimales collectées** (email, état du paiement),
- l'absence de logs réseau (à prouver par audit, voir §4).

---

## 3. Infrastructure serveurs RAM-only

### 3.1 Principe

Tous les services VPN tournent sur un **disque virtuel en mémoire vive**
(`tmpfs` Linux). Au moindre redémarrage, **rien ne subsiste** : pas de
logs, pas de traces, pas de récupération forensique possible.

### 3.2 Choix du fournisseur

| Hébergeur | RAM-only possible | Juridiction du datacenter | Bare metal disponible |
|---|---|---|---|
| **DataPacket / M247** | Oui (PXE boot) | Multi-pays | Oui |
| **Hetzner** | Oui (rescue + tmpfs) | DE, FI, US | Oui |
| **OVH BareMetal** | Oui | FR, CA, US, DE | Oui |
| **Quickpacket** | Oui | US | Oui |

Pour une infra crédible, prévoir **20 à 50 serveurs bare-metal**
répartis sur 4 continents minimum.

### 3.3 Boot diskless

```bash
# /etc/fstab (sur le serveur)
tmpfs    /var/log              tmpfs   defaults,noatime,size=512M  0  0
tmpfs    /etc/wireguard        tmpfs   defaults,noatime,size=64M   0  0
tmpfs    /tmp                  tmpfs   defaults,noatime,size=512M  0  0
```

Le système d'exploitation lui-même est chargé via **PXE / iPXE depuis
un serveur central** : le serveur local n'a aucun disque actif. Au
reboot, l'image est rerécupérée → mise à jour automatique + état zéro.

### 3.4 Hardening

- **SecureBoot + TPM 2.0** activés
- **LUKS** sur tout disque physique éventuel (clé dérivée de la TPM, jamais persistée)
- **Pas de SSH par mot de passe** : clés ED25519 uniquement, jamais root
- **Falco / auditd** envoyés vers un syslog central (le logging applicatif zéro est
  pour les utilisateurs ; l'opérationnel reste tracé pour la sécurité de l'infra)
- **WireGuard / strongSwan** lancés en mode systemd-tmpfiles, configs régénérées
  à chaque démarrage
- **Pas de swap** (zswap interdit) : aucune empreinte RAM ne touche le disque

### 3.5 Architecture réseau interne

```
                        ┌─────────────────┐
                        │  Control plane  │
                        │  (PXE + auth +  │
                        │   billing)      │
                        └────────┬────────┘
                                 │ TLS 1.3 mutuel
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
       ┌─────────┐          ┌─────────┐         ┌─────────┐
       │  POP-FR │          │  POP-CH │         │  POP-US │
       │ Paris   │          │ Zurich  │         │ NY/LA   │
       │ tmpfs   │          │ tmpfs   │         │ tmpfs   │
       │ WG/IKE  │          │ WG/IKE  │         │ WG/IKE  │
       └─────────┘          └─────────┘         └─────────┘
```

Le **control plane** ne voit **jamais** le contenu du tunnel — juste
l'authentification (token éphémère par session, généré côté client
avec ML-KEM hybride si activé).

---

## 4. Audit no-logs externe

### 4.1 Cabinets reconnus

- **Securitum** (Pologne) — a audité ProtonVPN et NordVPN
- **Cure53** (Allemagne) — audits exhaustifs, 4 à 6 semaines
- **PwC Switzerland** — audit financier + technique combinés (préféré pour la juridiction Suisse)
- **Deloitte CH** — alternative équivalente
- **KPMG** — gros budgets, format SOC 2 Type II

Coût : 30 000 à 120 000 CHF selon profondeur. Récurrence recommandée :
**1 audit complet par an + 1 audit allégé tous les 6 mois**.

### 4.2 Périmètre type d'un audit no-logs

L'auditeur examine :
1. **Configuration OS et services** sur 3 à 5 serveurs aléatoires,
   choisis par lui en RAM-only et en production.
2. **Code source** des services critiques (auth, dispatcher, kill switch).
3. **Politique d'accès** (qui peut SSH, qui peut redéployer).
4. **Tests d'intrusion** ciblés sur le control plane.
5. **Examen contractuel** entre la Sàrl et chaque hébergeur (clauses
   « pas d'écoute légale sans notification utilisateur »).

### 4.3 Communication

- Publier le rapport intégral sur le site (pas seulement un résumé marketing).
- Mentionner le périmètre exact (serveurs N°, datacenters, dates).
- Republier après chaque audit annuel pour montrer la régularité.

---

## 5. Pour aller plus loin : transparency report

Comme ProtonVPN et Mullvad, publier **trimestriellement** :
- Nombre de demandes des autorités reçues (Suisse + autres pays).
- Nombre de demandes auxquelles AuroraVPN a pu répondre (≈ 0 si l'infra est saine).
- Cas particuliers (warrant canary).

Ceci se construit sur **2-3 ans** et devient un **avantage concurrentiel
durable**.

---

## 6. Roadmap réaliste

| Étape | Délai | Coût indicatif |
|---|---|---|
| 0 — Sàrl Suisse + comptes | M+0 → M+2 | 5 k CHF |
| 1 — 5 serveurs PXE/tmpfs (CH, FR, DE, US, JP) | M+1 → M+3 | 1 500 CHF/mois |
| 2 — Backend control plane (auth + billing) | M+2 → M+4 | équipe interne |
| 3 — Client AuroraVPN production (ce repo) | déjà fait |   |
| 4 — Beta privée 100 utilisateurs | M+5 → M+6 |   |
| 5 — Premier audit Cure53 ou Securitum | M+7 → M+8 | 50 k CHF |
| 6 — Lancement public + transparency report Q1 | M+9 |   |

---

## 7. Synthèse

Pour qu'AuroraVPN soit **crédible au niveau "Proton"** :

1. **Société Sàrl Suisse** (Zoug ou Genève idéalement).
2. **Serveurs bare-metal RAM-only**, OS rechargé par PXE à chaque boot,
   pas de disque, pas de swap.
3. **Pas un seul log applicatif** sortant du serveur (control plane
   uniquement pour l'auth, jamais le trafic).
4. **Audit no-logs annuel** par Cure53 / Securitum / PwC, rapport publié
   intégralement.
5. **Transparency report** trimestriel.
6. **Code client open source** (MIT) — ce repo. Le moteur peut être
   audité par n'importe qui.
7. **Code serveur** : gardé interne, mais structure et configs publiées
   pour reproductibilité.

Avec ces 7 piliers, AuroraVPN se positionne sur le segment **premium
confidentialité maximale** aux côtés de ProtonVPN et Mullvad.
