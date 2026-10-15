$ErrorActionPreference = 'Stop'

$builder = Join-Path $PSScriptRoot 'build_plugin.py'
python $builder
if ($LASTEXITCODE -ne 0) {
    throw "Plugin build failed with exit code $LASTEXITCODE"
}
