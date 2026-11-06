"""Theme engine (pure Python, no Qt, testable anywhere).

* built-in themes + your own JSON themes in %APPDATA%\\Windows Bar\\themes\\*.json
* QSS builders for the dock and the launcher
* dominant_accent(): derive an accent colour from wallpaper pixels

Colours are "#rrggbb", "#rrggbbaa" or [r, g, b] / [r, g, b, a] with a in 0-255.
A user theme only needs the keys it wants to change; the rest come from
"midnight".
"""
import colorsys
import json
import math
from pathlib import Path

DEFAULT_THEME = "midnight"

BUILTIN = {
    "midnight": dict(
        panel=(18, 18, 22, 225), glass=(20, 20, 24, 60), border=(255, 255, 255, 40),
        card=(255, 255, 255, 18), text="#ffffff", muted=(255, 255, 255, 140),
        button=(255, 255, 255, 26), accent="#7aa2ff",
        radius=12, panel_radius=20, font="Segoe UI"),
    "daylight": dict(
        panel=(246, 246, 249, 235), glass=(246, 246, 249, 90), border=(0, 0, 0, 40),
        card=(0, 0, 0, 14), text="#16161a", muted=(0, 0, 0, 140),
        button=(0, 0, 0, 18), accent="#3b6cff"),
    "aurora": dict(
        panel=(8, 22, 30, 228), glass=(8, 22, 30, 70), border=(90, 255, 210, 50),
        card=(90, 255, 210, 20), accent="#3de6b0"),
    "rose": dict(
        panel=(30, 16, 24, 228), glass=(30, 16, 24, 70), border=(255, 140, 180, 50),
        card=(255, 150, 190, 22), accent="#ff7aa8"),
    "mono": dict(
        panel=(0, 0, 0, 238), glass=(0, 0, 0, 90), border=(255, 255, 255, 60),
        card=(255, 255, 255, 12), accent="#ffffff", radius=6, panel_radius=10),
}


def to_rgba(value):
    """'#rrggbb' / '#rrggbbaa' / [r,g,b(,a)] -> (r, g, b, a) ints."""
    if isinstance(value, str):
        h = value.strip().lstrip("#")
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            raise ValueError(f"bad colour {value!r}")
        vals = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
    else:
        vals = [int(v) for v in value]
    if len(vals) == 3:
        vals.append(255)
    if len(vals) != 4:
        raise ValueError(f"bad colour {value!r}")
    return tuple(max(0, min(255, v)) for v in vals)


def qss(value, alpha=None):
    r, g, b, a = to_rgba(value)
    return f"rgba({r},{g},{b},{a if alpha is None else alpha})"


COLOR_KEYS = ("panel", "glass", "border", "card", "text", "muted", "button", "accent")


def list_themes(user_dir=None):
    names = list(BUILTIN)
    if user_dir and Path(user_dir).is_dir():
        for p in sorted(Path(user_dir).glob("*.json")):
            if p.stem not in names:
                names.append(p.stem)
    return names


def resolve(name, user_dir=None, accent=None):
    """Full token dict for a theme name. Unknown/broken themes fall back."""
    tokens = dict(BUILTIN[DEFAULT_THEME])
    data = BUILTIN.get(name)
    if data is None and user_dir:
        try:
            data = json.loads((Path(user_dir) / f"{name}.json").read_text(encoding="utf-8"))
        except Exception:
            data = None
    for k, v in (data or {}).items():
        if k in tokens:
            tokens[k] = v
    for k in COLOR_KEYS:                      # validate once, here
        try:
            to_rgba(tokens[k])
        except Exception:
            tokens[k] = BUILTIN[DEFAULT_THEME][k]
    for k in ("radius", "panel_radius"):
        try:
            tokens[k] = int(tokens[k])
        except Exception:
            tokens[k] = BUILTIN[DEFAULT_THEME][k]
    if accent:
        try:
            to_rgba(accent)
            tokens["accent"] = accent
        except Exception:
            pass
    return tokens


def build_qss(t):
    """QSS for the dock's cards and buttons."""
    return f"""
QFrame#card {{ background: {qss(t['card'])}; border-radius: {t['radius']}px;
              border: 1px solid transparent; }}
QFrame#card:hover {{ border: 1px solid {qss(t['accent'], 90)}; }}
QLabel {{ background: transparent; }}
QLabel#cardtitle {{ color: {qss(t['muted'])}; font-size: 9px;
                   font-weight: 600; letter-spacing: 1px; }}
QLabel#cardbody {{ color: {qss(t['text'])}; font-size: 15px; font-weight: 600; }}
QPushButton {{ background: {qss(t['button'])}; color: {qss(t['text'])}; border: none;
              border-radius: {max(4, t['radius'] - 4)}px; padding: 6px 10px;
              font-size: 12px; }}
QPushButton:hover {{ background: {qss(t['accent'], 70)}; }}
QPushButton[active="true"] {{ background: {qss(t['accent'], 120)}; }}
QToolTip {{ color: {qss(t['text'])}; background: {qss(t['panel'], 255)};
           border: 1px solid {qss(t['border'])}; padding: 4px; }}
"""


def build_launcher_qss(t):
    return f"""
QLineEdit {{ background: {qss(t['card'])}; color: {qss(t['text'])};
            border: 1px solid {qss(t['accent'], 110)}; border-radius: {t['radius']}px;
            padding: 10px 14px; font-size: 17px; }}
QListWidget {{ background: transparent; border: none; outline: none;
              color: {qss(t['text'])}; font-size: 14px; }}
QListWidget::item {{ padding: 8px 12px; border-radius: {max(4, t['radius'] - 4)}px; }}
QListWidget::item:selected {{ background: {qss(t['accent'], 110)}; color: {qss(t['text'])}; }}
"""


def dominant_accent(pixels):
    """Pick a vivid accent from (r, g, b) pixels: saturated, bright pixels
    dominate; hue is averaged on the colour circle. None for grey images."""
    sx = sy = wsum = ss = sv = 0.0
    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        w = s * s * v
        if w < 0.02:
            continue
        a = h * 2 * math.pi
        sx += w * math.cos(a)
        sy += w * math.sin(a)
        ss += w * s
        sv += w * v
        wsum += w
    if wsum == 0:
        return None
    hue = (math.atan2(sy, sx) / (2 * math.pi)) % 1.0
    sat = min(0.85, max(0.45, ss / wsum))
    val = min(1.0, max(0.75, sv / wsum))
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
