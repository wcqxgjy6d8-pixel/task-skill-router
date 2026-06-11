param(
    [string]$Repo = "",
    [string]$Ref = "",
    [string]$InstallDir = "",
    [string]$ConfigDir = "",
    [string]$BinDir = ""
)

$ErrorActionPreference = "Stop"

$DefaultRepo = "wcqxgjy6d8-pixel/task-skill-router"

if (-not $Repo) {
    $Repo = $env:TASK_SKILL_ROUTER_REPO
}
if (-not $Repo) {
    $Repo = $env:SKILL_ROUTER_REPO
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
if (-not $InstallDir) {
    $InstallDir = $env:TASK_SKILL_ROUTER_HOME
}
if (-not $InstallDir) {
    $InstallDir = $env:SKILL_ROUTER_HOME
}
if (-not $InstallDir) {
    $InstallDir = Join-Path $HOME ".task-skill-router"
}
if (-not $ConfigDir) {
    if ($env:XDG_CONFIG_HOME) {
        $ConfigDir = Join-Path $env:XDG_CONFIG_HOME "task-skill-router"
    } else {
        $ConfigDir = Join-Path (Join-Path $HOME ".config") "task-skill-router"
    }
}
if (-not $BinDir) {
    $BinDir = Join-Path (Join-Path $HOME ".local") "bin"
}

$SourceDir = ""
if ($PSScriptRoot) {
    $SourceDir = $PSScriptRoot
}
if (-not $Repo -and -not $SourceDir) {
    $Repo = $DefaultRepo
}

if ($Repo) {
    Write-Host "Installing task-skill-router from $Repo@$Ref"
} else {
    Write-Host "Installing task-skill-router from $SourceDir"
}

New-Item -ItemType Directory -Force -Path $InstallDir, $ConfigDir, $BinDir | Out-Null

function Install-ProjectFile {
    param(
        [string]$RelativePath,
        [string]$Destination
    )

    if ($Repo) {
        $Uri = "https://raw.githubusercontent.com/$Repo/$Ref/$RelativePath"
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile $Destination
    } else {
        Copy-Item -LiteralPath (Join-Path $SourceDir $RelativePath) -Destination $Destination -Force
    }
}

$PythonExe = ""
$PythonArgs = @()
if (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
    $PythonArgs = @("-3")
} else {
    throw "Python 3 is required. Install it from https://www.python.org/downloads/windows/ and rerun this installer."
}

Install-ProjectFile "task-skill-router.py" (Join-Path $InstallDir "task-skill-router.py")

& $PythonExe @PythonArgs -c "import yaml" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyYAML is not installed. The router will use its built-in limited YAML parser."
    Write-Host "For full YAML support, run: $PythonExe $($PythonArgs -join ' ') -m pip install PyYAML"
}

if (-not (Test-Path (Join-Path $ConfigDir "config.yaml"))) {
    Install-ProjectFile "config/config.yaml" (Join-Path $ConfigDir "config.yaml")
    Write-Host "Created $(Join-Path $ConfigDir 'config.yaml')"
}

if (-not (Test-Path (Join-Path $ConfigDir "community.yaml"))) {
    Install-ProjectFile "config/community.yaml" (Join-Path $ConfigDir "community.yaml")
    Write-Host "Created $(Join-Path $ConfigDir 'community.yaml')"
}

$ScriptPath = Join-Path $InstallDir "task-skill-router.py"
$CmdPath = Join-Path $BinDir "task-skill-router.cmd"
$CompatCmdPath = Join-Path $BinDir "skill-router.cmd"

if ($PythonExe -eq "py") {
    $CmdContent = "@echo off`r`npy -3 `"$ScriptPath`" %*`r`n"
} else {
    $CmdContent = "@echo off`r`npython `"$ScriptPath`" %*`r`n"
}
Set-Content -Path $CmdPath -Value $CmdContent -Encoding ASCII
Set-Content -Path $CompatCmdPath -Value $CmdContent -Encoding ASCII

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathParts = @()
if ($UserPath) {
    $PathParts = $UserPath -split ";" | Where-Object { $_ }
}
if ($PathParts -notcontains $BinDir) {
    $NewPath = if ($UserPath) { "$UserPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    $env:Path = "$env:Path;$BinDir"
    Write-Host "Added $BinDir to your user PATH. Open a new terminal if the command is not found."
}

Write-Host ""
Write-Host "task-skill-router installed."
Write-Host ""
Write-Host "   Try it:"
Write-Host "   task-skill-router `"fix a bug in my auth module`""
Write-Host ""
Write-Host "   Configure: $(Join-Path $ConfigDir 'config.yaml')"
Write-Host "   Community: $(Join-Path $ConfigDir 'community.yaml')"
