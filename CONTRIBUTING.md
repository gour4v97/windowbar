# Contributing to Windows Bar

Thanks for helping improve Windows Bar. Keep changes local-first, respect the MIT license, and do not copy code, styles, names, or assets from projects whose licenses do not permit it.

## Set up a development environment

2. Create and activate a virtual environment.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Run `python windowsbar.py` to launch the app. Use a separate Windows account or VM for changes that affect taskbar state, global hooks, or window placement.


## Make a change

- Keep UI work on the Qt thread. Put Win32 integration in `native/` and background work in a worker or service.
- For widgets, follow [`docs/widget-sdk.md`](docs/widget-sdk.md) and the copyable [`docs/widget-template/`](docs/widget-template/) scaffold.
- Preserve crash-safe restoration for taskbar, hooks, and window geometry.
- Do not include credentials, personal paths, machine-specific logs, or generated runtime folders in commits.

## Check your work

The CI workflow runs the repository's Python checks on Windows. For UI or native changes, also describe which Windows version and interaction path you exercised; automated checks cannot prove behavior of desktop hooks, COM, or window stacking.

## Submit a contribution

Use a short branch and a focused commit, for example `feat(wm): add layout preset`. In the PR description, include:

- What changed and why.
- How it was checked, including any manual Windows steps.
- Screenshots or a short recording for visible UI changes, with personal data hidden.
- Any roadmap item that remains partial and the reason.

