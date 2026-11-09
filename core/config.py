"""Versioned, atomic JSON configuration storage for Windows Bar."""

import copy
import json
import os
import shutil
import threading
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1
MAX_IMPORT_BYTES = 2 * 1024 * 1024
# Keys that may hold private links or identifiers. They are blanked on export
# unless the caller explicitly asks to include them.
SENSITIVE_KEYS = ("calendar_url",)
_SAVE_LOCK = threading.Lock()


class ConfigImportError(ValueError):
    """The file given to ``import_config`` is not a usable config."""


def migrate(data):
    """Upgrade a config dictionary to the current schema in memory.

    Existing Windows Bar config files predate schema versioning. Version 0 is
    therefore the legacy shape; it retains all user values and receives only
    the current version marker.
    """
    if not isinstance(data, dict):
        return {}
    cfg = copy.deepcopy(data)
    version = cfg.get("schema_version", 0)
    try:
        version = int(version)
    except (TypeError, ValueError):
        version = 0
    if version < 1:
        cfg["schema_version"] = 1
        version = 1
    if version > CURRENT_SCHEMA_VERSION:
        # Preserve newer data rather than silently downgrading its marker.
        return cfg
    cfg["schema_version"] = CURRENT_SCHEMA_VERSION
    return cfg


def load(path, defaults):
    """Load config, migrate old data, and merge it over a fresh defaults map."""
    cfg = copy.deepcopy(defaults)
    schema_version = CURRENT_SCHEMA_VERSION
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        data = migrate(raw)
        if isinstance(data, dict):
            try:
                schema_version = max(
                    CURRENT_SCHEMA_VERSION, int(data.get("schema_version", 0)))
            except (TypeError, ValueError):
                schema_version = CURRENT_SCHEMA_VERSION
            for key, value in data.items():
                if key == "widgets" and isinstance(value, dict):
                    cfg["widgets"].update(value)
                elif key != "schema_version":
                    cfg[key] = value
    except (OSError, ValueError, TypeError):
        pass
    cfg["schema_version"] = schema_version
    return cfg


def save(path, cfg):
    """Write config atomically; callers may safely invoke from worker threads."""
    target = Path(path)
    with _SAVE_LOCK:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            _backup_before_migration(target)
            payload = copy.deepcopy(cfg)
            try:
                version = max(CURRENT_SCHEMA_VERSION,
                              int(payload.get("schema_version", 0)))
            except (TypeError, ValueError):
                version = CURRENT_SCHEMA_VERSION
            payload["schema_version"] = version
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(temporary, target)
        except (OSError, TypeError, ValueError):
            pass


def _on_disk_version(path):
    """Schema version stored in ``path`` (0 for legacy), or ``None``."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return int(raw.get("schema_version", 0))
    except (TypeError, ValueError):
        return 0


def _backup_before_migration(target):
    """Keep a one-time copy of an older-schema file before it is rewritten.

    The copy is named ``config.pre-v<N>.bak`` (N = the version being left)
    and is never overwritten, so the original pre-migration file survives.
    """
    version = _on_disk_version(target)
    if version is None or version >= CURRENT_SCHEMA_VERSION:
        return None
    backup = target.with_name(f"{target.stem}.pre-v{version}.bak")
    if backup.exists():
        return backup
    try:
        shutil.copy2(target, backup)
    except OSError:
        return None
    return backup


def export_config(path, defaults, destination, include_sensitive=False):
    """Write the effective config (defaults merged in) to ``destination``.

    Returns the list of sensitive keys that were blanked. Display-specific
    runtime keys (those starting with ``_``) are never exported.
    """
    cfg = load(path, defaults)
    cfg = {key: value for key, value in cfg.items() if not key.startswith("_")}
    redacted = []
    if not include_sensitive:
        for key in SENSITIVE_KEYS:
            if cfg.get(key):
                cfg[key] = ""
                redacted.append(key)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(temporary, destination)
    return redacted


def import_config(source, path, defaults):
    """Replace the config at ``path`` with the one in ``source``.

    The file is validated first; invalid input raises ``ConfigImportError``
    and leaves the current config untouched. The previous config is kept as
    ``<name>.before-import.bak``. Blank sensitive values in the import keep
    whatever the current config has, so an exported file does not wipe a
    private calendar link. Returns the resulting config.
    """
    source, target = Path(source), Path(path)
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise ConfigImportError(f"Cannot read {source}: {exc}") from exc
    if size > MAX_IMPORT_BYTES:
        raise ConfigImportError("Config file is too large to be valid.")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigImportError(f"Not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigImportError("Config must be a JSON object.")
    if raw.get("widgets") is not None and not isinstance(raw["widgets"], dict):
        raise ConfigImportError('"widgets" must be an object.')

    current = load(target, defaults)
    imported = migrate(raw)
    merged = copy.deepcopy(defaults)
    for key, value in imported.items():
        if key == "widgets" and isinstance(value, dict):
            merged["widgets"].update(value)
        elif key != "schema_version" and not key.startswith("_"):
            merged[key] = value
    for key in SENSITIVE_KEYS:
        if not merged.get(key) and current.get(key):
            merged[key] = current[key]
    merged["schema_version"] = CURRENT_SCHEMA_VERSION

    if target.exists():
        try:
            shutil.copy2(target, target.with_name(
                f"{target.stem}.before-import.bak"))
        except OSError as exc:
            raise ConfigImportError(
                f"Could not back up the current config: {exc}") from exc
    save(target, merged)
    return merged

