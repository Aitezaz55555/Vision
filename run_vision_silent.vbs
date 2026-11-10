Dim fso, scriptDir, WshShell, pythonwExe, visionPy
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

pythonwExe = fso.BuildPath(scriptDir, ".venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonwExe) Then
    pythonwExe = fso.BuildPath(scriptDir, ".venv\pythonw.exe")
End If
If Not fso.FileExists(pythonwExe) Then
    pythonwExe = "pythonw.exe"
End If

visionPy = fso.BuildPath(scriptDir, "vision.py")
If fso.FileExists(visionPy) Then
    WshShell.Run """" & pythonwExe & """ """ & visionPy & """", 0, False
End If

Set WshShell = Nothing
Set fso = Nothing
