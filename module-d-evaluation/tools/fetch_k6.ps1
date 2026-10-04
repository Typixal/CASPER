<#
.SYNOPSIS
    Downloads a pinned k6 release into module-d-evaluation\tools\k6.exe.

.DESCRIPTION
    k6 is a single standalone binary, not a Python package. This drops it
    inside the project folder so nothing is installed system-wide and the C:
    drive stays clean. tools\ is gitignored; re-run this on a fresh clone.

    Idempotent: does nothing if the pinned version is already present.
    Needs internet once, at fetch time. Running k6 afterwards does not.
#>

[CmdletBinding()]
param(
    [string]$Version = "v2.3.0"
)

$ErrorActionPreference = "Stop"

$ToolsDir = $PSScriptRoot
$Exe      = Join-Path $ToolsDir "k6.exe"

if (Test-Path $Exe) {
    $installed = (& $Exe version) -join " "
    if ($installed -match [regex]::Escape($Version.TrimStart("v"))) {
        Write-Host "k6 $Version already present at $Exe"
        exit 0
    }
    Write-Host "Replacing k6 ($installed) with $Version"
}

$name    = "k6-$Version-windows-amd64"
$url     = "https://github.com/grafana/k6/releases/download/$Version/$name.zip"
$zip     = Join-Path $ToolsDir "$name.zip"
$extract = Join-Path $ToolsDir $name

Write-Host "Downloading $url"
# TLS 1.2 explicitly: Windows PowerShell 5.1 can default to older protocols.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

try {
    Expand-Archive -Path $zip -DestinationPath $ToolsDir -Force
    Copy-Item (Join-Path $extract "k6.exe") $Exe -Force
} finally {
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
}

& $Exe version
Write-Host "k6 ready at $Exe"
