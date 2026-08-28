param(
    [Parameter(Mandatory = $true)]
    [string]$Script,

    [string]$SvgPath,
    [string]$LayerName = 'SI_redraw',
    [string]$PdfPath,
    [string]$PngPath,
    [string]$AiCopyPath,

    [ValidateSet('contain', 'artboard', 'none')]
    [string]$FitMode = 'none',

    [double]$MarginPoints = 18,
    [double]$PreviewScale = 150,
    [switch]$ReplaceGeneratedLayer,
    [switch]$AllowOverwriteOriginal,
    [switch]$AllowOverwriteOutput,
    [switch]$RequireOpen
)

$ErrorActionPreference = 'Stop'

function Resolve-FullPath {
    param(
        [string]$PathValue,
        [switch]$MustExist
    )

    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return $null
    }

    $candidate = $PathValue
    if (-not [System.IO.Path]::IsPathRooted($candidate)) {
        $candidate = Join-Path (Get-Location) $candidate
    }

    $full = [System.IO.Path]::GetFullPath($candidate)
    if ($MustExist -and -not (Test-Path -LiteralPath $full)) {
        throw "Path not found: $full"
    }
    return $full
}

function Ensure-ParentDirectory {
    param([string]$FilePath)
    if ([string]::IsNullOrWhiteSpace($FilePath)) { return }
    $parent = Split-Path -Parent $FilePath
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
}

$scriptPath = Resolve-FullPath -PathValue $Script -MustExist
$svgFull = $null
$pdfFull = $null
$pngFull = $null
$aiFull = $null

if ($SvgPath) {
    $svgFull = Resolve-FullPath -PathValue $SvgPath -MustExist
}
if ($PdfPath) {
    $pdfFull = Resolve-FullPath -PathValue $PdfPath
    Ensure-ParentDirectory $pdfFull
}
if ($PngPath) {
    $pngFull = Resolve-FullPath -PathValue $PngPath
    Ensure-ParentDirectory $pngFull
}
if ($AiCopyPath) {
    $aiFull = Resolve-FullPath -PathValue $AiCopyPath
    Ensure-ParentDirectory $aiFull
}

$config = [ordered]@{
    svgPath = $svgFull
    layerName = $LayerName
    pdfPath = $pdfFull
    pngPath = $pngFull
    aiCopyPath = $aiFull
    fitMode = $FitMode
    marginPoints = [double]$MarginPoints
    previewScale = [double]$PreviewScale
    replaceGeneratedLayer = [bool]$ReplaceGeneratedLayer
    allowOverwriteOriginal = [bool]$AllowOverwriteOriginal
    allowOverwriteOutput = [bool]$AllowOverwriteOutput
}

$configJson = $config | ConvertTo-Json -Compress
$scriptLiteral = $scriptPath | ConvertTo-Json -Compress
$wrapperPath = Join-Path ([System.IO.Path]::GetTempPath()) ("scientific-illustrator-" + [guid]::NewGuid().ToString('N') + '.jsx')
$wrapper = "var SI_CONFIG = $configJson;`r`n" + '$.evalFile(new File(' + $scriptLiteral + '));'
$utf8NoBom = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllText($wrapperPath, $wrapper, $utf8NoBom)

try {
    try {
        $ai = [System.Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
    } catch {
        throw 'Adobe Illustrator is not running. Open Illustrator and the target document first. This script never launches Illustrator automatically.'
    }

    if ($ai.Documents.Count -eq 0) {
        throw 'No Illustrator document is open. Open the target AI document first.'
    }

    $result = $ai.DoJavaScriptFile($wrapperPath)
    if ($null -ne $result -and -not [string]::IsNullOrWhiteSpace([string]$result)) {
        Write-Output ([string]$result)
    }
    Write-Output "ILLUSTRATOR_JSX_OK|script=$scriptPath|documents=$($ai.Documents.Count)"
} finally {
    if (Test-Path -LiteralPath $wrapperPath) {
        Remove-Item -LiteralPath $wrapperPath -Force -ErrorAction SilentlyContinue
    }
}
