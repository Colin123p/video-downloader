# Baut die fertige Setup-Datei: release\Video Downloader Setup.exe
# Aufruf:  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# Braucht: Python 3.12 mit den Paketen der App + pyinstaller, Inno Setup 6, ffmpeg "essentials" (winget Gyan.FFmpeg.Essentials)
$ErrorActionPreference = "Stop"
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $env:USERPROFILE "VideoDownloaderBuild"   # ausserhalb von OneDrive (gross)
$ff = $env:VD_FFMPEG_DIR   # GitHub Actions setzt das selbst
if (-not $ff) {
    $ff = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Directory -Filter "Gyan.FFmpeg.Essentials*" -ErrorAction SilentlyContinue |
           Get-ChildItem -Recurse -Filter ffmpeg.exe | Select-Object -First 1).DirectoryName
}
if (-not $ff) { throw "ffmpeg essentials fehlt: winget install Gyan.FFmpeg.Essentials" }
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 fehlt: winget install JRSoftware.InnoSetup" }

$env:VD_FFMPEG_DIR = $ff
$env:VD_BUILD = $build
New-Item -ItemType Directory -Force $build | Out-Null

Write-Host "1/3 EXE bauen (PyInstaller) ..."
python -m PyInstaller --noconfirm --clean --distpath "$build\dist" --workpath "$build\work" "$here\Video Downloader.spec"
if ($LASTEXITCODE) { throw "PyInstaller fehlgeschlagen" }

Write-Host "2/3 Lizenzhinweise sammeln ..."
if (Test-Path "$build\notices") { Remove-Item -Recurse -Force "$build\notices" }
New-Item -ItemType Directory "$build\notices" | Out-Null
python "$here\collect_licenses.py" "$build\notices"
if ($LASTEXITCODE) { throw "Lizenzen fehlgeschlagen" }

Write-Host "3/3 Setup bauen (Inno Setup) ..."
& $iscc /Q "$here\setup.iss"
if ($LASTEXITCODE) { throw "Inno Setup fehlgeschlagen" }
Get-Item (Join-Path $here "..\release\Video Downloader Setup.exe") | Select-Object FullName, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
