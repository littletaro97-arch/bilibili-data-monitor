param(
    [string]$Python = 'python',
    [string]$Iscc = 'E:\D-diskExpansionCabin\Inno Setup 6\ISCC.exe'
)
$ErrorActionPreference = 'Stop'
$windowsRoot = Split-Path $PSScriptRoot -Parent
Push-Location $windowsRoot
try {
    $env:PYTHONUTF8 = '1'
    $outputFile = Join-Path $windowsRoot 'releases\v0.11.1-installer.1\BilibiliMonitor-v0.11.1-installer.1-windows-x64-setup.exe'
    if (Test-Path -LiteralPath $outputFile) {
        throw 'Release already exists. Use a new installer revision/output directory; do not overwrite delivered packages.'
    }
    & $Python -m PyInstaller --noconfirm --clean --onedir --console --name BilibiliMonitor --paths . --specpath packaging --distpath dist --workpath build --add-data "${windowsRoot}/app/reports/templates:app/reports/templates" --add-data "${windowsRoot}/app/sample_responses:app/sample_responses" --collect-submodules uvicorn --collect-data plotly --collect-data certifi --hidden-import app.main --hidden-import app.launcher --hidden-import multipart --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy --exclude-module IPython --exclude-module notebook --exclude-module pytest packaging/desktop_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    & $Iscc packaging/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
} finally {
    Pop-Location
}

