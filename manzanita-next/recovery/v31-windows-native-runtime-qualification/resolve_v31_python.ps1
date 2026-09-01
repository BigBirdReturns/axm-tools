Set-StrictMode -Version Latest

function Add-V31PythonCandidate {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][AllowEmptyCollection()][System.Collections.Generic.List[object]]$Rows,
    [Parameter(Mandatory=$true)][string]$Path,
    [string[]]$Prefix=@(),
    [Parameter(Mandatory=$true)][string]$Source
  )
  if ([string]::IsNullOrWhiteSpace($Path)) { return }
  $full = $Path
  try { $full = [IO.Path]::GetFullPath($Path) } catch { }
  $key = ($full + '|' + ($Prefix -join ' ')).ToLowerInvariant()
  foreach ($row in $Rows) { if ($row.key -eq $key) { return } }
  $Rows.Add([pscustomobject]@{ key=$key; path=$full; prefix=@($Prefix); source=$Source })
}

function Invoke-V31PythonProbe {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string[]]$Prefix=@(),
    [int]$MinimumMajor=3,
    [int]$MinimumMinor=10
  )
  $passed=$false
  $version=$null
  $executable=$null
  $errorText=$null
  $exitCode=$null
  try {
    $code = "import json,sys; print(json.dumps({'version':list(sys.version_info[:3]),'executable':sys.executable})); raise SystemExit(0 if sys.version_info >= ($MinimumMajor,$MinimumMinor) else 17)"
    $probe = & $Path @($Prefix) -I -B -c $code 2>&1
    $exitCode=$LASTEXITCODE
    if($exitCode -eq 0){
      $parsed=($probe | Select-Object -Last 1 | ConvertFrom-Json)
      $version=@($parsed.version)
      $executable=[string]$parsed.executable
      if($version.Count -ge 2 -and ([int]$version[0] -gt $MinimumMajor -or ([int]$version[0] -eq $MinimumMajor -and [int]$version[1] -ge $MinimumMinor))){
        $passed=$true
      } else {
        $errorText='probe returned a version below the admitted floor'
      }
    } else {
      $errorText=($probe | Out-String).Trim()
    }
  } catch {
    $errorText=$_.Exception.Message
  }
  return [pscustomobject]@{
    path=$Path; prefix=@($Prefix); probe_passed=$passed; version=$version;
    executable=$executable; exit_code=$exitCode; error=$errorText
  }
}

function Resolve-V31Python {
  [CmdletBinding()]
  param([int]$MinimumMajor=3,[int]$MinimumMinor=10)
  $rows=[System.Collections.Generic.List[object]]::new()
  foreach($command in @(
    @{name='py.exe';prefix=@('-3');source='PATH_PY3_LAUNCHER'},
    @{name='python3.exe';prefix=@();source='PATH_PYTHON3'},
    @{name='python.exe';prefix=@();source='PATH_PYTHON'}
  )){
    $resolved=Get-Command $command.name -ErrorAction SilentlyContinue
    if($null -ne $resolved -and -not [string]::IsNullOrWhiteSpace($resolved.Source)){
      Add-V31PythonCandidate -Rows $rows -Path $resolved.Source -Prefix $command.prefix -Source $command.source
    }
  }
  $globs=@(
    @{pattern=(Join-Path $env:USERPROFILE '.cache\codex-runtimes\*\dependencies\python\python.exe');source='CODEX_DEPENDENCY_RUNTIME'},
    @{pattern=(Join-Path $env:USERPROFILE '.cache\codex-runtimes\*\python\python.exe');source='CODEX_RUNTIME'},
    @{pattern=(Join-Path $env:LOCALAPPDATA 'Programs\Python\Python*\python.exe');source='USER_LOCAL_PYTHON'},
    @{pattern=(Join-Path $env:ProgramFiles 'Python*\python.exe');source='PROGRAM_FILES_PYTHON'}
  )
  foreach($item in $globs){
    foreach($path in @(Get-ChildItem -Path $item.pattern -File -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)){
      Add-V31PythonCandidate -Rows $rows -Path $path.FullName -Prefix @() -Source $item.source
    }
  }
  $observations=[System.Collections.Generic.List[object]]::new()
  foreach($candidate in $rows){
    $probe=Invoke-V31PythonProbe -Path $candidate.path -Prefix $candidate.prefix -MinimumMajor $MinimumMajor -MinimumMinor $MinimumMinor
    $observations.Add([pscustomobject]@{
      source=$candidate.source;path=$candidate.path;prefix=@($candidate.prefix);
      probe_passed=$probe.probe_passed;version=$probe.version;executable=$probe.executable;
      exit_code=$probe.exit_code;error=$probe.error
    })
    if($probe.probe_passed){
      return [pscustomobject]@{
        result='PASS_SUPPORTED_PYTHON_RUNTIME_RESOLVED'
        selected=[pscustomobject]@{source=$candidate.source;path=$candidate.path;prefix=@($candidate.prefix);version=$probe.version;executable=$probe.executable}
        observations=@($observations)
      }
    }
  }
  return [pscustomobject]@{result='HOLD_NO_SUPPORTED_PYTHON_RUNTIME_FOUND';selected=$null;observations=@($observations)}
}

