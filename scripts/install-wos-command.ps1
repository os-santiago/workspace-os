param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ProfilePath = $PROFILE.CurrentUserAllHosts
)

$repoRootPath = (Resolve-Path $RepoRoot).Path
$scriptPath = Join-Path $repoRootPath "scripts/wos.ps1"
$marker = "# Workspace OS command"
$profileDirectory = Split-Path -Parent $ProfilePath

if (-not (Test-Path $profileDirectory)) {
    New-Item -ItemType Directory -Path $profileDirectory -Force | Out-Null
}

$profileContent = @'
# Workspace OS command
function wos {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$WorkspaceArgs
    )

    & "__SCRIPT_PATH__" @WorkspaceArgs
}
'@.Replace('__SCRIPT_PATH__', $scriptPath)

if (Test-Path $ProfilePath) {
    $existing = Get-Content $ProfilePath -Raw
    if ($existing -notmatch [regex]::Escape($marker)) {
        Add-Content -Path $ProfilePath -Value "`n$profileContent"
    }
} else {
    Set-Content -Path $ProfilePath -Value $profileContent
}

Write-Output "wos installed in $ProfilePath"
