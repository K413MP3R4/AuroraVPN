"""
============================================================================
 AuroraVPN - Module de securite (implementations Windows reelles)
============================================================================
 Fichier  : security.py
 Role     : Centralise les protections : kill switch, anti-fuite DNS/IPv6,
            PFS, hybride post-quantique, split tunneling, blocage trackers.

 Sur Windows, les implementations reelles s'appuient sur :
   - PowerShell New-NetFirewallRule pour le kill switch
   - netsh interface / dns pour DNS et IPv6
   - Une boucle de detection de fuites en thread d'arriere-plan

 Toutes les operations systeme sont gardees par le drapeau
 UserConfig.real_security : si False, on reste en mode demo (pas
 d'effet sur la machine).
============================================================================
"""

from __future__ import annotations

import dataclasses
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from utils import (
    IS_WINDOWS, hidden_subprocess_kwargs, is_admin, log, fetch_public_ip
)


# ============================================================================
#  Etat
# ============================================================================

@dataclass
class SecurityStatus:
    """Snapshot de l'etat des protections."""
    kill_switch:          bool = True
    dns_protection:       bool = True
    leak_protection:      bool = True
    pfs:                  bool = True
    post_quantum:         bool = False
    split_tunneling:      bool = False
    auto_reconnect:       bool = True
    auto_on_public_wifi:  bool = True
    block_trackers:       bool = True
    # Internes
    leak_detected:        bool = False
    last_check:           float = 0.0


# Constantes Windows
_KS_RULE_NAME = "AuroraVPN_KillSwitch"
_DNS_PRIMARY  = "1.1.1.1"
_DNS_SECONDARY = "9.9.9.9"


# ============================================================================
#  Manager
# ============================================================================

