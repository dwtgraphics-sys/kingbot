' Kingbot - hidden start
'
' Runs bot.py with pythonw.exe so the bot has NO console window. The console was the reason the
' bot died whenever Remote Desktop disconnected (tscon moved the session and the window vanished
' together with python). The bot writes everything to log.txt itself.
'
' Started by the scheduled task "Kingbot" at logon and by watchdog.bat when the bot is not running.

Option Explicit

Dim sh, fso, base, py, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = "C:\RisBot"
py = "C:\Program Files\Python312\pythonw.exe"

If Not fso.FileExists(py) Then
    ' fall back to python.exe in the same folder, then to PATH
    If fso.FileExists("C:\Program Files\Python312\python.exe") Then
        py = "C:\Program Files\Python312\python.exe"
    Else
        py = "pythonw.exe"
    End If
End If

sh.CurrentDirectory = base
cmd = """" & py & """ """ & base & "\bot.py"""

' 0 = hidden window, False = do not wait
sh.Run cmd, 0, False
