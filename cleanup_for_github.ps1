param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$keepBenchmark = "benchmark_20260731_024647"
$keepReview = "review-20260731-042323"

function Remove-DirectoryTree {
    param([string]$Path)

    $longPath = "\\?\" + [IO.Path]::GetFullPath($Path)
    cmd.exe /d /c "rd /s /q `"$longPath`""
    if (Test-Path -LiteralPath $Path) {
        throw "Could not remove directory: $Path"
    }
}

$fixedPaths = @(
    ".installed",
    "__pycache__",
    "tests\__pycache__",
    "mkdocs_preview\site",
    "analysis_output",
    "analysis_pdf",
    "analysis_pdf_visual",
    "test_results",
    "artifacts\after_docx",
    "artifacts\after_hybrid",
    "artifacts\after_hybrid_v2",
    "artifacts\after_verticalslice",
    "artifacts\after_visual",
    "artifacts\baseline",
    "artifacts\baseline_verticalslice_20260730_224127",
    "artifacts\before_after",
    "artifacts\endpoint_release_check",
    "artifacts\final_app_run"
)

$targets = [System.Collections.Generic.List[string]]::new()
foreach ($relativePath in $fixedPaths) {
    $targets.Add((Join-Path $root $relativePath))
}

$benchmarkRoot = Join-Path $root "artifacts\benchmarks"
if (Test-Path $benchmarkRoot) {
    Get-ChildItem $benchmarkRoot -Directory -Filter "benchmark_*" |
        Where-Object Name -ne $keepBenchmark |
        ForEach-Object { $targets.Add($_.FullName) }
}

$reviewRoot = Join-Path $root "artifacts\fidelity-reviews"
if (Test-Path $reviewRoot) {
    Get-ChildItem $reviewRoot -Directory -Filter "review-*" |
        Where-Object Name -ne $keepReview |
        ForEach-Object { $targets.Add($_.FullName) }
}

$parityRoot = Join-Path $root "artifacts\endpoint_release_check_live"
if (Test-Path $parityRoot) {
    Get-ChildItem $parityRoot -Directory -Filter "run_*" |
        ForEach-Object { $targets.Add($_.FullName) }
}

$existingTargets = $targets | Where-Object { Test-Path -LiteralPath $_ } | Sort-Object -Unique
$bytes = ($existingTargets | ForEach-Object {
    $item = Get-Item -LiteralPath $_
    if ($item.PSIsContainer) {
        (Get-ChildItem -LiteralPath $_ -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    } else {
        $item.Length
    }
} | Measure-Object -Sum).Sum

Write-Output ("Cleanup targets: {0}" -f $existingTargets.Count)
Write-Output ("Recoverable size: {0:N2} MiB" -f ($bytes / 1MB))

foreach ($target in $existingTargets) {
    $action = "Removing"
    if ($WhatIf) {
        $action = "Would remove"
    }
    Write-Output ($action + ": " + $target.Substring($root.Length + 1))
    if (-not $WhatIf) {
        $item = Get-Item -LiteralPath $target
        if ($item.PSIsContainer) {
            if ($target.EndsWith(".cleanup-delete")) {
                Remove-DirectoryTree $target
                continue
            }
            $staged = $target + ".cleanup-delete"
            if (Test-Path -LiteralPath $staged) {
                Remove-DirectoryTree $staged
            }
            try {
                Rename-Item -LiteralPath $target -NewName ([IO.Path]::GetFileName($staged))
                Remove-DirectoryTree $staged
            } catch {
                Remove-DirectoryTree $target
            }
        } else {
            Remove-Item -LiteralPath $target -Force
        }
    }
}
