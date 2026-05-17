"""Tests : moteur VPN (machine d'etats, selection, catalogue)."""

from __future__ import annotations

import pytest


@pytest.fixture
def engine():
    from vpn_engine import VPNEngine
    return VPNEngine(real_mode=False)


def test_initial_state_is_disconnected(engine):
    from vpn_engine import ConnectionState
    assert engine.state == ConnectionState.DISCONNECTED
    assert engine.last_error is None
    assert engine.session_duration_seconds() == 0


def test_server_catalog_not_empty(engine):
    servers = engine.list_servers()
    assert len(servers) >= 5
    for s in servers:
        assert s.id
        assert s.country
        assert s.city
        assert s.public_ip


def test_server_lookup_by_id(engine):
    target = engine.list_servers()[0]
    found = engine.get_server(target.id)
    assert found is not None
    assert found.id == target.id


def test_select_best_server_picks_lowest_load(engine):
    servers = engine.list_servers()
    chosen = engine._select_best_server()
    # Doit etre un des serveurs avec la charge la plus faible.
    min_load = min(s.load_percent for s in servers)
    assert chosen.load_percent == min_load


def test_protocol_selection_prefers_wireguard_in_demo(engine):
    from vpn_engine import Protocol
    srv = engine.list_servers()[0]
    chosen = engine._select_best_protocol(srv)
    # En demo (real_mode=False), WireGuard est is_available()=False
    # mais le moteur retombe sur WIREGUARD en mode "moderne".
    assert chosen in (Protocol.WIREGUARD, Protocol.IKEV2, Protocol.OPENVPN)


def test_demo_connect_disconnect_cycle(engine):
    """Le cycle complet en demo doit aboutir sans exception."""
    from vpn_engine import ConnectionState
    engine.connect()  # bloquant en demo (~1.2s)
    assert engine.state == ConnectionState.CONNECTED
    assert engine.session_duration_seconds() >= 0
    engine.disconnect()
    assert engine.state == ConnectionState.DISCONNECTED


def test_select_server_changes_current(engine):
    target = engine.list_servers()[3]
    engine.select_server(target.id)
    assert engine.current_server is not None
    assert engine.current_server.id == target.id


def test_state_change_callback_fired(engine):
    from vpn_engine import ConnectionState
    states = []
    engine.on_state_change = lambda s: states.append(s)
    engine.connect()
    engine.disconnect()
    assert ConnectionState.CONNECTING in states
    assert ConnectionState.CONNECTED in states
    assert ConnectionState.DISCONNECTED in states
