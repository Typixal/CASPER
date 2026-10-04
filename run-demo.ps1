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
      6. -Demo: runs the real pipeline end to end --
            Module A validates the event dataset,
            Module B turns it into Predictions,
            Module C schedules a time-shifted copy of one of them,
         so the scale-up fires during the demo from B's actual output
      7. -Compare: runs Module D's experiment instead -- the same exam-day
         traffic replayed twice through k6, once with the reactive baseline
         scaling and once with CASPER's predictive policy, then writes the
         comparison to module-d-evaluation\results\ and the dashboard

    Then it STAYS IN THE FOREGROUND and waits. Press Ctrl+C (or close this
    window) and it tears everything back down: dashboard, policy, and the
    containers. Nothing is left running to eat memory after the demo.

    Use -Detach if you deliberately want it to launch and exit, leaving the
    demo up; you are then responsible for running `.\run-demo.ps1 -Stop`.

    Teardown is deliberately thorough. It stops:
      - the dashboard, policy and comparison processes this run started
        (tracked by PID)
      - any ORPHANED python or k6 process whose command line points inside
        this repo (a window closed by hand, a previous run that lost its PID
        file, a k6 run or reactive scaler the comparison started)
      - whatever is listening on the dashboard port
      - every container in the Module C compose project, plus orphans
    It never touches processes belonging to anything else on the machine --
    the command line has to point inside this repo folder.

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
    With -Demo: cap the peak replica count Module B predicted. Default 4 --
    B's real estimates (12-20) are a lot of containers for a laptop. Pass 0
    to use B's number unchanged.

.PARAMETER EventId
    With -Demo: which event's Prediction to schedule. Default
    cbse_class12_2026. Any event_id from module-a-ingestion\events.json.

.PARAMETER Compare
    Run Module D's reactive-vs-predictive experiment (~9 minutes) instead of
    the live demo. Cannot be combined with -Demo.

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
    .\run-demo.ps1 -Compare
    The experiment. Results land in module-d-evaluation\results\.

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
    [string]$EventId = "cbse_class12_2026",
    [switch]$Compare,
    [switch]$NoDashboard,
    [switch]$NoBrowser,
    [switch]$Detach,
    [switch]$KeepContainers,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

# --- Paths -----------------------------------------------------------------
$Root      = $PSScriptRoot
$ModuleA   = Join-Path $Root "module-a-ingestion"
$ModuleB   = Join-Path $Root "module-b-estimation"
$ModuleC   = Join-Path $Root "casper-module-c"
$ModuleD   = Join-Path $Root "module-d-evaluation"
$Dashboard = Join-Path $Root "dashboard"
$PidFile   = Join-Path $Root ".casper-demo.pid"

