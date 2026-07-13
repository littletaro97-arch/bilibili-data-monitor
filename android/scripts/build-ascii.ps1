param(
    [string]$Version = "v0.12.0",
    [string]$ProjectRoot = "",
    [string]$AsciiRoot = "C:\Users\LittleTaro\codex-bilibili-monitor-ascii"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[android-build-ascii] $Message"
}

function Ensure-Junction {
    param(
        [string]$LinkPath,
        [string]$TargetPath
    )

    if (Test-Path -LiteralPath $LinkPath) {
        $item = Get-Item -LiteralPath $LinkPath -Force
        $isReparsePoint = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
        if (-not $isReparsePoint) {
            throw "Path exists but is not a junction or symlink: $LinkPath"
        }

        $actualTarget = $item.Target
        if ($actualTarget -and ($actualTarget -notcontains $TargetPath)) {
            throw "Junction points to unexpected target. Path=$LinkPath Target=$actualTarget Expected=$TargetPath"
        }

        Write-Step "ASCII junction already exists: $LinkPath -> $TargetPath"
        return
    }

    Write-Step "Creating ASCII junction: $LinkPath -> $TargetPath"
    New-Item -ItemType Junction -Path $LinkPath -Target $TargetPath | Out-Null
}

function Get-GradleVersion {
    param([string]$AndroidRoot)

    $output = & (Join-Path $AndroidRoot "gradlew.bat") --version --no-daemon
    $line = $output | Where-Object { $_ -match "^Gradle\s+" } | Select-Object -First 1
    if ($line -match "Gradle\s+(.+)$") {
        return $Matches[1].Trim()
    }
    return "unknown"
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
} else {
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}
Ensure-Junction -LinkPath $AsciiRoot -TargetPath $ProjectRoot

$androidRoot = Join-Path $AsciiRoot "android"
$formalAndroidRoot = Join-Path $ProjectRoot "android"
$releaseDir = Join-Path $ProjectRoot "releases\android\$Version"
$apkName = "bilibili-monitor-android-$Version-debug.apk"
$apkSource = Join-Path $formalAndroidRoot "app\build\outputs\apk\debug\app-debug.apk"
$apkTarget = Join-Path $releaseDir $apkName

Write-Step "Android root: $androidRoot"
Push-Location $androidRoot
try {
    Write-Step "Running Gradle tests"
    & .\gradlew.bat test --no-daemon --console=plain --stacktrace
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle test failed with exit code $LASTEXITCODE"
    }

    Write-Step "Running lintDebug"
    & .\gradlew.bat lintDebug --no-daemon --console=plain --stacktrace
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle lintDebug failed with exit code $LASTEXITCODE"
    }

    Write-Step "Running assembleDebug"
    & .\gradlew.bat assembleDebug --no-daemon --console=plain --stacktrace
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle assembleDebug failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Copy-Item -LiteralPath $apkSource -Destination $apkTarget -Force

$apkItem = Get-Item -LiteralPath $apkTarget
$sha256 = (Get-FileHash -LiteralPath $apkTarget -Algorithm SHA256).Hash
$buildTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
$commit = (& git -C $ProjectRoot rev-parse --short HEAD).Trim()
$branch = (& git -C $ProjectRoot branch --show-current).Trim()
$dirtyLines = @(& git -C $ProjectRoot status --short)
$workingTreeClean = if ($dirtyLines.Count -eq 0) { "yes" } else { "no" }
$gradleVersion = Get-GradleVersion -AndroidRoot $androidRoot

$buildInfoLines = New-Object System.Collections.Generic.List[string]
$buildInfoLines.Add("Version: $Version")
$buildInfoLines.Add("Git commit hash at build time: $commit")
$buildInfoLines.Add("Git branch: $branch")
$buildInfoLines.Add("Git working tree clean at build time: $workingTreeClean")
$buildInfoLines.Add("Build time: $buildTime")
$buildInfoLines.Add("Used ASCII junction: yes")
$buildInfoLines.Add("Gradle version: $gradleVersion")
$buildInfoLines.Add("Android Gradle Plugin version: 8.5.2")
$buildInfoLines.Add("Kotlin plugin version: 1.9.24")
$buildInfoLines.Add("minSdk: 26")
$buildInfoLines.Add("targetSdk: 35")
$buildInfoLines.Add("compileSdk: 35")
$buildInfoLines.Add("APK file name: $apkName")
$buildInfoLines.Add("APK size: $($apkItem.Length) bytes")
$buildInfoLines.Add("SHA256: $sha256")
$buildInfo = [string]::Join([Environment]::NewLine, $buildInfoLines)

