"""Runtime widget plugin loader and registry integration (no Qt, no Windows)."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import plugins
from core.registry import WidgetRegistry

GOOD = '''
WIDGET_ID = "hello_plugin"
WIDGET_LABEL = "Hello"
WIDGET_DEFAULT = True
WIDGET_ORDER = 5
def make_card(context):
    return ("card", context)
'''


def _write(folder, name, source):
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def teardown_function(_function):
    plugins.unload_plugins()


def test_missing_folder_loads_nothing(tmp_path):
    modules, errors = plugins.load_plugins(tmp_path / "nope")
    assert modules == [] and errors == []


def test_valid_file_and_package_plugins_load(tmp_path):
    _write(tmp_path, "hello.py", GOOD)
    _write(tmp_path, "pkg/__init__.py",
           GOOD.replace("hello_plugin", "pkg_plugin"))
    modules, errors = plugins.load_plugins(tmp_path)
    assert errors == []
    assert sorted(m.WIDGET_ID for m in modules) == ["hello_plugin", "pkg_plugin"]
    assert plugins.loaded_modules() == modules


def test_hidden_and_non_python_entries_are_ignored(tmp_path):
    _write(tmp_path, "_private.py", GOOD)
    _write(tmp_path, ".hidden.py", GOOD)
    _write(tmp_path, "notes.txt", GOOD)
    _write(tmp_path, "emptydir/readme.md", "x")
    assert plugins.load_plugins(tmp_path) == ([], [])


def test_broken_plugins_are_reported_not_raised(tmp_path):
    _write(tmp_path, "a_syntax.py", "def broken(:\n")
    _write(tmp_path, "b_raises.py", "raise RuntimeError('boom')\n")
    _write(tmp_path, "c_exits.py", "import sys\nsys.exit(3)\n")
    _write(tmp_path, "d_noid.py", "def make_card(context): pass\n")
    _write(tmp_path, "e_nocard.py", 'WIDGET_ID = "no_card"\n')
    _write(tmp_path, "f_badid.py",
           'WIDGET_ID = "Bad-Id"\ndef make_card(c): pass\n')
    _write(tmp_path, "g_api.py",
           'WIDGET_ID = "future"\nPLUGIN_API = 99\ndef make_card(c): pass\n')
    _write(tmp_path, "h_ok.py", GOOD)
    modules, errors = plugins.load_plugins(tmp_path)
    assert [m.WIDGET_ID for m in modules] == ["hello_plugin"]
    assert sorted(e.name for e in errors) == [
        "a_syntax", "b_raises", "c_exits", "d_noid", "e_nocard", "f_badid",
        "g_api"]
    assert all(e.reason for e in errors)


def test_ids_cannot_reuse_built_in_or_earlier_plugin_ids(tmp_path):
    _write(tmp_path, "a.py", GOOD)
    _write(tmp_path, "b.py", GOOD)                       # duplicate of a
    _write(tmp_path, "c.py", GOOD.replace("hello_plugin", "clock"))
    modules, errors = plugins.load_plugins(tmp_path, reserved_ids={"clock"})
    assert [m.WIDGET_ID for m in modules] == ["hello_plugin"]
    assert sorted(e.name for e in errors) == ["b", "c"]
    assert all("already used" in e.reason for e in errors)


def test_reloading_replaces_previous_results(tmp_path):
    _write(tmp_path, "a.py", GOOD)
    plugins.load_plugins(tmp_path)
    (tmp_path / "a.py").unlink()
    assert plugins.load_plugins(tmp_path) == ([], [])
    assert plugins.loaded_modules() == [] and plugins.load_errors() == []


def test_apply_plugins_adds_defaults_and_labels_without_overriding():
    defaults, labels = {"clock": True}, {"clock": "Clock"}
    fancy = SimpleNamespace(WIDGET_ID="fancy_one", WIDGET_LABEL="Fancy",
                            WIDGET_DEFAULT=True)
    plain = SimpleNamespace(WIDGET_ID="plain_one")
    taken = SimpleNamespace(WIDGET_ID="clock", WIDGET_LABEL="Hijack")
    plugins.apply_plugins([fancy, plain, taken], defaults, labels)
    assert defaults == {"clock": True, "fancy_one": True, "plain_one": False}
    assert labels == {"clock": "Clock", "fancy_one": "Fancy",
                      "plain_one": "Plain One"}


def test_registry_registers_plugin_modules_and_runs_their_lifecycle(tmp_path):
    started = []

    class Card:
        def start(self):
            started.append("start")

        def stop(self):
            started.append("stop")

    _write(tmp_path, "life.py", '''
WIDGET_ID = "life_cycle"
def make_card(context):
    return context["factory"]()
''')
    modules, _ = plugins.load_plugins(tmp_path)
    defaults, labels = {"life_cycle": True}, {"life_cycle": "Life"}
    registry = WidgetRegistry()
    registry.register_modules(modules, {"factory": Card}, defaults, labels)
    assert list(registry.definitions) == ["life_cycle"]
    active = registry.start_enabled({"widgets": {"life_cycle": True}})
    assert list(active) == ["life_cycle"] and started == ["start"]
    registry.start_enabled({"widgets": {"life_cycle": False}})
    assert started == ["start", "stop"]


def test_registry_keeps_first_registration_for_duplicate_ids():
    first = SimpleNamespace(WIDGET_ID="same", make_card=lambda c: "first")
    second = SimpleNamespace(WIDGET_ID="same", make_card=lambda c: "second")
    registry = WidgetRegistry()
    registry.register_modules([first, second], None, {"same": True}, {})
    assert registry.definitions["same"].factory().card() == "first"


# CLI: --export-config / --import-config
def test_cli_export_then_import_round_trip(tmp_path):
    import io
    import json
    from core.cli import run_config_command

    defaults = {"theme": "midnight", "calendar_url": "",
                "widgets": {"clock": True}}
    config = tmp_path / "config.json"
    config.write_text(json.dumps(
        {"theme": "nord", "calendar_url": "https://private.example/cal"}),
        encoding="utf-8")
    dest = tmp_path / "out.json"
    out, err = io.StringIO(), io.StringIO()
    assert run_config_command(["--export-config", str(dest)], config,
                              defaults, out, err) == 0
    exported = json.loads(dest.read_text(encoding="utf-8"))
    assert exported["theme"] == "nord" and exported["calendar_url"] == ""
    assert "calendar_url" in out.getvalue()

    config.write_text("{}", encoding="utf-8")
    assert run_config_command(["--import-config", str(dest)], config,
                              defaults, out, err) == 0
    assert json.loads(config.read_text(encoding="utf-8"))["theme"] == "nord"
    assert (tmp_path / "config.before-import.bak").exists()


def test_cli_include_private_and_failures_and_normal_start(tmp_path):
    import io
    import json
    from core.cli import run_config_command

    defaults = {"calendar_url": "", "widgets": {}}
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"calendar_url": "https://x.example/c"}),
                      encoding="utf-8")
    dest = tmp_path / "private.json"
    assert run_config_command(["--export-config", str(dest),
                               "--include-private"], config, defaults,
                              io.StringIO(), io.StringIO()) == 0
    assert json.loads(dest.read_text(encoding="utf-8"))["calendar_url"] \
        == "https://x.example/c"

    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    err = io.StringIO()
    assert run_config_command(["--import-config", str(bad)], config,
                              defaults, io.StringIO(), err) == 1
    assert "Import failed" in err.getvalue()
    # No config flag (or only Qt's own arguments): start the app normally.
    assert run_config_command([], config, defaults) is None
    assert run_config_command(["-platform", "windows"], config,
                              defaults) is None


def test_plugin_context_exposes_stable_members_and_warns_on_internals():
    import logging
    dock = SimpleNamespace(cfg={"theme": "nord", "apps": {"a": "b"}},
                           tokens={"accent": "#fff"}, secret_method=lambda: 7)
    ctx = plugins.PluginContext(dock, app_dir="C:/x")
    assert ctx.get_config("theme") == "nord"
    assert ctx.get_config("missing", 5) == 5
    ctx.get_config("apps")["a"] = "mutated"          # a copy: no effect
    assert dock.cfg["apps"] == {"a": "b"}
    ctx.tokens["accent"] = "#000"
    assert dock.tokens["accent"] == "#fff" and ctx.app_dir == "C:/x"

    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logging.getLogger("windowsbar.plugins").addHandler(handler)
    try:
        assert ctx.secret_method() == 7 and ctx.secret_method() == 7
    finally:
        logging.getLogger("windowsbar.plugins").removeHandler(handler)
    assert len(records) == 1                          # warned once only
    try:
        ctx.__missing__
    except AttributeError:
        pass
    else:
        raise AssertionError("dunder lookups must not be forwarded")
