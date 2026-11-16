"""Validate translation catalogs in ``locales/`` (run locally and in CI).

Checks: every file is a UTF-8 JSON object of string -> string; ``en.json``
exists when other locales do; translated files contain no keys that are not in
``en.json`` (stale); placeholders such as ``{count}`` match the English source.
Missing translations are reported as coverage, and only fail with --strict.

    python scripts/check_locales.py [--strict] [--dir locales]
"""
import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def check(directory, strict=False):
    """Return ``(errors, notes)`` lists of strings."""
    errors, notes = [], []
    folder = Path(directory)
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not files:
        return errors, ["no locale files found (nothing to check)"]
    catalogs = {}
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: invalid JSON ({exc})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{path.name}: top level must be an object")
            continue
        bad = [k for k, v in data.items()
               if not isinstance(k, str) or not isinstance(v, str)]
        if bad:
            errors.append(f"{path.name}: non-string entries: {bad[:3]}")
            continue
        blank = [k for k, v in data.items() if not v.strip()]
        if blank:
            errors.append(f"{path.name}: empty translations: {blank[:3]}")
        catalogs[path.stem] = data
    english = catalogs.get("en")
    if english is None:
        if any(tag != "en" for tag in catalogs):
            errors.append("en.json is missing but other locales exist")
        return errors, notes
    for tag, data in catalogs.items():
        if tag == "en":
            continue
        stale = sorted(set(data) - set(english))
        if stale:
            errors.append(f"{tag}.json: keys not in en.json: {stale[:5]}")
        for key, value in data.items():
            if key in english and (set(PLACEHOLDER.findall(key))
                                   != set(PLACEHOLDER.findall(value))):
                errors.append(f"{tag}.json: placeholders differ for {key!r}")
        missing = sorted(set(english) - set(data))
        covered = len(english) - len(missing)
        notes.append(f"{tag}: {covered}/{len(english)} translated")
        if missing and strict:
            errors.append(f"{tag}.json: {len(missing)} untranslated keys "
                          f"(e.g. {missing[:3]})")
    return errors, notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(Path(__file__).resolve()
                                             .parents[1] / "locales"))
    parser.add_argument("--strict", action="store_true",
                        help="fail on untranslated keys too")
    args = parser.parse_args(argv)
    errors, notes = check(args.dir, args.strict)
    for note in notes:
        print("note:", note)
    for error in errors:
        print("ERROR:", error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

