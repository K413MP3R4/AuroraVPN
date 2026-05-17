# Publier AuroraVPN sur ton GitHub

Guide étape par étape — environ 5 minutes.

---

## Pré-requis

- Un compte GitHub : https://github.com/signup (si pas encore fait)
- Git installé sur Windows : https://git-scm.com/download/win
  (accepter les options par défaut pendant l'installation)
- Avoir vérifié que **aucune donnée sensible** n'est dans le dossier
  (le `.gitignore` créé exclut déjà : clés SSH, `.conf` clients, logs,
  config local, etc.)

---

## Étape 1 — Créer le dépôt sur GitHub

1. Va sur https://github.com/new
2. **Owner** : ton compte (par défaut)
3. **Repository name** : `AuroraVPN` (ou un autre nom si tu préfères)
4. **Description** : `Client VPN moderne pour Windows — interface CustomTkinter, multi-protocoles, assistant Oracle Cloud intégré`
5. **Public** ou **Private** ? Au choix :
   - **Public** : visible par tous, recommandé si tu veux contribuer à
     l'open source et l'utiliser comme projet portfolio
   - **Private** : visible que par toi (passe à public plus tard si tu veux)
6. ⚠️ **NE COCHE PAS** :
   - "Add a README file"
   - "Add .gitignore"
   - "Choose a license"

   (Tu en as déjà localement, GitHub créerait des conflits.)
7. Bouton **Create repository**
8. GitHub te montre une page "Quick setup". **Note l'URL** affichée
   en haut, du style : `https://github.com/TON_USER/AuroraVPN.git`

---

## Étape 2 — Configurer Git localement (1ʳᵉ fois seulement)

Ouvre **PowerShell** (pas besoin d'admin) :

```powershell
git config --global user.name "Ton Nom"
git config --global user.email "ton-email@example.com"
```

> Utilise le même email que sur ton compte GitHub.

---

## Étape 3 — Initialiser le repo et pousser

Dans PowerShell, va dans le dossier AuroraVPN :

```powershell
cd "D:\Claude Code\AuroraVPN"
```

Initialise Git, ajoute tous les fichiers (sauf ceux du `.gitignore`),
fais le premier commit :

```powershell
git init
git add .
git commit -m "Initial commit : AuroraVPN v4 complet"
```

> Si Git te demande de définir une branche par défaut :
> ```powershell
> git branch -M main
> ```

Connecte au dépôt distant (remplace l'URL par celle de ton repo) :

```powershell
git remote add origin https://github.com/TON_USER/AuroraVPN.git
```

Pousse vers GitHub :

```powershell
git push -u origin main
```

GitHub te demandera de t'authentifier. **Deux options** :

### Option A : Personal Access Token (recommandé)

1. Sur GitHub, va sur https://github.com/settings/tokens
2. **Generate new token** → **Generate new token (classic)**
3. Note : `AuroraVPN dev`
4. Expiration : 90 days (ou plus)
5. Scopes : coche **`repo`** (suffit)
6. **Generate token** → copie le token (commence par `ghp_...`)
7. Dans PowerShell, quand Git demande :
   - **Username** : ton login GitHub
   - **Password** : colle le token (pas ton mot de passe GitHub)

### Option B : GitHub CLI (plus simple si tu prévois de pousser souvent)

```powershell
winget install GitHub.cli
gh auth login
# Suis le flow OAuth dans le navigateur
```

Puis simplement :

```powershell
git push -u origin main
```

→ pas de mot de passe à saisir.

---

## Étape 4 — Vérifier

1. Rafraîchis la page GitHub de ton dépôt
2. Tu dois voir tous les fichiers
3. Vérifie en particulier que **les fichiers sensibles ne sont PAS là** :
   - Pas de `*.conf` (sauf ceux dans `config_examples/`)
   - Pas de `*.key`
   - Pas de `__pycache__/`
   - Pas de `build/` ou `dist/`
4. Tu peux cliquer **About** (à droite) → **⚙ ** pour ajouter :
   - Topics : `vpn`, `wireguard`, `python`, `customtkinter`, `windows`
   - Website : éventuellement le lien vers une démo
   - **Releases** s'activera quand tu créeras une release

---

## Étape 5 — Activer la CI GitHub Actions

C'est déjà configuré dans `.github/workflows/tests.yml`. Dès le 1ᵉʳ push,
GitHub Actions lance les tests pytest automatiquement.

Vérifie : onglet **Actions** sur ton dépôt → tu verras le run en cours
ou terminé. Vert = tout passe, rouge = un test casse (regarde les logs).

---

## Étape 6 — (Optionnel) Première release

Une fois que tu es content de l'état :

1. Sur GitHub, onglet **Releases** → **Create a new release**
2. **Choose a tag** → tape `v1.0.0` → **Create new tag on publish**
3. **Release title** : `AuroraVPN v1.0.0`
4. **Describe this release** : Bref résumé des fonctionnalités
5. **Attach binaries** : si tu as compilé `dist/AuroraVPN.exe` avec
   `build_windows.bat`, glisse-le ici pour que les gens téléchargent
   directement l'exécutable
6. **Publish release**

---

## Pour les mises à jour futures

Quand tu modifies du code :

```powershell
cd "D:\Claude Code\AuroraVPN"
git add .
git commit -m "Description courte de tes changements"
git push
```

C'est tout.

---

## Astuces

### Renommer la branche `master` en `main` (si jamais nécessaire)

```powershell
git branch -M main
git push -u origin main
```

### Voir l'état du repo

```powershell
git status        # quels fichiers ont changé
git log --oneline # historique des commits
```

### Ignorer un fichier après l'avoir déjà commit par erreur

```powershell
git rm --cached fichier-a-ignorer
# Ajoute le fichier au .gitignore
git commit -m "Retire fichier sensible"
git push
```

⚠️ **Important** : si tu as commit une clé/mot de passe par erreur, il
faut RÉVOQUER la clé (pas juste la retirer du repo, elle reste dans
l'historique Git).

### Cloner ton repo depuis un autre PC

```bash
git clone https://github.com/TON_USER/AuroraVPN.git
cd AuroraVPN
python -m pip install -r requirements.txt
python main.py
```

---

## Si tu veux que je publie aussi sur GitHub pour toi

Je ne peux pas le faire directement depuis ce chat — je n'ai pas accès
à ton compte. Mais si tu installes le **connecteur GitHub** dans
Cowork (Settings → Connectors → GitHub), je pourrai dans une future
session créer le repo, pousser le code, et configurer les Actions sans
que tu n'aies à toucher à Git en ligne de commande.

---

Bonne publication 🚀
