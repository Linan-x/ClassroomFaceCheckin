param(
    [Parameter(Mandatory = $true)]
    [string]$LegacyDataRoot
)

$ErrorActionPreference = "Stop"
$moduleRoot = Split-Path -Parent $PSScriptRoot

Push-Location $moduleRoot
try {
    & .\mvnw.cmd spring-boot:run "--spring-boot.run.arguments=--spring.main.web-application-type=none --legacy-verification.enabled=true --legacy-verification.root=$LegacyDataRoot"
    if ($LASTEXITCODE -ne 0) {
        throw "Legacy migration verification failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
