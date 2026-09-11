<#
.SYNOPSIS
    Launches the whole CASPER demo with one command.

.DESCRIPTION
    Brings up everything needed for a Phase I demo, in order:

      1. Checks Docker is running (starts Docker Desktop and waits, if not)
      2. Creates the Python virtual environments if they are missing
      3. Builds the portal image (first run, or with -Build)
      4. Scales the portal to a starting replica count
      5. Opens the live dashboard in its own window, then in the browser
      6. Optionally starts the predictive policy against a time-shifted
         Prediction, so the scale-up actually fires during the demo

    Each long-running piece gets its own console window on purpose: during the
    demo you want the policy's "PLANNED / EXECUTING" lines visible on screen,
    not buried in a background job.

    This is a convenience wrapper only. Every step below can still be run by
    hand exactly as the module READMEs describe -- nothing here is required to
    use the system.

    TEMPORARY: this covers Modules C and the dashboard, the only pieces built
    so far. Extend it as Modules A, B and D land.

.PARAMETER Replicas
    Starting replica count. Default 2.

.PARAMETER Build
    Force `docker compose build` even if the image already exists.

.PARAMETER Demo
    Also launch the predictive policy against a time-shifted Prediction, so it
    scales up shortly after launch instead of on a real exam date.

.PARAMETER UpIn
    With -Demo: seconds from now until the scale-up fires. Default 20.

.PARAMETER DownIn
    With -Demo: seconds from now until the scale-down fires. Default 120.

.PARAMETER Peak
    With -Demo: peak replica count to scale up to. Default 4. The real
    prediction says 12, which is a lot of containers for a laptop.

.PARAMETER NoDashboard
    Skip the dashboard.

.PARAMETER NoBrowser
    Start the dashboard but do not open a browser window.

.PARAMETER Stop
    Tear the demo down: stop the dashboard and policy windows, then
    `docker compose down`.

.EXAMPLE
    .\run-demo.ps1
    Stack + dashboard, 2 replicas, nothing scheduled.

.EXAMPLE
    .\run-demo.ps1 -Demo -UpIn 20 -DownIn 120 -Peak 4
    Full demo: watch the dashboard scale up on its own before the traffic.

.EXAMPLE
    .\run-demo.ps1 -Stop
    Shut everything down.

.NOTES
    If PowerShell refuses to run this file:
        powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
#>

