"""
============================================================================
 AuroraVPN - Internationalisation (i18n)
============================================================================
 Fichier  : i18n.py
 Role     : Charge les fichiers locales/<lang>.json et expose une fonction
            _() pour traduire les chaines de l'UI a la volee.
============================================================================

 Usage :
   from i18n import _, set_language, available_languages
   _("connect_button")     # -> "Connecter" (fr) / "Connect" (en)
   set_language("en")
   _("connect_button")     # -> "Connect"

 Detection automatique au demarrage : utilise locale.getlocale() puis
 retombe sur l'anglais si la langue n'est pas supportee.
============================================================================
"""

from __future__ import annotations

import json
import locale as _locale
from pathlib import Path
from typing import Dict, List

from utils import log


_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_DEFAULT_LANG = "en"
_FALLBACK_LANG = "en"

_translations: Dict[str, Dict[str, str]] = {}
_current_lang: str = _DEFAULT_LANG


# ===========================================================================
#  Chargement
# ===========================================================================

def _load_all() -> None:
    """Charge tous les fichiers locales/*.json en memoire."""
    global _translations
    if not _LOCALES_DIR.exists():
        log.debug("Dossier locales/ absent, i18n desactivee")
        return
    for path in _LOCALES_DIR.glob("*.json"):
        lang = path.stem.lower()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _translations[lang] = {str(k): str(v) for k, v in data.items()}
                log.debug("Locale chargee : %s (%d cles)", lang, len(data))
        except Exception as exc:
            log.warning("Locale %s : %s", lang, exc)


def _detect_system_lang() -> str:
    """Detecte la langue systeme. Retombe sur _DEFAULT_LANG."""
    try:
        lang_code, _enc = _locale.getlocale()
        if lang_code:
            short = lang_code.split("_")[0].lower()
            if short in _translations:
                return short
    except Exception:
        pass
    return _DEFAULT_LANG


# ===========================================================================
#  API publique
# ===========================================================================

def set_language(lang: str) -> bool:
    """Change la langue active. Renvoie True si la langue est dispo."""
    global _current_lang
    lang = lang.lower()
    if lang in _translations:
        _current_lang = lang
        log.info("Langue active : %s", lang)
        return True
    log.warning("Langue inconnue : %s (dispos : %s)",
                lang, list(_translations.keys()))
    return False


def get_language() -> str:
    return _current_lang


def available_languages() -> List[str]:
    return sorted(_translations.keys())


def _(key: str, **kwargs) -> str:
    """
    Traduit une cle. Si la cle n'existe pas, retombe sur la langue de
    fallback puis sur la cle elle-meme. Supporte le formatting Python :

        _("hello_user", name="Alice")
        # avec en.json: {"hello_user": "Hello {name}!"}
    """
    table = _translations.get(_current_lang, {})
    text = table.get(key)
    if text is None:
        # Fallback langue.
        fb = _translations.get(_FALLBACK_LANG, {})
        text = fb.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# ===========================================================================
#  Initialisation au load du module
# ===========================================================================

_load_all()

# Selectionne la langue systeme si disponible, sinon defaut.
_current_lang = _detect_system_lang() if _translations else _DEFAULT_LANG
