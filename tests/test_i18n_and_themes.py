"""Localisation helper, locale checker, string extractor and theme validator.

All pure Python; none of this needs Windows or Qt.
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import i18n  # noqa: E402


def _script(name):
    spec = importlib.util.spec_from_file_location(
        f"_script_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(folder, tag, data):
    folder.mkdir(exist_ok=True)
    (folder / f"{tag}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _locales(tmp_path):
    folder = tmp_path / "locales"
    _write(folder, "en", {"Save": "Save", "{count} windows": "{count} windows",
                          "Close": "Close"})
    _write(folder, "hi", {"Save": "सहेजें", "{count} windows": "{count} विंडो"})
    return folder


def test_tr_translates_falls_back_and_formats(tmp_path):
    folder = _locales(tmp_path)
    assert i18n.set_locale("hi", folder) == "hi"
    assert i18n.tr("Save") == "सहेजें"
    assert i18n.tr("{count} windows", count=3) == "3 विंडो"
    assert i18n.tr("Close") == "Close"              # untranslated: English
    assert i18n.missing_keys() == ["Close"]
    assert i18n.set_locale("en", folder) == "en"
    assert i18n.tr("Save") == "Save"
    assert i18n.missing_keys() == []


def test_locale_resolution_prefers_exact_then_language_then_english(tmp_path):
    folder = _locales(tmp_path)
    assert i18n.available_locales(folder) == ["en", "hi"]
    assert i18n.resolve_locale("hi-IN", folder) == "hi"
    assert i18n.resolve_locale("HI", folder) == "hi"
    assert i18n.resolve_locale("fr_FR", folder) == "en"
    assert i18n.resolve_locale("", folder) == "en"
    assert i18n.available_locales(tmp_path / "nope") == ["en"]


def test_tr_never_raises_on_bad_input(tmp_path):
    folder = tmp_path / "locales"
    _write(folder, "en", {})
    _write(folder, "de", {"Hello {name}": "Hallo {wrong}", "Plain": "Einfach"})
    i18n.set_locale("de", folder)
    # translation with different placeholders is ignored, English is used
    assert i18n.tr("Hello {name}", name="Ana") == "Hello Ana"
    assert i18n.tr("Plain", extra=1) == "Einfach"
    assert i18n.tr("Needs {x}") == "Needs {x}"       # no values given
    assert i18n.tr("Needs {x}", y=1) == "Needs {x}"  # wrong value name
    i18n.set_locale("en", folder)


def test_broken_catalog_files_are_ignored(tmp_path):
    folder = tmp_path / "locales"
    folder.mkdir()
    (folder / "xx.json").write_text("{oops", encoding="utf-8")
    (folder / "yy.json").write_text("[1]", encoding="utf-8")
    assert i18n.load_catalog("xx", folder) == {}
    assert i18n.load_catalog("yy", folder) == {}
    assert i18n.load_catalog("zz", folder) == {}
    _write(folder, "ok", {"a": "b", "bad": 5, "empty": ""})
    assert i18n.load_catalog("ok", folder) == {"a": "b"}


def test_locale_check_accepts_valid_and_reports_coverage(tmp_path):
    check = _script("check_locales")
    errors, notes = check.check(_locales(tmp_path))
    assert errors == []
    assert notes == ["hi: 2/3 translated"]
    errors, _ = check.check(_locales(tmp_path), strict=True)
    assert len(errors) == 1 and "untranslated" in errors[0]


def test_locale_check_finds_stale_keys_and_placeholder_mismatches(tmp_path):
    check = _script("check_locales")
    folder = _locales(tmp_path)
    _write(folder, "hi", {"Save": "सहेजें", "{count} windows": "{n} विंडो",
                          "Gone": "गया"})
    errors, _ = check.check(folder)
    text = "\n".join(errors)
    assert "keys not in en.json" in text and "Gone" in text
    assert "placeholders differ" in text


def test_locale_check_handles_missing_english_and_bad_files(tmp_path):
    check = _script("check_locales")
    assert check.check(tmp_path / "none")[0] == []
    folder = tmp_path / "locales"
    _write(folder, "hi", {"a": "b"})
    assert any("en.json is missing" in e for e in check.check(folder)[0])
    (folder / "bad.json").write_text("{", encoding="utf-8")
    assert any("invalid JSON" in e for e in check.check(folder)[0])


def test_repo_locales_pass_the_checker():
    check = _script("check_locales")
    errors, _ = check.check(ROOT / "locales")
    assert errors == []


def test_extractor_finds_ui_strings_and_ignores_other_calls():
    extract = _script("extract_strings")
    source = '''
form.addRow("Layout engine", combo)
tabs.addTab(page, "Appearance")
box = QCheckBox("Track windows")
button.setToolTip("Closes the bar")
x = QLabel("")
y = compute("not ui text")
z = QLabel("1")
'''
    assert set(extract.strings_in(source)) == {
        "Layout engine", "Appearance", "Track windows", "Closes the bar"}


def test_gallery_themes_are_valid():
    validate = _script("validate_themes")
    for path in sorted((ROOT / "themes" / "gallery").glob("*.json")):
        errors, _ = validate.validate_file(path)
        assert errors == [], (path.name, errors)


def test_theme_validator_reports_what_theme_resolve_silently_fixes():
    validate = _script("validate_themes")
    errors, warnings = validate.validate_data({
        "accent": "not-a-colour", "panel": [1, 2], "radius": 999,
        "blur": "lots", "font": "", "mystery": 1})
    text = "\n".join(errors)
    assert "accent" in text and "panel" in text
    assert "radius" in text and "blur" in text and "font" in text
    assert any("mystery" in w for w in warnings)
    assert validate.validate_data([1])[0] == ["theme must be a JSON object"]


def test_theme_validator_warns_on_low_contrast_only():
    validate = _script("validate_themes")
    errors, warnings = validate.validate_data(
        {"panel": "#808080", "text": "#8a8a8a"})
    assert errors == []
    assert any("contrast" in w for w in warnings)
    errors, warnings = validate.validate_data({"panel": "#000000", "text": "#ffffff"})
    assert errors == [] and warnings == []
    assert round(validate.contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0

