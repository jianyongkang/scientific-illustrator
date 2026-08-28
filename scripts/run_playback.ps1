param(
    [Parameter(Mandatory = $true)]
    [string]$CacheDir,

    [string]$LayerName = 'SI_redraw',

    [ValidateSet('contain', 'artboard', 'none')]
    [string]$FitMode = 'contain',

    [double]$MarginPoints = 18,
    [int]$InterObjectDelayMs = 0,
    [string]$StatePath,
    [switch]$ResetGeneratedLayer
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Resolve-FullPath {
    param([string]$PathValue, [switch]$MustExist)
    $candidate = $PathValue
    if (-not [System.IO.Path]::IsPathRooted($candidate)) { $candidate = Join-Path (Get-Location) $candidate }
    $full = [System.IO.Path]::GetFullPath($candidate)
    if ($MustExist -and -not (Test-Path -LiteralPath $full)) { throw "Path not found: $full" }
    return $full
}

function Write-JsonAtomic {
    param([string]$Path, [object]$Value)
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $tmp = $Path + '.tmp'
    $json = $Value | ConvertTo-Json -Depth 12
    $utf8NoBom = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($tmp, $json + "`r`n", $utf8NoBom)
    Move-Item -Force -LiteralPath $tmp -Destination $Path
}

function Invoke-JsxConfig {
    param([object]$Ai, [string]$JsxPath, [hashtable]$Config)
    $configJson = $Config | ConvertTo-Json -Depth 12 -Compress
    $scriptLiteral = $JsxPath | ConvertTo-Json -Compress
    $wrapperPath = Join-Path ([System.IO.Path]::GetTempPath()) ("scientific-illustrator-playback-" + [guid]::NewGuid().ToString('N') + '.jsx')
    $wrapper = "var SI_CONFIG = $configJson;`r`n" + '$.evalFile(new File(' + $scriptLiteral + '));'
    $utf8NoBom = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($wrapperPath, $wrapper, $utf8NoBom)
    try {
        return [string]$Ai.DoJavaScriptFile($wrapperPath)
    } finally {
        Remove-Item -LiteralPath $wrapperPath -Force -ErrorAction SilentlyContinue
    }
}

$cacheFull = Resolve-FullPath -PathValue $CacheDir -MustExist
$manifestPath = Join-Path $cacheFull 'geometry-cache.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Geometry cache manifest missing: $manifestPath" }
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ([int]$manifest.schema -ne 2) { throw 'Unsupported geometry cache schema.' }
if ([string]::IsNullOrWhiteSpace($LayerName) -or -not $LayerName.StartsWith('SI_')) { throw 'LayerName must begin with SI_.' }
if ($InterObjectDelayMs -lt 0) { throw 'InterObjectDelayMs must be >= 0.' }

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillRoot = Split-Path -Parent $scriptRoot
$cacheQa = Join-Path $scriptRoot 'cache_qa.py'
$masterSvg = [string]$manifest.source.master_svg
& python $cacheQa $cacheFull --master-svg $masterSvg --strict
if ($LASTEXITCODE -ne 0) { throw 'Geometry cache QA failed; rebuild the cache before playback.' }

if ([string]::IsNullOrWhiteSpace($StatePath)) {
    $StatePath = Join-Path (Split-Path -Parent $cacheFull) 'playback-state.json'
}
$stateFull = Resolve-FullPath -PathValue $StatePath
$playJsx = Join-Path $skillRoot 'jsx\play_batch.jsx'
$resetJsx = Join-Path $skillRoot 'jsx\reset_generated_layer.jsx'

try {
    $ai = [System.Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
} catch {
    throw 'Adobe Illustrator is not running. Open Illustrator and the target document first. Playback never launches Illustrator.'
}
if ($ai.Documents.Count -eq 0) { throw 'No Illustrator document is open.' }
$doc = $ai.ActiveDocument
$docName = [string]$doc.Name
$docFullName = ''
try { $docFullName = [string]$doc.FullName } catch { $docFullName = '' }
$docFingerprint = $docName + '|' + $docFullName + '|artboards=' + [string]$doc.Artboards.Count

if ($ResetGeneratedLayer) {
    $resetResult = Invoke-JsxConfig -Ai $ai -JsxPath $resetJsx -Config @{ layerName = $LayerName }
    Write-Output $resetResult
    if (Test-Path -LiteralPath $stateFull) { Remove-Item -LiteralPath $stateFull -Force }
}

$state = $null
if (Test-Path -LiteralPath $stateFull) {
    $state = Get-Content -Raw -LiteralPath $stateFull | ConvertFrom-Json
    if ([string]$state.cache_id -ne [string]$manifest.cache_id) { throw 'Playback state belongs to a different geometry cache. Use -ResetGeneratedLayer after rebuilding the Master SVG cache.' }
    if ([string]$state.document_fingerprint -ne $docFingerprint) { throw 'Active Illustrator document differs from the document recorded in playback-state.json.' }
    if ([string]$state.layer_name -ne $LayerName) { throw 'LayerName differs from the existing playback state.' }
    if ([string]$state.fit_mode -ne $FitMode) { throw 'FitMode differs from the existing playback state.' }
} else {
    $state = [ordered]@{
        schema = 2
        status = 'running'
        cache_id = [string]$manifest.cache_id
        source_sha256 = [string]$manifest.source.sha256
        document_fingerprint = $docFingerprint
        document_name = $docName
        document_full_name = $docFullName
        layer_name = $LayerName
        fit_mode = $FitMode
        next_batch = 0
        completed_batches = @()
        total_batches = [int]$manifest.stats.batches
        started_utc = [DateTime]::UtcNow.ToString('o')
        updated_utc = [DateTime]::UtcNow.ToString('o')
    }
    Write-JsonAtomic -Path $stateFull -Value $state
}

$nextBatch = [int]$state.next_batch
$batches = @($manifest.batches)
$viewBox = @($manifest.source.viewBox | ForEach-Object { [double]$_ })

for ($i = $nextBatch; $i -lt $batches.Count; $i++) {
    $meta = $batches[$i]
    if ([int]$meta.index -ne $i) { throw "Non-contiguous batch manifest at index $i" }
    $batchPath = Join-Path $cacheFull ([string]$meta.file)
    $result = Invoke-JsxConfig -Ai $ai -JsxPath $playJsx -Config @{
        batchPath = $batchPath
        batchIndex = $i
        layerName = $LayerName
        fitMode = $FitMode
        marginPoints = [double]$MarginPoints
        interObjectDelayMs = [int]$InterObjectDelayMs
        viewBox = $viewBox
        cacheId = [string]$manifest.cache_id
    }
    if (-not ($result.StartsWith('BATCH_OK|') -or $result.StartsWith('BATCH_ALREADY_DONE|'))) {
        throw "Unexpected Illustrator batch result: $result"
    }
    Write-Output $result

    $completed = @($state.completed_batches)
    if (-not ($completed -contains $i)) { $completed += $i }
    $state.completed_batches = $completed
    $state.next_batch = $i + 1
    $state.status = if (($i + 1) -ge $batches.Count) { 'complete' } else { 'running' }
    $state.updated_utc = [DateTime]::UtcNow.ToString('o')
    Write-JsonAtomic -Path $stateFull -Value $state
}

Write-Output ("PLAYBACK_OK|cache_id=" + [string]$manifest.cache_id + "|batches=" + [string]$batches.Count + "|layer=" + $LayerName + "|state=" + $stateFull)
