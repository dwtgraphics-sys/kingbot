# Kingbot - install OBS Studio (portable) for the live stream on a new server.
# Run once in PowerShell as Administrator:
#   powershell -ExecutionPolicy Bypass -File C:\RisBot\tools\install_obs.ps1
#
# What it does:
#   1. downloads the latest official OBS Studio Windows zip from github.com/obsproject/obs-studio/releases
#   2. unpacks it to C:\Users\Administrator\obs-studio (the path stream_bot.py starts) in portable mode
#   3. writes a scene "Kingbot" with a Window Capture of the game (Rise of Kingdoms, MASS.exe)
#   4. registers the OBS virtual camera (the Chrome sender on VDO.Ninja uses it as its webcam)
# Nothing is changed in the game or the bot. Run it again to update OBS.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"     # v294: the progress bar made Invoke-WebRequest crawl (20 min timeout)
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$dest = "C:\Users\Administrator\obs-studio"
$tmp = Join-Path $env:TEMP "obs_install"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

Write-Host "== Kingbot: OBS Studio for the live stream ==" -ForegroundColor Cyan
Get-Process obs64 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Looking up the latest OBS release ..."
$rel = Invoke-RestMethod "https://api.github.com/repos/obsproject/obs-studio/releases/latest" -Headers @{ "User-Agent" = "kingbot" }
$asset = $rel.assets | Where-Object { $_.name -match "Windows" -and $_.name -match "\.zip$" -and $_.name -notmatch "PDB|arm64" } | Select-Object -First 1
if (-not $asset) { throw "No Windows zip found in OBS release $($rel.tag_name)" }
$zip = Join-Path $tmp $asset.name
Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB)) MB) ..."
Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing

Write-Host "Unpacking to $dest ..."
$un = Join-Path $tmp "unz"
if (Test-Path $un) { Remove-Item $un -Recurse -Force }
Expand-Archive $zip -DestinationPath $un -Force
$root = Get-ChildItem $un -Recurse -Filter obs64.exe | Select-Object -First 1
if (-not $root) { throw "obs64.exe not found in the zip" }
$top = $root.Directory.Parent.Parent.FullName          # ...\bin\64bit\obs64.exe -> top folder
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $top "*") $dest -Recurse -Force
Set-Content (Join-Path $dest "portable_mode.txt") "" -Encoding ascii

# --- settings: one scene with a Window Capture of the game ------------------------------------
$cfg = Join-Path $dest "config\obs-studio"
New-Item -ItemType Directory -Force -Path (Join-Path $cfg "basic\scenes"), (Join-Path $cfg "basic\profiles\Kingbot") | Out-Null
$global = @"
[General]
FirstRun=true
[Basic]
Profile=Kingbot
ProfileDir=Kingbot
SceneCollection=Kingbot
SceneCollectionFile=Kingbot
"@
Set-Content (Join-Path $cfg "global.ini") $global -Encoding utf8
$profile = @"
[General]
Name=Kingbot
[Video]
BaseCX=946
BaseCY=532
OutputCX=946
OutputCY=532
FPSCommon=15
"@
Set-Content (Join-Path $cfg "basic\profiles\Kingbot\basic.ini") $profile -Encoding utf8
$scene = @{
  current_scene = "Kingbot"; current_program_scene = "Kingbot"; name = "Kingbot"
  scene_order = @(@{ name = "Kingbot" })
  sources = @(
    @{ id = "window_capture"; versioned_id = "window_capture"; name = "Game"; uuid = [guid]::NewGuid().ToString()
       settings = @{ window = "Rise of Kingdoms:UnityWndClass:MASS.exe"; method = 2; priority = 2; cursor = $false; client_area = $true } },
    @{ id = "scene"; versioned_id = "scene"; name = "Kingbot"; uuid = [guid]::NewGuid().ToString()
       settings = @{ id_counter = 1; items = @(@{ name = "Game"; id = 1; visible = $true; pos = @{ x = 0; y = 0 }; scale = @{ x = 1.0; y = 1.0 };
                                                  bounds_type = 2; bounds = @{ x = 946.0; y = 532.0 }; bounds_align = 0 }) } }
  )
}
$scene | ConvertTo-Json -Depth 10 | Set-Content (Join-Path $cfg "basic\scenes\Kingbot.json") -Encoding utf8

# --- virtual camera ------------------------------------------------------------------------------
# regsvr32 directly (virtualcam-install.bat ends with PAUSE and waited forever when run by the bot)
$dlls = Get-ChildItem $dest -Recurse -Include "obs-virtualcam-module64.dll", "obs-virtualcam-module32.dll" -ErrorAction SilentlyContinue
if ($dlls) {
  foreach ($d in $dlls) { $p = Start-Process regsvr32.exe -ArgumentList "/s `"$($d.FullName)`"" -PassThru; if (-not $p.WaitForExit(60000)) { $p.Kill() } }
  Write-Host "Virtual camera registered."
} else { Write-Host "! virtual camera module not found - start OBS once and press 'Start Virtual Camera'" -ForegroundColor Yellow }

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
$ok = Test-Path (Join-Path $dest "bin\64bit\obs64.exe")
if ($ok) {
  Write-Host "Done: OBS $($rel.tag_name) at $dest. The bot starts it by itself when the dashboard's live stream is watched." -ForegroundColor Green
} else { Write-Host "! obs64.exe is missing after the install" -ForegroundColor Red }