function Install-V31PythonShims {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory=$true)]$Runtime,
    [Parameter(Mandatory=$true)][string]$ShimRoot
  )
  if($Runtime.result -ne 'PASS_SUPPORTED_PYTHON_RUNTIME_RESOLVED'){throw 'runtime is not admitted'}
  if(Test-Path -LiteralPath $ShimRoot){Remove-Item -LiteralPath $ShimRoot -Recurse -Force}
  New-Item -ItemType Directory -Path $ShimRoot -Force | Out-Null
  $env:V31_PYTHON_EXE=[string]$Runtime.selected.path
  $env:V31_PYTHON_PREFIX=(@($Runtime.selected.prefix) -join [char]31)
  $env:V31_PYTHON_PREFIX_CMD=(@($Runtime.selected.prefix) -join ' ')
  $driver=@'
from __future__ import annotations

import os
import subprocess
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "--keep"
arguments = list(sys.argv[2:])
if mode == "--strip-py3" and arguments[:1] == ["-3"]:
    arguments = arguments[1:]
executable = os.environ["V31_PYTHON_EXE"]
prefix = [item for item in os.environ.get("V31_PYTHON_PREFIX", "").split("\x1f") if item]
completed = subprocess.run([executable, *prefix, *arguments], check=False)
raise SystemExit(completed.returncode)
'@
  $driverPath=Join-Path $ShimRoot 'Invoke-ResolvedPython.py'
  [IO.File]::WriteAllText($driverPath,$driver,[Text.UTF8Encoding]::new($false))
  $py='@echo off'+"`r`n"+'setlocal EnableExtensions DisableDelayedExpansion'+"`r`n"+'"%V31_PYTHON_EXE%" %V31_PYTHON_PREFIX_CMD% -I -B "%~dp0Invoke-ResolvedPython.py" --strip-py3 %*'+"`r`n"+'exit /b %ERRORLEVEL%'+"`r`n"
  $python='@echo off'+"`r`n"+'setlocal EnableExtensions DisableDelayedExpansion'+"`r`n"+'"%V31_PYTHON_EXE%" %V31_PYTHON_PREFIX_CMD% -I -B "%~dp0Invoke-ResolvedPython.py" --keep %*'+"`r`n"+'exit /b %ERRORLEVEL%'+"`r`n"
  [IO.File]::WriteAllText((Join-Path $ShimRoot 'py.cmd'),$py,[Text.Encoding]::ASCII)
  [IO.File]::WriteAllText((Join-Path $ShimRoot 'python.cmd'),$python,[Text.Encoding]::ASCII)
  [IO.File]::WriteAllText((Join-Path $ShimRoot 'python3.cmd'),$python,[Text.Encoding]::ASCII)
  $env:PATH=$ShimRoot+';'+$env:PATH
  return [pscustomobject]@{root=$ShimRoot;driver='Invoke-ResolvedPython.py';aliases=@('py.cmd','python.cmd','python3.cmd');path_scope='current_process_only'}
}
