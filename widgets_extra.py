"""
============================================================================
 AuroraVPN - Widgets avances pour le tableau de bord
============================================================================
 Fichier  : widgets_extra.py
 Contient :
   * WorldMap        - Carte mondiale stylisee + pins serveurs cliquables
   * SpeedChart      - Graphique en direct latence + debit (~60 derniers s)
   * LeakTestPanel   - Bouton "Lancer le test" + affichage colorie
   * AppSplitTable   - Liste des applications + toggle split tunneling
============================================================================
"""

from __future__ import annotations

import collections
import threading
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from features import LeakTestResult, LeakTester


# ===== Palette (importee du main si besoin, ici en local pour autonomie) =====

_BG          = "#0A0A12"
_SURFACE     = "#15151F"
_SURFACE_2   = "#1E1E2C"
_BORDER      = "#26263A"
_TEXT        = "#F1F2F8"
_TEXT_SOFT   = "#C4C5D0"
_TEXT_MUTED  = "#7E7F95"
_VIOLET      = "#8B5CF6"
_VIOLET_DARK = "#6D28D9"
_CYAN        = "#22D3EE"
_GREEN       = "#34D399"
_AMBER       = "#FBBF24"
_RED         = "#EF4444"

_FONT = "Segoe UI"


# ============================================================================
#  WORLD MAP
# ============================================================================

# Coordonnees (longitude, latitude) approximatives des principales
# cellules de continent. Stippling tres simple pour un look "data viz".
_CONTINENT_DOTS: List[Tuple[float, float]] = [
    # Amerique du Nord
    (-130, 60), (-120, 55), (-110, 50), (-100, 45), (-95, 50), (-85, 50),
    (-80, 45), (-75, 40), (-90, 40), (-100, 35), (-110, 35), (-120, 40),
    (-115, 30), (-100, 25), (-90, 30), (-80, 30), (-100, 50), (-90, 45),
    # Amerique centrale + Caraibes
    (-90, 15), (-85, 12), (-75, 8),
    # Amerique du Sud
    (-70, -5), (-60, -10), (-55, -15), (-65, -20), (-70, -25), (-60, -30),
    (-65, -35), (-70, -40), (-50, -10), (-45, -15), (-55, -25),
    # Europe
    (-5, 50), (0, 50), (5, 50), (10, 50), (15, 50), (20, 50), (25, 55),
    (10, 45), (5, 45), (0, 45), (15, 55), (20, 60), (10, 55), (-5, 55),
    (-5, 40), (0, 40), (5, 40), (10, 40), (15, 40), (20, 40), (25, 40),
    # Afrique
    (0, 30), (10, 30), (20, 30), (30, 30), (0, 20), (10, 20), (20, 20),
    (30, 20), (0, 10), (10, 10), (20, 10), (30, 10), (40, 10),
    (10, 0), (20, 0), (30, 0), (40, 0),
    (15, -10), (25, -10), (35, -15), (20, -25), (25, -30),
    # Moyen-Orient
    (40, 30), (45, 25), (50, 25), (55, 25),
    # Asie centrale
    (50, 45), (60, 50), (70, 55), (80, 55), (50, 35), (60, 35), (70, 35),
    # Inde
    (75, 25), (80, 20), (85, 22),
    # Asie du Sud-Est
    (95, 20), (100, 15), (105, 15), (105, 5), (110, 0),
    # Chine / Japon
    (105, 35), (110, 30), (115, 30), (120, 35), (125, 40), (130, 35),
    (135, 35), (140, 38),
    # Russie
    (40, 60), (60, 60), (80, 60), (100, 60), (120, 60), (140, 60),
    (90, 65), (110, 70),
    # Oceanie
    (115, -25), (125, -20), (135, -25), (145, -25), (150, -30), (145, -35),
    (140, -38), (170, -40),
]

