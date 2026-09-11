<#
.SYNOPSIS
    Launches the whole CASPER demo with one command, and cleans up after itself.

.DESCRIPTION
    Brings up everything needed for a Phase I demo, in order:

      1. Checks Docker is running (starts Docker Desktop and waits, if not)
      2. Creates the Python virtual environments if they are missing
      3. Builds the portal image (first run, or with -Build)
      4. Scales the portal to a starting replica count
      5. Opens the live dashboard in its own window, then in the browser
      6. Optionally starts the predictive policy against a time-shifted
         Prediction, so the scale-up actually fires during the demo

    Then it STAYS IN THE FOREGROUND and waits. Press Ctrl+C (or close this
    window) and it tears everything back down: dashboard, policy, and the
    containers. Nothing is left running to eat memory after the demo.

    Use -Detach if you deliberately want it to launch and exit, leaving the
    demo up; you are then responsible for running `.\run-demo.ps1 -Stop`.

    Teardown is deliberately thorough. It stops:
      - the dashboard and policy processes this run started (tracked by PID)
      - any ORPHANED python process whose command line points inside this
        repo (a window closed by hand, a previous run that lost its PID file)
      - whatever is listening on the dashboard port
      - every container in the Module C compose project, plus orphans
    It never touches python processes belonging to anything else on the
    machine -- the command line has to point inside this repo folder.

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

.PARAMETER Detach
    Launch everything and exit immediately, leaving it running. Without this,
    the script waits and cleans up when you press Ctrl+C.

.PARAMETER KeepContainers
    On teardown, stop the dashboard and policy but leave the containers up.

.PARAMETER Stop
    Don't launch anything -- just tear down whatever is currently running.

.EXAMPLE
    .\run-demo.ps1 -Demo
    Full demo. Ctrl+C when finished and everything is cleaned up.

.EXAMPLE
    .\run-demo.ps1 -Stop
    Clean up a demo that was started with -Detach, or left over from a crash.

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
    [switch]$Detach,
    [switch]$KeepContainers,
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
function Write-Step { param([string]$Text) Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "    $Text" -ForegroundColor Green }
function Write-Info { param([string]$Text) Write-Host "    $Text" -ForegroundColor Gray }
function Write-Warn { param([string]$Text) Write-Host "    $Text" -ForegroundColor Yellow }

function Test-Port {
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
    param([int]$Port, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-Docker {
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

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
function Get-CasperPythonProcesses {
    <#
        Every python process whose command line points inside THIS repo.

        Matching on the command line rather than just the image name is what
        makes this safe: an unrelated python doing real work on this machine
        is never touched, and a dashboard or policy window that was closed by
        hand (so its PID file entry is stale) is still found.
    #>
    $escaped = [System.Management.Automation.WildcardPattern]::Escape($Root)
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$escaped*" -and $_.ProcessId -ne $PID }
}

function Stop-ProcessSafely {
    param([int]$ProcessId, [string]$Label)
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $proc) { return $false }
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Ok "stopped $Label (pid $ProcessId)"
        return $true
    } catch {
        Write-Warn "could not stop $Label (pid $ProcessId): $($_.Exception.Message)"
        return $false
    }
}

function Invoke-Teardown {
    param([switch]$LeaveContainers)

    Write-Step "Cleaning up"

    # 1. Processes this run started, by recorded PID.
    $saved = Get-SavedPids
    foreach ($key in @("dashboard", "policy")) {
        if ($saved[$key]) { [void](Stop-ProcessSafely -ProcessId ([int]$saved[$key]) -Label $key) }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue

    # 2. Orphans: anything python running out of this repo that survived.
    #    Catches windows closed by hand and processes left by earlier runs.
    $orphans = @(Get-CasperPythonProcesses)
    foreach ($orphan in $orphans) {
        [void](Stop-ProcessSafely -ProcessId $orphan.ProcessId -Label "orphaned python")
    }
    if ($orphans.Count -eq 0) { Write-Info "no orphaned python processes" }

    # 3. Anything still holding the dashboard port.
    $listeners = @(Get-NetTCPConnection -LocalPort $DashboardPort -State Listen -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        [void](Stop-ProcessSafely -ProcessId $listener.OwningProcess -Label "port $DashboardPort listener")
    }

    # 4. Containers.
    if ($LeaveContainers) {
        Write-Info "leaving containers running (-KeepContainers)"
    } elseif (Test-Docker) {
        Push-Location $ModuleC
        # docker compose writes its progress ("Container ... Stopping") to
        # stderr, which $ErrorActionPreference = "Stop" would otherwise turn
        # into a thrown error even on a completely successful teardown.
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            docker compose down --remove-orphans 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "containers and network removed"
            } else {
                Write-Warn "docker compose down exited with code $LASTEXITCODE"
            }
        } catch {
            Write-Warn "docker compose down failed: $($_.Exception.Message)"
        } finally {
            $ErrorActionPreference = $previousPreference
            Pop-Location
        }
    } else {
        Write-Info "Docker not running -- no containers to stop"
    }

    Write-Host "`nAll clean. The audit log in casper-module-c\logs\ is untouched.`n" -ForegroundColor White
}

function Initialize-Venv {
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
# Shutdown-only path
# ===========================================================================
if ($Stop) {
    Write-Host "`nCASPER -- shutting the demo down" -ForegroundColor White
    Invoke-Teardown -LeaveContainers:$KeepContainers
    exit 0
}

# ===========================================================================
# Startup
# ===========================================================================
Write-Host "`nCASPER -- Civic-event-Aware Scheduling for Predictive Elastic Resources" -ForegroundColor White
Write-Host "Starting the local demo" -ForegroundColor Gray

# Clear out anything left over from a previous run before starting a new one,
# so replicas and dashboards never stack up across runs.
$leftovers = @(Get-CasperPythonProcesses)
if ($leftovers.Count -gt 0) {
    Write-Step "Found $($leftovers.Count) leftover process(es) from an earlier run"
    foreach ($leftover in $leftovers) {
        [void](Stop-ProcessSafely -ProcessId $leftover.ProcessId -Label "leftover python")
    }
}

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
Initialize-Venv -Directory $ModuleC -PythonPath $ModuleCPython -Label "Module C"
if (-not $NoDashboard) {
    Initialize-Venv -Directory $Dashboard -PythonPath $DashboardPython -Label "dashboard"
}

# --- 3 & 4. Build and scale -----------------------------------------------
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

    Write-Step "Scaling the portal to $Replicas replica(s)"
    & $ModuleCPython (Join-Path $ModuleC "controller\scale_controller.py") $Replicas
    if ($LASTEXITCODE -ne 0) { throw "the scale controller failed" }
} finally {
    Pop-Location
}

$pids = @{}

try {
    # --- 5. Dashboard ------------------------------------------------------
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

    # --- 6. Predictive policy ---------------------------------------------
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

    # --- Summary -----------------------------------------------------------
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
    Write-Host "  Scale by hand      : casper-module-c\.venv\Scripts\python.exe casper-module-c\controller\scale_controller.py 5"

    if ($Detach) {
        Write-Host "`n  Running detached. Shut down with: .\run-demo.ps1 -Stop`n" -ForegroundColor Yellow
        exit 0
    }

    Write-Host "`n  Press Ctrl+C to shut everything down and clean up." -ForegroundColor Cyan
    Write-Host ""

    # Block here. The finally below runs on Ctrl+C, so the demo never
    # outlives this window unless -Detach was passed.
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    if (-not $Detach) {
        Invoke-Teardown -LeaveContainers:$KeepContainers
    }
}