$changelogLines = New-Object System.Collections.Generic.List[string]
$changelogLines.Add("# $Version Android Changelog")
$changelogLines.Add("")
$changelogLines.Add("## Added")
$changelogLines.Add("")
$changelogLines.Add("- Fixes parsing for mobile Bilibili share text, standard mobile links, wrapped text, and short-link redirects.")
$changelogLines.Add("- Adds compact expand/edit wheel rows to reduce accidental setting changes while scrolling Settings.")
$changelogLines.Add("- Stores new collection, log, export, and worker times with device local offset time.")
$changelogLines.Add("- Adds parser, short-link resolver, wheel editor, device-time, and notification-time unit coverage.")
$changelogLines.Add("- Generates versioned Debug APK under releases/android/$Version/.")
$changelogLines.Add("- Generates build info and test report with APK size and SHA256.")
$changelogLines.Add("")
$changelogLines.Add("## Changed")
$changelogLines.Add("")
$changelogLines.Add("- Android versionName/versionCode updated for $Version.")
$changelogLines.Add("- Short-link resolution is performed off the UI path through the existing OkHttp layer.")
$changelogLines.Add("- Settings time wheels are collapsed by default and expose an explicit completion action.")
$changelogLines.Add("- User-visible snapshot and worker times are formatted in the current device time zone.")
$changelogLines.Add("")
$changelogLines.Add("## Known Issues")
$changelogLines.Add("")
$changelogLines.Add("- Full SAF save-directory behavior still depends on user interaction in Android's system picker.")
$changelogLines.Add("- Nested scroll edge handoff for wheels still requires real device validation.")
$changelogLines.Add("- Real notification behavior still requires Android 13+ permission and device/emulator validation.")
$changelogLines.Add("- Device and emulator UI validation may be unavailable when no adb device or emulator is connected.")
$changelogLines.Add("- Direct Android unit tests under the formal Chinese path may still fail because of JDK/Gradle worker argfile classpath handling.")
$changelogLines.Add("- Auto refresh depends on Android WorkManager scheduling; values below 15 minutes are not guaranteed as background periodic work.")
$changelogLines.Add("- Network requests remain low frequency and cover only already-added videos; no login, Cookie, captcha, proxy, or risk-control bypass is implemented.")
$changelog = [string]::Join([Environment]::NewLine, $changelogLines)

$testReportLines = New-Object System.Collections.Generic.List[string]
$testReportLines.Add("# $Version Test Report")
$testReportLines.Add("")
$testReportLines.Add("## Windows")
$testReportLines.Add("")
$testReportLines.Add("- Command: python -m pytest")
$testReportLines.Add("- Result: run separately before release; record final result in the delivery report.")
$testReportLines.Add("")
$testReportLines.Add("## Android")
$testReportLines.Add("")
$testReportLines.Add("- Command: .\gradlew.bat test")
$testReportLines.Add("- Result: passed")
$testReportLines.Add("- Command: .\gradlew.bat lintDebug")
$testReportLines.Add("- Result: passed")
$testReportLines.Add("- Command: .\gradlew.bat assembleDebug")
$testReportLines.Add("- Result: passed")
$testReportLines.Add("- Notification policy tests: covered by Gradle unit tests.")
$testReportLines.Add("- Notification interval tests: covered by Gradle unit tests.")
$testReportLines.Add("- Build path: $androidRoot")
$testReportLines.Add("- Used ASCII junction: yes")
$testReportLines.Add("")
$testReportLines.Add("## APK")
$testReportLines.Add("")
$testReportLines.Add("- File: releases/android/$Version/$apkName")
$testReportLines.Add("- Size: $($apkItem.Length) bytes")
$testReportLines.Add("- SHA256: $sha256")
$testReportLines.Add("- Copied to release directory: yes")
$testReportLines.Add("")
$testReportLines.Add("## Real Device Test")
$testReportLines.Add("")
$testReportLines.Add("- Codex did not perform real-device installation testing. Waiting for user validation.")
$testReport = [string]::Join([Environment]::NewLine, $testReportLines)

Set-Content -LiteralPath (Join-Path $releaseDir "build-info.txt") -Value $buildInfo -Encoding UTF8
if (-not (Test-Path -LiteralPath (Join-Path $releaseDir "changelog.md"))) {
    Set-Content -LiteralPath (Join-Path $releaseDir "changelog.md") -Value $changelog -Encoding UTF8
}
if (-not (Test-Path -LiteralPath (Join-Path $releaseDir "test-report.md"))) {
    Set-Content -LiteralPath (Join-Path $releaseDir "test-report.md") -Value $testReport -Encoding UTF8
}

Write-Step "APK copied to: $apkTarget"
Write-Step "APK size: $($apkItem.Length) bytes"
Write-Step "SHA256: $sha256"
