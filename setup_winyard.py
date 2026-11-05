#!/usr/bin/env python3
"""
Winyard setup tool
==================
Installs Winyard (the PySide6 smart dock) for the current Windows user.

Run it from the repo folder (next to winyard.py), or on its own - if the app files
are missing it downloads them from GitHub:

    python setup_winyard.py              install / update
    python setup_winyard.py --uninstall  remove it
    python setup_winyard.py --help       all options

What install does:
  1. Copies the app files to %LOCALAPPDATA%\\Winyard
  2. Creates a private virtual environment there and installs requirements.txt
     (plus `winsdk` for the Now Playing widget, if it isn't already listed)
  3. Adds Start Menu (and optionally Desktop / Startup) shortcuts that launch the
     dock without a console window
  4. Optionally stores your Stripe key in the WINYARD_STRIPE_KEY user variable
  5. Optionally launches the dock

Your settings (%APPDATA%\\Winyard\\config.json) are never touched, except with
`--uninstall --purge`.
"""
import argparse
import getpass
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

APP_NAME = "Winyard"
SHORTCUT_NAME = "Winyard.lnk"
STRIPE_VAR = "WINYARD_STRIPE_KEY"

CORE_FILES = ["winyard.py", "services.py", "extras.py", "winapi.py", "requirements.txt"]
EXTRA_FILES = ["LICENSE", "README.md"]

LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
ROAMING = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
INSTALL_DIR = LOCAL / APP_NAME
CONFIG_DIR = ROAMING / APP_NAME
VENV_DIR = INSTALL_DIR / "venv"
SRC_DIR = Path(__file__).resolve().parent
REPO_ZIP = "https://github.com/gour4v97/windowbar/archive/refs/heads/main.zip"


def fetch_source():
    """Download the app from GitHub when the app files aren't next to this script."""
    say("    app files not found next to setup - downloading from GitHub...")
    tmp = Path(tempfile.mkdtemp(prefix="winyard_src_"))
    try:
        archive = tmp / "repo.zip"
        urllib.request.urlretrieve(REPO_ZIP, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
    except Exception as exc:  # network, DNS, proxy, bad zip
        fail(f"Download failed ({exc}).\n    Check your internet connection, or place the repo files "
             "next to this script and run again.")
    for sub in tmp.iterdir():
        if sub.is_dir() and (sub / "winyard.py").exists():
            return sub
    fail("Downloaded archive did not contain winyard.py.")


# --------------------------------------------------------------------------- helpers
def say(msg=""):
    print(msg, flush=True)


def fail(msg, code=1):
    say(f"\n[x] {msg}")
    sys.exit(code)


def confirm(question, default, assume_yes):
    if assume_yes:
        return default
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        ans = input(f"{question} {suffix} ").strip().lower()
    except EOFError:
        return default
    return default if not ans else ans.startswith("y")


def q(text):
    """Quote a string for a PowerShell single-quoted literal."""
    return "'" + str(text).replace("'", "''") + "'"


def powershell(script):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True,
    )


def special_folder(kind):
    """kind: 'Desktop', 'Programs' (Start Menu) or 'Startup'. Handles OneDrive redirection."""
    res = powershell(f"[Environment]::GetFolderPath({q(kind)})")
    path = res.stdout.strip()
    return Path(path) if path else None


def make_shortcut(kind, target, arguments, workdir):
    script = (
        f"$d = [Environment]::GetFolderPath({q(kind)}); "
        f"$sh = New-Object -ComObject WScript.Shell; "
        f"$l = $sh.CreateShortcut((Join-Path $d {q(SHORTCUT_NAME)})); "
        f"$l.TargetPath = {q(target)}; $l.Arguments = {q(arguments)}; "
        f"$l.WorkingDirectory = {q(workdir)}; $l.Description = 'Winyard smart dock'; "
        f"$l.Save()"
    )
    res = powershell(script)
    if res.returncode != 0:
        say(f"    (could not create {kind} shortcut: {res.stderr.strip()})")
        return False
    return True


def remove_shortcut(kind):
    folder = special_folder(kind)
    if not folder:
        return
    lnk = folder / SHORTCUT_NAME
    if lnk.exists():
        lnk.unlink()
        say(f"    removed {kind} shortcut")


def check_environment():
    if os.name != "nt":
        fail("Winyard is a Windows app. Run this setup on Windows 10/11.")
    if sys.version_info < (3, 9):
        fail(f"Python 3.9+ is required (you have {sys.version.split()[0]}). "
             "Get it from https://www.python.org/downloads/")


