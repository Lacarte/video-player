' Video Player Runner - VBScript Wrapper
' Launches Python launcher directly to handle paths with special characters (!, ~, etc.)

Option Explicit

Dim objShell, objFSO, strScriptDir, strTargetDir, strPythonExe, strLauncherPy

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get script directory
strScriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Get target directory from argument
If WScript.Arguments.Count > 0 Then
    strTargetDir = WScript.Arguments(0)
Else
    strTargetDir = objShell.CurrentDirectory
End If

' Verify path exists
If Not objFSO.FolderExists(strTargetDir) Then
    MsgBox "Folder not found:" & vbCrLf & vbCrLf & strTargetDir, vbCritical, "Video Player Error"
    WScript.Quit 1
End If

' Find Python executable
strPythonExe = strScriptDir & "\.venv\Scripts\python.exe"
If Not objFSO.FileExists(strPythonExe) Then
    strPythonExe = "python"
End If

strLauncherPy = strScriptDir & "\launcher.py"

' Run Python launcher directly (not via cmd.exe to preserve special chars)
' The launcher.py handles port finding, browser opening, and server startup
objShell.Run """" & strPythonExe & """ """ & strLauncherPy & """ """ & strTargetDir & """", 1, False

Set objShell = Nothing
Set objFSO = Nothing
