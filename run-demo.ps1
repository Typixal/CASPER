<#
.SYNOPSIS
    Launches the whole CASPER demo with one command, and cleans up after itself.

.DESCRIPTION
    Steps:
      1. Ensure Docker is running (starts Docker Desktop if needed)
      2. Create missing Python venvs
      3. Build the portal image (first run or -Build)
      4. Scale the portal to -Replicas
      5. Start the dashboard and open the browser
      6. -Demo: Module A validates events, Module B predicts, Module C
         schedules a time-shifted copy of one prediction
      7. -Compare: Module D's reactive-vs-predictive experiment

    With no arguments, an interactive menu chooses the mode.

    Stays in the foreground; Ctrl+C tears down everything it started:
    tracked processes, orphaned CASPER python/k6 processes, the dashboard
    port listener and the Module C containers. Only CASPER's own entry-point
    scripts are matched, never other processes. -Detach exits instead and
    leaves teardown to -Stop.

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

.PARAMETER PeakRps
    With -Compare: peak requests per second in the traffic curve. Default 250
    (CASPER plans 4 servers). 400 needs 6. The reactive scaler's ceiling is
    raised to match CASPER's whenever CASPER plans more than 6, so heavier
    load stays a fair test. Above 400 the laptop itself starts to be the
    bottleneck; the script warns.

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
    .\run-demo.ps1
    No arguments: a menu asks what to run (live demo, experiment and its
    load, just start, or stop), then confirms before doing anything.

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
    [int]$PeakRps = 250,
    [switch]$NoDashboard,
    [switch]$NoBrowser,
    [switch]$Detach,
    [switch]$KeepContainers,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

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

# Console output helpers.
function Write-Step { param([string]$Text) Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Text) Write-Host "    $Text" -ForegroundColor Green }
function Write-Info { param([string]$Text) Write-Host "    $Text" -ForegroundColor Gray }
function Write-Warn { param([string]$Text) Write-Host "    $Text" -ForegroundColor Yellow }

