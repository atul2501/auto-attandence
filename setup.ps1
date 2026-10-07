# Installs auto punch: punch in at login, punch out at shutdown. Run once.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = (Get-Command pythonw.exe).Source
$ws = New-Object -ComObject WScript.Shell

# Old version used a scheduled task - remove it
Unregister-ScheduledTask -TaskName "Auto Punch In" -Confirm:$false -ErrorAction SilentlyContinue

# 1. Background program started at every login (punches in, then punches out at shutdown)
$startup = [Environment]::GetFolderPath("Startup")
$lnk = $ws.CreateShortcut("$startup\FTS Auto Punch.lnk")
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$dir\autopunch.pyw`""
$lnk.WorkingDirectory = $dir
$lnk.Save()
Write-Host "Startup entry 'FTS Auto Punch' created."

# 2. Desktop shortcut: punch out, then shut down (manual backup)
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = $ws.CreateShortcut("$desktop\Punch Out & Shutdown.lnk")
$lnk.TargetPath = "$dir\punch_out_and_shutdown.bat"
$lnk.WorkingDirectory = $dir
$lnk.IconLocation = "$env:SystemRoot\System32\shell32.dll,27"
$lnk.Save()
Write-Host "Desktop shortcut 'Punch Out & Shutdown' created."

# Start it now so it is active for this session
Start-Process $pythonw -ArgumentList "`"$dir\autopunch.pyw`"" -WorkingDirectory $dir
Write-Host "Auto punch is running."
