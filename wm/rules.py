"""Floating-window rules: parsing and matching (no Windows or Qt imports)."""
import re

_SPLIT = re.compile(r"[,;\r\n]+")


def _values(raw, key):
    if isinstance(raw, str):
        return [raw] if key == "title_regex" else _SPLIT.split(raw)
    return list(raw) if isinstance(raw, (list, tuple, set)) else []


def split_names(value):
    """Turn ``"a.exe, b.exe"`` (or a list) into a set of lowercase names."""
    if isinstance(value, str):
        value = _SPLIT.split(value)
    return {str(item).strip().lower() for item in (value or [])
            if str(item).strip()}


class FloatingRules:
    """Executable, window-class and title-regex rules that exempt windows.

    ``matches`` takes callables for the class and title so the (comparatively
    expensive) Win32 lookups only happen when an earlier rule did not match.
    """

    def __init__(self, rules=None, floating_apps=()):
        rules = rules if isinstance(rules, dict) else {}
        self.executables = split_names(_values(rules.get("executables", []),
                                               "executables"))
        self.executables |= split_names(floating_apps)
        self.classes = split_names(_values(rules.get("classes", []), "classes"))
        self.title_patterns, self.invalid_title_patterns = [], []
        for value in _values(rules.get("title_regex", []), "title_regex"):
            text = str(value)
            if not text.strip():
                continue
            try:
                self.title_patterns.append(re.compile(text, re.IGNORECASE))
            except re.error:
                self.invalid_title_patterns.append(text)

    def matches(self, exe="", window_class=None, title=None):
        """True if the window should float.

        ``window_class`` and ``title`` may be strings or zero-argument
        callables returning strings.
        """
        if str(exe or "").lower() in self.executables:
            return True
        if self.classes:
            value = window_class() if callable(window_class) else window_class
            if str(value or "").lower() in self.classes:
                return True
        if self.title_patterns:
            value = title() if callable(title) else title
            value = str(value or "")
            return any(pattern.search(value) for pattern in self.title_patterns)
        return False

