"""
============================================================================
 AuroraVPN - Modules de fonctionnalites avancees
============================================================================
 Fichier  : features.py
 Contient :
   * MultiHopManager   - Double VPN (entree + sortie)
   * TorOverVPN        - Routage du trafic VPN -> Tor (SOCKS5 127.0.0.1:9150)
   * ThreatProtection  - Bloque pubs/trackers/malware via DNS sinkhole
   * LeakTester        - Tests de fuite IP / DNS / IPv6 / WebRTC
   * VpnAccelerator    - Tuning MTU, file de paquets, congestion control
   * Notifier          - Notifications Windows natives (toast)
============================================================================
"""

from __future__ import annotations

import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from utils import (
    IS_WINDOWS, hidden_subprocess_kwargs, is_admin, log, fetch_public_ip,
)
from config import app_data_dir


# ============================================================================
#  MULTI-HOP / DOUBLE VPN
# ============================================================================

@dataclass
class MultiHopConfig:
    """Configuration d'une cascade entree -> sortie."""
    entry_server_id: Optional[str] = None
    exit_server_id:  Optional[str] = None
    enabled:         bool = False


class MultiHopManager:
    """
    Orchestre une connexion en deux sauts : tunnel A vers le serveur
    d'entree, puis tunnel B vers le serveur de sortie a travers le tunnel A.

    Implementation production :
      1. Etablir le tunnel WireGuard A (par exemple Suisse).
      2. Lancer un second processus WireGuard dans le namespace de A,
         avec endpoint pointant vers le serveur B (Suede).
      3. Router 0.0.0.0/0 via le tunnel B uniquement.

    Implementation client : ce manager pilote l'engine en deux passes
    successives. Le serveur central doit supporter le forwarding inter-pop.
    """

    def __init__(self):
        self.config = MultiHopConfig()

    def set_route(self, entry_id: str, exit_id: str) -> None:
        if entry_id == exit_id:
            raise ValueError("Les serveurs d'entree et de sortie doivent differer.")
        self.config.entry_server_id = entry_id
        self.config.exit_server_id = exit_id
        log.info("Multi-hop : %s -> %s", entry_id, exit_id)

    def enable(self, enabled: bool) -> None:
        self.config.enabled = enabled

    @property
    def is_active(self) -> bool:
        return (self.config.enabled
                and self.config.entry_server_id
                and self.config.exit_server_id)

    def describe(self) -> str:
        if not self.is_active:
            return "desactive"
        return f"{self.config.entry_server_id} → {self.config.exit_server_id}"


# ============================================================================
#  TOR OVER VPN
# ============================================================================

class TorOverVPN:
    """
    Achemine le trafic apres connexion VPN a travers le reseau Tor.

    Production :
      - Detecte tor.exe (Tor Browser ou daemon Tor pour Windows).
      - Lance tor.exe en arriere-plan : SocksPort 9150, ControlPort 9151.
      - Configure le proxy systeme (WinINET) sur SOCKS 127.0.0.1:9150
        OU recommande l'utilisation d'un navigateur configurable.

    Avantage : double anonymat (FAI ne voit que le VPN, sortie Tor change
    d'IP en permanence).
    Inconvenient : latence elevee, debit reduit. A utiliser pour le
    journalisme, l'investigation, etc.
    """

    TOR_PATHS = [
        r"C:\Program Files\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
        r"C:\Program Files (x86)\Tor Browser\Browser\TorBrowser\Tor\tor.exe",
        r"C:\Tor\tor.exe",
    ]
    SOCKS_HOST = "127.0.0.1"
    SOCKS_PORT = 9150

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._enabled = False

    def is_available(self) -> bool:
        return any(Path(p).exists() for p in self.TOR_PATHS)

    def tor_path(self) -> Optional[str]:
        for p in self.TOR_PATHS:
            if Path(p).exists():
                return p
        return None

    def start(self) -> bool:
        """Lance tor.exe en arriere-plan."""
        if self._process and self._process.poll() is None:
            return True
        path = self.tor_path()
        if not path:
            log.warning("Tor introuvable. Installer le Tor Browser.")
            return False
        try:
            self._process = subprocess.Popen(
                [path, "--SocksPort", str(self.SOCKS_PORT)],
                **hidden_subprocess_kwargs(),
            )
            self._enabled = True
            log.info("Tor demarre (SOCKS5 %s:%s)", self.SOCKS_HOST, self.SOCKS_PORT)
            return True
        except Exception as exc:
            log.warning("Demarrage Tor impossible : %s", exc)
            return False

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
        self._process = None
        self._enabled = False

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def proxy_url(self) -> str:
        return f"socks5://{self.SOCKS_HOST}:{self.SOCKS_PORT}"


# ============================================================================
#  THREAT PROTECTION (blocage pubs / trackers / malware)
# ============================================================================

# Listes communautaires reconnues, fusionnees a chaque mise a jour.
_BLOCKLIST_SOURCES = [
    # Steven Black hosts (pubs + trackers + malware)
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
]

