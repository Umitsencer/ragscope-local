param(
    [Parameter(Mandatory = $true)][string]$ModelCache,
    [ValidateSet('retrieval', 'extractive')][string]$Mode = 'extractive'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Create the .venv environment using README.md before starting the demo.'
}
if (-not (Test-Path -LiteralPath $ModelCache -PathType Container)) {
    throw 'ModelCache must be an existing Foundry model-cache or application-data directory.'
}
$resolvedCache = (Resolve-Path -LiteralPath $ModelCache).Path
$nestedCache = Join-Path $resolvedCache 'cache/models'
if (Test-Path -LiteralPath (Join-Path $resolvedCache 'foundry.modelinfo.json') -PathType Leaf) {
    $modelCacheDir = $resolvedCache
} elseif (Test-Path -LiteralPath (Join-Path $nestedCache 'foundry.modelinfo.json') -PathType Leaf) {
    $modelCacheDir = $nestedCache
} else {
    throw 'ModelCache does not contain foundry.modelinfo.json directly or under cache/models.'
}
$appDataDir = Join-Path $projectRoot 'data/local_cache/foundry-app'
New-Item -ItemType Directory -Force -Path $appDataDir | Out-Null
$env:RAGSCOPE_FOUNDRY_APP_DATA_DIR = $appDataDir
$env:RAGSCOPE_FOUNDRY_MODEL_CACHE_DIR = $modelCacheDir
$env:PYTHONUTF8 = '1'
Write-Host 'RAGScope Local | Educational evidence inspection'
Write-Host 'Synthetic input only. Quotes are evidence candidates, not incident verdicts.'
$demoQuery = Read-Host 'Question (Enter uses the documented synthetic credential-dumping example)'
if ([string]::IsNullOrWhiteSpace($demoQuery)) {
    $demoQuery = 'Synthetic training question: Explain OS credential dumping based only on the retrieved ATT&CK definitions.'
}
if ($Mode -eq 'extractive') {
    $scriptFile = Join-Path $PSScriptRoot 'demo_local_extractive.py'
    & $pythonExecutable -u -B $scriptFile --generation-model 'Phi-4-mini-instruct-generic-cpu:5' --query $demoQuery
} else {
    $scriptFile = Join-Path $PSScriptRoot 'demo_local_retrieval.py'
    & $pythonExecutable -u -B $scriptFile --query $demoQuery --top-k 3
}
if ($LASTEXITCODE -ne 0) { throw "Demo failed (exit $LASTEXITCODE). No successful answer is claimed." }
