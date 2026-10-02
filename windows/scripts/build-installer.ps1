param(
    [string]$Python = 'python',
    [string]$Iscc = 'E:\D-diskExpansionCabin\Inno Setup 6\ISCC.exe'
)
$ErrorActionPreference = 'Stop'
$windowsRoot = Split-Path $PSScriptRoot -Parent
Push-Location $windowsRoot
try {
    $env:PYTHONUTF8 = '1'
    $versionFields = & $Python -c 'from app.version import APP_VERSION, INSTALLER_REVISION, PACKAGE_VERSION; print(APP_VERSION); print(INSTALLER_REVISION); print(PACKAGE_VERSION)'
    if ($LASTEXITCODE -ne 0 -or $versionFields.Count -ne 3) { throw 'Unable to read Windows version identity' }
    $appVersion = $versionFields[0].Trim()
    $installerRevision = $versionFields[1].Trim()
    $packageVersion = $versionFields[2].Trim()
    $outputFile = Join-Path $windowsRoot "releases\v$appVersion-installer.$installerRevision\BilibiliMonitor-v$appVersion-installer.$installerRevision-windows-x64-setup.exe"
    if (Test-Path -LiteralPath $outputFile) {
        throw 'Release already exists. Use a new installer revision/output directory; do not overwrite delivered packages.'
    }
    & $Python -m PyInstaller --noconfirm --clean --onedir --console --name BilibiliMonitor --paths . --specpath packaging --distpath dist --workpath build --add-data "${windowsRoot}/app/reports/templates:app/reports/templates" --add-data "${windowsRoot}/app/sample_responses:app/sample_responses" --collect-submodules uvicorn --collect-data plotly --collect-data certifi --hidden-import app.main --hidden-import app.launcher --hidden-import multipart --exclude-module tkinter --exclude-module matplotlib --exclude-module scipy --exclude-module IPython --exclude-module notebook --exclude-module pytest packaging/desktop_entry.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    & $Iscc "/DAppVersion=$appVersion" "/DInstallerRevision=$installerRevision" "/DPackageVersion=$packageVersion" packaging/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
} finally {
    Pop-Location
}

