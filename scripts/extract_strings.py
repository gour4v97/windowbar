"""List user-visible English strings found in the UI code (for translation).

It scans ``ui/``, ``widgets/`` and a few top-level modules for string literals
passed to common Qt calls (labels, buttons, tabs, tooltips, form rows ...) and
prints them as a JSON catalog seed. It is a helper for building
``locales/en.json``; review the output, it cannot see strings built at runtime.

    python scripts/extract_strings.py            # print JSON
    python scripts/extract_strings.py --write    # write locales/en.json
    python scripts/extract_strings.py --check    # exit 1 if en.json is stale
"""
import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALLS_FIRST = {"QLabel", "QCheckBox", "QPushButton", "QGroupBox", "QAction",
               "setText", "setToolTip", "setPlaceholderText", "setTitle",
               "setWindowTitle", "setStatusTip", "addItem", "addAction"}
CALLS_SECOND = {"addTab"}            # addTab(widget, "Title")
ROW_CALLS = {"addRow"}               # addRow("Label", widget)
SCAN = ["ui", "widgets", "launcher.py", "search.py"]


def _name(func):
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def strings_in(source):
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name, args = _name(node.func), node.args
        picks = []
        if name in CALLS_FIRST and args:
            picks.append(args[0])
        elif name in CALLS_SECOND and len(args) > 1:
            picks.append(args[1])
        elif name in ROW_CALLS and len(args) > 1:
            picks.append(args[0])
        elif name == "QLabel" and args:
            picks.append(args[0])
        for pick in picks:
            text = _literal(pick)
            if text and any(ch.isalpha() for ch in text) and len(text) > 1:
                found.append(text.strip())
    return found


def collect(root=ROOT):
    texts = {}
    for entry in SCAN:
        path = Path(root) / entry
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for file in files:
            if not file.is_file():
                continue
            try:
                source = file.read_text(encoding="utf-8")
                for text in strings_in(source):
                    texts.setdefault(text, str(file.relative_to(root)))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
    return texts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true",
                        help="write locales/en.json (English maps to itself)")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if locales/en.json lacks strings that "
                             "are now in the UI code")
    args = parser.parse_args(argv)
    texts = collect()
    catalog = {text: text for text in sorted(texts)}
    if args.check:
        target = ROOT / "locales" / "en.json"
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
        missing = sorted(set(catalog) - set(existing))
        stale = sorted(set(existing) - set(catalog))
        for text in missing:
            print(f"missing from en.json: {text!r}", file=sys.stderr)
        for text in stale:
            print(f"no longer in the code: {text!r}")
        if missing:
            print("Run: python scripts/extract_strings.py --write",
                  file=sys.stderr)
        return 1 if missing else 0
    if args.write:
        target = ROOT / "locales" / "en.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(catalog, indent=2, ensure_ascii=False)
                          + "\n", encoding="utf-8")
        print(f"wrote {len(catalog)} strings to {target}")
    else:
        print(json.dumps(catalog, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