# Liste de villes connues pour positionner les pins meme si le serveur
# n'est pas dans le catalogue par defaut.
CITY_COORDS = {
    "Paris":         (2.35, 48.85),
    "Marseille":     (5.37, 43.30),
    "Zurich":        (8.55, 47.37),
    "Francfort":     (8.68, 50.11),
    "Amsterdam":     (4.90, 52.37),
    "Londres":       (-0.13, 51.51),
    "New York":      (-74.00, 40.71),
    "Los Angeles":   (-118.24, 34.05),
    "Montreal":      (-73.57, 45.50),
    "Tokyo":         (139.69, 35.69),
    "Singapour":     (103.82, 1.35),
    "Sydney":        (151.21, -33.87),
}


class WorldMap(ctk.CTkCanvas):
    """
    Carte du monde stylisee. Cliquer sur un pin selectionne le serveur.

    Le canvas mesure WIDTH x HEIGHT, projection equirectangulaire simple.
    """

    WIDTH  = 600
    HEIGHT = 320

    def __init__(self, parent, servers, on_select: Callable[[str], None]):
        super().__init__(parent, width=self.WIDTH, height=self.HEIGHT,
                         bg=_BG, highlightthickness=0)
        self._servers = servers
        self._on_select = on_select
        self._pins = []
        self._tooltip = None
        self.bind("<Motion>", self._on_motion)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def update_servers(self, servers) -> None:
        self._servers = servers
        self._draw()

    def _project(self, lon: float, lat: float) -> Tuple[int, int]:
        # Equirectangulaire : x lineaire en lon, y lineaire en lat
        x = int((lon + 180.0) / 360.0 * self.WIDTH)
        y = int((90.0 - lat) / 180.0 * self.HEIGHT)
        return x, y

    def _draw(self) -> None:
        self.delete("all")
        # Fond degradient simule par 2 rectangles
        self.create_rectangle(0, 0, self.WIDTH, self.HEIGHT // 2,
                              fill="#0F0F1A", outline="")
        self.create_rectangle(0, self.HEIGHT // 2, self.WIDTH, self.HEIGHT,
                              fill="#0A0A14", outline="")

        # Grille (latitudes / longitudes principales)
        for lon in range(-180, 181, 30):
            x, _ = self._project(lon, 0)
            self.create_line(x, 0, x, self.HEIGHT, fill="#1A1A28", width=1)
        for lat in range(-60, 61, 30):
            _, y = self._project(0, lat)
            self.create_line(0, y, self.WIDTH, y, fill="#1A1A28", width=1)

        # Continents : nuage de points
        for lon, lat in _CONTINENT_DOTS:
            x, y = self._project(lon, lat)
            self.create_oval(x - 3, y - 3, x + 3, y + 3,
                             fill="#2A2A3D", outline="")

        # Pins serveurs
        self._pins = []
        for srv in self._servers:
            coords = CITY_COORDS.get(srv.city)
            if not coords:
                continue
            x, y = self._project(*coords)
            color = _GREEN if srv.latency_ms < 60 else (
                _AMBER if srv.latency_ms < 150 else _RED
            )
            # Halo
            self.create_oval(x - 9, y - 9, x + 9, y + 9,
                             outline=color, width=1)
            # Pin
            self.create_oval(x - 5, y - 5, x + 5, y + 5,
                             fill=color, outline="white", width=1)
            # Etiquette ville (au-dessus)
            self.create_text(x, y - 14, text=srv.city,
                             fill=_TEXT_SOFT,
                             font=(_FONT, 8, "bold"))
            self._pins.append((x, y, srv))

        # Legende
        self.create_text(10, self.HEIGHT - 12,
                         text="● < 60 ms     ● < 150 ms     ● > 150 ms",
                         anchor="w", fill=_TEXT_MUTED, font=(_FONT, 8))

    def _on_motion(self, event) -> None:
        # Tooltip simplifie : change le curseur si on survole un pin
        for x, y, _ in self._pins:
            if abs(event.x - x) < 8 and abs(event.y - y) < 8:
                self.configure(cursor="hand2")
                return
        self.configure(cursor="")

    def _on_click(self, event) -> None:
        for x, y, srv in self._pins:
            if abs(event.x - x) < 10 and abs(event.y - y) < 10:
                self._on_select(srv.id)
                return


