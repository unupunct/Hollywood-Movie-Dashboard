# HoloGrid installer: per-user install, Start Menu + Desktop shortcuts, uninstall entry.
$ErrorActionPreference = 'Stop'
$app    = 'HoloGrid'
$dir    = Join-Path $env:LOCALAPPDATA "Programs\$app"
$src    = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item (Join-Path $src 'HoloGrid.exe') $dir -Force
Copy-Item (Join-Path $src 'uninstall.ps1') $dir -Force
$exe = Join-Path $dir 'HoloGrid.exe'
$sh  = New-Object -ComObject WScript.Shell
$links = @(
  (Join-Path ([Environment]::GetFolderPath('Programs')) "$app.lnk"),
  (Join-Path ([Environment]::GetFolderPath('Desktop')) "$app.lnk")
)
foreach ($l in $links) {
  $s = $sh.CreateShortcut($l); $s.TargetPath = $exe; $s.WorkingDirectory = $dir
  $s.Description = 'HoloGrid sci-fi HUD generator'; $s.Save()
}
$key = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$app"
New-Item -Force $key | Out-Null
Set-ItemProperty $key DisplayName 'HoloGrid'
Set-ItemProperty $key DisplayVersion '2.1.1'
Set-ItemProperty $key Publisher 'unupunct'
Set-ItemProperty $key InstallLocation $dir
Set-ItemProperty $key DisplayIcon $exe
Set-ItemProperty $key UninstallString "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$dir\uninstall.ps1`""
Start-Process explorer.exe -ArgumentList "`"$exe`""
