# Creates and verifies the single-file Windows executable.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $buildPython)) {
    & python -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual." }
}

Push-Location -LiteralPath $projectRoot
try {
    & $buildPython -m pip install -e ".[build]"
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependências de build." }

    & $buildPython -m PyInstaller --noconfirm --clean packaging/wyrdfall.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o executável." }

    $gameExe = Join-Path $projectRoot "dist\wyrdfall.exe"
    & $gameExe --self-test
    if ($LASTEXITCODE -ne 0) { throw "O executável falhou na verificação de inicialização." }

    Write-Host "Pronto e verificado: $gameExe"
} finally {
    Pop-Location
}
