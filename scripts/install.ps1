param(
    [switch]$NoBackup
)

$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $PSScriptRoot
$skillsRoot = Join-Path $env:USERPROFILE '.codex\skills'
$targetRoot = Join-Path $skillsRoot 'scientific-illustrator'

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null

if (Test-Path -LiteralPath $targetRoot) {
    if ($NoBackup) {
        Remove-Item -LiteralPath $targetRoot -Recurse -Force
    } else {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $backup = Join-Path $skillsRoot ("scientific-illustrator.backup-" + $stamp)
        Move-Item -LiteralPath $targetRoot -Destination $backup
        Write-Output "BACKUP_OK|path=$backup"
    }
}

New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null
Copy-Item -Path (Join-Path $sourceRoot '*') -Destination $targetRoot -Recurse -Force

Write-Output "INSTALL_OK|target=$targetRoot"
Write-Output 'Restart Codex Desktop after installation or reload skills if the client exposes that action.'
