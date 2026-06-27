#!/usr/bin/env pwsh
# Installs dependencies and prints the exact config for Claude Code and
# Claude Desktop on Windows, with absolute paths resolved for THIS machine.
# Re-run this on each PC after cloning. From PowerShell, in the repo:
#     .\install.ps1
# If blocked by execution policy, run once:
#     powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

# Desktop default output dir. Claude Desktop's working directory is
# unpredictable, so it needs an absolute path. Claude Code ignores this and
# saves into the current project's .\generated-images folder.
$OutDir = if ($env:IMAGE_OUTPUT_DIR) { $env:IMAGE_OUTPUT_DIR } else { Join-Path $env:USERPROFILE "gpt-image-output" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
  Write-Host "==> Installing dependencies with uv"
  uv sync
  $CmdBin = $uv.Source
  # --project (not --directory) so uv does NOT chdir into the repo. The server
  # then inherits the client's working directory, letting Claude Code images
  # land in the project you're working in.
  $CmdArgs = @("run", "--project", $RepoDir, "gpt-image-mcp")
} else {
  Write-Host "==> uv not found; creating a virtualenv with pip instead"
  python -m venv .venv
  & ".\.venv\Scripts\pip.exe" install --quiet --upgrade pip
  & ".\.venv\Scripts\pip.exe" install --quiet -e .
  $CmdBin = Join-Path $RepoDir ".venv\Scripts\gpt-image-mcp.exe"
  $CmdArgs = @()
}

# Backslashes must be doubled when embedded in JSON strings.
function ConvertTo-JsonPath($p) { return ($p -replace '\\', '\\') }

# JSON array of args, with paths escaped for the Desktop config block.
$argsJsonItems = $CmdArgs | ForEach-Object { '"' + (ConvertTo-JsonPath $_) + '"' }
$argsJson = "[" + ($argsJsonItems -join ", ") + "]"

# `claude mcp add` command for Claude Code. No IMAGE_OUTPUT_DIR on purpose: in
# Claude Code the server runs in your project's directory, so images default to
# .\generated-images inside whatever project you're working in.
$ccArgs = ($CmdArgs | ForEach-Object { '"' + $_ + '"' }) -join " "
$ccCmd = "claude mcp add gpt-image --scope user -e OPENAI_API_KEY=`$env:OPENAI_API_KEY -- `"$CmdBin`" $ccArgs"

$cmdBinJson = ConvertTo-JsonPath $CmdBin
$outDirJson = ConvertTo-JsonPath $OutDir

Write-Host @"

============================================================
 Install complete.
============================================================

1) CLAUDE CODE - set your key in this shell, then run the command below:

   `$env:OPENAI_API_KEY = "sk-..."
   $ccCmd

   Verify with:  claude mcp list      (and /mcp inside a session)
   Images save to .\generated-images inside whatever project you launch
   Claude Code from. For a fixed location add  -e IMAGE_OUTPUT_DIR="C:\path"
   to the command, or override per call with the tool's output_dir argument.

2) CLAUDE DESKTOP - add this block under "mcpServers" in your config file,
   replace sk-REPLACE_ME with your key, then FULLY quit & relaunch Desktop
   (quit from the system tray, not just the window X):

    "gpt-image": {
      "command": "$cmdBinJson",
      "args": $argsJson,
      "env": {
        "OPENAI_API_KEY": "sk-REPLACE_ME",
        "IMAGE_OUTPUT_DIR": "$outDirJson"
      }
    }

   Config file:
     %APPDATA%\Claude\claude_desktop_config.json
     Open it via Desktop: Settings > Developer > Edit Config

   Desktop images will be saved to: $OutDir
============================================================
"@
