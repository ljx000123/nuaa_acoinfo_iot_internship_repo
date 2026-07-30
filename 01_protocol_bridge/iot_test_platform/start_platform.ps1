$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BridgeRoot = Split-Path -Parent $Root
$Python = $null

$PlatformPython = Join-Path $Root ".venv\Scripts\python.exe"
$BridgePython = Join-Path $BridgeRoot ".venv\Scripts\python.exe"

function Test-PythonModule([string]$PythonExe, [string]$ModuleName) {
    $ScriptsDir = Split-Path -Parent $PythonExe
    $VenvRoot = Split-Path -Parent $ScriptsDir
    return (Test-Path (Join-Path $VenvRoot "Lib\site-packages\$ModuleName"))
}

if ((Test-Path $PlatformPython) -and (Test-PythonModule $PlatformPython "fastapi")) {
    $Python = $PlatformPython
} elseif (Test-Path $BridgePython) {
    $Python = $BridgePython
} else {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $Python = $PythonCommand.Source
    }
}

$Vite = Join-Path $Root "frontend\node_modules\.bin\vite.cmd"

if (-not $Python) {
    throw "Python executable not found. Please activate your conda base environment or install Python first."
}

if (-not (Test-Path $Vite)) {
    throw "Frontend dependencies are missing. Please run corepack pnpm --dir .\frontend install first."
}

function Test-PortListening([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

# --- 后端：显式 PowerShell 窗口 ---
if (-not (Test-PortListening 8000)) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '=== 平台后端 (FastAPI :8000) ===' -ForegroundColor Cyan; cd '$Root'; python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000"
} else {
    Write-Host "[跳过] 端口 8000 已被占用"
}

# --- 前端：显式 PowerShell 窗口 ---
if (-not (Test-PortListening 5173)) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host '=== 平台前端 (Vite :5173) ===' -ForegroundColor Cyan; cd '$Root\frontend'; & '$Vite' --host 0.0.0.0 --port 5173"
} else {
    Write-Host "[跳过] 端口 5173 已被占用"
}

# --- 防火墙 ---
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$IsAdministrator = ([Security.Principal.WindowsPrincipal]$Identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($IsAdministrator) {
    foreach ($Port in 5173, 8000, 3001, 3000) {
        $RuleName = "ACOINFO IoT Platform TCP $Port"
        if (-not (Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $RuleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Any | Out-Null
        }
    }
} else {
    Write-Warning "Not running as administrator. Run this script once as administrator if other computers cannot connect."
}

Start-Sleep -Seconds 2
$LanAddress = Get-NetIPConfiguration |
    Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
    ForEach-Object { $_.IPv4Address.IPAddress } |
    Where-Object { $_ -and $_ -match "^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)" } |
    Select-Object -First 1

Write-Host "IoT platform started"
Write-Host "Local URL: http://127.0.0.1:5173"
if ($LanAddress) {
    Write-Host "LAN URL: http://${LanAddress}:5173"
} else {
    Write-Warning "No usable LAN IPv4 address was found."
}