class SecurityManager:
    """
    Gestion centralisee des protections.

    Le parametre `real_mode` decide si les methodes _apply_* effectuent
    de vrais appels systeme (Windows) ou restent en simulation. Quand
    real_mode est True mais que le processus n'est pas Administrator,
    les operations sont skipped avec un warning dans les logs.
    """

    def __init__(self, real_mode: bool = False):
        self._status = SecurityStatus()
        self._real_mode = real_mode
        self._leak_thread: Optional[threading.Thread] = None
        self._leak_stop = threading.Event()
        self._expected_vpn_ip: Optional[str] = None
        self.on_leak_detected: Callable[[bool], None] = lambda detected: None
        # Securite : nettoyage proactif d'une eventuelle regle firewall
        # orpheline d'une session precedente (si l'app a crashe).
        self._cleanup_orphan_rules()

    # ------------------------------------------------------------------
    # Lecture / mode
    # ------------------------------------------------------------------

    @property
    def status(self) -> SecurityStatus:
        return dataclasses.replace(self._status)

    def set_real_mode(self, enabled: bool) -> None:
        self._real_mode = enabled
        log.info("Security real_mode -> %s", enabled)

    def hydrate_from_config(self, cfg) -> None:
        """Recopie les toggles depuis UserConfig vers l'etat interne."""
        self._status.kill_switch          = cfg.kill_switch
        self._status.dns_protection       = cfg.dns_protection
        self._status.leak_protection      = cfg.leak_protection
        self._status.pfs                  = cfg.pfs
        self._status.post_quantum         = cfg.post_quantum
        self._status.split_tunneling      = cfg.split_tunneling
        self._status.auto_reconnect       = cfg.auto_reconnect
        self._status.auto_on_public_wifi  = cfg.auto_on_public_wifi
        self._status.block_trackers       = cfg.block_trackers

    def export_to_config(self, cfg) -> None:
        cfg.kill_switch         = self._status.kill_switch
        cfg.dns_protection      = self._status.dns_protection
        cfg.leak_protection     = self._status.leak_protection
        cfg.pfs                 = self._status.pfs
        cfg.post_quantum        = self._status.post_quantum
        cfg.split_tunneling     = self._status.split_tunneling
        cfg.auto_reconnect      = self._status.auto_reconnect
        cfg.auto_on_public_wifi = self._status.auto_on_public_wifi
        cfg.block_trackers      = self._status.block_trackers

    # ------------------------------------------------------------------
    # Setters
    # ------------------------------------------------------------------

    def set_kill_switch(self, enabled: bool) -> None:
        self._status.kill_switch = enabled
        self._apply_kill_switch(enabled)

    def set_dns_protection(self, enabled: bool) -> None:
        self._status.dns_protection = enabled
        self._apply_dns_protection(enabled)

    def set_leak_protection(self, enabled: bool) -> None:
        self._status.leak_protection = enabled
        self._apply_leak_protection(enabled)

    def set_pfs(self, enabled: bool) -> None:
        # PFS se gere au niveau du protocole (suite IKE / Curve25519).
        self._status.pfs = enabled

    def set_post_quantum(self, enabled: bool) -> None:
        self._status.post_quantum = enabled

    def set_split_tunneling(self, enabled: bool) -> None:
        self._status.split_tunneling = enabled
        self._apply_split_tunneling(enabled)

    def set_auto_reconnect(self, enabled: bool) -> None:
        self._status.auto_reconnect = enabled

    def set_auto_on_public_wifi(self, enabled: bool) -> None:
        self._status.auto_on_public_wifi = enabled

    def set_block_trackers(self, enabled: bool) -> None:
        self._status.block_trackers = enabled
        self._apply_tracker_blocking(enabled)

    # ------------------------------------------------------------------
    # Surveillance des fuites (thread)
    # ------------------------------------------------------------------

    def start_leak_monitor(self, expected_vpn_ip: Optional[str] = None) -> None:
        """Lance la verification periodique IP/DNS toutes les 30 s."""
        self._expected_vpn_ip = expected_vpn_ip
        if self._leak_thread and self._leak_thread.is_alive():
            return
        self._leak_stop.clear()
        self._leak_thread = threading.Thread(
            target=self._leak_loop, daemon=True, name="aurora-leak-monitor"
        )
        self._leak_thread.start()
        log.info("Leak monitor demarre (cible attendue: %s)", expected_vpn_ip)

    def stop_leak_monitor(self) -> None:
        self._leak_stop.set()
        self._leak_thread = None
        self._status.leak_detected = False

    def _leak_loop(self) -> None:
        while not self._leak_stop.is_set():
            try:
                if self._status.leak_protection:
                    current = fetch_public_ip(timeout=2.5)
                    self._status.last_check = time.time()
                    if current and self._expected_vpn_ip:
                        leak = (current != self._expected_vpn_ip)
                        if leak != self._status.leak_detected:
                            self._status.leak_detected = leak
                            try:
                                self.on_leak_detected(leak)
                            except Exception:
                                pass
                            if leak:
                                log.warning(
                                    "FUITE detectee : IP %s != attendue %s",
                                    current, self._expected_vpn_ip,
                                )
            except Exception as exc:
                log.debug("Leak loop erreur: %s", exc)
            # Sommeil interruptible.
            self._leak_stop.wait(30.0)

    # ------------------------------------------------------------------
    # Implementations systeme (gardees par real_mode + admin)
    # ------------------------------------------------------------------

    def _can_apply(self) -> bool:
        if not self._real_mode:
            return False
        if not IS_WINDOWS:
            log.debug("Operation Windows ignoree (OS non Windows)")
            return False
        if not is_admin():
            log.warning("Operation systeme requiert Administrateur, ignoree.")
            return False
        return True

    def _ps(self, command: str) -> bool:
        """Execute une commande PowerShell silencieusement."""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True, text=True, timeout=15,
                **hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                log.warning("PowerShell echec (%s): %s",
                            result.returncode, result.stderr.strip())
                return False
            return True
        except Exception as exc:
            log.warning("PowerShell exception : %s", exc)
            return False

    def _netsh(self, *args: str) -> bool:
        try:
            result = subprocess.run(
                ["netsh", *args],
                capture_output=True, text=True, timeout=10,
                **hidden_subprocess_kwargs(),
            )
            if result.returncode != 0:
                log.debug("netsh %s -> %s", " ".join(args), result.stderr.strip())
                return False
            return True
        except Exception as exc:
            log.warning("netsh exception : %s", exc)
            return False

    # ----- Kill switch -----
    #
    # ATTENTION : "block all outbound" appliqué AVANT que le VPN ne soit
    # connecté empêcherait le VPN lui-même de se connecter. Pour eviter
    # de bricker le reseau de l'utilisateur, on ne cree la regle qu'au
    # moment ou le tunnel est etabli (via arm_kill_switch) et on la
    # retire systematiquement a la deconnexion ou a la fermeture.
    # Le simple toggle ne fait QUE memoriser l'intention.

    def _apply_kill_switch(self, enabled: bool) -> None:
        """Le toggle ne fait qu'enregistrer l'intention.
        L'application physique se fait via arm_kill_switch / disarm_kill_switch
        appeles par le moteur a la (de)connexion."""
        log.info("Kill switch -> intent=%s (s'appliquera a la connexion)",
                 enabled)

    def arm_kill_switch(self, vpn_endpoint_ip: Optional[str] = None) -> None:
        """A appeler par l'engine apres CONNECTED. Cree la regle WFP.
        Si vpn_endpoint_ip est fourni, on autorise le trafic vers cette
        IP (sinon l'utilisateur perdrait le tunnel)."""
        if not (self._real_mode and self._status.kill_switch):
            return
        if not self._can_apply():
            return
        # Idempotent : on supprime puis on recree.
        self._ps(
            f"Remove-NetFirewallRule -DisplayName '{_KS_RULE_NAME}' "
            f"-ErrorAction SilentlyContinue"
        )
        # Regle d'exception pour l'endpoint VPN (priorite plus haute).
        if vpn_endpoint_ip:
            self._ps(
                f"New-NetFirewallRule -DisplayName '{_KS_RULE_NAME}_allow' "
                f"-Direction Outbound -Action Allow -Profile Any "
                f"-RemoteAddress '{vpn_endpoint_ip}' "
                f"-Description 'AuroraVPN allow endpoint' "
                f"-Enabled True | Out-Null"
            )
        # Regle de blocage globale.
        ok = self._ps(
            f"New-NetFirewallRule -DisplayName '{_KS_RULE_NAME}' "
            f"-Direction Outbound -Action Block -Profile Any "
            f"-Description 'AuroraVPN kill switch' "
            f"-Enabled True | Out-Null"
        )
        log.info("Kill switch arme : %s", "OK" if ok else "ECHEC")

    def disarm_kill_switch(self) -> None:
        """Retire les regles. Idempotent. A appeler par l'engine apres
        deconnexion ET par l'app au quit (safeguard)."""
        if not IS_WINDOWS:
            return
        # Pas de gardes _can_apply : on veut TOUJOURS pouvoir nettoyer,
        # meme apres un real_mode -> demo.
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-Command",
                 f"Remove-NetFirewallRule -DisplayName '{_KS_RULE_NAME}' "
                 f"-ErrorAction SilentlyContinue;"
                 f"Remove-NetFirewallRule -DisplayName '{_KS_RULE_NAME}_allow' "
                 f"-ErrorAction SilentlyContinue"],
                capture_output=True, text=True, timeout=10,
                **hidden_subprocess_kwargs(),
            )
            log.info("Kill switch desarme")
        except Exception as exc:
            log.warning("disarm_kill_switch : %s", exc)

    def _cleanup_orphan_rules(self) -> None:
        """Au demarrage, supprime toute regle laissee par une session
        precedente qui aurait crashe."""
        if IS_WINDOWS and is_admin():
            self.disarm_kill_switch()

    # ----- DNS chiffre -----

    def _apply_dns_protection(self, enabled: bool) -> None:
        """
        Force les serveurs DNS sur toutes les interfaces actives.
        Active DoH (Windows 11) si disponible.
        """
        if not self._can_apply():
            return
        if enabled:
            ok = self._ps(
                f"Get-DnsClient | ForEach-Object {{ "
                f"Set-DnsClientServerAddress -InterfaceIndex $_.InterfaceIndex "
                f"-ServerAddresses ('{_DNS_PRIMARY}','{_DNS_SECONDARY}') "
                f"-ErrorAction SilentlyContinue }}"
            )
            # DoH (Windows 11+, ignore l'erreur sur Windows 10)
            self._netsh(
                "dns", "add", "encryption", f"server={_DNS_PRIMARY}",
                "dohtemplate=https://cloudflare-dns.com/dns-query",
                "autoupgrade=yes", "udpfallback=no",
            )
            log.info("DNS protection appliquee : %s", "OK" if ok else "PARTIEL")
        else:
            self._ps(
                "Get-DnsClient | ForEach-Object { "
                "Set-DnsClientServerAddress -InterfaceIndex $_.InterfaceIndex "
                "-ResetServerAddresses -ErrorAction SilentlyContinue }"
            )
            log.info("DNS protection retiree")

    # ----- Anti-fuite IPv6 -----

    def _apply_leak_protection(self, enabled: bool) -> None:
        """
        Desactive IPv6 sur toutes les interfaces (anti-fuite la plus simple).
        En production avancee, on prefererait un filtre WFP plus fin.
        """
        if not self._can_apply():
            return
        if enabled:
            ok = self._ps(
                "Get-NetAdapter -Physical | Disable-NetAdapterBinding "
                "-ComponentID ms_tcpip6 -ErrorAction SilentlyContinue"
            )
            log.info("IPv6 desactive : %s", "OK" if ok else "ECHEC")
        else:
            self._ps(
                "Get-NetAdapter -Physical | Enable-NetAdapterBinding "
                "-ComponentID ms_tcpip6 -ErrorAction SilentlyContinue"
            )
            log.info("IPv6 reactive")

    # ----- Split tunneling -----

    def _apply_split_tunneling(self, enabled: bool) -> None:
        """
        Pour la connexion VPN nommee 'AuroraVPN', active le split tunneling.
        Le mappage par application reste a configurer cote client (Windows
        gere cela via Set-VpnConnection -SplitTunneling).
        """
        if not self._can_apply():
            return
        flag = "$true" if enabled else "$false"
        ok = self._ps(
            f"Set-VpnConnection -Name 'AuroraVPN' -SplitTunneling {flag} "
            f"-ErrorAction SilentlyContinue"
        )
        log.info("Split tunneling -> %s : %s", enabled, "OK" if ok else "N/A")

    # ----- Blocage trackers -----

    def _apply_tracker_blocking(self, enabled: bool) -> None:
        """
        Le blocage avance (hosts file ou resolveur DNS local) merite
        un installateur dedie. Ici on log seulement l'intention.
        """
        log.info("Tracker blocking -> %s (a brancher sur resolveur DNS)", enabled)