_BLOCKLIST_FILE = app_data_dir() / "blocklist.txt"
_BLOCKLIST_TTL_SECONDS = 7 * 24 * 3600   # 7 jours


class ThreatProtection:
    """
    Filtre DNS local : bloque la resolution de domaines connus pour
    diffuser pubs, trackers ou malware.

    Production :
      - Telecharge la liste a la demande.
      - L'application devrait soit relayer les requetes DNS via un mini
        resolveur local (port 53/UDP en localhost), soit injecter dans
        le hosts file. Ici on stocke le set en memoire et on expose
        check_domain() ; un futur service DNS viendra plus tard.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._domains: set[str] = set()
        self._enabled = False
        self._stats = {"queries": 0, "blocked": 0, "last_update": 0.0}
        self._refresh_in_progress = False  # evite les telechargements paralleles

    @property
    def stats(self) -> Dict[str, float]:
        return dict(self._stats)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self, enabled: bool) -> None:
        self._enabled = enabled
        # Telecharge UNE SEULE FOIS, meme si l'utilisateur toggle plusieurs fois.
        if enabled and not self._domains and not self._refresh_in_progress:
            self._refresh_in_progress = True
            threading.Thread(target=self._refresh_if_needed_safe,
                             daemon=True).start()

    def _refresh_if_needed_safe(self) -> None:
        try:
            self._refresh_if_needed()
        finally:
            self._refresh_in_progress = False

    # ----- Telechargement / parsing -----

    def _refresh_if_needed(self) -> None:
        try:
            mtime = _BLOCKLIST_FILE.stat().st_mtime if _BLOCKLIST_FILE.exists() else 0
            if time.time() - mtime > _BLOCKLIST_TTL_SECONDS:
                self._download()
            self._load()
        except Exception as exc:
            log.warning("Threat list : %s", exc)

    def force_refresh(self) -> None:
        if self._refresh_in_progress:
            log.info("Threat refresh deja en cours, on attend.")
            return
        self._refresh_in_progress = True
        threading.Thread(target=self._download_then_load_safe,
                         daemon=True).start()

    def _download_then_load_safe(self) -> None:
        try:
            self._download()
            self._load()
        except Exception as exc:
            log.warning("Force refresh : %s", exc)
        finally:
            self._refresh_in_progress = False

    def _download(self) -> None:
        all_lines: List[str] = []
        for url in _BLOCKLIST_SOURCES:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "AuroraVPN/1.0",
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    all_lines.extend(
                        resp.read().decode("utf-8", errors="ignore").splitlines()
                    )
            except Exception as exc:
                log.warning("Download %s : %s", url, exc)
        if all_lines:
            _BLOCKLIST_FILE.write_text("\n".join(all_lines), encoding="utf-8")
            self._stats["last_update"] = time.time()
            log.info("Blocklist mise a jour (%d lignes)", len(all_lines))

    def _load(self) -> None:
        if not _BLOCKLIST_FILE.exists():
            return
        domains: set[str] = set()
        for line in _BLOCKLIST_FILE.read_text(encoding="utf-8",
                                              errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format hosts : "0.0.0.0  badexample.com"
            parts = line.split()
            if len(parts) >= 2 and parts[0] in ("0.0.0.0", "127.0.0.1"):
                domains.add(parts[1].lower())
        with self._lock:
            self._domains = domains
        log.info("Blocklist chargee : %d domaines", len(domains))

    # ----- Lookup -----

    def check_domain(self, host: str) -> bool:
        """True si le domaine doit etre bloque."""
        with self._lock:
            self._stats["queries"] += 1
            if not self._enabled:
                return False
            host = host.lower().strip(".")
            # Match exact ou suffixe (pour bloquer les sous-domaines)
            for h in (host, "*." + host):
                if h in self._domains:
                    self._stats["blocked"] += 1
                    return True
            # Suffix match (lent mais correct)
            parts = host.split(".")
            for i in range(len(parts) - 1):
                suffix = ".".join(parts[i:])
                if suffix in self._domains:
                    self._stats["blocked"] += 1
                    return True
            return False


# ============================================================================
#  LEAK TESTER
# ============================================================================

@dataclass
class LeakTestResult:
    public_ip:        Optional[str] = None
    expected_ip:      Optional[str] = None
    ip_leak:          bool = False
    dns_servers:      List[str] = field(default_factory=list)
    dns_leak:         bool = False
    ipv6_present:     bool = False
    ipv6_leak:        bool = False
    webrtc_warning:   str = ""
    summary_ok:       bool = True


class LeakTester:
    """
    Effectue plusieurs tests de fuite et renvoie un rapport.

    Tests :
      - IP : compare l'IP publique recuperee a celle attendue
      - DNS : interroge les DNS systeme (psutil/netsh) et verifie qu'ils
        ne sont pas ceux du FAI
      - IPv6 : detecte une connectivite IPv6 hors tunnel
      - WebRTC : non testable cote OS (limitation du navigateur), affiche
        un message d'information
    """

    KNOWN_VPN_DNS = {"1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112",
                     "8.8.8.8", "8.8.4.4"}

    def run(self, expected_vpn_ip: Optional[str] = None) -> LeakTestResult:
        result = LeakTestResult(expected_ip=expected_vpn_ip)

        # 1. IP publique
        result.public_ip = fetch_public_ip()
        if expected_vpn_ip and result.public_ip:
            result.ip_leak = (result.public_ip != expected_vpn_ip)

        # 2. DNS systeme
        result.dns_servers = self._system_dns()
        # Heuristique : si on n'utilise QUE des DNS "VPN-friendly", pas de
        # fuite probable. Sinon, alerte.
        if result.dns_servers:
            non_vpn = [d for d in result.dns_servers
                       if d not in self.KNOWN_VPN_DNS]
            result.dns_leak = bool(non_vpn) and result.public_ip != expected_vpn_ip

        # 3. IPv6
        result.ipv6_present = self._has_ipv6()
        # Si IPv6 est present ET qu'on a une IP publique en IPv4 differente,
        # IPv6 peut fuiter. On marque comme leak potentiel.
        result.ipv6_leak = result.ipv6_present and not expected_vpn_ip

        # 4. WebRTC
        result.webrtc_warning = (
            "WebRTC ne peut etre verifie que dans le navigateur. "
            "Activer la protection WebRTC dans Chrome / Firefox."
        )

        result.summary_ok = not (result.ip_leak or result.dns_leak
                                 or result.ipv6_leak)
        return result

    def _system_dns(self) -> List[str]:
        """Liste des DNS configures sur la machine."""
        servers: List[str] = []
        if IS_WINDOWS:
            try:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-DnsClientServerAddress -AddressFamily IPv4).ServerAddresses"],
                    capture_output=True, text=True, timeout=5,
                    **hidden_subprocess_kwargs(),
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        if line and "." in line and not line.startswith("--"):
                            servers.append(line)
            except Exception as exc:
                log.debug("DNS list erreur : %s", exc)
        else:
            # Lecture /etc/resolv.conf (utile en dev sur Linux/macOS)
            try:
                for line in Path("/etc/resolv.conf").read_text().splitlines():
                    if line.startswith("nameserver"):
                        servers.append(line.split()[1])
            except Exception:
                pass
        return list(dict.fromkeys(servers))   # dedup en preservant l'ordre

    def _has_ipv6(self) -> bool:
        """Verifie si une connectivite IPv6 globale est dispo."""
        try:
            socket.setdefaulttimeout(2.0)
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
                s.connect(("2606:4700:4700::1111", 53))   # Cloudflare DNS v6
                return True
        except Exception:
            return False


# ============================================================================
#  VPN ACCELERATOR
# ============================================================================

class VpnAccelerator:
    """
    Tuning de la pile reseau Windows pour maximiser le debit VPN :
      - MTU optimal sur l'interface tunnel
      - Algorithme de congestion CUBIC (defaut Windows 10/11)
      - Auto-tuning Receive Window normal
      - Desactivation de l'offload TCP (sur certaines NIC, ameliore WG)
    """

    def __init__(self):
        self._enabled = False

    def enable(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled and IS_WINDOWS and is_admin():
            self._apply()

    def _apply(self) -> None:
        cmds = [
            # MTU 1420 (recommande WireGuard).
            'netsh interface ipv4 set subinterface "AuroraVPN" mtu=1420 store=active',
            # Algorithme de congestion (CTCP -> CUBIC).
            'netsh int tcp set supplemental Internet congestionprovider=cubic',
            # Auto-tuning level (normal).
            'netsh int tcp set global autotuninglevel=normal',
        ]
        for c in cmds:
            try:
                subprocess.run(c.split(), capture_output=True, timeout=5,
                               **hidden_subprocess_kwargs())
            except Exception:
                pass
        log.info("VPN accelerator : tuning applique")


# ============================================================================
#  NOTIFIER (toast Windows)
# ============================================================================

class Notifier:
    """
    Notifications systeme. Utilise plyer si dispo, sinon fallback console.
    """

    def __init__(self, app_name: str = "AuroraVPN"):
        self.app_name = app_name
        try:
            from plyer import notification   # type: ignore
            self._impl = notification
            self._available = True
        except ImportError:
            self._impl = None
            self._available = False

    def notify(self, title: str, message: str, timeout: int = 5) -> None:
        """Affichage non bloquant : delegue a un thread."""
        log.info("[NOTIF] %s - %s", title, message)
        # plyer peut bloquer plusieurs centaines de ms sur Windows ;
        # on l'execute hors du thread UI pour ne pas geler l'interface.
        threading.Thread(
            target=self._notify_blocking,
            args=(title, message, timeout),
            daemon=True,
        ).start()

    def _notify_blocking(self, title: str, message: str, timeout: int) -> None:
        if self._available:
            try:
                self._impl.notify(
                    title=title,
                    message=message,
                    app_name=self.app_name,
                    timeout=timeout,
                )
                return
            except Exception as exc:
                log.debug("Notify echec : %s", exc)
        # Fallback : print (utile en dev).
        print(f"[{self.app_name}] {title} - {message}")
