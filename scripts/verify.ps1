$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Blender = Join-Path $Root ".tools\blender-4.5.11-windows-x64\blender.exe"
$Source = Join-Path $Root "surface_layer_studio"
$Dist = Join-Path $Root "dist"
$Package = Join-Path $Dist "surface_layer_studio-1.1.0.zip"
$Artifacts = Join-Path $Root "artifacts"
$Profile = Join-Path $Root ".tmp-profile-4.5.11"
$BlendArtifact = Join-Path $Artifacts "sls-smoke.blend"

if (-not (Test-Path -LiteralPath $Blender)) {
    throw "Blender 4.5.11 not found at $Blender"
}

New-Item -ItemType Directory -Force -Path $Dist, $Artifacts | Out-Null
if (Test-Path -LiteralPath $Profile) {
    $ResolvedProfile = (Resolve-Path -LiteralPath $Profile).Path
    $ExpectedPrefix = $Root + [IO.Path]::DirectorySeparatorChar
    if (-not $ResolvedProfile.StartsWith($ExpectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove temp profile outside workspace: $ResolvedProfile"
    }
    Remove-Item -LiteralPath $ResolvedProfile -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Profile | Out-Null

$env:BLENDER_USER_CONFIG = Join-Path $Profile "config"
$env:BLENDER_USER_SCRIPTS = Join-Path $Profile "scripts"
$env:BLENDER_USER_DATAFILES = Join-Path $Profile "datafiles"
$env:BLENDER_USER_EXTENSIONS = Join-Path $Profile "extensions"
New-Item -ItemType Directory -Force -Path @(
    $env:BLENDER_USER_CONFIG,
    $env:BLENDER_USER_SCRIPTS,
    $env:BLENDER_USER_DATAFILES,
    $env:BLENDER_USER_EXTENSIONS
) | Out-Null

function Invoke-BlenderMarker {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Marker,
        [string]$WorkingDirectory = $Root
    )
    Push-Location $WorkingDirectory
    try {
        $Output = & $Blender @Arguments 2>&1
        $Output | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0) {
            throw "Blender check failed with exit code $LASTEXITCODE; expected marker $Marker"
        }
        if (-not ($Output -match [regex]::Escape($Marker))) {
            throw "Blender exited successfully but did not print marker $Marker"
        }
    }
    finally {
        Pop-Location
    }
}

Push-Location $Root
try {
    python -m compileall -q surface_layer_studio tests
    if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
    python -m unittest discover -s tests -p "test_core.py" -v
    if ($LASTEXITCODE -ne 0) { throw "pure unit tests failed" }

    & $Blender --version
    if ($LASTEXITCODE -ne 0) { throw "Blender version probe failed" }
    & $Blender --factory-startup --command extension validate $Source
    if ($LASTEXITCODE -ne 0) { throw "source manifest validation failed" }
    & $Blender --factory-startup --command extension build --source-dir $Source --output-dir $Dist
    if ($LASTEXITCODE -ne 0) { throw "extension build failed" }
    & $Blender --factory-startup --command extension validate $Package
    if ($LASTEXITCODE -ne 0) { throw "built extension validation failed" }
    python -m unittest discover -s tests -p "test_*.py" -v
    if ($LASTEXITCODE -ne 0) { throw "package inspection failed" }

    Invoke-BlenderMarker -Marker "SLS_SMOKE_PASS" -Arguments @(
        "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_smoke.py"), "--",
        "--source-root", $Root, "--artifact", $BlendArtifact
    )
    Invoke-BlenderMarker -Marker "SLS_UI_SMOKE_PASS" -Arguments @(
        "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_ui_smoke.py"), "--",
        "--source-root", $Root
    )
    Invoke-BlenderMarker -Marker "SLS_IMPORT_SMOKE_PASS" -Arguments @(
        "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_import_smoke.py"), "--",
        "--source-root", $Root, "--fixture-dir", (Join-Path $Artifacts "pbr-fixture")
    )
    Invoke-BlenderMarker -Marker "SLS_REOPEN_PASS" -Arguments @(
        "--background", "--factory-startup", $BlendArtifact, "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_reopen_smoke.py"), "--",
        "--source-root", $Root
    )
    Invoke-BlenderMarker -Marker "SLS_DESK_SMOKE_PASS" -Arguments @(
        "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_desk_smoke.py"), "--",
        "--source-root", $Root, "--output", $Artifacts
    )
    Invoke-BlenderMarker -Marker "SLS_INSTALL_PASS" -Arguments @(
        "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_install_extension.py"), "--",
        "--zip", $Package
    ) -WorkingDirectory $Profile
    Invoke-BlenderMarker -Marker "SLS_INSTALLED_SMOKE_PASS" -Arguments @(
        "--background", "--python-exit-code", "1",
        "--python", (Join-Path $Root "tests\blender_installed_smoke.py")
    ) -WorkingDirectory $Profile
}
finally {
    Pop-Location
}

Write-Host "SLS_VERIFY_ALL_PASS"
