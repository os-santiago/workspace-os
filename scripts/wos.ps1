param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$WorkspaceArgs
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot "config/workspace.sources.example.json"

if (-not $WorkspaceArgs -or $WorkspaceArgs.Count -eq 0) {
    $WorkspaceArgs = @("shell")
}

& python -m workspace_os --config $configPath @WorkspaceArgs
exit $LASTEXITCODE
