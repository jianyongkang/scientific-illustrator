param(
    [switch]$RequireIllustratorOpen,
    [switch]$Json
)

$ErrorActionPreference = 'Continue'
$script:Failed = $false
$script:Rows = @()

function Add-Status {
    param([string]$Name, [string]$Status, [string]$Detail)
    $row = [ordered]@{ name = $Name; status = $Status; detail = $Detail }
    $script:Rows += [pscustomobject]$row
    if ($Status -eq 'FAIL') { $script:Failed = $true }
    if (-not $Json) { Write-Output "$Status|$Name|$Detail" }
}

$isWindowsNow = $false
$isWindowsVar = Get-Variable -Name IsWindows -ErrorAction SilentlyContinue
if ($null -ne $isWindowsVar) {
    $isWindowsNow = [bool]$isWindowsVar.Value
} elseif ($env:OS -eq 'Windows_NT') {
    $isWindowsNow = $true
}

if (-not $isWindowsNow) {
    Add-Status 'platform' 'FAIL' 'This skill supports Windows only.'
    if ($Json) { $script:Rows | ConvertTo-Json -Compress }
    exit 1
}

Add-Status 'platform' 'OK' 'Windows detected.'
Add-Status 'powershell' 'OK' $PSVersionTable.PSVersion.ToString()
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Add-Status 'powershell_version' 'FAIL' 'PowerShell 5.1 or newer is required.'
}

$pythonExe = $null
$pythonArgs = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = 'python'
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = 'py'
    $pythonArgs = @('-3')
}

if ($null -eq $pythonExe) {
    Add-Status 'python' 'FAIL' 'Python 3.11-3.14 was not found as python or py -3.'
} else {
    $versionCode = 'import sys; print("%d.%d.%d" % sys.version_info[:3]); raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,15) else 2)'
    $versionOutput = & $pythonExe @pythonArgs -c $versionCode 2>&1
    if ($LASTEXITCODE -eq 0) {
        Add-Status 'python' 'OK' ([string]$versionOutput)
    } else {
        Add-Status 'python' 'FAIL' ("Expected Python 3.11-3.14; detected " + [string]$versionOutput)
    }
}

$registered = $false
try {
    $progId = Get-ItemProperty -Path 'Registry::HKEY_CLASSES_ROOT\Illustrator.Application\CLSID' -ErrorAction Stop
    if ($progId.'(default)' -or $progId.PSChildName) { $registered = $true }
} catch {
    try {
        $null = Get-Item -Path 'Registry::HKEY_CLASSES_ROOT\Illustrator.Application' -ErrorAction Stop
        $registered = $true
    } catch { $registered = $false }
}
if ($registered) {
    Add-Status 'illustrator_registration' 'OK' 'Illustrator COM ProgID is registered.'
} else {
    Add-Status 'illustrator_registration' 'WARN' 'Illustrator COM ProgID was not found in the registry.'
}

$ai = $null
try {
    $ai = [System.Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
    $version = 'unknown'
    try { $version = [string]$ai.Version } catch { }
    Add-Status 'illustrator_running' 'OK' "Active Illustrator COM instance found; version=$version"
    if ($version -and $version -ne 'unknown' -and -not $version.StartsWith('30.')) {
        Add-Status 'illustrator_version' 'WARN' "Preferred target is Illustrator 2026 (30.x); detected version=$version"
    } else {
        Add-Status 'illustrator_version' 'OK' "Target-compatible version=$version"
    }
    if ($ai.Documents.Count -gt 0) {
        Add-Status 'illustrator_document' 'OK' "Open documents: $($ai.Documents.Count)"
    } elseif ($RequireIllustratorOpen) {
        Add-Status 'illustrator_document' 'FAIL' 'Illustrator is running but no document is open.'
    } else {
        Add-Status 'illustrator_document' 'WARN' 'Illustrator is running but no document is open.'
    }
} catch {
    if ($RequireIllustratorOpen) {
        Add-Status 'illustrator_running' 'FAIL' 'Illustrator is not running or active COM access failed.'
    } else {
        Add-Status 'illustrator_running' 'WARN' 'Illustrator is not running. Doctor did not launch it.'
    }
}

$skillRoot = Split-Path -Parent $PSScriptRoot
Add-Status 'skill_root' 'OK' $skillRoot
$runtimeLock = Join-Path $skillRoot 'runtime-lock.json'
if (Test-Path -LiteralPath $runtimeLock) {
    Add-Status 'runtime_lock' 'OK' $runtimeLock
} else {
    Add-Status 'runtime_lock' 'FAIL' 'runtime-lock.json is missing.'
}

if ($Json) {
    [pscustomobject]@{ ok = (-not $script:Failed); checks = $script:Rows } | ConvertTo-Json -Depth 5 -Compress
}
if ($script:Failed) { exit 1 }
exit 0
