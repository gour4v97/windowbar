"""Versioned, atomic JSON configuration storage for Windows Bar."""

import copy
import json
import os
import threading
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1
_SAVE_LOCK = threading.Lock()


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
