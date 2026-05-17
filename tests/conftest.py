"""
============================================================================
 AuroraVPN - Configuration partagee pytest
============================================================================
 Ajoute le repertoire racine au sys.path pour que les tests puissent
 importer config, features, vpn_engine, security, utils, i18n, dns_resolver
 sans installation editable.
============================================================================
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Racine du projet (parent du dossier tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_appdata(monkeypatch, tmp_path):
    """Redirige %APPDATA% vers un dossier temporaire pour l'isolation."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # Force reimport du module config pour reprendre le nouveau APPDATA.
    # Les tests qui touchent a CONFIG_FILE doivent reimporter apres cette fixture.
    return tmp_path


@pytest.fixture
def isolated_config(tmp_appdata, monkeypatch):
    """Cree un UserConfig isole et retourne le module config recharge."""
    import importlib
    import config as cfg_module
    importlib.reload(cfg_module)
    return cfg_module
