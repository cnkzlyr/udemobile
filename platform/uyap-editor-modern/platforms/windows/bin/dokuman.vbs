' UYAP Dokuman Editoru - Sessiz Baslatici (Siyah CMD Penceresiz)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " """ & WScript.Arguments(i) & """"
Next

WshShell.Run """" & strPath & "\dokuman.bat""" & args, 0, False
