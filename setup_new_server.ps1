# Kingbot - prepare a NEW Windows server (run once, PowerShell as Administrator)
#
#   powershell -ExecutionPolicy Bypass -File setup_new_server.ps1
#
# 1. installs Python 3.12 (winget) and the packages the bot needs
# 2. downloads the bot from GitHub into C:\RisBot (asks for the GitHub token - it is NOT shown or logged)
# 3. writes local_config.json with the SERVER_ID you choose (must exist in kingbot-syn/servers/index.json)
# 4. imports kingbot_state_*.zip / kingbot_secrets_*.kbe if you put them next to this script (migrate.py)
# 5. registers the Kingbot + watchdog tasks (install_tasks.bat)
# Then: install Rise of Kingdoms, sign in once by hand, and start 3_start_bot.bat.

$ErrorActionPreference = "Stop"
$Dir = "C:\RisBot"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "== Kingbot new server setup ==" -ForegroundColor Cyan

# --- 1. Python --------------------------------------------------------------
$py = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Host "Installing Python 3.12 ..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --scope machine
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + $env:Path
}
py -3 -m pip install --upgrade pip
py -3 -m pip install opencv-python numpy pyautogui pillow cryptography

# --- 2. the bot from GitHub ------------------------------------------------
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$tokFile = Join-Path $Dir "github_token.txt"
if (-not (Test-Path $tokFile)) {
    $sec = Read-Host "GitHub token (fine-grained, read access to dwtgraphics-sys/kingbot + read/write kingbot-syn)" -AsSecureString
    $tok = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    Set-Content -Path $tokFile -Value $tok -NoNewline -Encoding ascii
} else { $tok = (Get-Content $tokFile -Raw).Trim() }
$zip = Join-Path $env:TEMP "kingbot_main.zip"
Write-Host "Downloading the bot ..."
Invoke-WebRequest -Uri "https://api.github.com/repos/dwtgraphics-sys/kingbot/zipball/main" -Headers @{ Authorization = "Bearer $tok"; "User-Agent" = "Kingbot-setup" } -OutFile $zip
$tmp = Join-Path $env:TEMP "kingbot_unzip"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Expand-Archive -Path $zip -DestinationPath $tmp
$src = Get-ChildItem $tmp | Select-Object -First 1
Copy-Item -Path (Join-Path $src.FullName "*") -Destination $Dir -Recurse -Force
Remove-Item -Recurse -Force $tmp, $zip

# --- 3. server id ----------------------------------------------------------
$cfg = Join-Path $Dir "local_config.json"
if (-not (Test-Path $cfg)) {
    $sid = Read-Host "SERVER_ID for this server (e.g. vps-04-acc2 - add it to kingbot-syn/servers/index.json from the dashboard)"
    @{ SERVER_ID = $sid } | ConvertTo-Json | Set-Content -Path $cfg -Encoding utf8
}

# --- 4. state / secrets from the old server --------------------------------
$state = Get-ChildItem -Path $Here -Filter "kingbot_state_*.zip" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
$sk = Get-ChildItem -Path $Here -Filter "kingbot_secrets_*.kbe" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
if ($state) {
    $fresh = Read-Host "Is this the SAME game account as the old server? (y = keep its state, n = new account, start clean)"
    $margs = @("migrate.py", "import", $state.FullName)
    if ($sk) { $margs += $sk.FullName }
    if ($fresh -ne "y") { $margs += "--fresh" }
    Push-Location $Dir; py -3 @margs; Pop-Location
} else {
    Push-Location $Dir; py -3 migrate.py check; Pop-Location
}

# --- 5. tasks --------------------------------------------------------------
Push-Location $Dir
cmd /c install_tasks.bat
Pop-Location
Write-Host ""
Write-Host "Done. Next: install Rise of Kingdoms, sign in once, then run C:\RisBot\3_start_bot.bat" -ForegroundColor Green
Write-Host "Optional: Telegram alerts -> put telegram.txt, KB_PASSPHRASE / DISCORD_WEBHOOK in local_config.json"