[CmdletBinding()]
param(
    [int]$Replicas = 2,
    [switch]$Build,
    [switch]$Demo,
    [int]$UpIn = 20,
    [int]$DownIn = 120,
    [int]$Peak = 4,
    [switch]$NoDashboard,
    [switch]$NoBrowser,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

# --- Paths -----------------------------------------------------------------
$Root      = $PSScriptRoot
$ModuleC   = Join-Path $Root "casper-module-c"
$Dashboard = Join-Path $Root "dashboard"
$PidFile   = Join-Path $Root ".casper-demo.pid"

$ModuleCPython   = Join-Path $ModuleC   ".venv\Scripts\python.exe"
$DashboardPython = Join-Path $Dashboard ".venv\Scripts\python.exe"

$DashboardPort = 8050
$PortalPort    = 8080

# --- Small helpers ---------------------------------------------------------
function Write-Step   { param([string]$Text) Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok     { param([string]$Text) Write-Host "    $Text" -ForegroundColor Green }
function Write-Info   { param([string]$Text) Write-Host "    $Text" -ForegroundColor Gray }
function Write-Warn   { param([string]$Text) Write-Host "    $Text" -ForegroundColor Yellow }

function Test-Port {
    <# Is something listening on this local port? #>
    param([int]$Port)
    $client = New-Object Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port {
    <# Wait until a port answers, or give up. #>
    param([int]$Port, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-Docker {
    <# True when the Docker daemon answers. #>
    try {
        docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Save-Pids {
    param([hashtable]$Pids)
    $Pids | ConvertTo-Json | Set-Content -Path $PidFile -Encoding utf8
}

function Get-SavedPids {
    if (-not (Test-Path $PidFile)) { return @{} }
    try {
        $raw = Get-Content $PidFile -Raw | ConvertFrom-Json
        $table = @{}
        foreach ($prop in $raw.PSObject.Properties) { $table[$prop.Name] = $prop.Value }
        return $table
    } catch {
        return @{}
    }
}

function Stop-TrackedProcess {
    <# Stop a process this script started, if it is still ours and alive. #>
    param([string]$Label, [int]$ProcessId)
    if (-not $ProcessId) { return }
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        Write-Info "$Label (pid $ProcessId) already stopped"
        return
    }
    # Only ever kill a python process -- the PID could have been recycled by
    # something else entirely since the file was written.
    if ($proc.ProcessName -notlike "python*") {
        Write-Warn "$Label pid $ProcessId is now '$($proc.ProcessName)', not python. Leaving it alone."
        return
    }
    Stop-Process -Id $ProcessId -Force
    Write-Ok "$Label stopped (pid $ProcessId)"
}

function Initialize-Venv {
    <#
        Create a virtual environment and install its requirements if it is not
        there yet. The pip cache is kept inside the project folder so nothing
        lands on the C: drive.
    #>
    param([string]$Directory, [string]$PythonPath, [string]$Label)

    if (Test-Path $PythonPath) {
        Write-Info "$Label venv present"
        return
    }

    Write-Info "$Label venv missing -- creating it (one time, ~30s)"
    Push-Location $Directory
    try {
        $env:PIP_CACHE_DIR = Join-Path $Directory ".pip-cache"
        python -m venv .venv
        if (-not (Test-Path $PythonPath)) {
            throw "Failed to create the $Label virtual environment. Is Python 3.10+ on PATH?"
        }
        & $PythonPath -m pip install --quiet --disable-pip-version-check -r requirements.txt
        Write-Ok "$Label venv ready"
    } finally {
        Pop-Location
    }
}

# ===========================================================================
# Shutdown path
# ===========================================================================
if ($Stop) {
    Write-Host "`nCASPER -- shutting the demo down" -ForegroundColor White

    Write-Step "Stopping dashboard and policy"
    $saved = Get-SavedPids
    Stop-TrackedProcess -Label "dashboard" -ProcessId $saved["dashboard"]
    Stop-TrackedProcess -Label "policy"    -ProcessId $saved["policy"]
    Remove-Item $PidFile -ErrorAction SilentlyContinue

    Write-Step "Stopping containers (docker compose down)"
    if (Test-Docker) {
        Push-Location $ModuleC
        try {
            docker compose down
            Write-Ok "containers removed"
        } finally {
            Pop-Location
        }
    } else {
        Write-Warn "Docker is not running -- nothing to stop"
    }

    Write-Host "`nDone. The audit log in casper-module-c\logs\ is untouched.`n" -ForegroundColor White
    exit 0
}

# ===========================================================================
# Startup path
# ===========================================================================
Write-Host "`nCASPER -- Civic-event-Aware Scheduling for Predictive Elastic Resources" -ForegroundColor White
Write-Host "Starting the local demo" -ForegroundColor Gray

# --- 1. Docker -------------------------------------------------------------
Write-Step "Checking Docker"
if (Test-Docker) {
    Write-Ok "Docker daemon is up"
} else {
    Write-Warn "Docker daemon is not responding -- trying to start Docker Desktop"

    $desktopCandidates = @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe",
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    )
    $desktop = $desktopCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $desktop) {
        Write-Host "`nCould not find Docker Desktop. Start it manually, then re-run this script.`n" -ForegroundColor Red
        exit 1
    }

    Start-Process $desktop
    Write-Info "waiting for the engine (up to 3 minutes)..."
    $deadline = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $deadline -and -not (Test-Docker)) {
        Start-Sleep -Seconds 5
    }

    if (-not (Test-Docker)) {
        Write-Host "`nDocker did not come up in time. Start Docker Desktop manually and re-run.`n" -ForegroundColor Red
        exit 1
    }
    Write-Ok "Docker daemon is up"
}

# --- 2. Virtual environments ----------------------------------------------
Write-Step "Checking Python environments"
Initialize-Venv -Directory $ModuleC   -PythonPath $ModuleCPython   -Label "Module C"
if (-not $NoDashboard) {
    Initialize-Venv -Directory $Dashboard -PythonPath $DashboardPython -Label "dashboard"
}

# --- 3. Build the portal image --------------------------------------------
Push-Location $ModuleC
try {
    $imageExists = (docker images -q casper-module-c-portal 2>$null)
    if ($Build -or -not $imageExists) {
        Write-Step "Building the portal image"
        docker compose build
        if ($LASTEXITCODE -ne 0) { throw "docker compose build failed" }
        Write-Ok "image built"
    } else {
        Write-Step "Portal image already built (use -Build to rebuild)"
    }

    # --- 4. Scale to the starting replica count ---------------------------
    Write-Step "Scaling the portal to $Replicas replica(s)"
    & $ModuleCPython (Join-Path $ModuleC "controller\scale_controller.py") $Replicas
    if ($LASTEXITCODE -ne 0) { throw "the scale controller failed" }
} finally {
    Pop-Location
}

$pids = Get-SavedPids

# --- 5. Dashboard ----------------------------------------------------------
if (-not $NoDashboard) {
    Write-Step "Starting the dashboard"
    if (Test-Port -Port $DashboardPort) {
        Write-Warn "port $DashboardPort is already in use -- reusing whatever is there"
    } else {
        $proc = Start-Process -FilePath $DashboardPython `
                              -ArgumentList "app.py" `
                              -WorkingDirectory $Dashboard `
                              -PassThru
        $pids["dashboard"] = $proc.Id
        if (Wait-Port -Port $DashboardPort -TimeoutSeconds 30) {
            Write-Ok "dashboard live on http://localhost:$DashboardPort (pid $($proc.Id))"
        } else {
            Write-Warn "dashboard did not answer on port $DashboardPort -- check its window"
        }
    }

    if (-not $NoBrowser) {
        Start-Process "http://localhost:$DashboardPort"
    }
}

# --- 6. Predictive policy --------------------------------------------------
if ($Demo) {
    Write-Step "Scheduling the predictive policy"

    if ($DownIn -le $UpIn) {
        throw "-DownIn ($DownIn) must be greater than -UpIn ($UpIn)"
    }

    Push-Location $ModuleC
    try {
        & $ModuleCPython (Join-Path $ModuleC "scripts\make_demo_prediction.py") `
            --up-in $UpIn --down-in $DownIn --peak $Peak
        if ($LASTEXITCODE -ne 0) { throw "could not write the demo prediction" }
    } finally {
        Pop-Location
    }

    $proc = Start-Process -FilePath $ModuleCPython `
                          -ArgumentList @("policy\predictive_policy.py", "policy\demo_prediction.json") `
                          -WorkingDirectory $ModuleC `
                          -PassThru
    $pids["policy"] = $proc.Id
    Write-Ok "policy running (pid $($proc.Id))"
    Write-Info "scale UP in ~$UpIn s to $Peak replicas, scale DOWN in ~$DownIn s"
}

Save-Pids -Pids $pids

# --- Summary ---------------------------------------------------------------
Write-Host "`n---------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host " CASPER demo is up" -ForegroundColor White
Write-Host "---------------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Portal (via nginx) : http://localhost:$PortalPort/results"
if (-not $NoDashboard) {
    Write-Host "  Dashboard          : http://localhost:$DashboardPort"
}
Write-Host "  Audit log          : casper-module-c\logs\scale_actions.jsonl"
if ($Demo) {
    Write-Host "`n  Watch the dashboard: replicas appear while the timeline is still"
    Write-Host "  in the 'before' phase -- capacity provisioned ahead of traffic."
} else {
    Write-Host "`n  Add -Demo to have the predictive policy scale up on its own."
}
Write-Host "`n  Scale by hand      : casper-module-c\.venv\Scripts\python.exe casper-module-c\controller\scale_controller.py 5"
Write-Host "  Shut down          : .\run-demo.ps1 -Stop"
Write-Host ""
