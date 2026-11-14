# winget manifest (template)

Winget needs a stable installer URL and its SHA-256, so fill these in only after
a signed or at least publicly downloadable `WindowsBar-Setup-<version>.exe`
exists on a GitHub Release.

1. Copy the three `*.yaml` files, replace every `<...>` value.
2. `winget validate --manifest <folder>`
3. `winget install --manifest <folder>` on a clean machine.
4. Submit a pull request to https://github.com/microsoft/winget-pkgs
   (or use `wingetcreate`).
