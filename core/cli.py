"""Command-line settings backup/restore (pure Python, no Qt).

    python windowsbar.py --export-config my-settings.json [--include-private]
    python windowsbar.py --import-config my-settings.json
"""
import argparse
import sys

from core import config as config_store


def build_parser():
    parser = argparse.ArgumentParser(prog="windowsbar.py", add_help=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--export-config", metavar="FILE",
                       help="write your settings to FILE and exit")
    group.add_argument("--import-config", metavar="FILE",
                       help="replace your settings with FILE and exit")
    parser.add_argument("--include-private", action="store_true",
                        help="keep private values (calendar link) in an export")
    return parser


def run_config_command(argv, config_path, defaults, out=None, err=None):
    """Handle export/import flags.

    Returns an exit code (0 or 1) when a config command was given and has been
    handled, or ``None`` when the app should start normally. Unknown arguments
    (Qt's own) are left alone.
    """
    out, err = out or sys.stdout, err or sys.stderr
    args, _unknown = build_parser().parse_known_args(argv)
    if args.export_config:
        try:
            redacted = config_store.export_config(
                config_path, defaults, args.export_config,
                include_sensitive=args.include_private)
        except OSError as exc:
            print(f"Export failed: {exc}", file=err)
            return 1
        print(f"Settings exported to {args.export_config}", file=out)
        if redacted:
            print("Left blank (use --include-private to keep): "
                  + ", ".join(redacted), file=out)
        return 0
    if args.import_config:
        try:
            config_store.import_config(args.import_config, config_path,
                                       defaults)
        except config_store.ConfigImportError as exc:
            print(f"Import failed: {exc}", file=err)
            return 1
        print("Settings imported. The previous file was kept as "
              "config.before-import.bak.", file=out)
        return 0
    return None
