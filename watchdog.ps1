# Kingbot watchdog (v193) - run every 2 minutes by the scheduled task "Kingbot watchdog" (hidden).
#  1. The bot is not running            -> start it (hidden, start_bot_hidden.vbs).
#  2. The bot runs but is frozen        -> heartbeat.txt older than 5 minutes: kill it and start it again.
# The bot is found through kingbot.pid, not by "any pythonw.exe": stream_bot.py also runs with pythonw.
$ErrorActionPreference = 'SilentlyContinue'
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$logf = Join-Path $base 'launcher.log'
function Say($m) { Add-Content -Path $logf -Value ("[{0}] watchdog: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m) }
function Start-Bot { Start-Process -FilePath 'wscript.exe' -ArgumentList '//B', "`"$base\start_bot_hidden.vbs`"" -WindowStyle Hidden }

$pidFile = Join-Path $base 'kingbot.pid'
$hbFile  = Join-Path $base 'heartbeat.txt'
$botPid = 0
if (Test-Path $pidFile) { [int]::TryParse((Get-Content $pidFile -Raw).Trim(), [ref]$botPid) | Out-Null }
$proc = $null
if ($botPid -gt 0) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$botPid" |
            Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -like '*bot.py*' }
}
if (-not $proc) {
    # pid file missing/old: is a bot.py running anyway? (never stream_bot.py)
    $proc = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
            Where-Object { $_.CommandLine -match '\\bot\.py"?\s*$' } | Select-Object -First 1
}
if (-not $proc) {
    Say 'the bot is not running - starting it (hidden)'
    Start-Bot
    exit 0
}
# running: is it alive? heartbeat.txt is written every 15 s by the bot's watchdog thread (v193+).
# Older bots have no heartbeat: then kingbot.pid (touched every 30 s while waiting) with a 20-minute limit.
$started = ((Get-Date) - $proc.CreationDate).TotalSeconds
$age = -1; $limit = 300
if ((Test-Path $hbFile) -and (Get-Item $hbFile).LastWriteTime -gt $proc.CreationDate) {
    $age = ((Get-Date) - (Get-Item $hbFile).LastWriteTime).TotalSeconds
} elseif (Test-Path $pidFile) {
    $age = ((Get-Date) - (Get-Item $pidFile).LastWriteTime).TotalSeconds; $limit = 1200
}
if ($age -ge 0) {
    if ($age -gt $limit -and $started -gt 300) {
        Say ("the bot (pid {0}) is frozen: no heartbeat for {1:N0} s - restarting it" -f $proc.ProcessId, $age)
        Stop-Process -Id $proc.ProcessId -Force
        Start-Sleep -Seconds 3
        Start-Bot
    }
}
exit 0