# ============================================================================
#  SPEED CHART (latence + debit en direct)
# ============================================================================

class SpeedChart(ctk.CTkCanvas):
    """Graphique line chart double : latence (cyan) + debit (violet)."""

    WIDTH  = 600
    HEIGHT = 200
    HISTORY = 60  # points = 60 secondes

    def __init__(self, parent):
        super().__init__(parent, width=self.WIDTH, height=self.HEIGHT,
                         bg=_BG, highlightthickness=0)
        self._latency = collections.deque(maxlen=self.HISTORY)
        self._throughput = collections.deque(maxlen=self.HISTORY)
        self._draw()

    def push(self, latency_ms: int, throughput_mbps: int) -> None:
        self._latency.append(max(0, latency_ms))
        self._throughput.append(max(0, throughput_mbps))
        self._draw()

    def reset(self) -> None:
        self._latency.clear()
        self._throughput.clear()
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w, h = self.WIDTH, self.HEIGHT

        # Fond + grille horizontale
        self.create_rectangle(0, 0, w, h, fill=_BG, outline="")
        for i in range(1, 5):
            y = int(h * i / 5)
            self.create_line(0, y, w, y, fill="#1A1A28", width=1)

        # Etiquettes
        self.create_text(8, 10, text="LATENCE (ms)", anchor="w",
                         fill=_CYAN, font=(_FONT, 9, "bold"))
        self.create_text(w - 8, 10, text="DEBIT (Mb/s)", anchor="e",
                         fill=_VIOLET, font=(_FONT, 9, "bold"))

        # Echelles dynamiques
        max_lat = max(self._latency, default=100) or 100
        max_thr = max(self._throughput, default=500) or 500
        # Garde des max minimums lisibles
        max_lat = max(max_lat, 100)
        max_thr = max(max_thr, 100)

        def draw_series(values, color, max_val):
            if len(values) < 2:
                return
            n = len(values)
            pts = []
            for i, v in enumerate(values):
                x = int(i / max(1, n - 1) * w)
                y = int(h - (v / max_val) * (h - 30) - 10)
                pts.extend([x, y])
            self.create_line(*pts, fill=color, width=2, smooth=True)
            # Petit point a l'extremite pour marquer la valeur courante
            if pts:
                xl, yl = pts[-2], pts[-1]
                self.create_oval(xl - 3, yl - 3, xl + 3, yl + 3,
                                 fill=color, outline="")

        draw_series(list(self._latency), _CYAN, max_lat)
        draw_series(list(self._throughput), _VIOLET, max_thr)

        # Valeurs courantes
        if self._latency:
            self.create_text(8, h - 12,
                             text=f"  ↳ {self._latency[-1]} ms",
                             anchor="w", fill=_CYAN, font=(_FONT, 9, "bold"))
        if self._throughput:
            self.create_text(w - 8, h - 12,
                             text=f"{self._throughput[-1]} Mb/s ↲  ",
                             anchor="e", fill=_VIOLET, font=(_FONT, 9, "bold"))


# ============================================================================
#  LEAK TEST PANEL
# ============================================================================

