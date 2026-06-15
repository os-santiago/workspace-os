param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ProfilePath = $PROFILE.CurrentUserAllHosts
)

$repoRootPath = (Resolve-Path $RepoRoot).Path
$scriptsPath = Join-Path $repoRootPath "scripts"
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

function Add-UserPathEntry {
    param([string]$Entry)

    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($current)) {
        [Environment]::SetEnvironmentVariable("Path", $Entry, "User")
        return
    }

    $parts = $current.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries)
    if ($parts -notcontains $Entry) {
        $updated = ($parts + $Entry) -join ';'
        [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    }
}

Add-UserPathEntry -Entry $scriptsPath
$env:Path = "$scriptsPath;$env:Path"

Write-Output "wos installed in $ProfilePath"
Write-Output "added_to_path=$scriptsPath"
