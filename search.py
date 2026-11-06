"""Launcher helpers (pure Python): fuzzy search, Start Menu scan, hotkey
parsing and a tiny safe calculator."""
import ast
import operator
import os
import re
from pathlib import Path


def fuzzy_score(query, text):
    """Higher is better; None when query is not a subsequence of text."""
    q, t = query.lower().strip(), text.lower()
    if not q:
        return 0
    if t == q:
        return 1000
    if t.startswith(q):
        return 900 - len(t)
    i = t.find(q)
    if i >= 0:
        word = i == 0 or not t[i - 1].isalnum()
        return 700 - i * 5 - len(t) + (50 if word else 0)
    pos, prev, score = -1, -2, 0
    for ch in q:
        pos = t.find(ch, pos + 1)
        if pos < 0:
            return None
        score += 10
        if pos == prev + 1:
            score += 15
        if pos == 0 or not t[pos - 1].isalnum():
            score += 10
        prev = pos
    return score - len(t) // 4


def rank(query, entries, limit=8):
    """entries: [(name, target, kind)] -> best matches first."""
    if not query.strip():
        return list(entries)[:limit]
    scored = []
    for e in entries:
        s = fuzzy_score(query, e[0])
        if s is not None:
            scored.append((-s, e[0].lower(), e))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [e for _, _, e in scored[:limit]]


def scan_start_menu():
    """[(name, .lnk path, 'app')] from the all-users and per-user Start Menu."""
    roots = []
    for var in ("ProgramData", "APPDATA"):
        base = os.environ.get(var)
        if base:
            roots.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    seen, out = set(), []
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, _, files in os.walk(root):
            for f in files:
                if not f.lower().endswith(".lnk"):
                    continue
                name = f[:-4]
                low = name.lower()
                if "uninstall" in low or low in seen:
                    continue
                seen.add(low)
                out.append((name, str(Path(dirpath) / f), "app"))
    return sorted(out, key=lambda e: e[0].lower())


MOD = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}


def parse_hotkey(spec):
    """'alt+space' -> (modifiers, virtual-key) or None."""
    parts = [p.strip().lower() for p in (spec or "").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    mods, key = 0, parts[-1]
    for p in parts[:-1]:
        if p not in MOD:
            return None
        mods |= MOD[p]
    if key == "space":
        return mods, 0x20
    if re.fullmatch(r"f([1-9]|1[0-2])", key):
        return mods, 0x70 + int(key[1:]) - 1
    if len(key) == 1 and key.isalnum():
        return mods, ord(key.upper())
    return None


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv, ast.Pow: operator.pow}


def safe_calc(expr):
    """Evaluate + - * / // % ** and parentheses. None for anything else,
    including a bare number."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return None
    if isinstance(tree.body, ast.Constant):
        return None

    def ev(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise ValueError("too big")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = ev(n.operand)
            return v if isinstance(n.op, ast.UAdd) else -v
        raise ValueError("unsupported")

    try:
        res = ev(tree.body)
    except (ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    return f"{res:,.10g}"
