# Pester 3.4 tests for menu.ps1, driven by scripted answers.
#     Invoke-Pester .\launcher

. (Join-Path $PSScriptRoot "menu.ps1")

function New-Reader {
    # Returns the answers in order; throws if the menu asks one question too many.
    param([string[]]$Answers)
    $queue = New-Object System.Collections.Queue
    foreach ($answer in $Answers) { $queue.Enqueue($answer) }
    return { param($prompt) if ($queue.Count -eq 0) { throw "unexpected prompt: $prompt" }; $queue.Dequeue() }.GetNewClosure()
}

$events = @(
    [pscustomobject]@{ Id = "cbse_class12_2026"; Label = "CBSE, 2026-05-13" },
    [pscustomobject]@{ Id = "ssc_cgl_result_2026"; Label = "SSC, 2026-07-20" }
)

Describe "Read-MenuChoice" {
    It "takes the default on Enter" {
        Read-MenuChoice -Prompt "Pick" -Options @("a", "b", "c") -Default 2 -Reader (New-Reader @("")) | Should Be 2
    }

    It "takes a valid number" {
        Read-MenuChoice -Prompt "Pick" -Options @("a", "b", "c") -Default 1 -Reader (New-Reader @("3")) | Should Be 3
    }

    It "asks again after an answer that is not one of the options" {
        Read-MenuChoice -Prompt "Pick" -Options @("a", "b") -Default 1 -Reader (New-Reader @("9", "x", "2")) | Should Be 2
    }
}

Describe "Read-MenuNumber" {
    It "takes the default on Enter" {
        Read-MenuNumber -Prompt "Servers" -Default 4 -Min 0 -Reader (New-Reader @("")) | Should Be 4
    }

    It "asks again for something below the minimum or not a number" {
        Read-MenuNumber -Prompt "Load" -Default 250 -Min 1 -Reader (New-Reader @("0", "lots", "300")) | Should Be 300
    }
}

Describe "Read-MenuYesNo" {
    It "defaults to yes" {
        Read-MenuYesNo -Prompt "Go?" -Reader (New-Reader @("")) | Should Be $true
    }

    It "accepts n as no" {
        Read-MenuYesNo -Prompt "Go?" -Reader (New-Reader @("n")) | Should Be $false
    }
}

Describe "Get-LoadWarning" {
    It "is quiet up to 400 req/s" {
        Get-LoadWarning -PeakRps 400 | Should BeNullOrEmpty
    }

    It "warns above 400 req/s that the laptop becomes the bottleneck" {
        Get-LoadWarning -PeakRps 401 | Should Match "laptop"
    }
}

Describe "Get-MenuEvents" {
    It "lists every event in Module A's dataset with a readable label" {
        $path = Join-Path $PSScriptRoot "..\module-a-ingestion\events.json"
        $list = @(Get-MenuEvents -EventsPath $path)

        $list.Count | Should Be 6
        ($list | Where-Object { $_.Id -eq "cbse_class12_2026" }).Label | Should Match "CBSE"
    }
}

Describe "Invoke-LauncherMenu" {
    It "live demo with every default" {
        $choice = Invoke-LauncherMenu -Events $events -Reader (New-Reader @("1", "", "", ""))

        $choice.Mode | Should Be "Demo"
        $choice.EventId | Should Be "cbse_class12_2026"
        $choice.Peak | Should Be 4
        $choice.Go | Should Be $true
    }

    It "live demo for another event using Module B's own number" {
        $choice = Invoke-LauncherMenu -Events $events -Reader (New-Reader @("1", "2", "0", "y"))

        $choice.EventId | Should Be "ssc_cgl_result_2026"
        $choice.Peak | Should Be 0
    }

    It "experiment at normal load is the default" {
        $choice = Invoke-LauncherMenu -Events $events -Reader (New-Reader @("2", "", ""))

        $choice.Mode | Should Be "Compare"
        $choice.PeakRps | Should Be 250
    }

    It "experiment at heavy load" {
        (Invoke-LauncherMenu -Events $events -Reader (New-Reader @("2", "2", ""))).PeakRps | Should Be 400
    }

    It "experiment at a custom load" {
        (Invoke-LauncherMenu -Events $events -Reader (New-Reader @("2", "3", "550", ""))).PeakRps | Should Be 550
    }

    It "just start it asks nothing more than confirmation" {
        $choice = Invoke-LauncherMenu -Events $events -Reader (New-Reader @("3", ""))

        $choice.Mode | Should Be "Start"
        $choice.Go | Should Be $true
    }

    It "stop everything" {
        (Invoke-LauncherMenu -Events $events -Reader (New-Reader @("4", ""))).Mode | Should Be "Stop"
    }

    It "answering no at the end launches nothing" {
        (Invoke-LauncherMenu -Events $events -Reader (New-Reader @("2", "", "n"))).Go | Should Be $false
    }
}
