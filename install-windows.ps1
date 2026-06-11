param(
    [string]$Repo = "",
    [string]$Ref = "",
    [string]$InstallDir = "",
    [string]$ConfigDir = "",
    [string]$BinDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $Repo) {
    $Repo = $env:TASK_SKILL_ROUTER_REPO
}
if (-not $Repo) {
    $Repo = $env:SKILL_ROUTER_REPO
}
if (-not $Repo) {
    $Repo = "wcqxgjy6d8-pixel/task-skill-router"
}
if (-not $Ref) {
    $Ref = $env:TASK_SKILL_ROUTER_REF
}
if (-not $Ref) {
    $Ref = $env:SKILL_ROUTER_REF
}
if (-not $Ref) {
    $Ref = "main"
}

$Forward = @{}
if ($Repo) { $Forward.Repo = $Repo }
if ($Ref) { $Forward.Ref = $Ref }
if ($InstallDir) { $Forward.InstallDir = $InstallDir }
if ($ConfigDir) { $Forward.ConfigDir = $ConfigDir }
if ($BinDir) { $Forward.BinDir = $BinDir }

$LocalInstaller = ""
if ($PSScriptRoot) {
    $Candidate = Join-Path $PSScriptRoot "install.ps1"
    if (Test-Path $Candidate) {
        $LocalInstaller = $Candidate
    }
}

if ($LocalInstaller) {
    & $LocalInstaller @Forward
    exit $LASTEXITCODE
}

$TempInstaller = Join-Path ([System.IO.Path]::GetTempPath()) ("task-skill-router-install-" + [System.Guid]::NewGuid().ToString() + ".ps1")
try {
    $Uri = "https://raw.githubusercontent.com/$Repo/$Ref/install.ps1"
    Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $TempInstaller
    & $TempInstaller @Forward
    exit $LASTEXITCODE
} finally {
    if (Test-Path $TempInstaller) {
        Remove-Item -LiteralPath $TempInstaller -Force
    }
}