$ModuleAPython   = Join-Path $ModuleA   ".venv\Scripts\python.exe"
$ModuleBPython   = Join-Path $ModuleB   ".venv\Scripts\python.exe"
$ModuleCPython   = Join-Path $ModuleC   ".venv\Scripts\python.exe"
$ModuleDPython   = Join-Path $ModuleD   ".venv\Scripts\python.exe"
$DashboardPython = Join-Path $Dashboard ".venv\Scripts\python.exe"
$K6Exe           = Join-Path $ModuleD   "tools\k6.exe"

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
function Get-CasperProcesses {
    <#
        Every python or k6 process whose command line points inside THIS repo.

        Matching on the command line rather than just the image name is what
        makes this safe: an unrelated python doing real work on this machine
        is never touched, and a dashboard, policy, reactive scaler or k6 run
        whose window was closed by hand (so its PID file entry is stale) is
        still found. k6 is included because Module D's comparison runs it from
        module-d-evaluation\tools\k6.exe -- inside the repo, so it matches.
    #>
    $escaped = [System.Management.Automation.WildcardPattern]::Escape($Root)
    $filter = "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'k6.exe'"
    Get-CimInstance Win32_Process -Filter $filter -ErrorAction SilentlyContinue |
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
    foreach ($key in @("dashboard", "policy", "compare")) {
        if ($saved[$key]) { [void](Stop-ProcessSafely -ProcessId ([int]$saved[$key]) -Label $key) }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue

    # 2. Orphans: anything python or k6 running out of this repo that
    #    survived -- the comparison's child processes (reactive scaler, k6,
    #    Module C's policy), windows closed by hand, earlier runs.
    $orphans = @(Get-CasperProcesses)
    foreach ($orphan in $orphans) {
        [void](Stop-ProcessSafely -ProcessId $orphan.ProcessId -Label "orphaned $($orphan.Name)")
    }
    if ($orphans.Count -eq 0) { Write-Info "no orphaned python or k6 processes" }

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

# -Demo runs CASPER's predictive policy against the live stack; -Compare runs
# the reactive baseline AND the predictive policy itself, one after the
# other. Running both at once would put two brains on one knob and void the
# experiment, so refuse up front rather than produce meaningless numbers.
if ($Demo -and $Compare) {
    Write-Host "`n-Demo and -Compare cannot run together: both drive the scaling knob.`n" -ForegroundColor Red
    exit 1
}

# Clear out anything left over from a previous run before starting a new one,
# so replicas and dashboards never stack up across runs.
$leftovers = @(Get-CasperProcesses)
if ($leftovers.Count -gt 0) {
    Write-Step "Found $($leftovers.Count) leftover process(es) from an earlier run"
    foreach ($leftover in $leftovers) {
        [void](Stop-ProcessSafely -ProcessId $leftover.ProcessId -Label "leftover $($leftover.Name)")
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
if ($Demo) {
    Initialize-Venv -Directory $ModuleA -PythonPath $ModuleAPython -Label "Module A"
    Initialize-Venv -Directory $ModuleB -PythonPath $ModuleBPython -Label "Module B"
}
if ($Compare) {
    Initialize-Venv -Directory $ModuleD -PythonPath $ModuleDPython -Label "Module D"
    if (-not (Test-Path $K6Exe)) {
        Write-Info "k6 missing -- fetching it into module-d-evaluation\tools (one time)"
        & (Join-Path $ModuleD "tools\fetch_k6.ps1")
        if (-not (Test-Path $K6Exe)) { throw "could not fetch k6" }
    }
    Write-Ok "k6 present"
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
            # During the experiment the dashboard's own latency probe would
            # add traffic to the very thing being measured, so start it off.
            if ($Compare) { $env:CASPER_DASH_PROBE = "0" }
            $proc = Start-Process -FilePath $DashboardPython `
                                  -ArgumentList "app.py" `
                                  -WorkingDirectory $Dashboard `
                                  -PassThru
            Remove-Item Env:\CASPER_DASH_PROBE -ErrorAction SilentlyContinue
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

    # --- 6. The real pipeline: A -> B -> C --------------------------------
    if ($Demo) {
        if ($DownIn -le $UpIn) {
            throw "-DownIn ($DownIn) must be greater than -UpIn ($UpIn)"
        }

        Write-Step "Module A: validating the event dataset"
        Push-Location $ModuleA
        try {
            & $ModuleAPython loader.py
            if ($LASTEXITCODE -ne 0) { throw "Module A rejected the event dataset" }
        } finally {
            Pop-Location
        }

        Write-Step "Module B: estimating a Prediction for every event"
        Push-Location $ModuleB
        try {
            & $ModuleBPython estimate.py (Join-Path $ModuleA "events.json")
            if ($LASTEXITCODE -ne 0) { throw "Module B failed to produce predictions" }
        } finally {
            Pop-Location
        }

        $predictionFile = Join-Path $ModuleB "predictions\$EventId.json"
        if (-not (Test-Path $predictionFile)) {
            throw "Module B produced no prediction for '$EventId' -- is it an event_id in module-a-ingestion\events.json?"
        }
        $predicted = (Get-Content $predictionFile -Raw | ConvertFrom-Json).predicted_peak_replicas

        Write-Step "Module C: scheduling B's prediction for $EventId"
        # Real event dates are months away, so shift B's prediction to start in
        # -UpIn seconds. Its replica count is B's, capped by -Peak for a laptop.
        $shiftArgs = @("--source", $predictionFile, "--up-in", $UpIn, "--down-in", $DownIn)
        if ($Peak -gt 0) {
            $shiftArgs += @("--peak", $Peak)
            Write-Info "Module B predicted $predicted replicas; capped to $Peak for this laptop (-Peak 0 to use B's number)"
        } else {
            $Peak = $predicted
            Write-Info "using Module B's prediction unchanged: $predicted replicas"
        }

        Push-Location $ModuleC
        try {
            & $ModuleCPython (Join-Path $ModuleC "scripts\make_demo_prediction.py") @shiftArgs
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

    # --- 7. Module D: the experiment --------------------------------------
    if ($Compare) {
        Write-Step "Module D: reactive vs predictive comparison"
        & $ModuleDPython (Join-Path $ModuleD "run_comparison.py") --dry-run
        $proc = Start-Process -FilePath $ModuleDPython `
                              -ArgumentList "run_comparison.py" `
                              -WorkingDirectory $ModuleD `
                              -PassThru
        $pids["compare"] = $proc.Id
        Write-Ok "comparison running in its own window (pid $($proc.Id))"
        Write-Info "results land in module-d-evaluation\results\ and on the dashboard when it finishes"
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
        Write-Host "`n  Pipeline: A ($EventId) -> B prediction -> C policy."
        Write-Host "  Watch the dashboard: replicas appear while the timeline is still"
        Write-Host "  in the 'before' phase -- capacity provisioned ahead of traffic."
    } elseif ($Compare) {
        Write-Host "`n  Experiment running (~9 min). Leave this window open; when the"
        Write-Host "  comparison window finishes, the dashboard shows the result."
        Write-Host "  Charts: module-d-evaluation\results\*.png"
    } else {
        Write-Host "`n  Add -Demo for the A->B->C pipeline, or -Compare for the experiment."
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
