param(
    [string] $SecretPath = "$env:LOCALAPPDATA\HTExperts\renalia-agent-engine\RENALIA_SIGNING_SECRET.dpapi"
)

$ErrorActionPreference = "Stop"

$directory = Split-Path -Parent $SecretPath
New-Item -ItemType Directory -Force -Path $directory | Out-Null

$secret = Read-Host -AsSecureString "Enter RENALIA_SIGNING_SECRET"
if ($secret.Length -eq 0) {
    throw "RENALIA_SIGNING_SECRET cannot be empty."
}

$encrypted = ConvertFrom-SecureString -SecureString $secret
Set-Content -LiteralPath $SecretPath -Value $encrypted -NoNewline
Write-Host "RENALIA_SIGNING_SECRET stored with Windows DPAPI for the current user."
Write-Host "Secret path: $SecretPath"
