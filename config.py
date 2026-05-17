"""
============================================================================
 AuroraVPN - Module de persistance
============================================================================
 Fichier  : config.py
 Role     : Sauvegarde/chargement des preferences utilisateur sur disque.
 Format   : JSON dans %APPDATA%\\AuroraVPN\\config.json
============================================================================
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
#  Chemins
# ---------------------------------------------------------------------------

def app_data_dir() -> Path:
    """Repertoire de donnees applicatif (cree s'il n'existe pas)."""
    base = os.getenv("APPDATA")
    if base:
        path = Path(base) / "AuroraVPN"
    else:
        # Fallback Linux/macOS pour developpement
        path = Path.home() / ".aurora-vpn"
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_FILE = app_data_dir() / "config.json"
LOG_DIR     = app_data_dir() / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
#  Structure
# ---------------------------------------------------------------------------

@dataclass
class UserConfig:
    """Preferences persistees entre les sessions."""

    # Selection
    last_server_id:    Optional[str] = None
    last_protocol:     str = "Auto"        # Auto / WireGuard / IKEv2 / OpenVPN
    last_mode:         str = "Auto"        # Auto / Securite max / Vitesse max ...

    # Securite (snapshot)
    kill_switch:       bool = True
    dns_protection:    bool = True
    leak_protection:   bool = True
    pfs:               bool = True
    post_quantum:      bool = False
    split_tunneling:   bool = False
    auto_reconnect:    bool = True
    auto_on_public_wifi: bool = True
    block_trackers:    bool = True

    # UI
    minimize_to_tray:  bool = True
    start_minimized:   bool = False
    confirm_on_exit:   bool = True

    # Avance
    real_subprocess:   bool = False        # Active les vrais appels VPN (Admin)
    real_security:     bool = False        # Active les vrais filtres WFP / netsh

    # Endpoint serveur reel (override) - laisser vide pour mode demo
    real_endpoint_host: str = ""
    real_endpoint_user: str = ""           # pour rasdial

    # ----- Fonctionnalites avancees (v3) -----
    multi_hop_enabled:    bool = False
    multi_hop_exit_id:    str = ""         # serveur de sortie

    tor_over_vpn_enabled: bool = False

    threat_protection:    bool = True      # alias de block_trackers
    accelerator_enabled:  bool = False     # tuning MTU / TCP

    notifications_enabled: bool = True

    # ----- v4 : tests, dns local, loopback, i18n -----
    language:             str = ""         # "" = auto-detect ; "fr" / "en"
    loopback_mode:        bool = False     # backend test UDP localhost
    dns_resolver_enabled: bool = False     # mini-resolveur DNS local
    dns_resolver_port:    int = 5353
    auto_ping_on_start:   bool = True      # mesure parallele au demarrage

    # ----- v4.1 : connexion automatique a l'ouverture -----
    auto_connect_on_start: bool = False    # se connecte tout seul a l'ouverture
    auto_connect_delay_ms: int  = 800      # delai apres rendu UI

    # ----- v4.2 : premier lancement / assistant -----
    setup_completed:       bool = False    # True apres passage de l'assistant
    server_label:          str  = ""       # nom affichage du serveur configure

    # ----------------------------------------------------------------------
    # IO
    # ----------------------------------------------------------------------

    @classmethod
    def load(cls) -> "UserConfig":
        if CONFIG_FILE.exists():
            try:
                data: Dict[str, Any] = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                # Filtrer les cles inconnues pour resister aux migrations.
                known = {f.name for f in cls.__dataclass_fields__.values()}
                clean = {k: v for k, v in data.items() if k in known}
                return cls(**clean)
            except Exception as exc:
                # En cas de corruption, on repart sur un profil par defaut.
                print(f"[config] Lecture impossible ({exc}), reinitialisation.")
        return cls()

    def save(self) -> None:
        try:
            CONFIG_FILE.write_text(
                json.dumps(asdict(self), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[config] Sauvegarde impossible : {exc}")
