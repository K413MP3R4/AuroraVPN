"""Tests : Multi-hop, Tor, Threat Protection, LeakTester."""

from __future__ import annotations

import pytest


# ===== Multi-hop ============================================================

def test_multihop_default_inactive():
    from features import MultiHopManager
    mh = MultiHopManager()
    assert mh.is_active is False


def test_multihop_route_setup():
    from features import MultiHopManager
    mh = MultiHopManager()
    mh.set_route("fr-par-01", "us-nyc-01")
    mh.enable(True)
    assert mh.is_active is True
    assert "fr-par-01" in mh.describe()
    assert "us-nyc-01" in mh.describe()


def test_multihop_rejects_same_entry_exit():
    from features import MultiHopManager
    mh = MultiHopManager()
    with pytest.raises(ValueError):
        mh.set_route("fr-par-01", "fr-par-01")


# ===== Tor over VPN =========================================================

def test_tor_default_not_running():
    from features import TorOverVPN
    tor = TorOverVPN()
    assert tor.is_running is False


def test_tor_proxy_url_format():
    from features import TorOverVPN
    tor = TorOverVPN()
    assert tor.proxy_url() == "socks5://127.0.0.1:9150"


# ===== Threat Protection ====================================================

def test_threat_protection_disabled_returns_false():
    from features import ThreatProtection
    tp = ThreatProtection()
    # Par defaut desactive : rien n'est bloque.
    assert tp.check_domain("doubleclick.net") is False


def test_threat_protection_enabled_with_seed():
    from features import ThreatProtection
    tp = ThreatProtection()
    tp._domains = {"badexample.com", "tracker.evil"}
    tp._enabled = True
    assert tp.check_domain("badexample.com") is True
    assert tp.check_domain("tracker.evil") is True
    assert tp.check_domain("good.com") is False


def test_threat_protection_subdomain_match():
    from features import ThreatProtection
    tp = ThreatProtection()
    tp._domains = {"evil.com"}
    tp._enabled = True
    # Sous-domaine bloque par suffixe.
    assert tp.check_domain("ads.evil.com") is True
    # Domaine voisin non bloque.
    assert tp.check_domain("evilfake.com") is False


def test_threat_protection_stats_increment():
    from features import ThreatProtection
    tp = ThreatProtection()
    tp._domains = {"bad.com"}
    tp._enabled = True
    tp.check_domain("bad.com")
    tp.check_domain("ok.com")
    s = tp.stats
    assert s["queries"] == 2
    assert s["blocked"] == 1


def test_threat_protection_no_double_download():
    """Toggle ON puis ON ne doit pas lancer 2 downloads."""
    from features import ThreatProtection
    tp = ThreatProtection()
    tp._refresh_in_progress = True   # simule un download deja en cours
    tp.enable(True)
    tp.enable(True)
    # Aucun nouveau thread n'a du etre lance (flag toujours True).
    assert tp._refresh_in_progress is True


# ===== LeakTester ===========================================================

def test_leak_tester_no_expected_ip():
    """Sans IP attendue, ip_leak doit etre False (rien a comparer)."""
    from features import LeakTester
    res = LeakTester().run(expected_vpn_ip=None)
    # public_ip peut etre None sans reseau.
    assert res.ip_leak is False


# ===== Notifier =============================================================

def test_notifier_does_not_crash():
    from features import Notifier
    n = Notifier()
    n.notify("Test", "Message de test")
    # Si plyer absent, fallback print. Pas d'exception attendue.
