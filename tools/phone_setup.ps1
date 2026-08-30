<#
.SYNOPSIS
    Publish Gridiron to your tailnet over TLS. Never to the public internet.

.DESCRIPTION
    The server keeps binding 127.0.0.1 and that does not change. `tailscale
    serve` puts a TLS listener in front of it that is reachable only from
    devices signed in to your own tailnet.

    Why not just bind 0.0.0.0 and forward a port:

      * 0.0.0.0 exposes the app to every device on whatever network the laptop
        happens to be joined to - a hotel wifi, a conference, a cafe.
      * A forwarded port exposes it to the internet, where it will be scanned
        within hours. The access token is good, but the best position is not
        being reachable at all.
      * `tailscale serve` is authenticated at the network layer by WireGuard
        before Gridiron's own token is ever asked for. Two independent gates.

    THIS IS `serve`, NOT `funnel`. `tailscale funnel` publishes to the public
    internet. This script will not configure it and the README says why.

.PARAMETER Remove
    Stop serving and leave the tailnet configuration clean.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\phone_setup.ps1
    powershell -ExecutionPolicy Bypass -File tools\phone_setup.ps1 -Remove
#>

[CmdletBinding()]
param(
    [switch]$Remove,
    [int]$Port = 8848
)

$ErrorActionPreference = "Stop"

$tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if ($null -eq $tailscale) {
    $candidate = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $candidate) {
        $tailscale = $candidate
    } else {
        Write-Host "Tailscale is not installed."
        Write-Host ""
        Write-Host "  1. Install it from https://tailscale.com/download"
        Write-Host "  2. Sign in on this machine AND on your phone, same account"
        Write-Host "  3. Run this script again"
        Write-Host ""
        Write-Host "Nothing was changed."
        exit 1
    }
} else {
    $tailscale = $tailscale.Source
}

if ($Remove) {
    Write-Host "Withdrawing Gridiron from the tailnet..."
    & $tailscale serve --https=443 off
    Write-Host "Done. The server is back to 127.0.0.1 only."
    exit 0
}

Write-Host "Checking tailnet status..."
$status = & $tailscale status --json 2>$null | ConvertFrom-Json
if ($null -eq $status -or $status.BackendState -ne "Running") {
    Write-Host "Tailscale is installed but not connected. Run: tailscale up"
    exit 1
}

$name = $status.Self.DNSName.TrimEnd('.')
Write-Host "  this machine is $name"

# HTTPS on the tailnet requires MagicDNS + HTTPS certificates enabled in the
# admin console. Say so plainly rather than failing with a certificate error.
Write-Host "Enabling the TLS listener..."
& $tailscale serve --bg --https=443 "http://127.0.0.1:$Port"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "That failed. The usual cause is HTTPS certificates not being"
    Write-Host "enabled for your tailnet. In the admin console:"
    Write-Host "    DNS -> enable MagicDNS, then enable HTTPS Certificates"
    Write-Host "Then run this script again."
    exit 1
}

Write-Host ""
Write-Host "Gridiron is on your tailnet:"
Write-Host ""
Write-Host "    https://$name/"
Write-Host ""
Write-Host "Open that on your phone while signed in to the same tailnet. You"
Write-Host "will be asked for the access token once, then 'Add to Home Screen'"
Write-Host "installs it as an app."
Write-Host ""
Write-Host "Verify it is NOT public:"
Write-Host "    tailscale serve status        # should list https:// and no funnel"
Write-Host "    tailscale funnel status       # should say no funnel configured"
Write-Host ""
Write-Host "To withdraw:  powershell -ExecutionPolicy Bypass -File tools\phone_setup.ps1 -Remove"
