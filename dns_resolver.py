"""
============================================================================
 AuroraVPN - Mini-resolveur DNS local (UDP)
============================================================================
 Fichier  : dns_resolver.py
 Role     : Ecoute en localhost (UDP 5353 par defaut, ou 53 si admin),
            forwarde vers un upstream (1.1.1.1), bloque les domaines
            connus de la blocklist via reponse NXDOMAIN.
============================================================================

 Pour activer effectivement la Threat Protection au niveau systeme :
   1. Demarrer ce resolveur (StartLocalResolver().start()).
   2. Pointer Windows DNS sur 127.0.0.1 (port 5353 ou 53).
   3. Le resolveur consulte ThreatProtection.check_domain() avant
      de forwarder. Si bloque, renvoie NXDOMAIN (RCODE=3).

 Conception :
   - Pas de framework dnspython requis pour le parsing DNS de base.
   - Implementation manuelle minimaliste (suffit pour A/AAAA queries).
   - Forwarding UDP simple, fallback NXDOMAIN si upstream injoignable.
============================================================================
"""

from __future__ import annotations

import socket
import struct
import threading
from typing import Callable, Optional, Tuple

from utils import log


# ============================================================================
#  Parsing DNS minimaliste
# ============================================================================

def _decode_qname(data: bytes, offset: int) -> Tuple[str, int]:
    """Decode un QNAME DNS (RFC 1035, sans gerer la compression poussee)."""
    labels = []
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            break
        # Compression : pointeur 0xC0
        if length & 0xC0 == 0xC0:
            # On ignore la compression pour la simplicite (rare en query).
            offset += 2
            break
        offset += 1
        labels.append(data[offset:offset + length].decode("ascii", errors="ignore"))
        offset += length
    return ".".join(labels), offset


def parse_question(data: bytes) -> Optional[Tuple[int, str, int, int]]:
    """
    Parse l'en-tete + premiere question d'un paquet DNS.
    Retourne (transaction_id, qname, qtype, qclass) ou None.
    """
    if len(data) < 12:
        return None
    txid, flags, qdcount = struct.unpack("!HHH", data[:6])
    if qdcount == 0:
        return None
    qname, offset = _decode_qname(data, 12)
    if offset + 4 > len(data):
        return None
    qtype, qclass = struct.unpack("!HH", data[offset:offset + 4])
    return txid, qname, qtype, qclass


def build_nxdomain_response(query: bytes) -> bytes:
    """
    Construit une reponse NXDOMAIN (RCODE=3) en reprenant la question.
    """
    if len(query) < 12:
        return b""
    txid = query[0:2]
    # Flags : QR=1, OPCODE=0, AA=0, TC=0, RD=1, RA=1, Z=0, RCODE=3 (NXDOMAIN)
    # 0x8183 = 1000 0001 1000 0011
    flags = b"\x81\x83"
    qdcount = query[4:6]   # garde la question
    ancount = b"\x00\x00"
    nscount = b"\x00\x00"
    arcount = b"\x00\x00"
    # Section question (recopie)
    return txid + flags + qdcount + ancount + nscount + arcount + query[12:]


# ============================================================================
#  Resolveur
# ============================================================================

class LocalDnsResolver:
    """
    Mini-serveur DNS UDP. Forwarde les requetes vers un upstream
    chiffre / classique, bloque les domaines listes via NXDOMAIN.

    Usage :
        resolver = LocalDnsResolver(blocker=lambda host: tp.check_domain(host))
        resolver.start()
        # ... (Windows DNS pointe sur 127.0.0.1:5353)
        resolver.stop()
    """

    DEFAULT_PORT = 5353
    UPSTREAM = ("1.1.1.1", 53)
    UPSTREAM_TIMEOUT = 2.0

    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = DEFAULT_PORT,
                 blocker: Optional[Callable[[str], bool]] = None,
                 upstream: Tuple[str, int] = UPSTREAM):
        self.host = host
        self.port = port
        self.blocker = blocker or (lambda _h: False)
        self.upstream = upstream

        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._stats = {"queries": 0, "blocked": 0, "forwarded": 0,
                       "errors": 0}

    # ------------------------------------------------------------------ Lifecycle

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    def start(self) -> bool:
        if self.is_running:
            return True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind((self.host, self.port))
            self._sock.settimeout(0.5)
        except Exception as exc:
            log.warning("DNS resolver bind echec : %s", exc)
            self._cleanup_socket()
            return False

        self._stop.clear()
        self._thread = threading.Thread(target=self._serve_loop,
                                        daemon=True,
                                        name="aurora-dns-resolver")
        self._thread.start()
        log.info("DNS resolver demarre sur %s:%d", self.host, self.port)
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._cleanup_socket()
        log.info("DNS resolver arrete")

    def _cleanup_socket(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    # ------------------------------------------------------------------ Loop

    def _serve_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception as exc:
                if not self._stop.is_set():
                    log.debug("DNS recv erreur : %s", exc)
                    self._stats["errors"] += 1
                continue

            self._stats["queries"] += 1
            try:
                self._handle_query(data, addr)
            except Exception as exc:
                log.debug("DNS handle erreur : %s", exc)
                self._stats["errors"] += 1

    def _handle_query(self, data: bytes, addr) -> None:
        parsed = parse_question(data)
        if not parsed:
            return
        txid, qname, qtype, qclass = parsed

        # Decision : bloquer ou forwarder.
        if self.blocker(qname):
            response = build_nxdomain_response(data)
            if response:
                self._sock.sendto(response, addr)
                self._stats["blocked"] += 1
                log.debug("DNS BLOCK %s", qname)
            return

        # Forward vers l'upstream.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as up:
                up.settimeout(self.UPSTREAM_TIMEOUT)
                up.sendto(data, self.upstream)
                answer, _ = up.recvfrom(4096)
            self._sock.sendto(answer, addr)
            self._stats["forwarded"] += 1
        except Exception as exc:
            log.debug("Upstream %s%s : %s", *self.upstream[:1], self.upstream, exc)
            self._stats["errors"] += 1
            # On renvoie NXDOMAIN plutot que de laisser le client en timeout.
            response = build_nxdomain_response(data)
            if response:
                try:
                    self._sock.sendto(response, addr)
                except Exception:
                    pass
