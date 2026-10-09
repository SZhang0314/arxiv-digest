# run_local.ps1 — 本地一键跑完整流水线并预览
# 用法：powershell -ExecutionPolicy Bypass -File run_local.ps1
#      powershell -ExecutionPolicy Bypass -File run_local.ps1 -Preview
param([switch]$Preview)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 密钥：优先环境变量，其次 keys.txt（一行一个 key）
if (-not $env:LLM_API_KEY -and (Test-Path "keys.txt")) {
    $env:LLM_API_KEY = (Get-Content "keys.txt" | Where-Object { $_ -and $_ -notmatch '^#' } | Select-Object -First 1)
}
if (-not $env:LLM_API_KEY) {
    Write-Error "未找到 LLM_API_KEY（设置环境变量或写 keys.txt）"
    exit 1
}

python scripts/fetch_arxiv.py
python scripts/translate.py
python scripts/review.py
python scripts/build_site.py

Write-Host "`n站点已生成：$root\docs\index.html"
if ($Preview) { Start-Process "$root\docs\index.html" }