class LeakTestPanel(ctk.CTkFrame):
    """Panneau qui lance LeakTester et affiche les resultats colories."""

    def __init__(self, parent, expected_ip_provider: Callable[[], Optional[str]]):
        super().__init__(parent, fg_color=_BG)
        self._expected_ip_provider = expected_ip_provider
        self._tester = LeakTester()

        head = ctk.CTkLabel(self, text="Test de fuite",
                            text_color=_TEXT,
                            font=(_FONT, 14, "bold"))
        head.pack(anchor="w", padx=14, pady=(12, 2))

        sub = ctk.CTkLabel(self,
            text="Verifie en temps reel que votre vraie IP, vos DNS et votre "
                 "IPv6 ne fuient pas hors du tunnel VPN.",
            text_color=_TEXT_MUTED, font=(_FONT, 10),
            anchor="w", justify="left", wraplength=540)
        sub.pack(anchor="w", padx=14, pady=(0, 10))

        self._btn = ctk.CTkButton(
            self, text="LANCER LE TEST",
            font=(_FONT, 12, "bold"),
            fg_color=_VIOLET, hover_color=_VIOLET_DARK,
            text_color="white", corner_radius=10, height=38,
            command=self._run,
        )
        self._btn.pack(fill="x", padx=14, pady=(0, 12))

        # Conteneur des resultats
        self._results_frame = ctk.CTkFrame(self, fg_color=_SURFACE,
                                           corner_radius=10,
                                           border_color=_BORDER,
                                           border_width=1)
        self._results_frame.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        self._placeholder = ctk.CTkLabel(self._results_frame,
            text="Aucun test lance.", text_color=_TEXT_MUTED,
            font=(_FONT, 11))
        self._placeholder.pack(pady=24)

    def _run(self) -> None:
        self._btn.configure(text="TEST EN COURS...", state="disabled")
        self._clear_results()
        ctk.CTkLabel(self._results_frame, text="⏳ Verification...",
                     text_color=_CYAN, font=(_FONT, 11)).pack(pady=24)

        def worker():
            expected = self._expected_ip_provider()
            res = self._tester.run(expected)
            self.after(0, self._render, res)

        threading.Thread(target=worker, daemon=True).start()

    def _clear_results(self) -> None:
        for child in self._results_frame.winfo_children():
            child.destroy()

    def _render(self, res: LeakTestResult) -> None:
        self._clear_results()
        self._btn.configure(text="LANCER LE TEST", state="normal")

        # Resume global
        if res.summary_ok:
            head_text = "✓  Aucune fuite detectee"
            head_color = _GREEN
        else:
            head_text = "⚠  Fuites potentielles"
            head_color = _AMBER
        ctk.CTkLabel(self._results_frame, text=head_text,
                     text_color=head_color,
                     font=(_FONT, 13, "bold")).pack(anchor="w",
                                                    padx=14, pady=(12, 8))

        # Detail ligne par ligne
        self._row("IP publique",
                  res.public_ip or "non determinee",
                  ok=not res.ip_leak,
                  hint=("Conforme" if not res.ip_leak
                        else f"Attendue : {res.expected_ip}"))

        self._row("DNS systeme",
                  ", ".join(res.dns_servers) or "aucun",
                  ok=not res.dns_leak,
                  hint=("DNS proteges" if not res.dns_leak
                        else "DNS non chiffres detectes"))

        self._row("IPv6",
                  "Connectivite IPv6 active" if res.ipv6_present
                  else "IPv6 desactive",
                  ok=not res.ipv6_leak,
                  hint=("OK" if not res.ipv6_leak
                        else "Risque de fuite IPv6 hors tunnel"))

        self._row("WebRTC", "Test cote navigateur",
                  ok=True, hint=res.webrtc_warning)

    def _row(self, label: str, value: str, ok: bool, hint: str) -> None:
        row = ctk.CTkFrame(self._results_frame, fg_color=_SURFACE_2,
                           corner_radius=8)
        row.pack(fill="x", padx=14, pady=4)
        color = _GREEN if ok else _AMBER
        # Pastille
        dot = ctk.CTkFrame(row, width=10, height=10, corner_radius=5,
                           fg_color=color)
        dot.pack(side="left", padx=10, pady=10)
        # Texte
        block = ctk.CTkFrame(row, fg_color="transparent")
        block.pack(side="left", fill="x", expand=True, padx=(0, 10),
                   pady=6)
        ctk.CTkLabel(block, text=label, text_color=_TEXT_MUTED,
                     font=(_FONT, 9, "bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(block, text=value, text_color=_TEXT,
                     font=(_FONT, 11),
                     anchor="w", justify="left",
                     wraplength=420).pack(fill="x")
        ctk.CTkLabel(block, text=hint, text_color=color,
                     font=(_FONT, 9),
                     anchor="w", justify="left",
                     wraplength=420).pack(fill="x")
