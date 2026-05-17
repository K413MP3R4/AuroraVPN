"""
============================================================================
 AuroraVPN - Moteur VPN (avec connexion Windows reelle)
============================================================================
 Fichier  : vpn_engine.py
 Role     : Machine d'etats + abstraction des backends WG/IKEv2/OpenVPN.
            Mode demo (default) ou mode reel (UserConfig.real_subprocess).
============================================================================
"""

from __future__ import annotations

import concurrent.futures
import enum
import os
import random
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from utils import (
    IS_WINDOWS, hidden_subprocess_kwargs, is_admin, log,
    fetch_public_ip, measure_latency_ms,
)


# ============================================================================
#  Types
# ============================================================================

class ConnectionState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    ERROR        = "error"


class Protocol(enum.Enum):
    WIREGUARD = "wireguard"
    IKEV2     = "ikev2"
    OPENVPN   = "openvpn"


@dataclass
class ServerInfo:
    id: str
    country: str
    city: str
    public_ip: str
    latency_ms: int = 0
    throughput_mbps: int = 0
    load_percent: int = 0
    supports_wg: bool = True
    supports_ikev2: bool = True
    supports_openvpn: bool = True
    endpoint_wg: str = ""
    endpoint_ikev2: str = ""
    endpoint_openvpn: str = ""


# ============================================================================
#  Backends (interface commune)
# ============================================================================

_RAS_NAME = "AuroraVPN"
_WG_TUNNEL_NAME = "AuroraVPN"


class _BaseBackend:
    """Contrat minimal qu'un backend de protocole doit respecter."""
    name: Protocol

    def __init__(self, real_mode: bool = False):
        self._real = real_mode

    def set_real_mode(self, enabled: bool) -> None:
        self._real = enabled

    def is_available(self) -> bool:
        raise NotImplementedError

    def connect(self, server: ServerInfo, host_override: str = "") -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError


# ----------------------------------------------------------------------------
#  WireGuard
# ----------------------------------------------------------------------------

