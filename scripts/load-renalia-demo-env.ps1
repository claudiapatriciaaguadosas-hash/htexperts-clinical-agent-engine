param(
    [string] $EnvFile = ".env",
    [string] $SecretPath = "$env:LOCALAPPDATA\HTExperts\renalia-agent-engine\RENALIA_SIGNING_SECRET.dpapi"
)

$ErrorActionPreference = "Stop"

if (Test-Path -LiteralPath $EnvFile) {
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }
        $parts = $line.Split("=", 2)
        if ($parts.Count -eq 2) {
            [Environment]::SetEnvironmentVariable($parts[0], $parts[1], "Process")
        }
    }
}

if (-not (Test-Path -LiteralPath $SecretPath)) {
    throw "RENALIA_SIGNING_SECRET is not stored. Run scripts\set-renalia-secret.ps1 first."
}

$encrypted = Get-Content -LiteralPath $SecretPath -Raw
$secure = ConvertTo-SecureString -String $encrypted
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [Environment]::SetEnvironmentVariable("RENALIA_SIGNING_SECRET", $plain, "Process")
} finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

Write-Host "RENALIA demo environment loaded for this process."
Write-Host "No signed requests were executed."
