# The one-time setup, and safe to run again any time. Everything it does is
# written to setup.log as well as the screen, so a closed window loses
# nothing. Each step reports pass or fail and the run keeps going, because a
# failed push should never cost you the poll that came before it.

Set-Location (Join-Path $PSScriptRoot "..")
$log = Join-Path (Get-Location) "setup.log"
try { Start-Transcript -Path $log -Append | Out-Null } catch { }
$fail = @()

function Step($label) { Write-Host ""; Write-Host "== $label" }
function Ok($m) { Write-Host "   ok: $m" }
function Bad($label, $m) { Write-Host "   FAILED: $m"; $script:fail += "$label`: $m" }

# python, under either name Windows installs it as
$py = $null
foreach ($c in @("python", "py")) {
  try { & $c --version *> $null; if ($LASTEXITCODE -eq 0) { $py = $c; break } } catch { }
}

Step "Checking the basics"
if (-not (Test-Path ".git")) {
  Bad "repo" "this folder is not a clone of the jobhunt repo"
  Write-Host ""
  Write-Host "Nothing else can run. This script has to sit inside the cloned repo folder."
  try { Stop-Transcript | Out-Null } catch { }
  exit 1
}
Ok "this is the repo"
if (-not $py) {
  Bad "python" "python was not found on the PATH"
  Write-Host ""
  Write-Host "Install Python 3.12 or newer from python.org and tick 'Add python.exe to PATH', then run this again."
  try { Stop-Transcript | Out-Null } catch { }
  exit 1
}
Ok "python found as '$py'"

$name = (git config user.name) 2>$null
$email = (git config user.email) 2>$null
$identity = $name -and $email
if ($identity) {
  Ok "git knows you as $name <$email>"
} else {
  Bad "identity" "git has no name and email yet, so it cannot commit"
  Write-Host ""
  Write-Host "   Run these two lines in Git Bash, then run this setup again:"
  Write-Host "     git config --global user.name ""Your Name"""
  Write-Host "     git config --global user.email ""crypticnull@users.noreply.github.com"""
  Write-Host ""
  Write-Host "   Everything below still runs. Only the push at the end needs this."
}

Step "Getting the latest from GitHub"
# autoStash so a half-finished earlier run, which can leave the company list
# staged but uncommitted, never blocks the pull.
git -c rebase.autoStash=true pull --rebase origin main
if ($LASTEXITCODE -eq 0) { Ok "up to date" } else { Bad "pull" "git pull failed, see above" }

Step "Settings"
git config core.hooksPath .githooks
New-Item -ItemType Directory -Force -Path "data\local" | Out-Null
Ok "hooks and the private folder are in place"
if (Test-Path "data\local\scoring.local.json") {
  Ok "the comp band is configured"
} else {
  Write-Host "   NOTE: data\local\scoring.local.json is missing, so posted salaries will be flagged instead of scored."
  Write-Host "         Put that file there and run this again when you have it."
}

if (Test-Path "assets\companies.txt") {
  Step "Seeding the company list from assets\companies.txt"
  & $py -m scraper import "assets\companies.txt"
  if ($LASTEXITCODE -eq 0) { Ok "seeded" } else { Bad "import" "the import did not finish, see above" }
}

Step "Registering the nightly and Sunday tasks"
& powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\install-schedule.ps1"
if ($LASTEXITCODE -eq 0) { Ok "registered" } else { Bad "schedule" "the tasks were not registered, see above" }

Step "First poll, this can take a few minutes"
& $py -m scraper poll
if ($LASTEXITCODE -eq 0) { Ok "polled" } else { Bad "poll" "the poll did not finish, see above" }

Step "Pushing the company list"
if ($identity) {
  git add data/companies.json
  git diff --cached --quiet
  if ($LASTEXITCODE -eq 0) {
    Ok "nothing new to push"
  } else {
    git commit --quiet -m "companies: first poll"
    git push origin HEAD:main
    if ($LASTEXITCODE -eq 0) { Ok "pushed" } else { Bad "push" "the push was refused, the list is committed locally and will go up on the next nightly run" }
  }
} else {
  Write-Host "   skipped, git has no name and email yet"
}

Write-Host ""
if ($fail.Count -eq 0) {
  Write-Host "== Done, everything passed."
} else {
  Write-Host "== Done, with $($fail.Count) problem(s):"
  foreach ($f in $fail) { Write-Host "   - $f" }
  Write-Host ""
  Write-Host "   Paste the contents of setup.log into the chat and I will sort it out."
}
Write-Host ""
Write-Host "The digest lands in data\digests every Sunday morning and is pushed to GitHub."
Write-Host "Nothing else to run. The nightly task pulls updates and pushes the list on its own."
try { Stop-Transcript | Out-Null } catch { }
