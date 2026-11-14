"""Small runtime localisation helper (pure Python, no Qt).

Catalogs are flat UTF-8 JSON objects in ``locales/<tag>.json`` that map the
English source text (the message key) to its translation, as described in
``docs/localization.md``. English text is always the fallback, so a missing
translation shows readable English instead of an empty label.

"""
import json
import locale as _system_locale
import re
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")

_catalog = {}
_current = "en"
_missing = set()


def placeholders(text):
    """Return the set of ``{name}`` placeholders used in ``text``."""
    return set(PLACEHOLDER.findall(str(text)))


def load_catalog(tag, directory=None):
    """Load ``<directory>/<tag>.json``; return ``{}`` if absent or invalid."""
    path = Path(directory or LOCALES_DIR) / f"{tag}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items()
            if isinstance(value, str) and value}


def available_locales(directory=None):
    """Locale tags that have a catalog file, with ``en`` always first."""
    tags = []
    folder = Path(directory or LOCALES_DIR)
    if folder.is_dir():
        tags = sorted(p.stem for p in folder.glob("*.json") if p.stem != "en")
    return ["en"] + tags


def resolve_locale(tag, directory=None):
    """Best available locale for ``tag``: exact, then base language, then en.

    ``hi-IN`` -> ``hi-IN`` if present, else ``hi``, else ``en``.
    """
    tag = str(tag or "").replace("_", "-").strip()
    available = {t.lower(): t for t in available_locales(directory)}
    for candidate in (tag, tag.split("-")[0]):
        if candidate.lower() in available:
            return available[candidate.lower()]
    return "en"


def system_locale():
    """The Windows/OS UI language tag (for example ``en-US``), or ``en``."""
    try:
        tag = _system_locale.getlocale()[0] or ""
    except (ValueError, TypeError):
        tag = ""
    return tag.replace("_", "-") or "en"


def set_locale(tag="system", directory=None):
    """Switch the active locale; returns the locale actually used."""
    global _catalog, _current
    wanted = system_locale() if str(tag).lower() == "system" else tag
    _current = resolve_locale(wanted, directory)
    _catalog = {} if _current == "en" else load_catalog(_current, directory)
    _missing.clear()
    return _current


def current_locale():
    return _current


def missing_keys():
    """Keys looked up in the active non-English locale with no translation."""
    return sorted(_missing)


def tr(text, **values):
    """Translate ``text`` (English source) and fill ``{placeholders}``.

    Never raises: bad placeholders or a missing translation fall back to the
    English text.
    """
    translated = _catalog.get(text)
    if translated is None:
        if _current != "en":
            _missing.add(text)
        translated = text
    elif placeholders(translated) != placeholders(text):
        translated = text                  # a broken translation is ignored
    if values:
        try:
            return translated.format(**values)
        except (KeyError, IndexError, ValueError):
            try:
                return text.format(**values)
            except (KeyError, IndexError, ValueError):
                return text
    return translated

