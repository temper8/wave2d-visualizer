' ============================================================
'  Wave2D GUI navigator launcher without a console window.
'
'  Double-click this file: it runs run_w2d_app.bat hidden,
'  so only the GUI window stays (no terminal).
'
'  Arguments are forwarded to the .bat, e.g. via a shortcut:
'      wscript run_w2d_app.vbs "<data_root>"
' ============================================================
Option Explicit

Dim sh, fso, here, bat, cmd, a
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

here = fso.GetParentFolderName(WScript.ScriptFullName)
bat = fso.BuildPath(here, "run_w2d_app.bat")

If Not fso.FileExists(bat) Then
    MsgBox "run_w2d_app.bat was not found next to this script:" & vbCrLf & bat, 16, "Wave2D"
    WScript.Quit 1
End If

sh.CurrentDirectory = here

cmd = """" & bat & """"
For Each a In WScript.Arguments
    cmd = cmd & " """ & a & """"
Next

' 0 = hidden window, False = do not wait (the GUI runs independently)
sh.Run cmd, 0, False
