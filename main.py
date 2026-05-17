"""
============================================================================
 AuroraVPN - Application VPN moderne pour Windows (UI v2 polish)
============================================================================
 Fichier  : main.py
 Role     : Interface graphique CustomTkinter, hero anime, system tray,
            persistance, integration moteur VPN reel/demo.
 Theme    : Sombre + accents violet (#8B5CF6) et cyan (#22D3EE)
============================================================================

Lancement :
    python main.py

Compilation .exe Windows :
    build_windows.bat
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

try:
    import customtkinter as ctk
except ImportError:
    print("[ERREUR] CustomTkinter n'est pas installe.")
    print("         Lancez : pip install -r requirements.txt")
    sys.exit(1)

# pystray + Pillow sont optionnels (system tray).
try:
    import pystray
    from PIL import Image, ImageDraw
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False

from config import UserConfig
from utils import (
    IS_WINDOWS, acquire_single_instance, release_single_instance,
    is_admin, log,
)
from vpn_engine import VPNEngine, ConnectionState, Protocol, ServerInfo
from security import SecurityManager, SecurityStatus
from features import (
    MultiHopManager, TorOverVPN, ThreatProtection,
    VpnAccelerator, Notifier,
)
from widgets_extra import WorldMap, SpeedChart, LeakTestPanel
from dns_resolver import LocalDnsResolver
import i18n


# ============================================================================
#  CHARTE GRAPHIQUE
# ============================================================================

COLOR_BG          = "#0A0A12"
COLOR_BG_ALT      = "#0E0E18"
COLOR_SURFACE     = "#15151F"
COLOR_SURFACE_2   = "#1E1E2C"
COLOR_SURFACE_3   = "#2A2A3A"
COLOR_BORDER      = "#26263A"
COLOR_BORDER_LIT  = "#3A3A55"
COLOR_TEXT        = "#F1F2F8"
COLOR_TEXT_SOFT   = "#C4C5D0"
COLOR_TEXT_MUTED  = "#7E7F95"
COLOR_VIOLET      = "#8B5CF6"
COLOR_VIOLET_2    = "#A78BFA"
COLOR_VIOLET_DARK = "#6D28D9"
COLOR_CYAN        = "#22D3EE"
COLOR_CYAN_DIM    = "#0E7490"
COLOR_GREEN       = "#34D399"
COLOR_GREEN_DIM   = "#065F46"
COLOR_AMBER       = "#FBBF24"
COLOR_RED         = "#EF4444"

FONT_FAMILY       = "Segoe UI"


# ============================================================================
#  WIDGETS PERSONNALISES
# ============================================================================

class HeroOrb(ctk.CTkCanvas):
    """
    Disque central avec halos concentriques anime selon l'etat.
    - DISCONNECTED : halo gris fixe
    - CONNECTING   : halos cyan tournants
    - CONNECTED    : halos verts pulsants doux
    - ERROR        : halo rouge fixe
    """

    SIZE = 180

    def __init__(self, parent, on_click: Callable[[], None]):
        super().__init__(parent, width=self.SIZE, height=self.SIZE,
                         bg=COLOR_SURFACE, highlightthickness=0)
        self._on_click = on_click
        self._state = ConnectionState.DISCONNECTED
        self._phase = 0.0
        self._duration_text = ""
        self._sub_text = "Pret"
        self._tick_after_id: Optional[str] = None
        self._animating = False
        self.bind("<Button-1>", lambda _e: self._on_click())
        self.bind("<Destroy>", lambda _e: self.stop_animation())
        self.configure(cursor="hand2")
        self._draw()  # Premier rendu statique

    def set_state(self, state: ConnectionState, duration_text: str = "",
                  sub_text: str = "") -> None:
        self._state = state
        self._duration_text = duration_text
        self._sub_text = sub_text
        # Animation seulement si CONNECTING ou CONNECTED.
        if state in (ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            self.start_animation()
        else:
            self.stop_animation()
        self._draw()

    def start_animation(self) -> None:
        if self._animating:
            return
        self._animating = True
        self._tick()

    def stop_animation(self) -> None:
        self._animating = False
        if self._tick_after_id is not None:
            try:
                self.after_cancel(self._tick_after_id)
            except Exception:
                pass
            self._tick_after_id = None

    def _tick(self) -> None:
        if not self._animating:
            return
        try:
            if not self.winfo_exists():
                self._animating = False
                return
        except Exception:
            return
        self._phase = (self._phase + 0.04) % 1.0
        self._draw()
        self._tick_after_id = self.after(80, self._tick)

    def _draw(self) -> None:
        self.delete("all")
        s = self.SIZE
        cx = cy = s // 2

        # Couleurs selon etat
        if self._state == ConnectionState.CONNECTED:
            c_main = COLOR_GREEN
            c_glow = COLOR_GREEN
            label  = "CONNECTE"
        elif self._state == ConnectionState.CONNECTING:
            c_main = COLOR_CYAN
            c_glow = COLOR_CYAN
            label  = "CONNEXION..."
        elif self._state == ConnectionState.ERROR:
            c_main = COLOR_RED
            c_glow = COLOR_RED
            label  = "ERREUR"
        else:
            c_main = COLOR_TEXT_MUTED
            c_glow = COLOR_VIOLET
            label  = "PRET"

        # Halos animes (3 anneaux dephases)
        for i, offset in enumerate([0.0, 0.33, 0.66]):
            phase = (self._phase + offset) % 1.0
            radius = int(40 + phase * 50)
            alpha = 1.0 - phase
            # Tk ne supporte pas l'alpha vrai sur Canvas ; on triche en
            # melangeant la couleur vers le fond pour simuler la fade.
            color = _blend_hex(c_glow, COLOR_BG, 1.0 - alpha)
            try:
                self.create_oval(cx - radius, cy - radius,
                                 cx + radius, cy + radius,
                                 outline=color, width=2)
            except Exception:
                pass

        # Disque principal
        r = 50
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill=COLOR_SURFACE_2, outline=c_main, width=2)
        # Pastille interieure
        r2 = 8
        self.create_oval(cx - r2, cy - r2, cx + r2, cy + r2,
                         fill=c_main, outline="")

        # Etiquettes (etat + duree)
        self.create_text(cx, cy - 22, text=label,
                         fill=c_main,
                         font=(FONT_FAMILY, 10, "bold"))
        if self._duration_text:
            self.create_text(cx, cy + 22, text=self._duration_text,
                             fill=COLOR_TEXT,
                             font=(FONT_FAMILY, 12, "bold"))


class InfoCard(ctk.CTkFrame):
    """Carte d'information : icone + libelle + valeur (compacte)."""

    def __init__(self, parent, label: str, value: str = "--", icon: str = ""):
        super().__init__(parent, fg_color=COLOR_SURFACE_2, corner_radius=10,
                         border_color=COLOR_BORDER, border_width=1)
        self.grid_columnconfigure(0, weight=1)

        head = ctk.CTkLabel(
            self,
            text=f"{icon}  {label}".strip(),
            text_color=COLOR_TEXT_MUTED,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        )
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        self._value_label = ctk.CTkLabel(
            self,
            text=value,
            text_color=COLOR_TEXT,
            font=(FONT_FAMILY, 13, "bold"),
            anchor="w",
        )
        self._value_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))

    def set_value(self, value: str, color: Optional[str] = None) -> None:
        self._value_label.configure(text=value)
        if color:
            self._value_label.configure(text_color=color)


class SecurityBadge(ctk.CTkFrame):
    """Badge ronde compact pour une protection."""

    def __init__(self, parent, label: str):
        super().__init__(parent, fg_color="transparent")
        self._dot = ctk.CTkFrame(self, width=8, height=8, corner_radius=4,
                                 fg_color=COLOR_TEXT_MUTED)
        self._dot.grid(row=0, column=0, padx=(0, 6), pady=4)
        self._dot.grid_propagate(False)
        self._label = ctk.CTkLabel(
            self, text=label, text_color=COLOR_TEXT_MUTED,
            font=(FONT_FAMILY, 10),
        )
        self._label.grid(row=0, column=1, sticky="w")

    def set_active(self, active: bool, warning: bool = False) -> None:
        if warning:
            self._dot.configure(fg_color=COLOR_AMBER)
            self._label.configure(text_color=COLOR_AMBER)
        elif active:
            self._dot.configure(fg_color=COLOR_GREEN)
            self._label.configure(text_color=COLOR_TEXT)
        else:
            self._dot.configure(fg_color=COLOR_TEXT_MUTED)
            self._label.configure(text_color=COLOR_TEXT_MUTED)


# ============================================================================
#  HELPERS GRAPHIQUES
# ============================================================================

def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb

def _blend_hex(c1: str, c2: str, t: float) -> str:
    """Melange c1 vers c2 avec t in [0,1]."""
    a = _hex_to_rgb(c1)
    b = _hex_to_rgb(c2)
    out = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return _rgb_to_hex(out)


# ============================================================================
#  FENETRE PRINCIPALE
# ============================================================================

