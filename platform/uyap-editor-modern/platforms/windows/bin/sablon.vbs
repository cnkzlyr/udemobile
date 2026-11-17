' UYAP Sablon Editoru - Sessiz Baslatici
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " """ & WScript.Arguments(i) & """"
Next

WshShell.Run """" & strPath & "\sablon.bat""" & args, 0, False