function Test-Port {
    <#
    .SYNOPSIS
        True if something accepts TCP connections on localhost:$Port.
    #>
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
    <#
    .SYNOPSIS
        Poll Test-Port until it succeeds or the timeout passes; returns the outcome.
    #>
    param([int]$Port, [int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port -Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-Docker {
    <#
    .SYNOPSIS
        True if the Docker daemon answers.
    #>
    try {
        docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Save-Pids {
    <#
    .SYNOPSIS
        Record started process ids in the pid file, for teardown.
    #>
    param([hashtable]$Pids)
    $Pids | ConvertTo-Json | Set-Content -Path $PidFile -Encoding utf8
}

function Get-SavedPids {
    <#
    .SYNOPSIS
        Read the pid file as a hashtable; empty if missing or unreadable.
    #>
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

# Only these entry points are swept; matching on the repo path alone also
# caught IDE tooling running from project venvs.
$CasperScripts = '(app|predictive_policy|reactive_baseline|run_comparison|scale_controller|loader|estimate|make_demo_prediction)\.py'

function Get-CasperProcesses {
    <#
    .SYNOPSIS
        CASPER's own python and k6 processes, and nothing else.
    .DESCRIPTION
        Matches python running one of $CasperScripts from inside this repo,
        and the k6.exe in module-d-evaluation\tools.
    #>
    $escaped = [System.Management.Automation.WildcardPattern]::Escape($Root)
    $k6Escaped = [System.Management.Automation.WildcardPattern]::Escape($ModuleD)
    $filter = "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'k6.exe'"
    Get-CimInstance Win32_Process -Filter $filter -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ProcessId -ne $PID -and $_.CommandLine -and (
                ($_.Name -eq 'k6.exe' -and $_.ExecutablePath -like "$k6Escaped*") -or
                ($_.CommandLine -like "*$escaped*" -and $_.CommandLine -match $CasperScripts)
            )
        }
}

function Stop-ProcessSafely {
    <#
    .SYNOPSIS
        Force-stop a process if it exists; returns whether it was stopped.
    #>
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
    <#
    .SYNOPSIS
        Stop everything CASPER started: processes, port listener, containers.
    .PARAMETER LeaveContainers
        Keep the Module C containers running.
    #>
    param([switch]$LeaveContainers)

    Write-Step "Cleaning up"

    # Processes this run started.
    $saved = Get-SavedPids
    foreach ($key in @("dashboard", "policy", "compare")) {
        if ($saved[$key]) { [void](Stop-ProcessSafely -ProcessId ([int]$saved[$key]) -Label $key) }
    }
    Remove-Item $PidFile -ErrorAction SilentlyContinue

    # Orphans: the comparison's children, windows closed by hand, earlier runs.
    $orphans = @(Get-CasperProcesses)
    foreach ($orphan in $orphans) {
        [void](Stop-ProcessSafely -ProcessId $orphan.ProcessId -Label "orphaned $($orphan.Name)")
    }
    if ($orphans.Count -eq 0) { Write-Info "no orphaned python or k6 processes" }

    $listeners = @(Get-NetTCPConnection -LocalPort $DashboardPort -State Listen -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        [void](Stop-ProcessSafely -ProcessId $listener.OwningProcess -Label "port $DashboardPort listener")
    }

    if ($LeaveContainers) {
        Write-Info "leaving containers running (-KeepContainers)"
    } elseif (Test-Docker) {
        Push-Location $ModuleC
        # Compose writes progress to stderr, which "Stop" would turn into an error.
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
    <#
    .SYNOPSIS
        Create a module's .venv and install its requirements, if missing.
    .DESCRIPTION
        pip's cache stays inside the module folder.
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

# No arguments: ask what to run.
. (Join-Path $Root "launcher\menu.ps1")

# Skipped when stdin is redirected, rather than hang.
if ($PSBoundParameters.Count -eq 0 -and -not [Console]::IsInputRedirected) {
    $menu = Invoke-LauncherMenu -Events @(Get-MenuEvents -EventsPath (Join-Path $ModuleA "events.json"))
    if (-not $menu.Go) {
        Write-Host "`nNothing started.`n" -ForegroundColor Gray
        exit 0
    }
    switch ($menu.Mode) {
        "Demo"    { $Demo = [switch]$true; $EventId = $menu.EventId; $Peak = $menu.Peak }
        "Compare" { $Compare = [switch]$true; $PeakRps = $menu.PeakRps }
        "Stop"    { $Stop = [switch]$true }
    }
}

if ($Stop) {
    Write-Host "`nCASPER -- shutting the demo down" -ForegroundColor White
    Invoke-Teardown -LeaveContainers:$KeepContainers
    exit 0
}

Write-Host "`nCASPER -- Civic-event-Aware Scheduling for Predictive Elastic Resources" -ForegroundColor White
Write-Host "Starting the local demo" -ForegroundColor Gray

# Both drive the scaling knob; together they would void the experiment.
if ($Demo -and $Compare) {
    Write-Host "`n-Demo and -Compare cannot run together: both drive the scaling knob.`n" -ForegroundColor Red
    exit 1
}

# Clear leftovers from earlier runs so nothing stacks up.
$leftovers = @(Get-CasperProcesses)
if ($leftovers.Count -gt 0) {
    Write-Step "Found $($leftovers.Count) leftover process(es) from an earlier run"
    foreach ($leftover in $leftovers) {
        [void](Stop-ProcessSafely -ProcessId $leftover.ProcessId -Label "leftover $($leftover.Name)")
    }
}

# 1. Docker
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

# 2. Virtual environments
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

# 3-4. Build and scale
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
    # 5. Dashboard
    if (-not $NoDashboard) {
        Write-Step "Starting the dashboard"
        if (Test-Port -Port $DashboardPort) {
            Write-Warn "port $DashboardPort is already in use -- reusing whatever is there"
        } else {
            # The probe would add traffic to the measured run: start it off and locked.
            if ($Compare) {
                $env:CASPER_DASH_PROBE = "0"
                $env:CASPER_DASH_PROBE_LOCKED = "1"
            }
            $proc = Start-Process -FilePath $DashboardPython `
                                  -ArgumentList "app.py" `
                                  -WorkingDirectory $Dashboard `
                                  -PassThru
            Remove-Item Env:\CASPER_DASH_PROBE -ErrorAction SilentlyContinue
            Remove-Item Env:\CASPER_DASH_PROBE_LOCKED -ErrorAction SilentlyContinue
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

    # 6. Pipeline A -> B -> C
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
        # Shift B's prediction to start in -UpIn seconds; cap replicas at -Peak.
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

    # 7. Module D experiment
    if ($Compare) {
        Write-Step "Module D: reactive vs predictive comparison"
        & $ModuleDPython (Join-Path $ModuleD "run_comparison.py") --dry-run --peak-rps $PeakRps
        $loadWarning = Get-LoadWarning -PeakRps $PeakRps
        if ($loadWarning) { Write-Warn $loadWarning }
        $proc = Start-Process -FilePath $ModuleDPython `
                              -ArgumentList @("run_comparison.py", "--hold", "--peak-rps", $PeakRps) `
                              -WorkingDirectory $ModuleD `
                              -PassThru
        $pids["compare"] = $proc.Id
        Write-Ok "comparison running in its own window (pid $($proc.Id))"
        Write-Info "results land in module-d-evaluation\results\ and on the dashboard when it finishes"
    }

    Save-Pids -Pids $pids

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

    # Wait; the finally below tears down on Ctrl+C.
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    if (-not $Detach) {
        Invoke-Teardown -LeaveContainers:$KeepContainers
    }
}
