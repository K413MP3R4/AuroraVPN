"""Tests : utilitaires (logging, single-instance, helpers)."""

from __future__ import annotations


def test_setup_logging_idempotent():
    from utils import setup_logging
    log1 = setup_logging()
    log2 = setup_logging()
    assert log1 is log2  # cache via getLogger("aurora")
    # Ne duplique pas les handlers.
    assert len(log1.handlers) == len(log2.handlers)


def test_hidden_subprocess_kwargs_returns_dict():
    from utils import hidden_subprocess_kwargs
    kw = hidden_subprocess_kwargs()
    assert isinstance(kw, dict)


def test_is_admin_returns_bool():
    from utils import is_admin
    assert isinstance(is_admin(), bool)


def test_is_online_returns_bool():
    from utils import is_online
    assert isinstance(is_online(timeout=1.0), bool)


def test_acquire_release_single_instance():
    from utils import acquire_single_instance, release_single_instance
    ok = acquire_single_instance()
    # Premiere acquisition reussit.
    assert ok is True
    # Seconde acquisition echoue (verrou pris).
    assert acquire_single_instance() is False
    release_single_instance()
    # Apres release, on peut reacquerir.
    assert acquire_single_instance() is True
    release_single_instance()
