"""
============================================================================
 AuroraVPN - Utilitaires
============================================================================
 Fichier  : utils.py
 Role     : Single-instance lock, recuperation IP publique reelle, ping
            de latence, journalisation rotative legere, helpers Windows.
============================================================================
"""

from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

from config import LOG_DIR


# ---------------------------------------------------------------------------
#  Journalisation
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    """Logger applicatif avec rotation 7 jours, 1 fichier par jour."""
    logger = logging.getLogger("aurora")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    # Fichier rotatif quotidien.
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_DIR / "aurora.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # Console (utile en dev).
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    return logger


log = setup_logging()


# ---------------------------------------------------------------------------
#  Plateforme
# ---------------------------------------------------------------------------

IS_WINDOWS = platform.system() == "Windows"


def is_admin() -> bool:
    """Renvoie True si le processus tourne en tant qu'Administrateur (Windows)."""
    if not IS_WINDOWS:
        return os.geteuid() == 0  # Linux/macOS
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def hidden_subprocess_kwargs() -> dict:
    """Empeche l'apparition de fenetres CMD lors des subprocess.run."""
    kwargs = {}
    if IS_WINDOWS:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


# ---------------------------------------------------------------------------
#  Single instance lock
# ---------------------------------------------------------------------------

_LOCK_FILE = Path(os.getenv("TEMP", "/tmp")) / "AuroraVPN.lock"
_lock_handle = None


def acquire_single_instance() -> bool:
    """
    Renvoie True si l'application a obtenu le verrou.
    False signifie qu'une autre instance est deja en cours (l'appli doit quitter).
    """
    global _lock_handle
    try:
        # Sous Windows, on cree un fichier en mode exclusif.
        if IS_WINDOWS:
            import msvcrt
            _lock_handle = open(_LOCK_FILE, "w")
            msvcrt.locking(_lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            _lock_handle = open(_LOCK_FILE, "w")
            fcntl.flock(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_handle.write(str(os.getpid()))
        _lock_handle.flush()
        return True
    except (IOError, OSError):
        return False


def release_single_instance() -> None:
    global _lock_handle
    try:
        if _lock_handle:
            _lock_handle.close()
            _lock_handle = None
        if _LOCK_FILE.exists():
            _LOCK_FILE.unlink()
    except Exception:
        pass


# ---------------------------------------------------------------------------
#  IP publique reelle
# ---------------------------------------------------------------------------

_IP_PROVIDERS = [
    "https://api.ipify.org?format=json",
    "https://ipv4.icanhazip.com",
    "https://api64.ipify.org?format=json",
]


def fetch_public_ip(timeout: float = 3.0) -> Optional[str]:
    """Interroge plusieurs services pour obtenir l'IP publique."""
    import json
    for url in _IP_PROVIDERS:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "AuroraVPN/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore").strip()
                if body.startswith("{"):
                    return json.loads(body).get("ip")
                return body
        except Exception as exc:
            log.debug("Provider %s indisponible: %s", url, exc)
    return None


# ---------------------------------------------------------------------------
#  Latence reelle (ping)
# ---------------------------------------------------------------------------

def measure_latency_ms(host: str, count: int = 3) -> Optional[int]:
    """
    Mesure de latence par ping ICMP. Renvoie la moyenne en millisecondes,
    ou None en cas d'echec.
    """
    if not host:
        return None
    try:
        if IS_WINDOWS:
            cmd = ["ping", "-n", str(count), "-w", "1500", host]
        else:
            cmd = ["ping", "-c", str(count), "-W", "2", host]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            **hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            return None
        # Extraction simple du temps moyen.
        out = result.stdout
        # Windows : "Moyenne = 23ms"  ou  "Average = 23ms"
        # Linux   : "rtt min/avg/max/mdev = 12.345/23.456/.../... ms"
        import re
        m = re.search(r"(?:Moyenne|Average|avg)[^=]*=\s*([\d\.]+)", out, re.IGNORECASE)
        if m:
            return int(round(float(m.group(1).replace(",", "."))))
        # Fallback : moyenne des valeurs "time=XXms"
        times = re.findall(r"(?:time|temps)[=<]\s*([\d\.]+)", out, re.IGNORECASE)
        if times:
            vals = [float(t.replace(",", ".")) for t in times]
            return int(round(sum(vals) / len(vals)))
    except Exception as exc:
        log.debug("Ping %s echoue: %s", host, exc)
    return None


# ---------------------------------------------------------------------------
#  Helpers reseau
# ---------------------------------------------------------------------------

def is_online(timeout: float = 2.0) -> bool:
    """Verifie une connectivite Internet basique (DNS Cloudflare)."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("1.1.1.1", 53)).close()
        return True
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """
    Relance le processus actuel avec elevation UAC.
    Renvoie True si la relance a ete demandee (l'instance courante doit quitter).
    """
    if not IS_WINDOWS or is_admin():
        return False
    try:
        params = " ".join(f'"{a}"' for a in sys.argv)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        return True
    except Exception as exc:
        log.warning("Relance UAC echouee : %s", exc)
        return False
