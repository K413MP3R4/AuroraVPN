"""
============================================================================
 AuroraVPN - Import d'un fichier .conf WireGuard
============================================================================
 Fichier  : import_wireguard_config.py
 Role     : Prend un fichier WireGuard .conf genere par install_wireguard.sh
            et configure AuroraVPN pour s'y connecter en mode reel.

 Usage :
   python import_wireguard_config.py <chemin>\\<client>.conf
   python import_wireguard_config.py aurora-client.conf --name "Mon Serveur"

 Effets :
   1. Copie le fichier dans C:\\ProgramData\\AuroraVPN\\aurora.conf
   2. Met a jour la config utilisateur : real_subprocess=True,
      loopback_mode=False, real_endpoint_host=<host extracted from .conf>
   3. Imprime le rappel : "Lancez AuroraVPN en tant qu'Administrateur".
============================================================================
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional

# Ajout du repertoire racine au path pour reutiliser config.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import UserConfig


PROGRAMDATA_TARGET = Path(os.getenv("PROGRAMDATA", "C:/ProgramData")) \
                     / "AuroraVPN" / "aurora.conf"


def parse_wg_conf(path: Path) -> Dict[str, str]:
    """
    Parse minimaliste d'un .conf WireGuard. Renvoie un dict plat avec
    les cles utiles : PrivateKey, Address, DNS, PublicKey (peer),
    Endpoint, AllowedIPs.
    """
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    text = path.read_text(encoding="utf-8", errors="ignore")
    result: Dict[str, str] = {}
    current_section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("["):
            current_section = line.strip("[]").lower()
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # On prefixe par la section pour eviter les collisions
            # (Address existe dans [Interface], pas dans [Peer]).
            result[f"{current_section}.{key.lower()}"] = value
    return result


def validate(parsed: Dict[str, str]) -> None:
    required = [
        ("interface.privatekey",  "PrivateKey dans [Interface]"),
        ("interface.address",     "Address dans [Interface]"),
        ("peer.publickey",        "PublicKey dans [Peer]"),
        ("peer.endpoint",         "Endpoint dans [Peer]"),
    ]
    missing = [label for key, label in required if not parsed.get(key)]
    if missing:
        raise ValueError(
            "Fichier .conf incomplet. Champs manquants :\n  - "
            + "\n  - ".join(missing)
        )


def extract_endpoint_host(endpoint: str) -> str:
    """'vpn.example.com:51820' -> 'vpn.example.com'"""
    return endpoint.rsplit(":", 1)[0]


def copy_to_programdata(source: Path) -> Path:
    """Copie le fichier dans %PROGRAMDATA%\\AuroraVPN\\aurora.conf."""
    PROGRAMDATA_TARGET.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, PROGRAMDATA_TARGET)
        # Restreint la lecture aux administrateurs (Windows ACL).
        if os.name == "nt":
            try:
                import subprocess
                subprocess.run(
                    ["icacls", str(PROGRAMDATA_TARGET),
                     "/inheritance:r",
                     "/grant", "Administrators:R",
                     "/grant", "SYSTEM:R"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass
    except PermissionError:
        raise PermissionError(
            f"Permission refusee pour ecrire dans {PROGRAMDATA_TARGET}.\n"
            "Lancez ce script en tant qu'Administrateur."
        )
    return PROGRAMDATA_TARGET


def update_user_config(endpoint_host: str, server_label: Optional[str] = None) -> Path:
    """Met a jour %APPDATA%\\AuroraVPN\\config.json."""
    cfg = UserConfig.load()
    cfg.real_subprocess     = True
    cfg.real_security       = False   # l'utilisateur l'activera s'il veut
    cfg.loopback_mode       = False   # on bascule sur le vrai endpoint
    cfg.real_endpoint_host  = endpoint_host
    if server_label:
        cfg.real_endpoint_user = server_label   # affichage seulement
    cfg.save()
    from config import CONFIG_FILE
    return CONFIG_FILE


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importe un fichier .conf WireGuard dans AuroraVPN."
    )
    parser.add_argument("config_file", type=Path,
                        help="Chemin vers le fichier .conf WireGuard genere "
                             "par install_wireguard.sh")
    parser.add_argument("--name", type=str, default=None,
                        help="Nom personnalise du serveur (affichage)")
    parser.add_argument("--dry-run", action="store_true",
                        help="N'ecrit rien, affiche juste ce qui serait fait.")
    args = parser.parse_args()

    print(f"\n=== Import AuroraVPN ===")
    print(f"Source : {args.config_file}")

    try:
        parsed = parse_wg_conf(args.config_file)
        validate(parsed)
    except (FileNotFoundError, ValueError) as exc:
        print(f"\n[ERREUR] {exc}")
        return 1

    endpoint = parsed["peer.endpoint"]
    host = extract_endpoint_host(endpoint)
    address = parsed["interface.address"]
    pubkey = parsed["peer.publickey"]

    print(f"  Endpoint   : {endpoint}")
    print(f"  IP tunnel  : {address}")
    print(f"  Cle pub    : {pubkey[:24]}...")

    if args.dry_run:
        print("\n[DRY-RUN] Aucune modification ecrite.")
        return 0

    try:
        target = copy_to_programdata(args.config_file)
        print(f"\nFichier copie dans : {target}")
    except PermissionError as exc:
        print(f"\n[ERREUR] {exc}")
        return 2

    cfg_file = update_user_config(host, server_label=args.name)
    print(f"Config utilisateur maj : {cfg_file}")
    print(f"  - real_subprocess     : True")
    print(f"  - loopback_mode       : False")
    print(f"  - real_endpoint_host  : {host}")

    print("\n=== Termine ===")
    print("Pour vous connecter au VRAI serveur WireGuard :")
    print("  1. Verifiez que wireguard.exe est installe (https://www.wireguard.com)")
    print("  2. Relancez AuroraVPN en tant qu'Administrateur")
    print("  3. Cliquez sur CONNECTER (ou laissez l'auto-connexion faire son travail)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
