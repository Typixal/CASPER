<#
.SYNOPSIS
    Downloads a pinned k6 release into module-d-evaluation\tools\k6.exe.

.DESCRIPTION
    Keeps k6 inside the project instead of installing it system-wide.
    tools\ is gitignored, so run this once per clone. Does nothing if the
    pinned version is already present.

.PARAMETER Version
    k6 release tag. Default v2.3.0.
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
# Windows PowerShell 5.1 may default to TLS below 1.2.
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
