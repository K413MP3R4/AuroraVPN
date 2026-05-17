"""Tests : SecurityManager (toggles + leak monitor + kill switch)."""

from __future__ import annotations

import pytest


@pytest.fixture
def sec():
    from security import SecurityManager
    # real_mode=False : aucun appel systeme reel.
    return SecurityManager(real_mode=False)


def test_default_security_status_safe(sec):
    s = sec.status
    assert s.kill_switch is True
    assert s.dns_protection is True
    assert s.leak_protection is True
    assert s.pfs is True
    assert s.post_quantum is False


def test_toggles_update_status(sec):
    sec.set_kill_switch(False)
    assert sec.status.kill_switch is False
    sec.set_dns_protection(False)
    assert sec.status.dns_protection is False
    sec.set_post_quantum(True)
    assert sec.status.post_quantum is True


def test_status_returns_immutable_snapshot(sec):
    """Modifier le snapshot retourne ne doit pas affecter l'etat interne."""
    snapshot = sec.status
    snapshot.kill_switch = False
    assert sec.status.kill_switch is True


def test_real_mode_toggle(sec):
    sec.set_real_mode(True)
    sec.set_real_mode(False)
    # Verifie juste qu'aucune exception n'est levee.


def test_kill_switch_demo_mode_is_no_op(sec):
    """En demo (real_mode=False), aucune regle firewall n'est creee."""
    sec.set_kill_switch(True)
    # arm/disarm doivent etre des no-ops silencieux.
    sec.arm_kill_switch(vpn_endpoint_ip="1.2.3.4")
    sec.disarm_kill_switch()
    # Pas d'assertion forte : on verifie surtout que rien ne crashe.


def test_leak_monitor_start_stop(sec):
    sec.start_leak_monitor(expected_vpn_ip="1.2.3.4")
    assert sec._leak_thread is not None
    assert sec._leak_thread.is_alive()
    sec.stop_leak_monitor()
    # Le thread est demon, il s'arrete au prochain wait().


def test_hydrate_and_export_config(sec):
    """Verifie que les toggles peuvent etre persistes via UserConfig."""
    from config import UserConfig

    cfg = UserConfig()
    cfg.kill_switch = False
    cfg.post_quantum = True
    sec.hydrate_from_config(cfg)
    assert sec.status.kill_switch is False
    assert sec.status.post_quantum is True

    # Maj cote security puis export.
    sec.set_dns_protection(False)
    cfg2 = UserConfig()
    sec.export_to_config(cfg2)
    assert cfg2.dns_protection is False
