# Builds HoloGrid-Setup.exe with Windows' built-in IExpress. Run after PyInstaller (dist\HoloGrid.exe).
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $env:TEMP 'hologrid-stage'
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $stage | Out-Null
Copy-Item "$root\dist\HoloGrid.exe", "$PSScriptRoot\install.ps1", "$PSScriptRoot\uninstall.ps1" $stage
$out = Join-Path $root 'HoloGrid-Setup.exe'
$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=HoloGrid installed. Look for it in the Start Menu and on your Desktop.
TargetName=$out
FriendlyName=HoloGrid Setup
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File install.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[Strings]
[SourceFiles]
SourceFiles0=$stage\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
"@
$sed = $sed -replace '%FILE0%=', 'HoloGrid.exe=' -replace '%FILE1%=', 'install.ps1=' -replace '%FILE2%=', 'uninstall.ps1='
$sedPath = Join-Path $stage 'hologrid.sed'
Set-Content $sedPath $sed -Encoding ASCII
& "$env:WINDIR\System32\iexpress.exe" /N /Q $sedPath
Start-Sleep 3
while (Get-Process iexpress -ErrorAction SilentlyContinue) { Start-Sleep 1 }
Get-Item $out
