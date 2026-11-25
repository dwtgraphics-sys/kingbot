' Kingbot watchdog, hidden launcher: the scheduled task runs this VBS so no console
' window appears and steals the focus from the game.
Set sh = CreateObject("WScript.Shell")
sh.Run "cmd /c ""C:\RisBot\watchdog.bat""", 0, False