# --------------------------------------------------------------------------- install
def install(args):
    check_environment()
    say(f"== {APP_NAME} setup ==")

    global SRC_DIR
    if any(not (SRC_DIR / f).exists() for f in CORE_FILES):
        SRC_DIR = fetch_source()

    # 1. copy files
    say(f"\n[1/5] Copying files to {INSTALL_DIR}")
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        for name in CORE_FILES + EXTRA_FILES:
            src = SRC_DIR / name
            if src.exists():
                shutil.copy2(src, INSTALL_DIR / name)
    except PermissionError:
        fail("Could not overwrite files - Winyard is probably running.\n"
             "    Right-click the dock, quit it, and run setup again.")

    # 2. venv + dependencies
    say("\n[2/5] Creating virtual environment and installing dependencies (this can take a minute)")
    venv_python = VENV_DIR / "Scripts" / "python.exe"
    venv_pythonw = VENV_DIR / "Scripts" / "pythonw.exe"
    try:
        if not venv_python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "-q"],
                       check=False)
        subprocess.run([str(venv_python), "-m", "pip", "install", "-r",
                        str(INSTALL_DIR / "requirements.txt")], check=True)
    except subprocess.CalledProcessError as exc:
        fail(f"Dependency install failed ({exc}). Check your internet connection and try again.")

    reqs = (INSTALL_DIR / "requirements.txt").read_text(encoding="utf-8", errors="ignore").lower()
    if "winsdk" not in reqs:
        say("    installing winsdk (Now Playing widget)")
        res = subprocess.run([str(venv_python), "-m", "pip", "install", "winsdk", "-q"])
        if res.returncode != 0:
            say("    (winsdk failed to install - everything else will still work, "
                "but the Now Playing widget won't)")

    # 3. shortcuts
    say("\n[3/5] Creating shortcuts")
    script = str(INSTALL_DIR / "winyard.py")
    launch_args = f'"{script}"'
    if make_shortcut("Programs", str(venv_pythonw), launch_args, str(INSTALL_DIR)):
        say("    Start Menu: Winyard")
    if confirm("Add a Desktop shortcut?", not args.no_desktop, args.yes) and not args.no_desktop:
        if make_shortcut("Desktop", str(venv_pythonw), launch_args, str(INSTALL_DIR)):
            say("    Desktop: Winyard")
    if args.autostart or confirm(
            "Start Winyard when Windows starts? (skip this if you already enabled\n"
            "    'Start with Windows' inside the dock's own menu)", False, args.yes):
        if make_shortcut("Startup", str(venv_pythonw), launch_args, str(INSTALL_DIR)):
            say("    Startup folder: Winyard")

    # 4. Stripe key
    say("\n[4/5] Optional: Stripe revenue widget")
    env = os.environ.copy()
    if not args.yes and confirm("Set your Stripe key now? (use a restricted read-only key)",
                                False, False):
        key = getpass.getpass("    Paste key (input hidden): ").strip()
        if key:
            res = subprocess.run(["setx", STRIPE_VAR, key], capture_output=True, text=True)
            if res.returncode == 0:
                env[STRIPE_VAR] = key
                say(f"    saved to your user environment as {STRIPE_VAR}")
            else:
                say(f"    (setx failed: {res.stderr.strip()})")
    else:
        say(f"    skipped - set it later with:  setx {STRIPE_VAR} \"your_key\"")

    # 5. launch
    say("\n[5/5] Done.")
    say(f"    Installed to: {INSTALL_DIR}")
    say(f"    Settings:     {CONFIG_DIR / 'config.json'} (created on first run)")
    say("    Right-click the dock to choose widgets, position and options.")
    if not args.no_launch and confirm("\nLaunch Winyard now?", True, args.yes):
        subprocess.Popen([str(venv_pythonw), script], cwd=str(INSTALL_DIR), env=env,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED | NEW_PROCESS_GROUP
        say("    launched.")


# --------------------------------------------------------------------------- uninstall
def uninstall(args):
    check_environment()
    say(f"== {APP_NAME} uninstall ==")
    say("Quit the dock first (right-click it > Quit) so the taskbar state is restored "
        "and files aren't locked.")
    if not confirm("Continue?", True, args.yes):
        return

    for kind in ("Programs", "Desktop", "Startup"):
        remove_shortcut(kind)

    if INSTALL_DIR.exists():
        try:
            shutil.rmtree(INSTALL_DIR)
            say(f"    removed {INSTALL_DIR}")
        except PermissionError:
            fail("Some files are in use - Winyard is still running. Quit it and try again.")

    if args.purge:
        if CONFIG_DIR.exists():
            shutil.rmtree(CONFIG_DIR, ignore_errors=True)
            say(f"    removed settings in {CONFIG_DIR}")
        subprocess.run(["reg", "delete", r"HKCU\Environment", "/v", STRIPE_VAR, "/f"],
                       capture_output=True)
        say(f"    cleared {STRIPE_VAR} (if it was set)")
    else:
        say(f"    kept your settings in {CONFIG_DIR} (use --purge to delete them)")

    say("\nIf you turned on 'Start with Windows' inside the dock's menu, that Run entry is "
        "removed by turning it off in the dock before quitting.")
    say("Uninstall complete.")


# --------------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="Install or remove the Winyard dock for this user.")
    p.add_argument("--uninstall", action="store_true", help="remove Winyard")
    p.add_argument("--purge", action="store_true",
                   help="with --uninstall: also delete settings and the Stripe variable")
    p.add_argument("--yes", "-y", action="store_true",
                   help="no prompts: accept defaults (Desktop shortcut + launch, no Stripe, no autostart)")
    p.add_argument("--no-desktop", action="store_true", help="skip the Desktop shortcut")
    p.add_argument("--autostart", action="store_true", help="add a Startup-folder shortcut")
    p.add_argument("--no-launch", action="store_true", help="don't launch when finished")
    args = p.parse_args()

    if args.uninstall:
        uninstall(args)
    else:
        install(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\nCancelled.")
        sys.exit(130)
