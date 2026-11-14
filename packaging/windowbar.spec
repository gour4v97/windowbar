# EXPERIMENTAL PyInstaller spec for Windows Bar.  Build on Windows with:
#   pip install -r requirements.txt pyinstaller
#   pyinstaller packaging/windowbar.spec --noconfirm
# The widget registry discovers modules with pkgutil, which PyInstaller cannot
# see, so every submodule is listed explicitly. Test the result on a clean
# Windows account before shipping it; the supported install path is setup.bat.
from PyInstaller.utils.hooks import collect_submodules

hidden = []
for package in ("widgets", "core", "native", "ui", "wm"):
    hidden += collect_submodules(package)
hidden += ["services", "extras", "winapi", "theme", "search", "launcher"]

a = Analysis(
    ["../windowsbar.py"],
    pathex=[".."],
    datas=[("../themes", "themes"), ("../locales", "locales")],
    hiddenimports=hidden,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Windows Bar",
          console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Windows Bar")
