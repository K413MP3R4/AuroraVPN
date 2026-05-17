"""Tests : persistance des preferences utilisateur."""

from __future__ import annotations


def test_default_config_has_safe_defaults(isolated_config):
    cfg = isolated_config.UserConfig()
    assert cfg.last_protocol == "Auto"
    assert cfg.last_mode == "Auto"
    assert cfg.kill_switch is True
    assert cfg.dns_protection is True
    assert cfg.real_subprocess is False, \
        "Le mode reel doit etre OFF par defaut (securite)"
    assert cfg.real_security is False
    assert cfg.notifications_enabled is True


def test_save_and_load_roundtrip(isolated_config):
    cfg = isolated_config.UserConfig()
    cfg.last_protocol = "WireGuard"
    cfg.last_server_id = "fr-par-01"
    cfg.kill_switch = False
    cfg.save()

    reloaded = isolated_config.UserConfig.load()
    assert reloaded.last_protocol == "WireGuard"
    assert reloaded.last_server_id == "fr-par-01"
    assert reloaded.kill_switch is False


def test_load_with_unknown_keys_ignored(isolated_config, tmp_appdata):
    """Si un futur upgrade ajoute des cles, l'ancien fichier doit toujours
    se charger sans erreur (forward-compat) et inversement."""
    import json
    config_path = tmp_appdata / "AuroraVPN" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({
        "last_protocol": "OpenVPN",
        "unknown_field_from_future": "ignore_me",
        "another_unknown": 42,
    }), encoding="utf-8")

    cfg = isolated_config.UserConfig.load()
    assert cfg.last_protocol == "OpenVPN"


def test_load_corrupted_json_returns_defaults(isolated_config, tmp_appdata):
    config_path = tmp_appdata / "AuroraVPN" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{not valid json", encoding="utf-8")

    cfg = isolated_config.UserConfig.load()
    # Doit retomber sur les defauts sans crasher.
    assert cfg.last_protocol == "Auto"


def test_app_data_dir_creates_folder(isolated_config, tmp_appdata):
    path = isolated_config.app_data_dir()
    assert path.exists()
    assert path.is_dir()
