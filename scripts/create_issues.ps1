# Create the roadmap's outstanding GitHub Issues (needs the GitHub CLI: `gh auth login`).
# Usage: .\scripts\create_issues.ps1 [-DryRun]
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$issues = @(
  @("Verify Settings > General on Windows", "Language picker, plugin switch, export/import dialogs."),
  @("Verify custom Alt+Tab hook and latency", "Phase 4: real key navigation and response time."),
  @("Verify desktop-layer widgets stacking", "Phase 4: draggable clock/system panel stays on the desktop layer."),
  @("Verify per-desktop wallpaper and pyvda COM access", "Phase 4: Windows 11 builds; graceful message on Windows 10."),
  @("Verify tiling hotkeys and safe release", "Phase 5: RegisterHotKey, Ctrl+Alt+Esc release, per-desktop persistence."),
  @("Test runtime plugins end to end", "Use plugins-example/hello_plugin.py in %APPDATA%\Windows Bar\plugins."),
  @("Route remaining UI through tr()", "Dock menus, popups, launcher and widget cards; then run extract_strings.py --write."),
  @("Ship a reviewed non-English locale", "Needs a native-speaker review before it is advertised."),
  @("Stabilise the plugin API", "Small public context object instead of Dock; plan PLUGIN_API 2; consider an allow-list."),
  @("Installer: Inno Setup or MSIX, signing, winget", "Replace the experimental PyInstaller zip with a proper installer."),
  @("README screenshots and demo GIF", "Release-ready visuals."),
  @("Qt UI tests with pytest-qt (offscreen)", "Cover Dock and Settings; add a Linux CI job."),
  @("Keyboard paths for remaining controls", "Phase 3 keyboard-first goal.")
)
gh label create roadmap --description "Windows Bar roadmap" --color "0e8a16" --force 2>$null
foreach ($i in $issues) {
  if ($DryRun) { Write-Host "would create: $($i[0])" }
  else { gh issue create --title $i[0] --body $i[1] --label "roadmap" }
}
