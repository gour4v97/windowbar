"""Pure parsing helpers for safe Windows hotkey specifications."""

MODIFIERS = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004}
MODIFIER_ORDER = ("ctrl", "alt", "shift")
KEYS = {
    "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "enter": 0x0D,
    "return": 0x0D, "space": 0x20, "pause": 0x13, "insert": 0x2D,
    "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21,
    "pgup": 0x21, "pagedown": 0x22, "pgdn": 0x22, "left": 0x25,
    "up": 0x26, "right": 0x27, "down": 0x28,
}
RESERVED = {
    (0x0003, ord(key.upper())) for key in "jkfhlt"
} | {
    (0x0007, 0x25), (0x0007, 0x27),
}


def parse_hotkey_spec(spec):
    """Parse a chord such as ``ctrl+alt+esc`` into a Win32 binding.

    Safe-release bindings require Ctrl plus at least one additional modifier.
    Windows-key chords, system-reserved chords, and Windows Bar's own tiling
    shortcuts are rejected so the release key cannot shadow another action.
    """
    aliases = {"control": "ctrl", "ctl": "ctrl", "windows": "win",
               "super": "win"}
    parts = [part.strip().lower() for part in str(spec or "").split("+")]
    if len(parts) < 2 or any(not part for part in parts):
        raise ValueError("Use a chord such as ctrl+alt+esc.")
    parts = [aliases.get(part, part) for part in parts]
    modifiers = [part for part in parts if part in (*MODIFIERS, "win")]
    keys = [part for part in parts if part not in (*MODIFIERS, "win")]
    if len(set(modifiers)) != len(modifiers):
        raise ValueError("Each modifier may appear only once.")
    if len(keys) != 1:
        raise ValueError("Choose exactly one non-modifier key.")
    if "win" in modifiers:
        raise ValueError("Windows-key shortcuts are reserved by Windows.")
    if "ctrl" not in modifiers or len(modifiers) < 2:
        raise ValueError("Use Ctrl plus at least one other modifier.")

    key = keys[0]
    if key in KEYS:
        vk = KEYS[key]
    elif len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif len(key) in (2, 3) and key[0] == "f" and key[1:].isdigit():
        number = int(key[1:])
        if not 1 <= number <= 24:
            raise ValueError("Function key must be F1 through F24.")
        vk = 0x70 + number - 1
    else:
        raise ValueError(f"Unsupported key: {key}.")

    modifier_flags = sum(MODIFIERS[name] for name in modifiers)
    if (modifier_flags, vk) in {(0x0003, 0x2E), (0x0006, 0x1B),
                                (0x0001, 0x73)}:
        raise ValueError("That shortcut is reserved by Windows.")
    if (modifier_flags, vk) in RESERVED:
        raise ValueError("That shortcut is already used by Windows Bar tiling.")

    canonical = "+".join(
        [name for name in MODIFIER_ORDER if name in modifiers]
        + ["esc" if vk == 0x1B else key])
    return {"spec": canonical, "modifiers": modifier_flags, "vk": vk}

