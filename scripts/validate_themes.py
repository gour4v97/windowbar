"""Validate theme JSON files against the rules ``theme.resolve`` applies.

Windows Bar silently falls back to defaults for bad colours or numbers, which
hides mistakes. This tool reports them instead, plus a readability warning
when the text colour has low contrast against the panel colour.

    python scripts/validate_themes.py [files or folders ...]

With no arguments it checks ``themes/gallery``. Exit code 1 on errors;
contrast warnings never fail the run.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import theme  # noqa: E402  (pure Python, no Qt)

NUMBER_RANGES = {"radius": (0, 48), "panel_radius": (0, 64),
                 "spacing": (0, 32), "blur": (0, 100)}
KNOWN = set(theme.COLOR_KEYS) | set(NUMBER_RANGES) | {"font"}
MIN_CONTRAST = 4.5


def _linear(channel):
    value = channel / 255.0
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_linear(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(first, second):
    """WCAG contrast ratio between two RGB(A) colours (alpha ignored)."""
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def validate_data(data):
    """Return ``(errors, warnings)`` for one parsed theme dictionary."""
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["theme must be a JSON object"], warnings
    for key in data:
        if key not in KNOWN:
            warnings.append(f"unknown key {key!r} is ignored")
    for key in theme.COLOR_KEYS:
        if key in data:
            try:
                theme.to_rgba(data[key])
            except Exception:
                errors.append(f"{key}: invalid colour {data[key]!r}")
    for key, (low, high) in NUMBER_RANGES.items():
        if key in data:
            try:
                value = int(data[key])
            except (TypeError, ValueError):
                errors.append(f"{key}: not a number ({data[key]!r})")
                continue
            if not low <= value <= high:
                errors.append(f"{key}: {value} is outside {low}-{high} "
                              "and would be clamped")
    if "font" in data and not (isinstance(data["font"], str) and data["font"].strip()):
        errors.append("font: must be a non-empty string")
    merged = dict(theme.BUILTIN[theme.DEFAULT_THEME])
    merged.update({k: v for k, v in data.items() if k in KNOWN})
    try:
        ratio = contrast_ratio(theme.to_rgba(merged["text"]),
                               theme.to_rgba(merged["panel"]))
        if ratio < MIN_CONTRAST:
            warnings.append(f"text/panel contrast is {ratio:.1f}:1 "
                            f"(below {MIN_CONTRAST}:1)")
    except Exception:
        pass
    return errors, warnings


def validate_file(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"cannot read JSON: {exc}"], []
    return validate_data(data)


def main(argv=None):
    targets = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    if not targets:
        targets = [ROOT / "themes" / "gallery"]
    files = []
    for target in targets:
        files += sorted(target.glob("*.json")) if target.is_dir() else [target]
    failed = False
    for path in files:
        errors, warnings = validate_file(path)
        status = "ERROR" if errors else ("warn" if warnings else "ok")
        print(f"{status:5} {path.name}")
        for message in errors:
            print(f"      error: {message}", file=sys.stderr)
            failed = True
        for message in warnings:
            print(f"      warning: {message}")
    if not files:
        print("no theme files found")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

