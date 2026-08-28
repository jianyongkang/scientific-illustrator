$ErrorActionPreference = 'Stop'

$targetRoot = Join-Path $env:USERPROFILE '.codex\skills\scientific-illustrator'
if (Test-Path -LiteralPath $targetRoot) {
    Remove-Item -LiteralPath $targetRoot -Recurse -Force
    Write-Output "UNINSTALL_OK|target=$targetRoot"
} else {
    Write-Output "UNINSTALL_SKIP|target_missing=$targetRoot"
}
