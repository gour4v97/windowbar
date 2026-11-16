# Commit everything and push the current branch.
# Usage: .\scripts\checkpoint.ps1 "feat: short description"
param([string]$Message = "wip: checkpoint")
$ErrorActionPreference = "Stop"

git rev-parse --is-inside-work-tree 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Run this inside the Windows Bar repository." }

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$staged = git status --porcelain
if ($staged -match "(?i)(\.env|secret|apikey|stripe.*key)") {
    throw "A file that looks like a secret is about to be committed. Check git status."
}

git add -A
if (git status --porcelain) { git commit -m $Message }
else { Write-Host "Nothing new to commit." }
git push -u origin $branch
Write-Host "Pushed branch '$branch'."
