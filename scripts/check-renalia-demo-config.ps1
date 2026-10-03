param(
    [string] $EnvFile = ".env",
    [string] $SecretPath = "$env:LOCALAPPDATA\HTExperts\renalia-agent-engine\RENALIA_SIGNING_SECRET.dpapi"
)

$ErrorActionPreference = "Stop"

$required = @(
    "RENALIA_API_BASE_URL",
    "RENALIA_INSTALLATION_ID",
    "RENALIA_CREDENTIAL_ID",
    "RENALIA_REQUEST_TIMEOUT_SECONDS",
    "RENALIA_CHANNEL_MODE",
    "RENALIA_ENABLE_REAL_CHANNELS",
    "RENALIA_TEST_PHONE_E164",
    "RENALIA_TEST_DOCUMENT_SUFFIX",
    "RENALIA_TEST_BIRTH_DATE"
)

$values = @{}
if (Test-Path -LiteralPath $EnvFile) {
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            $values[$parts[0]] = $parts[1]
        }
    }
}

$missing = $required | Where-Object { -not $values.ContainsKey($_) -or [string]::IsNullOrWhiteSpace($values[$_]) }
if ($missing.Count -gt 0) {
    throw "Missing non-secret RENALIA demo config values: $($missing -join ', ')"
}

if ($values["RENALIA_ENABLE_REAL_CHANNELS"] -ne "false") {
    throw "RENALIA_ENABLE_REAL_CHANNELS must remain false for this demo."
}

if (-not (Test-Path -LiteralPath $SecretPath)) {
    Write-Host "Secret status: not configured. Run scripts\set-renalia-secret.ps1 when the secret is delivered securely."
} else {
    Write-Host "Secret status: configured in local DPAPI store."
}

Write-Host "Non-secret RENALIA demo config is present."
Write-Host "No signed requests were executed."
