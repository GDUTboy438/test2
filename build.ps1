$ErrorActionPreference = "Stop"

$VenvPath = ".venv"
$Python = Join-Path $VenvPath "Scripts\python.exe"
$Pip = Join-Path $VenvPath "Scripts\pip.exe"
$PyInstaller = Join-Path $VenvPath "Scripts\pyinstaller.exe"

if (-not (Test-Path $Python)) {
  python -m venv $VenvPath
}

& $Pip install -r requirements.txt

$buildArgs = @(
  "--noconfirm"
  "--windowed"
  "--name"
  "PortableVideoManager"
  "app\main.py"
)

$ffmpegBin = "tools\ffmpeg\bin"
$ffmpegExe = Join-Path $ffmpegBin "ffmpeg.exe"
$ffprobeExe = Join-Path $ffmpegBin "ffprobe.exe"
if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
  $buildArgs += "--add-data"
  $buildArgs += "$ffmpegBin;$ffmpegBin"
  Write-Host "Include local FFmpeg binaries: $ffmpegBin"
} else {
  Write-Host "Local FFmpeg not found, build without bundled FFmpeg."
}

& $PyInstaller @buildArgs

Write-Host "Build complete: dist\PortableVideoManager\PortableVideoManager.exe"
