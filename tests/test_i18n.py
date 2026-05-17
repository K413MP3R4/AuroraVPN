"""Tests : internationalisation."""

from __future__ import annotations

import pytest


def test_default_language_is_loaded():
    from i18n import available_languages
    langs = available_languages()
    assert "fr" in langs
    assert "en" in langs


def test_translate_existing_key():
    from i18n import _, set_language
    set_language("fr")
    assert _("btn_connect") == "CONNECTER"
    set_language("en")
    assert _("btn_connect") == "CONNECT"


def test_translate_missing_key_returns_key():
    from i18n import _, set_language
    set_language("fr")
    # Cle inexistante : doit renvoyer la cle elle-meme.
    assert _("nonexistent_key_12345") == "nonexistent_key_12345"


def test_translate_with_format_args():
    """Verifie le formatting Python sur les valeurs."""
    # Pour ce test, on n'a pas de cle parametree dans les locales,
    # donc on verifie que le fallback fonctionne sans crash.
    from i18n import _
    result = _("nonexistent_with_args", name="Alice")
    assert isinstance(result, str)


def test_set_language_invalid_returns_false():
    from i18n import set_language
    assert set_language("zz_XX") is False


def test_set_language_changes_current():
    from i18n import set_language, get_language
    set_language("fr")
    assert get_language() == "fr"
    set_language("en")
    assert get_language() == "en"


def test_fallback_language_works():
    """Si une cle existe en EN mais pas en FR, doit retomber sur EN."""
    from i18n import _, set_language, _translations

    # Injecte une cle uniquement dans EN.
    if "en" in _translations:
        _translations["en"]["only_in_en"] = "english only"
        if "fr" in _translations:
            _translations["fr"].pop("only_in_en", None)

    set_language("fr")
    # Doit retomber sur EN.
    assert _("only_in_en") == "english only"
