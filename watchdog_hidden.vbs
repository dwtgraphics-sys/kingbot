' Kingbot - hidden watchdog runner
'
' The scheduled task "Kingbot watchdog" runs this file so that watchdog.bat executes with no
' console window at all (a visible console steals the focus from the game and every click then
' lands in the wrong window).
'
Option Explicit

Dim sh
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\RisBot"
sh.Run "cmd /c ""C:\RisBot\watchdog.bat""", 0, False
