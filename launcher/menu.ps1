<#
.SYNOPSIS
    Interactive menu for run-demo.ps1 when it is run without arguments.

.DESCRIPTION
    Only asks and returns answers; run-demo.ps1 maps them onto its flags.
    Prompts go through -Reader (default Read-Host) so tests can script them.
    Keep this file ASCII: Windows PowerShell 5.1 reads .ps1 files as ANSI.
#>

$DefaultReader = { param($prompt) Read-Host $prompt }

# Above this the laptop itself becomes the bottleneck for both strategies.
$LaptopRpsLimit = 400

function Read-MenuChoice {
    <#
    .SYNOPSIS
        Show numbered options and return the chosen 1-based index.
    .DESCRIPTION
        Enter returns -Default; invalid answers are asked again.
    #>
    param([string]$Prompt, [string[]]$Options, [int]$Default = 1, [scriptblock]$Reader = $DefaultReader)

    Write-Host ""
    Write-Host $Prompt -ForegroundColor White
    for ($i = 0; $i -lt $Options.Count; $i++) {
        Write-Host ("  {0}) {1}" -f ($i + 1), $Options[$i])
    }
    while ($true) {
        $answer = ([string](& $Reader "Choose [$Default]")).Trim()
        if ($answer -eq "") { return $Default }
        $number = 0
        if ([int]::TryParse($answer, [ref]$number) -and $number -ge 1 -and $number -le $Options.Count) {
            return $number
        }
        Write-Host ("    pick a number from 1 to {0}" -f $Options.Count) -ForegroundColor Yellow
    }
}

function Read-MenuNumber {
    <#
    .SYNOPSIS
        Ask for a whole number >= -Min; Enter returns -Default.
    #>
    param([string]$Prompt, [int]$Default, [int]$Min = 0, [scriptblock]$Reader = $DefaultReader)

    while ($true) {
        $answer = ([string](& $Reader "$Prompt [$Default]")).Trim()
        if ($answer -eq "") { return $Default }
        $number = 0
        if ([int]::TryParse($answer, [ref]$number) -and $number -ge $Min) { return $number }
        Write-Host "    enter a whole number, $Min or more" -ForegroundColor Yellow
    }
}

function Read-MenuYesNo {
    <#
    .SYNOPSIS
        Ask a yes/no question; Enter means yes.
    #>
    param([string]$Prompt, [scriptblock]$Reader = $DefaultReader)

    while ($true) {
        $answer = ([string](& $Reader "$Prompt [Y/n]")).Trim().ToLower()
        if ($answer -eq "" -or $answer -eq "y" -or $answer -eq "yes") { return $true }
        if ($answer -eq "n" -or $answer -eq "no") { return $false }
        Write-Host "    answer y or n" -ForegroundColor Yellow
    }
}

function Get-LoadWarning {
    <#
    .SYNOPSIS
        Warning text for loads above $LaptopRpsLimit, else $null.
    #>
    param([int]$PeakRps)
    if ($PeakRps -le $LaptopRpsLimit) { return $null }
    return "Above $LaptopRpsLimit req/s the laptop itself (k6, nginx, every container) " +
           "becomes the bottleneck for both strategies, which muddies the comparison."
}

function Get-MenuEvents {
    <#
    .SYNOPSIS
        Module A's events as Id + Label objects, in dataset order.
    #>
    param([string]$EventsPath)
    $raw = Get-Content $EventsPath -Raw | ConvertFrom-Json
    # Not $event: that is a PowerShell automatic variable.
    foreach ($item in $raw) {
        $date = ([string]$item.date).Substring(0, 10)
        $type = ([string]$item.event_type) -replace "_", " "
        [pscustomobject]@{
            Id    = $item.event_id
            Label = "{0} {1}, {2}  ({3})" -f $item.board, $type, $date, $item.event_id
        }
    }
}

function Invoke-LauncherMenu {
    <#
    .SYNOPSIS
        Ask what to run, confirm, and return the answers.
    .OUTPUTS
        Hashtable: Mode (Demo | Compare | Start | Stop), EventId and Peak
        (Demo), PeakRps (Compare), Go ($false if declined at confirmation).
    #>
    param([object[]]$Events, [scriptblock]$Reader = $DefaultReader)

    $choice = @{ Mode = "Start"; EventId = "cbse_class12_2026"; Peak = 4; PeakRps = 250; Go = $false }

    $modes = @(
        "Live demo      - schedule an event, watch servers arrive before the rush",
        "Experiment     - reactive vs CASPER on the same traffic, about 9 min",
        "Just start it  - portal + dashboard, nothing scheduled",
        "Stop everything"
    )
    $mode = Read-MenuChoice -Prompt "CASPER - what do you want to run?" -Options $modes -Default 1 -Reader $Reader
    $choice.Mode = @("Demo", "Compare", "Start", "Stop")[$mode - 1]

    if ($choice.Mode -eq "Demo") {
        $labels = @($Events | ForEach-Object { $_.Label })
        $default = 1
        for ($i = 0; $i -lt $Events.Count; $i++) {
            if ($Events[$i].Id -eq $choice.EventId) { $default = $i + 1 }
        }
        $picked = Read-MenuChoice -Prompt "Which event? (from Module A)" -Options $labels -Default $default -Reader $Reader
        $choice.EventId = $Events[$picked - 1].Id
        Write-Host ""
        $choice.Peak = Read-MenuNumber -Prompt "Servers at the rush (0 = Module B's own number)" -Default 4 -Min 0 -Reader $Reader
        $summary = "Live demo: $($choice.EventId), " +
                   $(if ($choice.Peak -eq 0) { "Module B's server count" } else { "up to $($choice.Peak) servers" })
    } elseif ($choice.Mode -eq "Compare") {
        $loads = @(
            "Normal  - 250 req/s (CASPER plans 4 servers)",
            "Heavy   - 400 req/s (CASPER plans 6 servers)",
            "Custom"
        )
        $load = Read-MenuChoice -Prompt "How much traffic at the peak?" -Options $loads -Default 1 -Reader $Reader
        if ($load -eq 1) { $choice.PeakRps = 250 }
        elseif ($load -eq 2) { $choice.PeakRps = 400 }
        else {
            Write-Host ""
            $choice.PeakRps = Read-MenuNumber -Prompt "Peak requests per second" -Default 250 -Min 1 -Reader $Reader
        }
        $warning = Get-LoadWarning -PeakRps $choice.PeakRps
        if ($warning) { Write-Host "`n  $warning" -ForegroundColor Yellow }
        $summary = "Experiment at $($choice.PeakRps) req/s"
    } elseif ($choice.Mode -eq "Start") {
        $summary = "Portal + dashboard, nothing scheduled"
    } else {
        $summary = "Stop everything CASPER is running"
    }

    Write-Host ""
    Write-Host "  About to run: $summary" -ForegroundColor Cyan
    $choice.Go = Read-MenuYesNo -Prompt "Go?" -Reader $Reader
    return $choice
}
