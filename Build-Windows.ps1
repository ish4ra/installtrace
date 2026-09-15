$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Install Python 3.12 for Windows with the Python Launcher and Tcl/Tk, then run this script again.'
}
& py -3.12 -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw 'Could not create the build environment.' }
$python = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
& $python -m pip install pyinstaller==6.11.1
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; EXE not built.' }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name InstallTrace launch.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
$report = Join-Path $PSScriptRoot 'dist\smoke-test.json'
$process = Start-Process -FilePath '.\dist\InstallTrace.exe' -ArgumentList @('self-test', '--out', ('"' + $report + '"')) -PassThru
if (-not $process.WaitForExit(180000)) { $process.Kill(); throw 'Executable smoke test timed out.' }
if ($process.ExitCode -ne 0) { throw 'Executable smoke test failed; inspect dist\smoke-test.json.' }
$result = Get-Content $report -Raw | ConvertFrom-Json
if ($result.status -ne 'passed') { throw 'Executable smoke test did not pass.' }
$hash = (Get-FileHash '.\dist\InstallTrace.exe' -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  InstallTrace.exe" | Set-Content '.\dist\SHA256SUMS.txt' -Encoding ascii
Write-Host 'Built and smoke-tested: dist\InstallTrace.exe'
