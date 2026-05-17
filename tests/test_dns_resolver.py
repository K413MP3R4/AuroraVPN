"""Tests : resolveur DNS local."""

from __future__ import annotations

import socket
import struct
import time

import pytest


def _build_dns_query(qname: str, txid: int = 0x1234) -> bytes:
    """Construit une requete DNS A pour qname."""
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    qname_encoded = b""
    for label in qname.split("."):
        qname_encoded += bytes([len(label)]) + label.encode("ascii")
    qname_encoded += b"\x00"
    qtype_qclass = struct.pack("!HH", 1, 1)  # A, IN
    return header + qname_encoded + qtype_qclass


def test_parse_question_valid():
    from dns_resolver import parse_question
    query = _build_dns_query("example.com")
    parsed = parse_question(query)
    assert parsed is not None
    txid, qname, qtype, qclass = parsed
    assert txid == 0x1234
    assert qname == "example.com"
    assert qtype == 1   # A
    assert qclass == 1  # IN


def test_parse_question_too_short():
    from dns_resolver import parse_question
    assert parse_question(b"\x00\x00") is None


def test_build_nxdomain_response_format():
    from dns_resolver import build_nxdomain_response
    query = _build_dns_query("blocked.com")
    response = build_nxdomain_response(query)
    # Verifier les flags : QR=1, RCODE=3
    flags = struct.unpack("!H", response[2:4])[0]
    assert (flags >> 15) & 1 == 1   # QR=1 (reponse)
    assert flags & 0x0F == 3        # RCODE=3 (NXDOMAIN)


def test_resolver_start_stop_idempotent():
    from dns_resolver import LocalDnsResolver
    # Port haut pour eviter conflits avec un vrai DNS local.
    resolver = LocalDnsResolver(port=15353)
    assert resolver.start() is True
    assert resolver.is_running is True
    # Re-start ne crashe pas.
    assert resolver.start() is True
    resolver.stop()
    assert resolver.is_running is False


def test_resolver_blocks_listed_domain():
    """Le resolveur doit retourner NXDOMAIN pour un domaine bloque."""
    from dns_resolver import LocalDnsResolver

    blocked = {"badtest.example"}
    resolver = LocalDnsResolver(
        port=15354,
        blocker=lambda host: host in blocked,
    )
    assert resolver.start()
    try:
        # Envoie une requete pour le domaine bloque.
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.settimeout(2.0)
        query = _build_dns_query("badtest.example")
        client.sendto(query, ("127.0.0.1", 15354))
        response, _ = client.recvfrom(4096)
        client.close()

        # Verifie RCODE=3 (NXDOMAIN).
        flags = struct.unpack("!H", response[2:4])[0]
        assert flags & 0x0F == 3

        # Stats.
        time.sleep(0.05)
        assert resolver.stats["blocked"] >= 1
    finally:
        resolver.stop()


def test_resolver_stats_initial_zero():
    from dns_resolver import LocalDnsResolver
    resolver = LocalDnsResolver(port=15355)
    s = resolver.stats
    assert s["queries"] == 0
    assert s["blocked"] == 0
    assert s["forwarded"] == 0
    assert s["errors"] == 0