class WireGuardBackend(_BaseBackend):
    name = Protocol.WIREGUARD

    WG_PATHS = [
        r"C:\Program Files\WireGuard\wireguard.exe",
        r"C:\Program Files (x86)\WireGuard\wireguard.exe",
    ]

    def is_available(self) -> bool:
        if not IS_WINDOWS:
            return False
        return any(Path(p).exists() for p in self.WG_PATHS)

    def _wg_path(self) -> str:
        for p in self.WG_PATHS:
            if Path(p).exists():
                return p
        return ""

    def connect(self, server: ServerInfo, host_override: str = "") -> None:
        if not self._real:
            time.sleep(1.2)
            return
        if not is_admin():
            raise RuntimeError("WireGuard requiert les droits Administrateur")
        wg = self._wg_path()
        if not wg:
            raise RuntimeError("wireguard.exe introuvable")

        cfg = self._build_config(server, host_override)
        cfg_path = Path(os.getenv("PROGRAMDATA", "C:/ProgramData")) \
                   / "AuroraVPN" / "aurora.conf"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(cfg, encoding="utf-8")
        log.info("Installation tunnel WireGuard : %s", cfg_path)
        subprocess.check_call(
            [wg, "/installtunnelservice", str(cfg_path)],
            **hidden_subprocess_kwargs(),
        )

    def disconnect(self) -> None:
        if not self._real:
            time.sleep(0.4)
            return
        wg = self._wg_path()
        if not wg:
            return
        subprocess.call(
            [wg, "/uninstalltunnelservice", _WG_TUNNEL_NAME],
            **hidden_subprocess_kwargs(),
        )

    def _build_config(self, server: ServerInfo, host_override: str) -> str:
        endpoint = host_override or server.endpoint_wg or "wg.example.com:51820"
        return f"""[Interface]
PrivateKey = REMPLACER_PAR_CLE_PRIVEE_CLIENT
Address    = 10.66.66.2/32
DNS        = 1.1.1.1, 9.9.9.9
MTU        = 1420

[Peer]
PublicKey           = REMPLACER_PAR_CLE_PUBLIQUE_SERVEUR
PresharedKey        = REMPLACER_PAR_PSK_OPTIONNELLE
Endpoint            = {endpoint}
AllowedIPs          = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""


# ----------------------------------------------------------------------------
#  IKEv2 (pile RAS Windows native)
# ----------------------------------------------------------------------------

class IKEv2Backend(_BaseBackend):
    name = Protocol.IKEV2

    def is_available(self) -> bool:
        return IS_WINDOWS

    def connect(self, server: ServerInfo, host_override: str = "") -> None:
        if not self._real:
            time.sleep(1.6)
            return
        if not is_admin():
            raise RuntimeError("IKEv2 requiert les droits Administrateur")

        host = host_override or server.endpoint_ikev2 or server.public_ip
        # Recree la connexion RAS avec la suite forte.
        ps_cmd = (
            f"$ErrorActionPreference='Stop';"
            f"$n='{_RAS_NAME}';"
            f"if (Get-VpnConnection -Name $n -ErrorAction SilentlyContinue) {{"
            f"  Remove-VpnConnection -Name $n -Force }};"
            f"Add-VpnConnection -Name $n -ServerAddress '{host}'"
            f"  -TunnelType IKEv2 -EncryptionLevel Required"
            f"  -AuthenticationMethod MachineCertificate"
            f"  -SplitTunneling $false -RememberCredential $false"
            f"  -PassThru | Out-Null;"
            f"Set-VpnConnectionIPsecConfiguration -ConnectionName $n"
            f"  -AuthenticationTransformConstants GCMAES256"
            f"  -CipherTransformConstants GCMAES256"
            f"  -EncryptionMethod GCMAES256"
            f"  -IntegrityCheckMethod SHA384"
            f"  -DHGroup ECP384 -PfsGroup ECP384 -Force"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=20,
            **hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            raise RuntimeError(f"Setup VPN echoue : {result.stderr.strip()}")

        # Composition du tunnel.
        result = subprocess.run(
            ["rasdial", _RAS_NAME],
            capture_output=True, text=True, timeout=30,
            **hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            raise RuntimeError(f"rasdial echoue : {result.stdout.strip()}")

    def disconnect(self) -> None:
        if not self._real:
            time.sleep(0.5)
            return
        subprocess.call(
            ["rasdial", _RAS_NAME, "/disconnect"],
            **hidden_subprocess_kwargs(),
        )


# ----------------------------------------------------------------------------
#  OpenVPN
# ----------------------------------------------------------------------------

class LoopbackBackend(_BaseBackend):
    """
    Backend de TEST : etablit un vrai socket UDP localhost (127.0.0.1)
    pour permettre de valider le cycle connect/disconnect dans une vraie
    boucle reseau, sans avoir besoin d'un serveur distant.

    Utile pour : tests unitaires, demos, presentation, validation du
    flux complet (state machine + UI + leak monitor) sans infra.
    """

    name = Protocol.WIREGUARD  # se fait passer pour WireGuard cote UI

    def __init__(self, real_mode: bool = False):
        super().__init__(real_mode)
        self._sock: Optional[socket.socket] = None
        self._port = 0

    def is_available(self) -> bool:
        return True   # toujours dispo, pas de prerequis

    def connect(self, server: ServerInfo, host_override: str = "") -> None:
        """Ouvre un socket UDP sur 127.0.0.1, port libre choisi par l'OS."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind(("127.0.0.1", 0))
            self._port = self._sock.getsockname()[1]
            log.info("Loopback backend : socket UDP 127.0.0.1:%d", self._port)
            time.sleep(0.5)  # simule la negociation des cles
        except Exception as exc:
            self._cleanup()
            raise RuntimeError(f"Loopback backend echec : {exc}") from exc

    def disconnect(self) -> None:
        self._cleanup()
        time.sleep(0.2)

    def _cleanup(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
            self._port = 0


class OpenVPNBackend(_BaseBackend):
    name = Protocol.OPENVPN

    OVPN_PATHS = [
        r"C:\Program Files\OpenVPN\bin\openvpn.exe",
        r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
    ]

    def __init__(self, real_mode: bool = False):
        super().__init__(real_mode)
        self._proc: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        if not IS_WINDOWS:
            return False
        return any(Path(p).exists() for p in self.OVPN_PATHS)

    def _ovpn_path(self) -> str:
        for p in self.OVPN_PATHS:
            if Path(p).exists():
                return p
        return ""

    def connect(self, server: ServerInfo, host_override: str = "") -> None:
        if not self._real:
            time.sleep(2.0)
            return
        if not is_admin():
            raise RuntimeError("OpenVPN requiert les droits Administrateur")
        ovpn = self._ovpn_path()
        if not ovpn:
            raise RuntimeError("openvpn.exe introuvable")
        cfg_path = Path(os.getenv("PROGRAMDATA", "C:/ProgramData")) \
                   / "AuroraVPN" / "aurora.ovpn"
        if not cfg_path.exists():
            raise RuntimeError(f"Config OpenVPN absente : {cfg_path}")
        log.info("Lancement OpenVPN avec %s", cfg_path)
        self._proc = subprocess.Popen(
            [ovpn, "--config", str(cfg_path)],
            **hidden_subprocess_kwargs(),
        )

    def disconnect(self) -> None:
        if not self._real:
            time.sleep(0.6)
            return
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None


# ============================================================================
#  Moteur principal
# ============================================================================

class VPNEngine:
    """Orchestre la connexion VPN et expose une API simple a l'UI."""

    def __init__(self, real_mode: bool = False, host_override: str = "",
                 loopback_mode: bool = False):
        self._lock = threading.RLock()
        self._state: ConnectionState = ConnectionState.DISCONNECTED
        self._error: Optional[str] = None
        self._connected_at: Optional[float] = None
        self._current_server: Optional[ServerInfo] = None
        self._active_protocol: Optional[Protocol] = None
        self._real_mode = real_mode
        self._host_override = host_override
        self._loopback_mode = loopback_mode

        self._servers = self._build_server_catalog()
        self._backends = {
            Protocol.WIREGUARD: WireGuardBackend(real_mode),
            Protocol.IKEV2:     IKEv2Backend(real_mode),
            Protocol.OPENVPN:   OpenVPNBackend(real_mode),
        }
        # Backend test "vrai socket UDP localhost", active par toggle.
        self._loopback_backend = LoopbackBackend(real_mode=False)
        self._active_backend: Optional[_BaseBackend] = None
        self._public_ip: Optional[str] = None

        self.on_state_change: Callable[[ConnectionState], None] = lambda _s: None
        self.on_public_ip:    Callable[[str], None] = lambda _ip: None
        self.on_latencies_updated: Callable[[Dict[str, int]], None] = \
            lambda _latencies: None

    def set_loopback_mode(self, enabled: bool) -> None:
        self._loopback_mode = enabled

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_real_mode(self, enabled: bool) -> None:
        self._real_mode = enabled
        for b in self._backends.values():
            b.set_real_mode(enabled)

    def set_host_override(self, host: str) -> None:
        self._host_override = host or ""

    # ------------------------------------------------------------------
    # Etat
    # ------------------------------------------------------------------

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def last_error(self) -> Optional[str]:
        return self._error

    @property
    def current_server(self) -> Optional[ServerInfo]:
        return self._current_server

    @property
    def active_protocol(self) -> Optional[Protocol]:
        return self._active_protocol

    @property
    def public_ip(self) -> Optional[str]:
        return self._public_ip

    def session_duration_seconds(self) -> int:
        if self._connected_at is None:
            return 0
        return int(time.time() - self._connected_at)

    # ------------------------------------------------------------------
    # Catalogue
    # ------------------------------------------------------------------

    def list_servers(self) -> List[ServerInfo]:
        return list(self._servers)

    def get_server(self, server_id: str) -> Optional[ServerInfo]:
        for s in self._servers:
            if s.id == server_id:
                return s
        return None

    def select_server(self, server_id: str) -> None:
        s = self.get_server(server_id)
        if s:
            with self._lock:
                self._current_server = s
            self._notify()

    # ------------------------------------------------------------------
    # Connexion
    # ------------------------------------------------------------------

    def connect(self, protocol: Optional[Protocol] = None) -> None:
        with self._lock:
            if self._state in (ConnectionState.CONNECTING,
                               ConnectionState.CONNECTED):
                return
            self._state = ConnectionState.CONNECTING
            self._error = None
        self._notify()

        try:
            if self._current_server is None:
                self._current_server = self._select_best_server()

            chosen = protocol or self._select_best_protocol(self._current_server)
            backend = self._backends[chosen]

            # Mode loopback : ouvre un vrai socket UDP localhost pour
            # tester le cycle complet sans serveur distant.
            if self._loopback_mode:
                backend = self._loopback_backend
                log.info("Mode loopback active : utilisation du backend "
                         "LoopbackBackend (socket UDP localhost)")
            elif self._real_mode and not backend.is_available():
                # Fallback sur les backends presents.
                for fb in (Protocol.OPENVPN, Protocol.IKEV2, Protocol.WIREGUARD):
                    if self._backends[fb].is_available():
                        chosen = fb
                        backend = self._backends[chosen]
                        break

            self._active_protocol = chosen
            self._active_backend = backend

            log.info("Connexion %s vers %s (%s)",
                     chosen.name, self._current_server.id,
                     "REEL" if self._real_mode else "DEMO")

            backend.connect(self._current_server, self._host_override)

            # Mesures reelles ou simulees.
            if self._real_mode:
                # Ping sur l'endpoint et IP publique reelle.
                lat = measure_latency_ms(self._current_server.endpoint_ikev2
                                         or self._current_server.public_ip)
                if lat:
                    self._current_server.latency_ms = lat
                self._public_ip = fetch_public_ip()
            else:
                self._current_server.latency_ms = random.randint(18, 65)
                self._current_server.throughput_mbps = random.randint(120, 480)
                self._public_ip = self._current_server.public_ip

            try:
                self.on_public_ip(self._public_ip or "")
            except Exception:
                pass

            with self._lock:
                self._state = ConnectionState.CONNECTED
                self._connected_at = time.time()
        except Exception as exc:
            log.warning("Connexion echouee : %s", exc)
            with self._lock:
                self._state = ConnectionState.ERROR
                self._error = str(exc)
        finally:
            self._notify()

    def disconnect(self) -> None:
        with self._lock:
            if self._state == ConnectionState.DISCONNECTED:
                return
        try:
            if self._active_backend:
                self._active_backend.disconnect()
        except Exception as exc:
            log.warning("Deconnexion : %s", exc)
        finally:
            with self._lock:
                self._state = ConnectionState.DISCONNECTED
                self._connected_at = None
                self._active_backend = None
                self._active_protocol = None
                self._public_ip = None
            self._notify()

    # ------------------------------------------------------------------
    # Selection automatique
    # ------------------------------------------------------------------

    def _select_best_protocol(self, server: ServerInfo) -> Protocol:
        if server.supports_wg and self._backends[Protocol.WIREGUARD].is_available():
            return Protocol.WIREGUARD
        if server.supports_ikev2 and self._backends[Protocol.IKEV2].is_available():
            return Protocol.IKEV2
        if not self._real_mode:
            # En demo on garde WireGuard comme protocole "moderne".
            return Protocol.WIREGUARD
        return Protocol.OPENVPN

    def _select_best_server(self) -> ServerInfo:
        # Tri par charge croissante puis latence theorique.
        return sorted(self._servers,
                      key=lambda s: (s.load_percent, s.latency_ms or 999))[0]

    # ------------------------------------------------------------------
    # Mesure parallele de latence sur tous les serveurs
    # ------------------------------------------------------------------

    def measure_all_latencies(self, max_workers: int = 8,
                              timeout: float = 3.0) -> Dict[str, int]:
        """
        Pingue tous les serveurs en parallele, met a jour les latences
        reelles dans le catalogue, et renvoie un dict {server_id: ms}.
        Bloquant : a appeler dans un thread depuis l'UI.
        """
        results: Dict[str, int] = {}

        def ping_one(srv: ServerInfo) -> Optional[int]:
            host = srv.endpoint_ikev2 or srv.public_ip
            return measure_latency_ms(host, count=2)

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers) as pool:
            futures = {pool.submit(ping_one, s): s for s in self._servers}
            try:
                for future in concurrent.futures.as_completed(
                        futures, timeout=timeout * 2):
                    srv = futures[future]
                    try:
                        lat = future.result(timeout=timeout)
                    except Exception:
                        lat = None
                    if lat is not None:
                        srv.latency_ms = lat
                        results[srv.id] = lat
                    else:
                        results[srv.id] = srv.latency_ms
            except concurrent.futures.TimeoutError:
                log.warning("Mesure latence : timeout global")

        log.info("Mesure parallele : %d/%d serveurs",
                 len(results), len(self._servers))
        try:
            self.on_latencies_updated(results)
        except Exception:
            pass
        return results

    def measure_all_latencies_async(self,
            on_done: Optional[Callable[[Dict[str, int]], None]] = None) -> None:
        """Lance la mesure en arriere-plan, ne bloque pas."""
        def worker():
            res = self.measure_all_latencies()
            if on_done:
                try:
                    on_done(res)
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True,
                         name="aurora-latency-scan").start()

    # ------------------------------------------------------------------
    # Catalogue d'exemple
    # ------------------------------------------------------------------

    def _build_server_catalog(self) -> List[ServerInfo]:
        raw = [
            ("fr-par-01", "France",        "Paris",     "185.10.20.30", 22, 12),
            ("fr-mrs-01", "France",        "Marseille", "185.10.21.31", 28, 18),
            ("ch-zur-01", "Suisse",        "Zurich",    "185.10.22.32", 32,  9),
            ("de-fra-01", "Allemagne",     "Francfort", "185.10.23.33", 35, 22),
            ("nl-ams-01", "Pays-Bas",      "Amsterdam", "185.10.24.34", 38, 14),
            ("uk-lon-01", "Royaume-Uni",   "Londres",   "185.10.25.35", 41, 20),
            ("us-nyc-01", "Etats-Unis",    "New York",  "185.10.26.36", 92, 35),
            ("us-lax-01", "Etats-Unis",    "Los Angeles","185.10.27.37",148, 28),
            ("ca-mtl-01", "Canada",        "Montreal",  "185.10.28.38", 95, 17),
            ("jp-tok-01", "Japon",         "Tokyo",     "185.10.29.39",210, 30),
            ("sg-sin-01", "Singapour",     "Singapour", "185.10.30.40",195, 25),
            ("au-syd-01", "Australie",     "Sydney",    "185.10.31.41",260, 33),
        ]
        return [
            ServerInfo(
                id=i, country=c, city=ci, public_ip=ip,
                latency_ms=lat, load_percent=load,
                endpoint_wg=f"wg-{i}.aurora.net:51820",
                endpoint_ikev2=f"ike-{i}.aurora.net",
                endpoint_openvpn=f"ovpn-{i}.aurora.net 1194",
            )
            for (i, c, ci, ip, lat, load) in raw
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _notify(self) -> None:
        try:
            self.on_state_change(self._state)
        except Exception:
            pass
