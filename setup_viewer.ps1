# Kingbot: create the "viewer" user and the self-connection to the game session.
# Run in PowerShell as Administrator.
$p = Read-Host "Choose a password for the new user 'viewer'" -AsSecureString
if (-not (Get-LocalUser -Name viewer -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name viewer -Password $p -PasswordNeverExpires -FullName "Kingbot viewer" | Out-Null
}
Add-LocalGroupMember -Group "Remote Desktop Users" -Member viewer -ErrorAction SilentlyContinue
Add-LocalGroupMember -Group "Users" -Member viewer -ErrorAction SilentlyContinue

# keep the game session drawing even if the inner window is minimized
foreach ($k in "HKLM:\Software\Microsoft\Terminal Server Client", "HKLM:\Software\Wow6432Node\Microsoft\Terminal Server Client") {
    New-Item $k -Force | Out-Null
    Set-ItemProperty $k -Name RemoteDesktop_SuppressWhenMinimized -Value 2 -Type DWord
}

# connection file on every user's desktop: opens the administrator (game) session at a fixed size
$rdp = @"
full address:s:127.0.0.2
username:s:administrator
screen mode id:i:1
desktopwidth:i:1600
desktopheight:i:900
smart sizing:i:1
session bpp:i:32
authentication level:i:0
negotiate security layer:i:1
redirectclipboard:i:1
autoreconnection enabled:i:1
"@
Set-Content -Path "C:\Users\Public\Desktop\Kingbot_session.rdp" -Value $rdp -Encoding ASCII
"Done. User 'viewer' is ready and Kingbot_session.rdp is on the desktop."