class AuroraVPNApp(ctk.CTk):
    """Fenetre principale ~480 x 760."""

    WIDTH  = 480
    HEIGHT = 780

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # Configuration persistee
        self.config_data = UserConfig.load()

        # Langue : config explicite ou auto-detect.
        if self.config_data.language:
            i18n.set_language(self.config_data.language)
        # Sinon i18n auto-detecte la langue systeme au load du module.

        # Moteur + securite (avec mode loopback pour tester sans serveur)
        self.engine = VPNEngine(
            real_mode=self.config_data.real_subprocess,
            host_override=self.config_data.real_endpoint_host,
            loopback_mode=self.config_data.loopback_mode,
        )
        self.engine.on_state_change = self._on_engine_state_change
        self.engine.on_public_ip    = lambda ip: self.after(0, self._update_ip_label, ip)

        self.security = SecurityManager(real_mode=self.config_data.real_security)
        self.security.hydrate_from_config(self.config_data)
        self.security.on_leak_detected = lambda d: self.after(0, self._on_leak, d)

        # Fonctionnalites avancees (v3)
        self.multi_hop      = MultiHopManager()
        self.multi_hop.enable(self.config_data.multi_hop_enabled)
        if self.config_data.multi_hop_exit_id and self.config_data.last_server_id:
            try:
                self.multi_hop.set_route(self.config_data.last_server_id,
                                         self.config_data.multi_hop_exit_id)
            except Exception:
                pass

        self.tor_over_vpn   = TorOverVPN()
        self.threat_protect = ThreatProtection()
        self.threat_protect.enable(self.config_data.threat_protection)
        self.accelerator    = VpnAccelerator()
        self.accelerator.enable(self.config_data.accelerator_enabled)
        self.notifier       = Notifier()

        # Resolveur DNS local (active par config). Branche sur la
        # ThreatProtection pour bloquer en NXDOMAIN les domaines listes.
        self.dns_resolver: Optional[LocalDnsResolver] = None
        if self.config_data.dns_resolver_enabled:
            self._start_dns_resolver()

        # Dashboard et fenetres secondaires (single instance par type)
        self._dashboard: Optional["DashboardWindow"] = None
        self._settings_win: Optional["SettingsWindow"] = None
        self._servers_win: Optional["ServersWindow"] = None

        # Suivi des after() pour eviter les chaines paralleles
        self._refresh_after_id: Optional[str] = None
        self._speed_after_id: Optional[str] = None
        self._is_minimized = False

        # Restauration serveur prefere
        if self.config_data.last_server_id:
            srv = self.engine.get_server(self.config_data.last_server_id)
            if srv:
                self.engine.select_server(srv.id)

        # Fenetre
        self.title("AuroraVPN")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(self.WIDTH, self.HEIGHT)
        self.configure(fg_color=COLOR_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # System tray
        self._tray_icon: Optional["pystray.Icon"] = None
        self._tray_thread: Optional[threading.Thread] = None
        if _TRAY_AVAILABLE and self.config_data.minimize_to_tray:
            self._setup_tray()

        # Construction de l'UI
        self._build_header()
        self._build_hero()
        self._build_info_grid()
        self._build_protocol_selector()
        self._build_security_panel()
        self._build_footer()

        # Demarrage minimise
        if self.config_data.start_minimized and self._tray_icon:
            self.after(100, self.withdraw)

        # Raccourcis clavier (sur la fenetre principale uniquement, pas
        # bind_all qui hijackerait les champs texte / autres fenetres).
        self.bind("<Control-k>",  lambda _e: self._toggle_connection())
        self.bind("<Control-m>",  lambda _e: self._open_dashboard())
        self.bind("<Control-l>",  lambda _e: self._open_servers())
        self.bind("<F5>",         lambda _e: self._force_ip_refresh())

        # Premier rafraichissement
        self._refresh_ui()

        # Mesure de latence parallele au demarrage (en arriere-plan).
        if self.config_data.auto_ping_on_start:
            self.engine.measure_all_latencies_async(
                on_done=lambda _r: self.after(0, self._refresh_ui_once)
            )

        # PREMIER LANCEMENT : assistant de configuration
        if not self.config_data.setup_completed:
            self.after(300, self._open_setup_wizard)
        else:
            # Auto-connexion uniquement si l'assistant a deja ete passe.
            if self.config_data.auto_connect_on_start:
                delay = max(100, int(self.config_data.auto_connect_delay_ms))
                self.after(delay, self._auto_connect_once)

        # Avertissement admin si reel demande sans elevation
        if self.config_data.real_subprocess and IS_WINDOWS and not is_admin():
            self.after(800, self._warn_admin_needed)

    def _open_setup_wizard(self) -> None:
        """Ouvre l'assistant de configuration (premier lancement ou manuel)."""
        SetupWizard(self, self.config_data,
                    on_completed=self._on_setup_completed)

    def _on_setup_completed(self) -> None:
        """Callback apres fermeture/finalisation de l'assistant."""
        self.config_data.setup_completed = True
        self.config_data.save()
        # Re-cree le moteur avec les nouvelles options (real / loopback).
        self.engine.set_real_mode(self.config_data.real_subprocess)
        self.engine.set_loopback_mode(self.config_data.loopback_mode)
        self.engine.set_host_override(self.config_data.real_endpoint_host)
        self._refresh_ui_once()

    def _auto_connect_once(self) -> None:
        """Lance une connexion automatique si on est encore deconnecte."""
        if self.engine.state == ConnectionState.DISCONNECTED:
            log.info("Auto-connexion declenchee (auto_connect_on_start=True)")
            self._toggle_connection()

    # --------------------------------------------------------------------
    #  DNS resolver helpers
    # --------------------------------------------------------------------

    def _start_dns_resolver(self) -> None:
        """Demarre le resolveur DNS local. Idempotent."""
        if self.dns_resolver and self.dns_resolver.is_running:
            return
        self.dns_resolver = LocalDnsResolver(
            host="127.0.0.1",
            port=self.config_data.dns_resolver_port,
            blocker=self.threat_protect.check_domain,
        )
        if self.dns_resolver.start():
            log.info("DNS resolver actif sur 127.0.0.1:%d",
                     self.config_data.dns_resolver_port)
        else:
            self.dns_resolver = None

    def _stop_dns_resolver(self) -> None:
        if self.dns_resolver:
            self.dns_resolver.stop()
            self.dns_resolver = None

    # --------------------------------------------------------------------
    #  Construction de l'interface
    # --------------------------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color=COLOR_BG, height=64)
        header.pack(fill="x", padx=22, pady=(20, 0))
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        # Logo : disque concentrique violet -> cyan
        logo = ctk.CTkCanvas(header, width=40, height=40,
                             bg=COLOR_BG, highlightthickness=0)
        logo.grid(row=0, column=0, rowspan=2, sticky="w")
        logo.create_oval(2, 2, 38, 38, fill=COLOR_VIOLET, outline="")
        logo.create_oval(8, 8, 32, 32, fill=COLOR_VIOLET_DARK, outline="")
        logo.create_oval(13, 13, 27, 27, fill=COLOR_CYAN, outline="")
        logo.create_oval(17, 17, 23, 23, fill=COLOR_BG, outline="")

        # Titre
        title = ctk.CTkLabel(
            header, text="AURORA  VPN",
            text_color=COLOR_TEXT,
            font=(FONT_FAMILY, 17, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=1, sticky="sw", padx=(14, 0))

        # Sous-titre / etat global
        sub = ctk.CTkLabel(
            header,
            text="Tunnel chiffre . Confidentialite . Performance",
            text_color=COLOR_TEXT_MUTED,
            font=(FONT_FAMILY, 9),
            anchor="w",
        )
        sub.grid(row=1, column=1, sticky="nw", padx=(14, 0))

        # Boutons (minimiser + parametres)
        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.grid(row=0, column=2, rowspan=2, sticky="e")

        if self._tray_supported():
            mini = ctk.CTkButton(
                btns, text="—", width=30, height=30,
                fg_color=COLOR_SURFACE, hover_color=COLOR_SURFACE_2,
                text_color=COLOR_TEXT_MUTED, corner_radius=8,
                font=(FONT_FAMILY, 12, "bold"),
                command=self._minimize_to_tray,
            )
            mini.pack(side="left", padx=(0, 6))

        wizard_btn = ctk.CTkButton(
            btns, text="?", width=30, height=30,
            fg_color=COLOR_SURFACE, hover_color=COLOR_SURFACE_2,
            text_color=COLOR_CYAN, corner_radius=8,
            font=(FONT_FAMILY, 13, "bold"),
            command=self._open_setup_wizard,
        )
        wizard_btn.pack(side="left", padx=(0, 6))

        gear = ctk.CTkButton(
            btns, text="⚙", width=30, height=30,
            fg_color=COLOR_SURFACE, hover_color=COLOR_SURFACE_2,
            text_color=COLOR_TEXT_MUTED, corner_radius=8,
            font=(FONT_FAMILY, 14),
            command=self._open_settings,
        )
        gear.pack(side="left")

    def _build_hero(self) -> None:
        wrap = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=18,
                            border_color=COLOR_BORDER, border_width=1)
        wrap.pack(fill="x", padx=22, pady=(18, 0))

        inner = ctk.CTkFrame(wrap, fg_color="transparent")
        inner.pack(padx=10, pady=14)

        # Orb anime cliquable
        self._orb = HeroOrb(inner, on_click=self._toggle_connection)
        self._orb.pack()

        # Etiquette texte sous l'orb
        self._hero_sub = ctk.CTkLabel(
            inner, text="Cliquez pour vous connecter",
            text_color=COLOR_TEXT_SOFT,
            font=(FONT_FAMILY, 11),
        )
        self._hero_sub.pack(pady=(4, 0))

        # Bouton d'action principal
        self._action_btn = ctk.CTkButton(
            wrap, text="CONNECTER",
            font=(FONT_FAMILY, 13, "bold"),
            fg_color=COLOR_VIOLET,
            hover_color=COLOR_VIOLET_DARK,
            text_color="#FFFFFF",
            corner_radius=14,
            height=52,
            command=self._toggle_connection,
        )
        self._action_btn.pack(fill="x", padx=18, pady=(8, 16))

    def _build_info_grid(self) -> None:
        grid = ctk.CTkFrame(self, fg_color=COLOR_BG)
        grid.pack(fill="x", padx=22, pady=(14, 0))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)

        self._card_server  = InfoCard(grid, "SERVEUR",  "Auto",  icon="◎")
        self._card_server.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._card_latency = InfoCard(grid, "LATENCE", "-- ms", icon="≡")
        self._card_latency.grid(row=0, column=1, sticky="ew", padx=4)

        self._card_proto   = InfoCard(grid, "PROTOCOLE", "Auto", icon="§")
        self._card_proto.grid(row=0, column=2, sticky="ew", padx=(4, 0))

    def _build_protocol_selector(self) -> None:
        wrap = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=12,
                            border_color=COLOR_BORDER, border_width=1)
        wrap.pack(fill="x", padx=22, pady=(14, 0))

        label = ctk.CTkLabel(
            wrap, text="PROTOCOLE", text_color=COLOR_TEXT_MUTED,
            font=(FONT_FAMILY, 9, "bold"), anchor="w",
        )
        label.pack(fill="x", padx=14, pady=(10, 4))

        self._proto_var = ctk.StringVar(value=self.config_data.last_protocol)
        seg = ctk.CTkSegmentedButton(
            wrap,
            values=["Auto", "WireGuard", "IKEv2", "OpenVPN"],
            variable=self._proto_var,
            command=self._on_protocol_changed,
            fg_color=COLOR_SURFACE_2,
            selected_color=COLOR_VIOLET,
            selected_hover_color=COLOR_VIOLET_DARK,
            unselected_color=COLOR_SURFACE_2,
            unselected_hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            font=(FONT_FAMILY, 10, "bold"),
            height=30,
        )
        seg.pack(fill="x", padx=14, pady=(0, 8))

        self._reco_label = ctk.CTkLabel(
            wrap,
            text="Le moteur choisit automatiquement le meilleur protocole.",
            text_color=COLOR_CYAN,
            font=(FONT_FAMILY, 9),
            anchor="w", justify="left",
            wraplength=self.WIDTH - 90,
        )
        self._reco_label.pack(fill="x", padx=14, pady=(0, 10))

    def _build_security_panel(self) -> None:
        wrap = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=12,
                            border_color=COLOR_BORDER, border_width=1)
        wrap.pack(fill="x", padx=22, pady=(14, 0))

        head = ctk.CTkFrame(wrap, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(head, text="PROTECTIONS", text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 9, "bold"),
                     anchor="w").pack(side="left")
        self._leak_label = ctk.CTkLabel(
            head, text="", text_color=COLOR_AMBER,
            font=(FONT_FAMILY, 9, "bold"),
        )
        self._leak_label.pack(side="right")

        grid = ctk.CTkFrame(wrap, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(0, 10))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)

        self._badge_killswitch = SecurityBadge(grid, "Kill switch")
        self._badge_killswitch.grid(row=0, column=0, sticky="w")
        self._badge_dns        = SecurityBadge(grid, "DNS chiffre")
        self._badge_dns.grid(row=0, column=1, sticky="w")
        self._badge_leak       = SecurityBadge(grid, "Anti-fuite")
        self._badge_leak.grid(row=0, column=2, sticky="w")

        self._badge_pfs        = SecurityBadge(grid, "PFS")
        self._badge_pfs.grid(row=1, column=0, sticky="w")
        self._badge_pq         = SecurityBadge(grid, "Post-Q")
        self._badge_pq.grid(row=1, column=1, sticky="w")
        self._badge_split      = SecurityBadge(grid, "Split tunnel")
        self._badge_split.grid(row=1, column=2, sticky="w")

    def _build_footer(self) -> None:
        # Carte IP + mode + serveurs
        bar = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=12,
                           border_color=COLOR_BORDER, border_width=1)
        bar.pack(fill="x", padx=22, pady=(14, 12))

        line1 = ctk.CTkFrame(bar, fg_color="transparent")
        line1.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(line1, text="IP PUBLIQUE",
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 9, "bold"),
                     anchor="w").pack(side="left")
        self._ip_label = ctk.CTkLabel(
            line1, text="--", text_color=COLOR_CYAN,
            font=(FONT_FAMILY, 11, "bold"),
        )
        self._ip_label.pack(side="right")

        line2 = ctk.CTkFrame(bar, fg_color="transparent")
        line2.pack(fill="x", padx=10, pady=(2, 10))
        line2.grid_columnconfigure(0, weight=1)

        modes = ["Auto", "Securite max", "Vitesse max", "Streaming",
                 "Entreprise", "Reseau hostile"]
        self._mode_var = ctk.StringVar(value=self.config_data.last_mode)
        mode_menu = ctk.CTkOptionMenu(
            line2, values=modes, variable=self._mode_var,
            command=self._on_mode_changed,
            fg_color=COLOR_SURFACE_2,
            button_color=COLOR_VIOLET,
            button_hover_color=COLOR_VIOLET_DARK,
            dropdown_fg_color=COLOR_SURFACE_2,
            dropdown_hover_color=COLOR_SURFACE_3,
            dropdown_text_color=COLOR_TEXT,
            text_color=COLOR_TEXT,
            font=(FONT_FAMILY, 10, "bold"),
            corner_radius=8, height=30,
        )
        mode_menu.grid(row=0, column=0, sticky="ew", padx=(4, 6))

        dash_btn = ctk.CTkButton(
            line2, text="Tableau de bord", width=130, height=30,
            fg_color=COLOR_VIOLET, hover_color=COLOR_VIOLET_DARK,
            text_color="white", corner_radius=8,
            font=(FONT_FAMILY, 10, "bold"),
            command=self._open_dashboard,
        )
        dash_btn.grid(row=0, column=1, sticky="e", padx=(0, 6))

        servers_btn = ctk.CTkButton(
            line2, text="Serveurs ›", width=90, height=30,
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
            text_color=COLOR_TEXT, corner_radius=8,
            font=(FONT_FAMILY, 10, "bold"),
            command=self._open_servers,
        )
        servers_btn.grid(row=0, column=2, sticky="e", padx=(0, 4))

    # --------------------------------------------------------------------
    #  Actions utilisateur
    # --------------------------------------------------------------------

    def _toggle_connection(self) -> None:
        state = self.engine.state
        if state in (ConnectionState.DISCONNECTED, ConnectionState.ERROR):
            proto_str = self._proto_var.get()
            proto = None if proto_str == "Auto" else Protocol[proto_str.upper()]
            threading.Thread(
                target=self.engine.connect, args=(proto,), daemon=True
            ).start()
        elif state == ConnectionState.CONNECTED:
            threading.Thread(target=self.engine.disconnect, daemon=True).start()

    def _on_protocol_changed(self, value: str) -> None:
        self._card_proto.set_value(value)
        recos = {
            "Auto":      "Le moteur choisit automatiquement le meilleur "
                         "protocole selon le contexte reseau.",
            "WireGuard": "WireGuard : latence faible, simple, ideal pour le "
                         "cloud (ChaCha20-Poly1305, Curve25519).",
            "IKEv2":     "IPsec/IKEv2 : reference site-a-site et entreprise "
                         "(AES-GCM-256, PFS, NAT-T).",
            "OpenVPN":   "OpenVPN : compatibilite maximale et traversee de "
                         "reseaux restrictifs (TLS 1.3, AES-GCM, UDP/TCP).",
        }
        self._reco_label.configure(text=recos.get(value, ""))
        self.config_data.last_protocol = value
        self.config_data.save()

    def _on_mode_changed(self, value: str) -> None:
        policy = {
            "Auto":           ("Auto",      True,  True,  True,  True,  False, True),
            "Securite max":   ("IKEv2",     True,  True,  True,  True,  True,  False),
            "Vitesse max":    ("WireGuard", True,  True,  False, True,  False, True),
            "Streaming":      ("WireGuard", True,  True,  False, True,  False, True),
            "Entreprise":     ("IKEv2",     True,  True,  True,  True,  True,  True),
            "Reseau hostile": ("OpenVPN",   True,  True,  True,  True,  False, False),
        }.get(value)
        if not policy:
            return
        proto, ks, dns, leak, pfs, pq, split = policy
        self._proto_var.set(proto)
        self._on_protocol_changed(proto)
        self.security.set_kill_switch(ks)
        self.security.set_dns_protection(dns)
        self.security.set_leak_protection(leak)
        self.security.set_pfs(pfs)
        self.security.set_post_quantum(pq)
        self.security.set_split_tunneling(split)
        self.config_data.last_mode = value
        self.security.export_to_config(self.config_data)
        self.config_data.save()
        self._refresh_security_badges()

    def _open_settings(self) -> None:
        if self._settings_win is None or not self._settings_win.winfo_exists():
            self._settings_win = SettingsWindow(
                self, self.security, self.engine, self.config_data,
                on_changed=self._on_settings_changed)
        else:
            self._settings_win.lift()
            self._settings_win.focus_force()

    def _open_servers(self) -> None:
        if self._servers_win is None or not self._servers_win.winfo_exists():
            self._servers_win = ServersWindow(
                self, self.engine, on_select=self._on_server_selected)
        else:
            self._servers_win.lift()
            self._servers_win.focus_force()

    def _open_dashboard(self) -> None:
        if self._dashboard is None or not self._dashboard.winfo_exists():
            self._dashboard = DashboardWindow(self)
        else:
            self._dashboard.lift()
            self._dashboard.focus_force()

    def _force_ip_refresh(self) -> None:
        """Raccourci F5 : retente une recuperation de l'IP publique."""
        from utils import fetch_public_ip
        def worker():
            ip = fetch_public_ip()
            self.after(0, self._update_ip_label, ip or "--")
        threading.Thread(target=worker, daemon=True).start()

    def _on_server_selected(self, server_id: str) -> None:
        self.config_data.last_server_id = server_id
        self.config_data.save()
        self._refresh_ui()

    def _on_settings_changed(self) -> None:
        self.security.export_to_config(self.config_data)
        self.engine.set_real_mode(self.config_data.real_subprocess)
        self.engine.set_host_override(self.config_data.real_endpoint_host)
        self.security.set_real_mode(self.config_data.real_security)
        self.config_data.save()
        self._refresh_security_badges()

    # --------------------------------------------------------------------
    #  Synchronisation moteur -> UI
    # --------------------------------------------------------------------

    def _on_engine_state_change(self, state: ConnectionState) -> None:
        # Force un refresh immediat (sans chainer un nouveau cycle).
        self.after(0, self._refresh_ui_once)
        if state == ConnectionState.CONNECTED:
            self.security.start_leak_monitor(self.engine.public_ip)
            # Arme le kill switch UNIQUEMENT apres connexion etablie,
            # avec exception sur l'IP publique du serveur.
            try:
                srv = self.engine.current_server
                self.security.arm_kill_switch(
                    vpn_endpoint_ip=srv.public_ip if srv else None
                )
            except Exception:
                pass
            self._notify_state("Tunnel actif",
                "Connecte a {}".format(
                    self.engine.current_server.city
                    if self.engine.current_server else "AuroraVPN"))
            self._start_speed_loop()
        elif state == ConnectionState.DISCONNECTED:
            self.security.stop_leak_monitor()
            # Desarme le kill switch.
            try:
                self.security.disarm_kill_switch()
            except Exception:
                pass
            self._stop_speed_loop()
            self._notify_state("Tunnel ferme", "Connexion VPN deconnectee.")
        elif state == ConnectionState.ERROR:
            try:
                self.security.disarm_kill_switch()
            except Exception:
                pass
            self._stop_speed_loop()
            self._notify_state("Erreur VPN",
                self.engine.last_error or "Connexion impossible.")

    def _notify_state(self, title: str, msg: str) -> None:
        if self.config_data.notifications_enabled:
            try:
                self.notifier.notify(title, msg)
            except Exception:
                pass

    def _start_speed_loop(self) -> None:
        """Demarre une SEULE chaine d'alimentation du SpeedChart."""
        self._stop_speed_loop()  # garantit l'absence de doublon
        self._push_speed_sample()

    def _stop_speed_loop(self) -> None:
        if self._speed_after_id is not None:
            try:
                self.after_cancel(self._speed_after_id)
            except Exception:
                pass
            self._speed_after_id = None

    def _push_speed_sample(self) -> None:
        """Alimente le SpeedChart si le dashboard est ouvert."""
        if self.engine.state != ConnectionState.CONNECTED:
            self._speed_after_id = None
            return
        if self._dashboard and self._dashboard.winfo_exists():
            srv = self.engine.current_server
            if srv:
                self._dashboard.push_speed(srv.latency_ms, srv.throughput_mbps)
        # Re-schedule UNE fois.
        self._speed_after_id = self.after(1000, self._push_speed_sample)

    def _on_leak(self, detected: bool) -> None:
        if detected:
            self._leak_label.configure(text="⚠  Fuite detectee",
                                       text_color=COLOR_AMBER)
        else:
            self._leak_label.configure(text="")

    def _update_ip_label(self, ip: str) -> None:
        self._ip_label.configure(text=ip or "--")

    def _refresh_ui_once(self) -> None:
        """Met a jour l'UI une seule fois (sans rescheduling)."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        st = self.engine.state
        srv = self.engine.current_server

        # Duree session
        secs = self.engine.session_duration_seconds()
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        duration = f"{h:02d}:{m:02d}:{s:02d}" if secs > 0 else ""

        # Hero orb + sous-titre + bouton action
        if st == ConnectionState.CONNECTED:
            self._orb.set_state(st, duration)
            self._hero_sub.configure(text="Tunnel actif et chiffre",
                                     text_color=COLOR_GREEN)
            self._action_btn.configure(text="DECONNECTER",
                                       fg_color=COLOR_SURFACE_3,
                                       hover_color=COLOR_BORDER_LIT)
        elif st == ConnectionState.CONNECTING:
            self._orb.set_state(st, "")
            self._hero_sub.configure(text="Negociation des cles en cours...",
                                     text_color=COLOR_CYAN)
            self._action_btn.configure(text="ANNULER")
        elif st == ConnectionState.ERROR:
            self._orb.set_state(st, "")
            self._hero_sub.configure(text=self.engine.last_error or "Echec",
                                     text_color=COLOR_RED)
            self._action_btn.configure(text="REESSAYER",
                                       fg_color=COLOR_VIOLET,
                                       hover_color=COLOR_VIOLET_DARK)
        else:  # DISCONNECTED
            self._orb.set_state(st, "")
            self._hero_sub.configure(text="Cliquez pour vous connecter",
                                     text_color=COLOR_TEXT_SOFT)
            self._action_btn.configure(text="CONNECTER",
                                       fg_color=COLOR_VIOLET,
                                       hover_color=COLOR_VIOLET_DARK)

        # Cartes d'info
        if srv:
            self._card_server.set_value(f"{srv.country} - {srv.city}")
            self._card_latency.set_value(f"{srv.latency_ms} ms",
                                         color=COLOR_CYAN)
            self._card_proto.set_value(
                self.engine.active_protocol.name
                if self.engine.active_protocol else self._proto_var.get()
            )
        else:
            self._card_server.set_value("Auto")
            self._card_latency.set_value("-- ms")
            self._card_proto.set_value(self._proto_var.get())

        self._refresh_security_badges()

    def _refresh_ui(self) -> None:
        """Boucle de rafraichissement 1 Hz, single-chain garanti."""
        self._refresh_ui_once()
        # Si l'app est minimisee dans le tray, on ne reschedule pas
        # (economie CPU). Reprend a la ré-affichage.
        if self._is_minimized:
            self._refresh_after_id = None
            return
        # Annule l'ancien tick avant d'en programmer un nouveau.
        if self._refresh_after_id is not None:
            try:
                self.after_cancel(self._refresh_after_id)
            except Exception:
                pass
        # Tick uniquement si CONNECTED ou CONNECTING (sinon rien ne bouge).
        if self.engine.state in (ConnectionState.CONNECTED,
                                 ConnectionState.CONNECTING):
            interval = 1000
        else:
            # En idle, tick lent (reste reactif aux changements externes).
            interval = 5000
        self._refresh_after_id = self.after(interval, self._refresh_ui)

    def _refresh_security_badges(self) -> None:
        s: SecurityStatus = self.security.status
        self._badge_killswitch.set_active(s.kill_switch)
        self._badge_dns.set_active(s.dns_protection)
        self._badge_leak.set_active(s.leak_protection,
                                    warning=s.leak_detected)
        self._badge_pfs.set_active(s.pfs)
        self._badge_pq.set_active(s.post_quantum, warning=not s.post_quantum)
        self._badge_split.set_active(s.split_tunneling)

    # --------------------------------------------------------------------
    #  System tray
    # --------------------------------------------------------------------

    def _tray_supported(self) -> bool:
        return _TRAY_AVAILABLE and self._tray_icon is not None

    def _setup_tray(self) -> None:
        if not _TRAY_AVAILABLE:
            return
        # Icone : disque violet
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, 60, 60), fill=(139, 92, 246, 255))
        d.ellipse((14, 14, 50, 50), fill=(34, 211, 238, 255))
        d.ellipse((22, 22, 42, 42), fill=(10, 10, 18, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Afficher", self._tray_show, default=True),
            pystray.MenuItem("Connecter / Deconnecter",
                             lambda *_: self._toggle_connection()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", self._tray_quit),
        )
        self._tray_icon = pystray.Icon("AuroraVPN", img, "AuroraVPN", menu)
        self._tray_thread = threading.Thread(
            target=self._tray_icon.run, daemon=True, name="aurora-tray"
        )
        self._tray_thread.start()

    def _tray_show(self, icon=None, item=None) -> None:
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(50, self._on_deiconify)

    def _tray_quit(self, icon=None, item=None) -> None:
        self.after(0, self._quit_app)

    def _minimize_to_tray(self) -> None:
        self._is_minimized = True
        # Stoppe l'animation du hero (econome CPU en arriere-plan).
        if hasattr(self, "_orb"):
            self._orb.stop_animation()
        if self._tray_supported():
            self.withdraw()
        else:
            self.iconify()

    def _on_deiconify(self) -> None:
        """Reprend les animations / rafraichissements a la ré-affichage."""
        self._is_minimized = False
        # Restaure l'animation orb si etat actif.
        if hasattr(self, "_orb") and self.engine.state in (
                ConnectionState.CONNECTING, ConnectionState.CONNECTED):
            self._orb.start_animation()
        # Relance la boucle de refresh si elle s'etait arretee.
        if self._refresh_after_id is None:
            self._refresh_ui()

    def _on_window_close(self) -> None:
        if self.config_data.minimize_to_tray and self._tray_supported():
            self._minimize_to_tray()
        else:
            self._quit_app()

    def _quit_app(self) -> None:
        try:
            # Annule les boucles after()
            for after_id in (self._refresh_after_id, self._speed_after_id):
                if after_id is not None:
                    try:
                        self.after_cancel(after_id)
                    except Exception:
                        pass
            self._refresh_after_id = None
            self._speed_after_id = None

            # Stoppe les animations
            if hasattr(self, "_orb"):
                self._orb.stop_animation()

            # Deconnexion VPN si actif
            if self.engine.state == ConnectionState.CONNECTED:
                try:
                    self.engine.disconnect()
                except Exception:
                    pass
            self.security.stop_leak_monitor()
            # SAFEGUARD : retire toujours la regle firewall, meme si
            # l'utilisateur n'avait pas active le kill switch dans cette
            # session (peut etre un residu d'une session precedente).
            try:
                self.security.disarm_kill_switch()
            except Exception:
                pass

            # Stoppe Tor si demarre
            try:
                self.tor_over_vpn.stop()
            except Exception:
                pass

            # Stoppe le resolveur DNS local
            try:
                self._stop_dns_resolver()
            except Exception:
                pass

            # Sauvegarde la config
            try:
                self.config_data.save()
            except Exception:
                pass

            # Stoppe le tray
            if self._tray_icon:
                try:
                    self._tray_icon.stop()
                except Exception:
                    pass
        finally:
            release_single_instance()
            try:
                self.destroy()
            except Exception:
                pass
            # _exit obligatoire car le thread pystray empeche un exit normal.
            os._exit(0)

    # --------------------------------------------------------------------
    #  Avertissements
    # --------------------------------------------------------------------

    def _warn_admin_needed(self) -> None:
        from tkinter import messagebox
        messagebox.showwarning(
            "Privileges requis",
            "Le mode VPN reel necessite les droits Administrateur.\n\n"
            "Relancez AuroraVPN en tant qu'Administrateur, "
            "ou desactivez 'Connexion VPN reelle' dans les Parametres."
        )


# ============================================================================
#  FENETRES SECONDAIRES
# ============================================================================

class SettingsWindow(ctk.CTkToplevel):
    """Panneau de parametres + section Avance."""

    def __init__(self, parent, security: SecurityManager, engine: VPNEngine,
                 cfg: UserConfig, on_changed: Callable[[], None]):
        super().__init__(parent)
        self.title("Parametres - AuroraVPN")
        self.geometry("440x620")
        self.configure(fg_color=COLOR_BG)
        self.security = security
        self.engine = engine
        self.cfg = cfg
        self.on_changed = on_changed

        title = ctk.CTkLabel(self, text="Parametres",
                             text_color=COLOR_TEXT,
                             font=(FONT_FAMILY, 16, "bold"))
        title.pack(anchor="w", padx=20, pady=(20, 4))

        sub = ctk.CTkLabel(self,
            text="Configuration des protections et options avancees.",
            text_color=COLOR_TEXT_MUTED,
            font=(FONT_FAMILY, 11))
        sub.pack(anchor="w", padx=20, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 14))

        self._section(scroll, "PROTECTIONS")
        self._add_switch(scroll, "Kill Switch systeme",
                         security.status.kill_switch,
                         security.set_kill_switch)
        self._add_switch(scroll, "DNS chiffre (DoH/DoT)",
                         security.status.dns_protection,
                         security.set_dns_protection)
        self._add_switch(scroll, "Anti-fuite IPv6 / WebRTC",
                         security.status.leak_protection,
                         security.set_leak_protection)
        self._add_switch(scroll, "Perfect Forward Secrecy",
                         security.status.pfs,
                         security.set_pfs)
        self._add_switch(scroll, "Hybride post-quantique (ML-KEM)",
                         security.status.post_quantum,
                         security.set_post_quantum)
        self._add_switch(scroll, "Split tunneling",
                         security.status.split_tunneling,
                         security.set_split_tunneling)

        self._section(scroll, "COMPORTEMENT")
        self._add_switch(scroll, "Reconnexion automatique",
                         security.status.auto_reconnect,
                         security.set_auto_reconnect)
        self._add_switch(scroll, "Connexion auto sur Wi-Fi public",
                         security.status.auto_on_public_wifi,
                         security.set_auto_on_public_wifi)
        self._add_switch(scroll, "Bloquer trackers et domaines malveillants",
                         security.status.block_trackers,
                         security.set_block_trackers)

        self._section(scroll, "INTERFACE")
        self._add_switch(scroll, "Reduire dans la zone de notification",
                         cfg.minimize_to_tray,
                         lambda v: self._set_cfg("minimize_to_tray", v))
        self._add_switch(scroll, "Demarrer minimise",
                         cfg.start_minimized,
                         lambda v: self._set_cfg("start_minimized", v))

        self._section(scroll, "AVANCE (ATTENTION)")
        warn = ctk.CTkLabel(scroll,
            text="Ces options activent les vrais appels systeme. "
                 "Necessite les droits Administrateur.",
            text_color=COLOR_AMBER,
            font=(FONT_FAMILY, 10),
            justify="left", wraplength=380)
        warn.pack(anchor="w", padx=14, pady=(0, 6))

        self._add_switch(scroll, "Connexion VPN reelle (subprocess)",
                         cfg.real_subprocess,
                         lambda v: self._set_cfg("real_subprocess", v))
        self._add_switch(scroll, "Securite reelle (filtres firewall, DNS, IPv6)",
                         cfg.real_security,
                         lambda v: self._set_cfg("real_security", v))
        self._add_switch(scroll, "Mode loopback (test sans serveur distant)",
                         cfg.loopback_mode,
                         lambda v: self._set_cfg("loopback_mode", v))
        self._add_switch(scroll, "Resolveur DNS local (active Threat Protection)",
                         cfg.dns_resolver_enabled,
                         lambda v: self._set_cfg("dns_resolver_enabled", v))
        self._add_switch(scroll, "Mesure parallele de latence au demarrage",
                         cfg.auto_ping_on_start,
                         lambda v: self._set_cfg("auto_ping_on_start", v))

        # Selecteur de langue
        self._section(scroll, "LANGUE")
        lang_row = ctk.CTkFrame(scroll, fg_color=COLOR_SURFACE,
                                corner_radius=8,
                                border_color=COLOR_BORDER, border_width=1)
        lang_row.pack(fill="x", padx=10, pady=3)
        ctk.CTkLabel(lang_row, text="Langue de l'interface",
                     text_color=COLOR_TEXT,
                     font=(FONT_FAMILY, 11),
                     anchor="w").pack(side="left", padx=12, pady=8,
                                      fill="x", expand=True)

        # Liste : Auto + langues dispo dans locales/
        lang_options = ["Auto"] + [l.upper() for l in i18n.available_languages()]
        current = "Auto" if not cfg.language else cfg.language.upper()
        if current not in lang_options:
            current = "Auto"
        self._lang_var = ctk.StringVar(value=current)
        ctk.CTkOptionMenu(
            lang_row, values=lang_options, variable=self._lang_var,
            command=self._on_lang_changed,
            fg_color=COLOR_SURFACE_2,
            button_color=COLOR_VIOLET,
            button_hover_color=COLOR_VIOLET_DARK,
            text_color=COLOR_TEXT,
            dropdown_fg_color=COLOR_SURFACE_2,
            dropdown_text_color=COLOR_TEXT,
            font=(FONT_FAMILY, 10, "bold"),
            corner_radius=8, height=28, width=80,
        ).pack(side="right", padx=10, pady=4)

        # Endpoint host override
        ctk.CTkLabel(scroll, text="Hote serveur (override pour mode reel)",
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 10),
                     anchor="w").pack(anchor="w", padx=14, pady=(8, 2))
        self._host_var = ctk.StringVar(value=cfg.real_endpoint_host)
        host_entry = ctk.CTkEntry(scroll, textvariable=self._host_var,
            placeholder_text="vpn.example.com",
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=(FONT_FAMILY, 11))
        host_entry.pack(fill="x", padx=14, pady=(0, 6))
        host_entry.bind("<FocusOut>",
                        lambda _e: self._set_cfg("real_endpoint_host",
                                                 self._host_var.get()))

    def _set_cfg(self, key: str, value) -> None:
        setattr(self.cfg, key, value)
        self.on_changed()

    def _on_lang_changed(self, value: str) -> None:
        if value == "Auto":
            self.cfg.language = ""
            # Ne change pas la langue active immediatement (necessite
            # redemarrage pour la detection systeme).
        else:
            lang = value.lower()
            self.cfg.language = lang
            i18n.set_language(lang)
        self.on_changed()

    def _section(self, parent, label: str) -> None:
        lbl = ctk.CTkLabel(parent, text=label,
                           text_color=COLOR_TEXT_MUTED,
                           font=(FONT_FAMILY, 9, "bold"),
                           anchor="w")
        lbl.pack(anchor="w", padx=14, pady=(14, 6))

    def _add_switch(self, parent, label: str, initial: bool,
                    callback: Callable[[bool], None]) -> None:
        row = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=8,
                           border_color=COLOR_BORDER, border_width=1)
        row.pack(fill="x", padx=10, pady=3)

        lbl = ctk.CTkLabel(row, text=label, text_color=COLOR_TEXT,
                           font=(FONT_FAMILY, 11), anchor="w")
        lbl.pack(side="left", padx=12, pady=8, fill="x", expand=True)

        var = ctk.BooleanVar(value=initial)
        sw = ctk.CTkSwitch(
            row, text="", variable=var,
            command=lambda: (callback(var.get()), self.on_changed()),
            progress_color=COLOR_VIOLET,
            button_color=COLOR_TEXT,
            button_hover_color=COLOR_CYAN,
            width=40,
        )
        sw.pack(side="right", padx=10, pady=4)


class ServersWindow(ctk.CTkToplevel):
    """Liste des serveurs avec latence et bouton de selection."""

    def __init__(self, parent, engine: VPNEngine,
                 on_select: Callable[[str], None]):
        super().__init__(parent)
        self.title("Serveurs - AuroraVPN")
        self.geometry("440x540")
        self.configure(fg_color=COLOR_BG)
        self.engine = engine
        self.on_select = on_select

        title = ctk.CTkLabel(self, text="Serveurs disponibles",
                             text_color=COLOR_TEXT,
                             font=(FONT_FAMILY, 16, "bold"))
        title.pack(anchor="w", padx=20, pady=(20, 4))

        sub = ctk.CTkLabel(self, text="Cliquez sur un serveur pour le selectionner.",
                           text_color=COLOR_TEXT_MUTED,
                           font=(FONT_FAMILY, 11))
        sub.pack(anchor="w", padx=20, pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        for srv in engine.list_servers():
            self._server_row(scroll, srv)

    def _server_row(self, parent, srv: ServerInfo) -> None:
        row = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=10,
                           border_color=COLOR_BORDER, border_width=1)
        row.pack(fill="x", pady=3)

        # Pastille de qualite (vert / ambre / rouge selon latence)
        if srv.latency_ms < 60:
            color = COLOR_GREEN
        elif srv.latency_ms < 150:
            color = COLOR_AMBER
        else:
            color = COLOR_RED
        dot = ctk.CTkFrame(row, width=8, height=8, corner_radius=4,
                           fg_color=color)
        dot.pack(side="left", padx=(12, 8))

        # Nom
        ctk.CTkLabel(row, text=f"{srv.country} - {srv.city}",
                     text_color=COLOR_TEXT,
                     font=(FONT_FAMILY, 12, "bold"),
                     anchor="w").pack(side="left", padx=0, pady=10,
                                      fill="x", expand=True)

        # Latence
        ctk.CTkLabel(row, text=f"{srv.latency_ms} ms",
                     text_color=COLOR_CYAN,
                     font=(FONT_FAMILY, 10, "bold")).pack(side="right", padx=12)

        # Bouton selection
        btn = ctk.CTkButton(
            row, text="Choisir", width=80, height=26,
            fg_color=COLOR_VIOLET, hover_color=COLOR_VIOLET_DARK,
            font=(FONT_FAMILY, 10, "bold"),
            command=lambda s=srv: (self.engine.select_server(s.id),
                                   self.on_select(s.id),
                                   self.destroy()),
        )
        btn.pack(side="right", padx=(0, 10))


# ============================================================================
#  DASHBOARD WINDOW (carte + stats + tests)
# ============================================================================

class DashboardWindow(ctk.CTkToplevel):
    """
    Tableau de bord avance, ouvert en fenetre secondaire.
    Onglets : Carte mondiale, Statistiques temps reel, Tests de fuite,
              Multi-hop, Tor over VPN, Threat Protection.
    """

    def __init__(self, parent: "AuroraVPNApp"):
        super().__init__(parent)
        self.parent_app = parent
        self.title("Tableau de bord - AuroraVPN")
        self.geometry("680x560")
        self.minsize(640, 500)
        self.configure(fg_color=COLOR_BG)
        self._threat_after_id: Optional[str] = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Tabview natif customtkinter
        self._tabs = ctk.CTkTabview(
            self, fg_color=COLOR_BG,
            segmented_button_fg_color=COLOR_SURFACE,
            segmented_button_selected_color=COLOR_VIOLET,
            segmented_button_selected_hover_color=COLOR_VIOLET_DARK,
            segmented_button_unselected_color=COLOR_SURFACE,
            segmented_button_unselected_hover_color=COLOR_SURFACE_2,
            text_color=COLOR_TEXT,
        )
        self._tabs.pack(fill="both", expand=True, padx=12, pady=12)

        self._tabs.add("Carte")
        self._tabs.add("Stats")
        self._tabs.add("Tests")
        self._tabs.add("Multi-hop")
        self._tabs.add("Tor")
        self._tabs.add("Threat")

        self._build_map_tab()
        self._build_stats_tab()
        self._build_tests_tab()
        self._build_multihop_tab()
        self._build_tor_tab()
        self._build_threat_tab()

    # ------------------------------------------------------------------ Carte
    def _build_map_tab(self) -> None:
        frame = self._tabs.tab("Carte")
        ctk.CTkLabel(frame, text="Selectionnez un serveur sur la carte",
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 10)).pack(pady=(8, 8))
        self._map = WorldMap(
            frame,
            servers=self.parent_app.engine.list_servers(),
            on_select=self._on_map_select,
        )
        self._map.pack()

    def _on_map_select(self, server_id: str) -> None:
        self.parent_app.engine.select_server(server_id)
        self.parent_app.config_data.last_server_id = server_id
        self.parent_app.config_data.save()
        self.parent_app._refresh_ui()
        self.parent_app.notifier.notify(
            "Serveur change",
            f"Cible : {self.parent_app.engine.current_server.city}",
        )

    # ------------------------------------------------------------------ Stats
    def _build_stats_tab(self) -> None:
        frame = self._tabs.tab("Stats")
        ctk.CTkLabel(frame, text="Mesures en direct (latence + debit)",
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 10)).pack(pady=(8, 8))
        self._chart = SpeedChart(frame)
        self._chart.pack(pady=4)

        info = ctk.CTkLabel(frame,
            text="Le graphique se met a jour chaque seconde lorsque le "
                 "tunnel est actif.",
            text_color=COLOR_TEXT_MUTED, font=(FONT_FAMILY, 9))
        info.pack(pady=(8, 0))

    def push_speed(self, latency_ms: int, throughput_mbps: int) -> None:
        if hasattr(self, "_chart"):
            try:
                self._chart.push(latency_ms, throughput_mbps)
            except Exception:
                pass

    # ------------------------------------------------------------------ Tests
    def _build_tests_tab(self) -> None:
        frame = self._tabs.tab("Tests")
        panel = LeakTestPanel(
            frame,
            expected_ip_provider=lambda: self.parent_app.engine.public_ip,
        )
        panel.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ Multi-hop
    def _build_multihop_tab(self) -> None:
        frame = self._tabs.tab("Multi-hop")
        ctk.CTkLabel(frame, text="Double VPN (cascade entree -> sortie)",
                     text_color=COLOR_TEXT, anchor="w",
                     font=(FONT_FAMILY, 13, "bold")).pack(
            anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(frame,
            text="Achemine votre trafic via deux serveurs successifs pour "
                 "isoler votre IP source de votre IP de sortie. Augmente la "
                 "latence de 30 a 80 ms.",
            text_color=COLOR_TEXT_MUTED, font=(FONT_FAMILY, 10),
            justify="left", wraplength=600,
            anchor="w").pack(anchor="w", padx=14, pady=(0, 10))

        # Toggle
        var = ctk.BooleanVar(value=self.parent_app.config_data.multi_hop_enabled)
        sw = ctk.CTkSwitch(
            frame, text="Activer Multi-hop", variable=var,
            text_color=COLOR_TEXT,
            command=lambda: self._toggle_multihop(var.get()),
            progress_color=COLOR_VIOLET,
        )
        sw.pack(anchor="w", padx=14, pady=4)

        # Selecteurs entree / sortie
        servers = self.parent_app.engine.list_servers()
        names = [f"{s.country} - {s.city}" for s in servers]
        self._mh_id_by_name = {f"{s.country} - {s.city}": s.id for s in servers}

        ctk.CTkLabel(frame, text="Serveur d'entree",
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 9, "bold"),
                     anchor="w").pack(anchor="w", padx=14, pady=(10, 2))
        self._mh_entry_var = ctk.StringVar(value=names[0])
        ctk.CTkOptionMenu(frame, values=names, variable=self._mh_entry_var,
                          fg_color=COLOR_SURFACE_2,
                          button_color=COLOR_VIOLET,
                          button_hover_color=COLOR_VIOLET_DARK,
                          text_color=COLOR_TEXT,
                          dropdown_fg_color=COLOR_SURFACE_2,
                          dropdown_hover_color=COLOR_SURFACE_3,
                          dropdown_text_color=COLOR_TEXT).pack(
            fill="x", padx=14, pady=(0, 6))

        ctk.CTkLabel(frame, text="Serveur de sortie",
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 9, "bold"),
                     anchor="w").pack(anchor="w", padx=14, pady=(6, 2))
        self._mh_exit_var = ctk.StringVar(value=names[-1])
        ctk.CTkOptionMenu(frame, values=names, variable=self._mh_exit_var,
                          fg_color=COLOR_SURFACE_2,
                          button_color=COLOR_VIOLET,
                          button_hover_color=COLOR_VIOLET_DARK,
                          text_color=COLOR_TEXT,
                          dropdown_fg_color=COLOR_SURFACE_2,
                          dropdown_hover_color=COLOR_SURFACE_3,
                          dropdown_text_color=COLOR_TEXT).pack(
            fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(
            frame, text="Appliquer cette route",
            fg_color=COLOR_VIOLET, hover_color=COLOR_VIOLET_DARK,
            text_color="white", corner_radius=8,
            command=self._apply_multihop_route,
        ).pack(fill="x", padx=14, pady=(0, 4))

    def _toggle_multihop(self, enabled: bool) -> None:
        self.parent_app.multi_hop.enable(enabled)
        self.parent_app.config_data.multi_hop_enabled = enabled
        self.parent_app.config_data.save()

    def _apply_multihop_route(self) -> None:
        try:
            entry_id = self._mh_id_by_name[self._mh_entry_var.get()]
            exit_id  = self._mh_id_by_name[self._mh_exit_var.get()]
            self.parent_app.multi_hop.set_route(entry_id, exit_id)
            self.parent_app.config_data.multi_hop_exit_id = exit_id
            self.parent_app.config_data.last_server_id = entry_id
            self.parent_app.config_data.save()
            self.parent_app.notifier.notify(
                "Multi-hop", f"Route active : {entry_id} → {exit_id}")
        except Exception as exc:
            self.parent_app.notifier.notify("Multi-hop", f"Erreur : {exc}")

    # ------------------------------------------------------------------ Tor
    def _build_tor_tab(self) -> None:
        frame = self._tabs.tab("Tor")
        ctk.CTkLabel(frame, text="Tor over VPN",
                     text_color=COLOR_TEXT, anchor="w",
                     font=(FONT_FAMILY, 13, "bold")).pack(
            anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(frame,
            text="Achemine le trafic du navigateur a travers Tor APRES la "
                 "connexion VPN. Double anonymat. Necessite Tor Browser "
                 "installe.",
            text_color=COLOR_TEXT_MUTED, font=(FONT_FAMILY, 10),
            justify="left", wraplength=600,
            anchor="w").pack(anchor="w", padx=14, pady=(0, 10))

        # Detection Tor
        available = self.parent_app.tor_over_vpn.is_available()
        ctk.CTkLabel(frame,
            text=("✓  Tor detecte sur le systeme"
                  if available else
                  "✗  Tor non detecte. Installer Tor Browser : "
                  "https://www.torproject.org"),
            text_color=(COLOR_GREEN if available else COLOR_AMBER),
            font=(FONT_FAMILY, 10),
            anchor="w").pack(anchor="w", padx=14, pady=(0, 12))

        # Toggle
        self._tor_var = ctk.BooleanVar(
            value=self.parent_app.config_data.tor_over_vpn_enabled)
        sw = ctk.CTkSwitch(
            frame, text="Activer Tor over VPN",
            variable=self._tor_var,
            text_color=COLOR_TEXT,
            command=lambda: self._toggle_tor(self._tor_var.get()),
            progress_color=COLOR_VIOLET,
        )
        sw.pack(anchor="w", padx=14, pady=4)

        ctk.CTkLabel(frame,
            text="Une fois active, configurez votre navigateur sur "
                 "SOCKS5 127.0.0.1:9150",
            text_color=COLOR_TEXT_MUTED, font=(FONT_FAMILY, 9),
            anchor="w", justify="left",
            wraplength=600).pack(anchor="w", padx=14, pady=(8, 0))

    def _toggle_tor(self, enabled: bool) -> None:
        self.parent_app.config_data.tor_over_vpn_enabled = enabled
        self.parent_app.config_data.save()
        if enabled:
            ok = self.parent_app.tor_over_vpn.start()
            self.parent_app.notifier.notify(
                "Tor over VPN",
                "Tor demarre : SOCKS5 127.0.0.1:9150" if ok
                else "Tor introuvable. Installer Tor Browser.")
        else:
            self.parent_app.tor_over_vpn.stop()
            self.parent_app.notifier.notify("Tor over VPN", "Tor arrete.")

    # ------------------------------------------------------------------ Threat
    def _build_threat_tab(self) -> None:
        frame = self._tabs.tab("Threat")
        ctk.CTkLabel(frame, text="Threat Protection",
                     text_color=COLOR_TEXT, anchor="w",
                     font=(FONT_FAMILY, 13, "bold")).pack(
            anchor="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(frame,
            text="Bloque automatiquement les domaines connus pour diffuser "
                 "des publicites, des trackers ou des logiciels malveillants. "
                 "Source : StevenBlack/hosts (mise a jour hebdomadaire).",
            text_color=COLOR_TEXT_MUTED, font=(FONT_FAMILY, 10),
            justify="left", wraplength=600,
            anchor="w").pack(anchor="w", padx=14, pady=(0, 10))

        var = ctk.BooleanVar(
            value=self.parent_app.config_data.threat_protection)
        sw = ctk.CTkSwitch(
            frame, text="Activer la Threat Protection",
            variable=var,
            text_color=COLOR_TEXT,
            command=lambda: self._toggle_threat(var.get()),
            progress_color=COLOR_VIOLET,
        )
        sw.pack(anchor="w", padx=14, pady=4)

        # Stats
        stats = self.parent_app.threat_protect.stats
        self._threat_stats = ctk.CTkLabel(frame,
            text=self._format_threat_stats(stats),
            text_color=COLOR_TEXT_SOFT,
            font=(FONT_FAMILY, 11),
            anchor="w", justify="left")
        self._threat_stats.pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkButton(
            frame, text="Mettre a jour la liste maintenant",
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
            text_color=COLOR_TEXT, corner_radius=8,
            command=self._refresh_threat_list,
        ).pack(fill="x", padx=14, pady=(8, 4))

        # Auto-refresh des stats
        self._tick_threat_stats()

    def _toggle_threat(self, enabled: bool) -> None:
        self.parent_app.threat_protect.enable(enabled)
        self.parent_app.config_data.threat_protection = enabled
        self.parent_app.config_data.save()
        self.parent_app.notifier.notify(
            "Threat Protection",
            "Activee" if enabled else "Desactivee",
        )

    def _refresh_threat_list(self) -> None:
        self.parent_app.threat_protect.force_refresh()
        self.parent_app.notifier.notify("Threat Protection",
                                        "Mise a jour en arriere-plan.")

    def _format_threat_stats(self, stats) -> str:
        upd = stats.get("last_update", 0)
        if upd:
            import datetime
            upd_str = datetime.datetime.fromtimestamp(upd).strftime("%d/%m %H:%M")
        else:
            upd_str = "jamais"
        return (f"Requetes verifiees : {int(stats.get('queries', 0))}\n"
                f"Domaines bloques  : {int(stats.get('blocked', 0))}\n"
                f"Derniere mise a jour : {upd_str}")

    def _tick_threat_stats(self) -> None:
        try:
            if not self.winfo_exists():
                self._threat_after_id = None
                return
        except Exception:
            return
        try:
            self._threat_stats.configure(
                text=self._format_threat_stats(
                    self.parent_app.threat_protect.stats))
        except Exception:
            pass
        self._threat_after_id = self.after(3000, self._tick_threat_stats)

    def _on_close(self) -> None:
        """Annule les boucles before destroying."""
        if self._threat_after_id is not None:
            try:
                self.after_cancel(self._threat_after_id)
            except Exception:
                pass
            self._threat_after_id = None
        try:
            self.destroy()
        except Exception:
            pass


# ============================================================================
#  SETUP WIZARD (premier lancement, configuration guidee)
# ============================================================================

class SetupWizard(ctk.CTkToplevel):
    """
    Assistant 3-en-1 qui s'ouvre au premier lancement :
      1) Voie ProtonVPN Free  (vrai VPN immediat, pas notre app)
      2) Importer un fichier .conf WireGuard existant
      3) Aide pour creer son propre serveur (ouvre les guides)
    """

    WIDTH  = 560
    HEIGHT = 540

    def __init__(self, parent: "AuroraVPNApp",
                 cfg: UserConfig,
                 on_completed: Callable[[], None]):
        super().__init__(parent)
        self.parent_app = parent
        self.cfg = cfg
        self.on_completed = on_completed

        self.title("Bienvenue dans AuroraVPN")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(self.WIDTH, self.HEIGHT)
        self.configure(fg_color=COLOR_BG)
        self.protocol("WM_DELETE_WINDOW", self._skip)
        self.transient(parent)

        self._build()

    # --------------------------------------------------------------- UI

    def _build(self) -> None:
        # En-tete
        head = ctk.CTkFrame(self, fg_color=COLOR_BG)
        head.pack(fill="x", padx=24, pady=(20, 8))

        ctk.CTkLabel(head, text="Bienvenue",
                     text_color=COLOR_TEXT,
                     font=(FONT_FAMILY, 18, "bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(head,
            text="AuroraVPN est l'application. Pour vraiment chiffrer ton "
                 "trafic, il te faut un serveur. Choisis ton scenario.",
            text_color=COLOR_TEXT_MUTED,
            font=(FONT_FAMILY, 11),
            anchor="w", justify="left",
            wraplength=self.WIDTH - 60).pack(fill="x", pady=(4, 0))

        # Conteneur des 3 cartes
        cards = ctk.CTkFrame(self, fg_color=COLOR_BG)
        cards.pack(fill="both", expand=True, padx=20, pady=(8, 0))

        # Option 1 : ProtonVPN Free
        self._card(
            cards,
            icon="🟢",
            title="Juste un VPN qui marche maintenant",
            desc="Recommande pour debuter. On utilise ProtonVPN Free "
                 "(suisse, illimite, sans carte). Tu n'utiliseras PAS "
                 "AuroraVPN mais l'app Proton officielle.",
            btn_text="Ouvrir le site ProtonVPN Free",
            btn_color=COLOR_GREEN,
            action=self._open_protonvpn,
        )

        # Option 2 : Import .conf
        self._card(
            cards,
            icon="🟡",
            title="J'ai deja un fichier .conf WireGuard",
            desc="Quelqu'un t'a donne un .conf, ou tu l'as cree avec ton "
                 "propre serveur. Importe-le ici en un clic.",
            btn_text="Choisir et importer le .conf",
            btn_color=COLOR_VIOLET,
            action=self._import_conf,
        )

        # Option 3 : Assistant Oracle Cloud (pas a pas, integre)
        self._card(
            cards,
            icon="🔵",
            title="Deployer mon vrai serveur (Oracle Cloud gratuit)",
            desc="Assistant integre en 8 etapes : creation de compte, "
                 "VM gratuite a vie, install automatique, import .conf. "
                 "Carte bancaire requise pour Oracle (verification, pas de debit). "
                 "Duree : ~30 min.",
            btn_text="Demarrer l'assistant Oracle",
            btn_color=COLOR_CYAN,
            action=self._open_guide,
        )

        # Pied : skip
        footer = ctk.CTkFrame(self, fg_color=COLOR_BG)
        footer.pack(fill="x", padx=24, pady=14)
        ctk.CTkButton(
            footer, text="Plus tard (mode demo)",
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
            text_color=COLOR_TEXT_MUTED, corner_radius=8,
            font=(FONT_FAMILY, 11),
            command=self._skip,
        ).pack(side="right")

    def _card(self, parent, icon: str, title: str, desc: str,
              btn_text: str, btn_color: str, action: Callable[[], None]) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE, corner_radius=10,
                            border_color=COLOR_BORDER, border_width=1)
        card.pack(fill="x", pady=5)

        line1 = ctk.CTkFrame(card, fg_color="transparent")
        line1.pack(fill="x", padx=14, pady=(10, 0))
        ctk.CTkLabel(line1, text=icon, font=(FONT_FAMILY, 14),
                     text_color=COLOR_TEXT).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(line1, text=title, text_color=COLOR_TEXT,
                     font=(FONT_FAMILY, 12, "bold"),
                     anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(card, text=desc, text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 10),
                     justify="left", anchor="w",
                     wraplength=self.WIDTH - 80).pack(
            fill="x", padx=14, pady=(2, 6))

        ctk.CTkButton(
            card, text=btn_text, height=32,
            fg_color=btn_color,
            hover_color=COLOR_VIOLET_DARK if btn_color == COLOR_VIOLET
                else COLOR_BORDER_LIT,
            text_color="white", corner_radius=8,
            font=(FONT_FAMILY, 11, "bold"),
            command=action,
        ).pack(fill="x", padx=14, pady=(0, 12))

    # --------------------------------------------------------------- Actions

    def _open_protonvpn(self) -> None:
        import webbrowser
        webbrowser.open("https://protonvpn.com/fr/free-vpn")
        self._info(
            "ProtonVPN Free",
            "La page ProtonVPN s'est ouverte dans ton navigateur.\n\n"
            "1. Cree un compte gratuit (juste un email).\n"
            "2. Telecharge leur application Windows.\n"
            "3. Connecte-toi et clique 'Quick Connect'.\n\n"
            "Tu pourras revenir sur AuroraVPN plus tard."
        )
        self._finish()

    def _import_conf(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self,
            title="Selectionner un fichier .conf WireGuard",
            filetypes=[("WireGuard config", "*.conf"),
                       ("Tous les fichiers", "*.*")],
        )
        if not path:
            return

        # Utilise le module d'import deja ecrit.
        try:
            from import_wireguard_config import (
                parse_wg_conf, validate, extract_endpoint_host,
                copy_to_programdata, update_user_config,
            )
            parsed = parse_wg_conf(Path(path))
            validate(parsed)
            host = extract_endpoint_host(parsed["peer.endpoint"])
            try:
                copy_to_programdata(Path(path))
                copied = True
            except PermissionError:
                copied = False
            update_user_config(host, server_label="Mon Serveur")
            # Maj de la config en memoire pour reflexion immediate.
            self.cfg.real_subprocess    = True
            self.cfg.loopback_mode      = False
            self.cfg.real_endpoint_host = host
            self.cfg.server_label       = "Mon Serveur"
        except Exception as exc:
            self._error("Import echoue", str(exc))
            return

        msg = f"Le fichier a ete importe.\nServeur : {host}\n\n"
        if copied:
            msg += "La config a ete copiee dans C:\\ProgramData\\AuroraVPN\\.\n"
        else:
            msg += ("La copie dans ProgramData a echoue (relancer en "
                    "Administrateur si tu veux le mode reel).\n")
        msg += "\nAuroraVPN se connectera au lancement (relance le launcher)."
        self._info("Import termine", msg)
        self._finish()

    def _open_guide(self) -> None:
        """Lance le wizard Oracle Cloud pas-a-pas dans AuroraVPN."""
        self.destroy()
        OracleSetupWizard(self.parent_app, self.cfg,
                          on_completed=self.on_completed)

    def _skip(self) -> None:
        """Ferme sans configurer : reste en mode demo loopback."""
        self.cfg.loopback_mode = True
        self.cfg.real_subprocess = False
        self._finish()

    def _finish(self) -> None:
        try:
            self.on_completed()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    # --------------------------------------------------------------- Dialogs

    def _info(self, title: str, message: str) -> None:
        from tkinter import messagebox
        messagebox.showinfo(title, message, parent=self)

    def _error(self, title: str, message: str) -> None:
        from tkinter import messagebox
        messagebox.showerror(title, message, parent=self)


# ============================================================================
#  ORACLE SETUP WIZARD (assistant pas-a-pas integre)
# ============================================================================

class OracleSetupWizard(ctk.CTkToplevel):
    """
    Assistant 8 etapes pour deployer un vrai serveur WireGuard sur
    Oracle Cloud Free Tier, et le connecter a AuroraVPN.

    Etat persistant entre les etapes : self._state (dict).
    """

    WIDTH  = 720
    HEIGHT = 620
    TOTAL_STEPS = 8

    def __init__(self, parent: "AuroraVPNApp",
                 cfg: UserConfig,
                 on_completed: Callable[[], None]):
        super().__init__(parent)
        self.parent_app = parent
        self.cfg = cfg
        self.on_completed = on_completed
        self._step = 1
        self._state = {
            "server_ip": "",
            "ssh_user":  "ubuntu",
            "ssh_key":   "",
            "conf_path": "",
        }

        self.title("Assistant Oracle Cloud - AuroraVPN")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(self.WIDTH, self.HEIGHT)
        self.configure(fg_color=COLOR_BG)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.transient(parent)

        # Conteneur racine
        self._header = ctk.CTkFrame(self, fg_color=COLOR_BG, height=70)
        self._header.pack(fill="x", padx=20, pady=(16, 0))

        self._body = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG)
        self._body.pack(fill="both", expand=True, padx=14, pady=8)

        self._nav = ctk.CTkFrame(self, fg_color=COLOR_BG, height=56)
        self._nav.pack(fill="x", side="bottom", padx=20, pady=(0, 16))

        self._render()

    # ------------------------------------------------------------------ Layout

    def _render(self) -> None:
        # Header
        for w in self._header.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._header,
            text=f"ETAPE {self._step} / {self.TOTAL_STEPS}",
            text_color=COLOR_VIOLET_2,
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w").pack(fill="x")
        # Barre de progression simple
        bar = ctk.CTkFrame(self._header, fg_color=COLOR_SURFACE_2, height=4,
                           corner_radius=2)
        bar.pack(fill="x", pady=(6, 6))
        filled = ctk.CTkFrame(
            bar, fg_color=COLOR_VIOLET, height=4, corner_radius=2,
            width=int((self.WIDTH - 40) * self._step / self.TOTAL_STEPS),
        )
        filled.place(x=0, y=0)

        # Body
        for w in self._body.winfo_children():
            w.destroy()
        builder = getattr(self, f"_build_step_{self._step}", None)
        if builder:
            builder()

        # Nav
        for w in self._nav.winfo_children():
            w.destroy()
        if self._step > 1:
            ctk.CTkButton(self._nav, text="‹ Precedent", width=110, height=34,
                fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
                text_color=COLOR_TEXT, corner_radius=8,
                font=(FONT_FAMILY, 11),
                command=self._prev).pack(side="left")
        ctk.CTkButton(self._nav, text="Annuler", width=80, height=34,
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
            text_color=COLOR_TEXT_MUTED, corner_radius=8,
            font=(FONT_FAMILY, 10),
            command=self._cancel).pack(side="left", padx=8)
        nxt_label = "Terminer ✓" if self._step == self.TOTAL_STEPS else "Suivant ›"
        ctk.CTkButton(self._nav, text=nxt_label, width=130, height=34,
            fg_color=COLOR_VIOLET, hover_color=COLOR_VIOLET_DARK,
            text_color="white", corner_radius=8,
            font=(FONT_FAMILY, 11, "bold"),
            command=self._next).pack(side="right")

    def _next(self) -> None:
        if self._step < self.TOTAL_STEPS:
            self._step += 1
            self._render()
        else:
            self._finish()

    def _prev(self) -> None:
        if self._step > 1:
            self._step -= 1
            self._render()

    def _cancel(self) -> None:
        try:
            self.destroy()
        except Exception:
            pass

    def _finish(self) -> None:
        try:
            self.on_completed()
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------ Helpers UI

    def _title(self, text: str) -> None:
        ctk.CTkLabel(self._body, text=text, text_color=COLOR_TEXT,
                     font=(FONT_FAMILY, 16, "bold"),
                     anchor="w").pack(anchor="w", padx=6, pady=(4, 8))

    def _para(self, text: str, color: str = COLOR_TEXT_SOFT) -> None:
        ctk.CTkLabel(self._body, text=text, text_color=color,
                     font=(FONT_FAMILY, 11),
                     anchor="w", justify="left",
                     wraplength=self.WIDTH - 60).pack(
            anchor="w", padx=6, pady=(0, 6))

    def _bullet(self, text: str) -> None:
        ctk.CTkLabel(self._body, text=f"  •  {text}",
                     text_color=COLOR_TEXT_SOFT,
                     font=(FONT_FAMILY, 11),
                     anchor="w", justify="left",
                     wraplength=self.WIDTH - 80).pack(
            anchor="w", padx=10, pady=2)

    def _link(self, label: str, url: str) -> None:
        import webbrowser
        ctk.CTkButton(self._body, text=label, height=32,
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
            text_color=COLOR_CYAN, corner_radius=8,
            font=(FONT_FAMILY, 11, "bold"),
            command=lambda: webbrowser.open(url)).pack(
            anchor="w", padx=6, pady=(4, 10))

    def _code_block(self, code: str, copy_label: str = "Copier") -> None:
        """Affiche du code dans une CTkTextbox monospace + bouton Copier."""
        wrap = ctk.CTkFrame(self._body, fg_color=COLOR_SURFACE_2,
                            corner_radius=8,
                            border_color=COLOR_BORDER, border_width=1)
        wrap.pack(fill="x", padx=6, pady=6)

        lines = code.count("\n") + 1
        height = max(40, min(180, lines * 18))
        tb = ctk.CTkTextbox(wrap, height=height,
            fg_color=COLOR_SURFACE_2,
            text_color=COLOR_TEXT,
            font=("Consolas", 10),
            border_width=0,
            wrap="none")
        tb.pack(fill="x", padx=6, pady=(6, 0))
        tb.insert("1.0", code)
        tb.configure(state="disabled")

        ctk.CTkButton(wrap, text=f"📋  {copy_label}", height=28,
            fg_color=COLOR_VIOLET, hover_color=COLOR_VIOLET_DARK,
            text_color="white", corner_radius=6,
            font=(FONT_FAMILY, 10, "bold"),
            command=lambda: self._copy_to_clipboard(code)).pack(
            anchor="e", padx=6, pady=6)

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except Exception:
            pass

    def _input(self, label: str, state_key: str,
               placeholder: str = "") -> None:
        ctk.CTkLabel(self._body, text=label,
                     text_color=COLOR_TEXT_MUTED,
                     font=(FONT_FAMILY, 10, "bold"),
                     anchor="w").pack(anchor="w", padx=6, pady=(8, 2))
        var = ctk.StringVar(value=self._state.get(state_key, ""))
        entry = ctk.CTkEntry(self._body, textvariable=var,
            placeholder_text=placeholder,
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, font=(FONT_FAMILY, 11),
            height=32)
        entry.pack(fill="x", padx=6, pady=(0, 6))
        # Sauvegarde a chaque modif.
        var.trace_add("write",
            lambda *_a: self._state.__setitem__(state_key, var.get()))

    # ------------------------------------------------------------------ Etapes

    def _build_step_1(self) -> None:
        self._title("Bienvenue dans l'assistant Oracle Cloud")
        self._para(
            "Cet assistant va te guider en 8 etapes pour deployer un vrai "
            "serveur VPN sur Oracle Cloud Free Tier. C'est gratuit a VIE "
            "(pas un trial), 4 coeurs ARM + 24 Go RAM, 10 To de bande "
            "passante par mois."
        )
        self._para("Ce qu'il te faut :", color=COLOR_TEXT)
        self._bullet("Une carte bancaire (pour la verification d'identite "
                     "uniquement, aucun debit)")
        self._bullet("Un email valide")
        self._bullet("Environ 30 minutes")

        self._para("Ce que tu auras a la fin :", color=COLOR_TEXT)
        self._bullet("Un VRAI serveur VPN a TOI, en Allemagne ou en France")
        self._bullet("Ton trafic Internet vraiment chiffre")
        self._bullet("Une IP publique d'un autre pays")
        self._bullet("AuroraVPN connecte automatiquement a TON serveur")

    def _build_step_2(self) -> None:
        self._title("Etape 2 : Creer ton compte Oracle Cloud")
        self._para("Clique sur le bouton ci-dessous pour ouvrir la page "
                   "Oracle Cloud Free Tier.")
        self._link("🌐  Ouvrir Oracle Cloud Free Tier",
                   "https://www.oracle.com/cloud/free/")
        self._para("Sur la page Oracle :", color=COLOR_TEXT)
        self._bullet("Clique sur Start for free")
        self._bullet("Renseigne email, telephone, mot de passe")
        self._bullet("IMPORTANT : choisis la region Germany (Frankfurt) "
                     "ou France (Marseille) pour rester en UE. Ce choix "
                     "est definitif.")
        self._bullet("Saisis ta carte bancaire (verification, pas de debit)")
        self._bullet("Validation par SMS, compte cree en ~10 min")
        self._para("Une fois ton compte cree, reviens ici et clique Suivant.",
                   color=COLOR_AMBER)

    def _build_step_3(self) -> None:
        self._title("Etape 3 : Creer la VM gratuite (Ampere ARM)")
        self._para("Dans la console Oracle Cloud :")
        self._bullet("Menu hamburger > Compute > Instances")
        self._bullet("Bouton Create Instance")
        self._bullet("Name : aurora-vpn-fr")
        self._bullet("Image : Canonical Ubuntu 22.04")
        self._bullet("Shape : clic Change shape > Ampere > VM.Standard.A1.Flex")
        self._bullet("OCPUs : 1, Memory : 6 GB (etiquette verte "
                     "Always Free Eligible)")
        self._bullet("Networking : laisser le VCN par defaut, "
                     "Assign public IPv4 = OUI")
        self._bullet("SSH key : Generate SSH key pair for me, "
                     "TELECHARGE LA CLE PRIVEE")
        self._bullet("Clic Create. Delai ~30 secondes.")
        self._para(
            "Une fois RUNNING, note l'adresse IP publique affichee "
            "(par exemple 141.94.123.45).",
            color=COLOR_AMBER,
        )

    def _build_step_4(self) -> None:
        self._title("Etape 4 : Ouvrir le port UDP 51820")
        self._para(
            "Oracle bloque TOUS les ports entrants par defaut. Il faut "
            "autoriser explicitement le port WireGuard."
        )
        self._para("Dans la console Oracle :", color=COLOR_TEXT)
        self._bullet("Clique sur le nom de ton instance")
        self._bullet("Section Primary VNIC > clic sur le nom du subnet")
        self._bullet("Section Security Lists > clic celle par defaut")
        self._bullet("Bouton Add Ingress Rules")
        self._bullet("Source CIDR : 0.0.0.0/0")
        self._bullet("IP Protocol : UDP")
        self._bullet("Destination Port Range : 51820")
        self._bullet("Description : AuroraVPN WireGuard")
        self._bullet("Bouton Add Ingress Rules pour sauvegarder")

    def _build_step_5(self) -> None:
        self._title("Etape 5 : Se connecter en SSH")
        self._para("Saisis ci-dessous les informations de ton serveur :")

        self._input("Adresse IP publique du serveur",
                    "server_ip", placeholder="141.94.123.45")
        self._input("Utilisateur SSH (laisser ubuntu pour Oracle)",
                    "ssh_user", placeholder="ubuntu")
        self._input("Chemin de la cle SSH privee (.key telechargee)",
                    "ssh_key",
                    placeholder=r"C:\Users\toi\Downloads\ssh-key-XXX.key")

        ip = self._state.get("server_ip", "<IP-A-SAISIR>")
        user = self._state.get("ssh_user", "ubuntu") or "ubuntu"
        key = self._state.get("ssh_key", "<CHEMIN-CLE>")
        self._para("Sur Windows, ouvre PowerShell et lance :",
                   color=COLOR_TEXT)
        self._code_block(
            f'icacls "{key}" /inheritance:r /grant:r "$env:USERNAME:R"\n'
            f'ssh -i "{key}" {user}@{ip}',
            copy_label="Copier les commandes SSH",
        )
        self._para("Tape yes a la premiere connexion. Tu es dans le serveur.",
                   color=COLOR_AMBER)

    def _build_step_6(self) -> None:
        self._title("Etape 6 : Installer WireGuard sur le serveur")
        self._para(
            "Toujours dans la fenetre SSH ouverte (etape 5), lance ceci :"
        )
        self._code_block(
            "nano install_wireguard.sh\n"
            "# (Colle le script Bash ci-dessous, puis Ctrl+O Enter Ctrl+X)\n"
            "chmod +x install_wireguard.sh\n"
            "sudo ./install_wireguard.sh mon-pc",
            copy_label="Copier les commandes",
        )
        self._para("Le script complet a coller :", color=COLOR_TEXT)
        # Lit install_wireguard.sh depuis le disque
        script_path = (Path(__file__).resolve().parent
                       / "server_setup" / "install_wireguard.sh")
        script_content = "# Script introuvable, voir server_setup/install_wireguard.sh"
        try:
            if script_path.exists():
                script_content = script_path.read_text(encoding="utf-8")
        except Exception:
            pass

        # Affichage tronque + bouton de copie integral
        ctk.CTkButton(self._body,
            text=f"📋  Copier install_wireguard.sh ({len(script_content)} caracteres)",
            height=34,
            fg_color=COLOR_VIOLET, hover_color=COLOR_VIOLET_DARK,
            text_color="white", corner_radius=8,
            font=(FONT_FAMILY, 11, "bold"),
            command=lambda: self._copy_to_clipboard(script_content)).pack(
            fill="x", padx=6, pady=8)

        self._para(
            "Le script tourne 60-90 secondes. A la fin, il affiche le "
            "chemin du fichier .conf cree pour ton client.",
            color=COLOR_AMBER,
        )

    def _build_step_7(self) -> None:
        self._title("Etape 7 : Rapatrier le fichier .conf")
        ip = self._state.get("server_ip", "<IP>")
        user = self._state.get("ssh_user", "ubuntu") or "ubuntu"
        key = self._state.get("ssh_key", "<CHEMIN-CLE>")
        dest = str(Path(__file__).resolve().parent / "mon-pc.conf")

        self._para(
            "Le serveur a genere un fichier de configuration WireGuard "
            "pour ton PC. On va le telecharger localement."
        )
        self._para("Dans une NOUVELLE fenetre PowerShell sur ton Windows :",
                   color=COLOR_TEXT)
        self._code_block(
            f'scp -i "{key}" {user}@{ip}:'
            f'/etc/wireguard/clients/mon-pc/mon-pc.conf "{dest}"',
            copy_label="Copier la commande scp",
        )
        # On pre-remplit pour l'etape 8
        self._state["conf_path"] = dest

    def _build_step_8(self) -> None:
        self._title("Etape 8 : Importer dans AuroraVPN et connecter")
        self._para(
            "Derniere etape ! On va importer le fichier .conf, configurer "
            "AuroraVPN pour utiliser ton vrai serveur, puis lancer la "
            "connexion."
        )

        self._input("Chemin du fichier .conf telecharge",
                    "conf_path", placeholder=str(Path(__file__).resolve().parent
                                                  / "mon-pc.conf"))

        # Bouton "Parcourir"
        from tkinter import filedialog
        def browse():
            path = filedialog.askopenfilename(
                parent=self,
                title="Selectionner le fichier .conf",
                filetypes=[("WireGuard config", "*.conf"),
                           ("Tous les fichiers", "*.*")])
            if path:
                self._state["conf_path"] = path
                self._render()

        ctk.CTkButton(self._body, text="📁  Parcourir...",
            height=30, width=140,
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_SURFACE_3,
            text_color=COLOR_TEXT, corner_radius=8,
            font=(FONT_FAMILY, 10, "bold"),
            command=browse).pack(anchor="w", padx=6, pady=4)

        # Bouton "Importer et configurer"
        ctk.CTkButton(self._body,
            text="✓  Importer maintenant et configurer AuroraVPN",
            height=42,
            fg_color=COLOR_GREEN, hover_color=COLOR_GREEN_DIM,
            text_color="white", corner_radius=8,
            font=(FONT_FAMILY, 12, "bold"),
            command=self._do_import).pack(fill="x", padx=6, pady=12)

        self._para(
            "Apres l'import : ferme cette fenetre, relance AuroraVPN.bat "
            "en tant qu'Administrateur, et il se connectera tout seul a "
            "ton serveur. Verifie sur https://ifconfig.me que ton IP "
            "publique correspond bien a celle de ton serveur.",
            color=COLOR_AMBER,
        )

    def _do_import(self) -> None:
        conf_path = self._state.get("conf_path", "").strip()
        if not conf_path:
            self._error("Chemin vide",
                        "Saisis le chemin du fichier .conf ou clique Parcourir.")
            return
        path = Path(conf_path)
        if not path.exists():
            self._error("Fichier introuvable", f"Le fichier {path} n'existe pas.")
            return
        try:
            from import_wireguard_config import (
                parse_wg_conf, validate, extract_endpoint_host,
                copy_to_programdata, update_user_config,
            )
            parsed = parse_wg_conf(path)
            validate(parsed)
            host = extract_endpoint_host(parsed["peer.endpoint"])
            copied = False
            try:
                copy_to_programdata(path)
                copied = True
            except PermissionError:
                pass
            update_user_config(host, server_label="Mon Serveur Oracle")
            self.cfg.real_subprocess    = True
            self.cfg.loopback_mode      = False
            self.cfg.real_endpoint_host = host
            self.cfg.server_label       = "Mon Serveur Oracle"
            self.cfg.save()
        except Exception as exc:
            self._error("Import echoue", str(exc))
            return
        msg = (
            f"Serveur configure : {host}\n\n"
            + ("Le fichier .conf a ete copie dans C:\\ProgramData\\AuroraVPN\\.\n"
               if copied else
               "Le copie dans ProgramData a echoue (lance AuroraVPN en Admin).\n")
            + "\nFerme cette fenetre, relance AuroraVPN.bat en tant qu'Administrateur."
        )
        from tkinter import messagebox
        messagebox.showinfo("Import reussi", msg, parent=self)

    def _error(self, title: str, message: str) -> None:
        from tkinter import messagebox
        messagebox.showerror(title, message, parent=self)


# ============================================================================
#  ENTREE
# ============================================================================

def main() -> int:
    # Single instance
    if not acquire_single_instance():
        # Une autre instance tourne deja : on quitte silencieusement.
        # On pourrait notifier la zone de notification de cette autre instance,
        # mais une simple sortie suffit.
        try:
            from tkinter import messagebox
            import tkinter as tk
            root = tk.Tk(); root.withdraw()
            messagebox.showinfo("AuroraVPN",
                "AuroraVPN est deja en cours d'execution.")
            root.destroy()
        except Exception:
            pass
        return 0

    log.info("Demarrage AuroraVPN (admin=%s, windows=%s)",
             is_admin(), IS_WINDOWS)

    try:
        app = AuroraVPNApp()
        app.mainloop()
    finally:
        release_single_instance()
    return 0


if __name__ == "__main__":
    sys.exit(main())
