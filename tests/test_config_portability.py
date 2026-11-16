"""Config backup-before-migration, export and import (no Windows or Qt)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import ConfigImportError, export_config, import_config, save

DEFAULTS = {"position": "bottom", "theme": "midnight", "calendar_url": "",
            "widgets": {"clock": True, "weather": True}}


def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _raises_import_error(call):
    try:
        call()
    except ConfigImportError:
        return True
    return False


def test_saving_over_a_legacy_file_keeps_a_one_time_backup(tmp_path):
    path = tmp_path / "config.json"
    legacy = {"position": "top", "widgets": {"clock": False}}
    _write(path, legacy)
    save(path, {"position": "bottom", "widgets": {}})
    backup = tmp_path / "config.pre-v0.bak"
    assert json.loads(backup.read_text(encoding="utf-8")) == legacy
    save(path, {"position": "left", "widgets": {}})
    assert json.loads(backup.read_text(encoding="utf-8")) == legacy


def test_saving_current_schema_or_new_files_makes_no_backup(tmp_path):
    path = tmp_path / "config.json"
    save(path, {"position": "top", "widgets": {}})
    save(path, {"position": "left", "widgets": {}})
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


def test_export_writes_effective_config_and_blanks_private_values(tmp_path):
    path = tmp_path / "config.json"
    _write(path, {"position": "top", "calendar_url": "https://secret/ical",
                  "_display_id": "x"})
    out = tmp_path / "out" / "backup.json"
    redacted = export_config(path, DEFAULTS, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert redacted == ["calendar_url"]
    assert data["calendar_url"] == ""
    assert data["position"] == "top" and data["theme"] == "midnight"
    assert "_display_id" not in data


def test_export_can_include_private_values_when_asked(tmp_path):
    path = tmp_path / "config.json"
    _write(path, {"calendar_url": "https://secret/ical"})
    out = tmp_path / "backup.json"
    assert export_config(path, DEFAULTS, out, include_sensitive=True) == []
    assert json.loads(out.read_text(encoding="utf-8"))[
        "calendar_url"] == "https://secret/ical"


def test_import_replaces_config_and_keeps_a_backup(tmp_path):
    path = tmp_path / "config.json"
    save(path, {"position": "bottom", "widgets": {"clock": True}})
    source = tmp_path / "incoming.json"
    _write(source, {"position": "top", "widgets": {"weather": False}})
    result = import_config(source, path, DEFAULTS)
    assert result["position"] == "top"
    assert result["widgets"] == {"clock": True, "weather": False}
    assert result["theme"] == "midnight"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["position"] == "top" and saved["schema_version"] == 1
    previous = json.loads((tmp_path / "config.before-import.bak")
                          .read_text(encoding="utf-8"))
    assert previous["position"] == "bottom"


def test_import_keeps_existing_private_value_when_import_is_blank(tmp_path):
    path = tmp_path / "config.json"
    save(path, {"calendar_url": "https://secret/ical", "widgets": {}})
    source = tmp_path / "incoming.json"
    _write(source, {"position": "top", "calendar_url": ""})
    assert import_config(source, path, DEFAULTS)[
        "calendar_url"] == "https://secret/ical"
    _write(source, {"calendar_url": "https://other/ical"})
    assert import_config(source, path, DEFAULTS)[
        "calendar_url"] == "https://other/ical"


def test_import_rejects_bad_files_without_touching_the_current_config(tmp_path):
    path = tmp_path / "config.json"
    save(path, {"position": "bottom", "widgets": {}})
    before = path.read_text(encoding="utf-8")
    cases = {"notjson.json": "{oops", "list.json": "[1, 2]",
             "widgets.json": json.dumps({"widgets": [1]}),
             "huge.json": "{" + " " * (3 * 1024 * 1024) + "}"}
    for name, text in cases.items():
        source = tmp_path / name
        source.write_text(text, encoding="utf-8")
        assert _raises_import_error(
            lambda: import_config(source, path, DEFAULTS)), name
    assert _raises_import_error(
        lambda: import_config(tmp_path / "missing.json", path, DEFAULTS))
    assert path.read_text(encoding="utf-8") == before
    assert not (tmp_path / "config.before-import.bak").exists()


def test_import_ignores_runtime_keys_and_unknown_schema_markers(tmp_path):
    path = tmp_path / "config.json"
    source = tmp_path / "incoming.json"
    _write(source, {"_display_id": "evil", "schema_version": 99,
                    "position": "top"})
    result = import_config(source, path, DEFAULTS)
    assert "_display_id" not in result
    assert result["schema_version"] == 1

