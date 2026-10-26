# Puts the board software on a board's CIRCUITPY drive:
#   gamehost/ and every game in a folder (games/rush/)      compiled to .mpy (no compiling on the board, which takes
#                                                          more RAM than running them)
#   games in one file (games/paint.py, clock, ...)         compiled to .mpy too: the game picker loads a game's card
#                                                          while another game is running, and compiling a big one
#                                                          there runs out of memory. Their sources go to games/src/
#                                                          on the drive, which the board doesn't load: to change one
#                                                          there, edit it and copy it into games/ (a .py is loaded
#                                                          before a .mpy)
#   code.py, Lemnos.html                                   copied (the page was Salient.html before the board
#                                                          was named Lemnos: an old one is removed)
#   config.py                                              only if the drive has none: it's the board's own wiring
# settings.toml, lib/ and anything else on the drive are left alone. Only files that changed are written. A .py on
# the drive that a new .mpy replaces is removed (CircuitPython would load the .py first), and so is a .mpy whose
# game is now a .py, and old modules no longer in the source.
# The compiler is Adafruit's mpy-cross for the board's exact CircuitPython version (read from boot_out.txt),
# downloaded the first time into %LOCALAPPDATA%\Lemnos\.
#
#   powershell -ExecutionPolicy Bypass -File tools\deploy.ps1                finds the CIRCUITPY drive
#   powershell -ExecutionPolicy Bypass -File tools\deploy.ps1 -Drive E: -DryRun   says what it would do
param([string]$Drive, [switch]$DryRun)
$ErrorActionPreference = "Stop"
$src = Split-Path -Parent $PSScriptRoot

# ---- the drive and its CircuitPython version
if (-not $Drive) {
    $vol = Get-Volume | Where-Object { $_.FileSystemLabel -eq "CIRCUITPY" -and $_.DriveLetter } | Select-Object -First 1
    if (-not $vol) { throw "No CIRCUITPY drive found. Plug the board in, or name the drive: -Drive E:" }
    $Drive = "$($vol.DriveLetter):"
}
$root = $Drive.TrimEnd("\") + "\"
$bootOut = Join-Path $root "boot_out.txt"
if (-not (Test-Path $bootOut)) { throw "$root has no boot_out.txt: is it a CircuitPython board?" }
$m = [regex]::Match((Get-Content $bootOut -TotalCount 1), "CircuitPython (\S+)")
if (-not $m.Success) { throw "Can't read the CircuitPython version from $bootOut" }
$version = $m.Groups[1].Value

# ---- the compiler
$cache = Join-Path $env:LOCALAPPDATA "Lemnos"
$exe = Join-Path $cache "mpy-cross-windows-$version.static.exe"
if (-not (Test-Path $exe)) {
    New-Item -ItemType Directory -Force $cache | Out-Null
    $url = "https://adafruit-circuit-python.s3.amazonaws.com/bin/mpy-cross/windows/mpy-cross-windows-$version.static.exe"
    "Downloading mpy-cross $version"
    $tmp = "$exe.download"
    try { Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing }
    catch { throw "Couldn't download $url ($($_.Exception.Message)). Put mpy-cross for CircuitPython $version at $exe." }
    Move-Item -Force $tmp $exe
}

# ---- what goes where: drive path -> file to copy (compiled ones built first)
$build = Join-Path ([System.IO.Path]::GetTempPath()) "lemnos-build"
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
$plan = [ordered]@{}
$compiledDirs = @("gamehost") + @(Get-ChildItem (Join-Path $src "games") -Directory |
    Where-Object { $_.Name -notlike "_*" -and (Test-Path (Join-Path $_.FullName "game.py")) } |
    ForEach-Object { "games/" + $_.Name })
Push-Location $src
try {
    foreach ($dir in $compiledDirs) {
        foreach ($f in Get-ChildItem $dir -Filter *.py -File) {
            $rel = "$dir/$($f.Name)"
            if ($f.Name -eq "__init__.py") { $plan[$rel] = $f.FullName; continue }
            $out = Join-Path $build ($rel -replace "\.py$", ".mpy")
            New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
            & $exe -o $out $rel                      # relative, so tracebacks say gamehost/host.py
            if ($LASTEXITCODE -ne 0) { throw "mpy-cross failed on $rel" }
            $plan[($rel -replace "\.py$", ".mpy")] = $out
        }
    }
} finally { Pop-Location }
Push-Location $src
try {
    foreach ($f in Get-ChildItem (Join-Path $src "games") -Filter *.py -File) {
        $rel = "games/$($f.Name)"
        if ($f.Name -eq "__init__.py") { $plan[$rel] = $f.FullName; continue }
        $out = Join-Path $build ($rel -replace "\.py$", ".mpy")
        New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
        & $exe -o $out $rel
        if ($LASTEXITCODE -ne 0) { throw "mpy-cross failed on $rel" }
        $plan[($rel -replace "\.py$", ".mpy")] = $out
        $plan["games/src/$($f.Name)"] = $f.FullName           # the source, to read and change (not loaded)
    }
} finally { Pop-Location }
$plan["code.py"] = Join-Path $src "code.py"
$plan["Lemnos.html"] = Join-Path $src "Lemnos.html"
if (-not (Test-Path (Join-Path $root "config.py"))) { $plan["config.py"] = Join-Path $src "config.py" }

# ---- remove what would shadow or outlive the new files
$remove = @()
foreach ($rel in $plan.Keys) {
    if ($rel -like "*.mpy") { $other = $rel -replace "\.mpy$", ".py" }
    elseif ($rel -like "*.py") { $other = $rel -replace "\.py$", ".mpy" }
    else { continue }
    if (Test-Path (Join-Path $root $other)) { $remove += $other }
}
if (Test-Path (Join-Path $root "Salient.html")) { $remove += "Salient.html" }
foreach ($dir in $compiledDirs + @("games", "games/src")) {
    $d = Join-Path $root $dir
    if (-not (Test-Path $d)) { continue }
    foreach ($f in Get-ChildItem $d -File | Where-Object { $_.Extension -in ".py", ".mpy" }) {
        $rel = "$dir/$($f.Name)"
        if (-not $plan.Contains($rel) -and $remove -notcontains $rel) { $remove += $rel }
    }
}

# ---- write
$written = 0; $same = 0
foreach ($rel in $plan.Keys) {
    $to = Join-Path $root $rel
    $from = $plan[$rel]
    if ((Test-Path $to) -and ([System.IO.File]::ReadAllBytes($to).Length -eq (Get-Item $from).Length) -and
        $null -eq (Compare-Object ([System.IO.File]::ReadAllBytes($to)) ([System.IO.File]::ReadAllBytes($from)) -SyncWindow 0)) {
        $same++
        continue
    }
    "  write  $rel"
    if (-not $DryRun) {
        $dir = Split-Path $to
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }   # (not the drive's root)
        Copy-Item -Force $from $to
    }
    $written++
}
foreach ($rel in $remove) {
    "  remove $rel"
    if (-not $DryRun) { Remove-Item -Force (Join-Path $root $rel) }
}
if ($DryRun) { "Would write $written, remove $($remove.Count); $same unchanged, on $root (CircuitPython $version)." }
else { "Wrote $written, removed $($remove.Count); $same unchanged, on $root (CircuitPython $version)." }
