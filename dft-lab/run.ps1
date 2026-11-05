# 用途：Windows 的薄入口；真正的依赖顺序与失败处理只维护在 Python 中。
# 输入为传给 run_all.py 的 --iverilog / --vvp / --yosys 路径参数。
# 示例：.\run.ps1 --yosys yowasp-yosys；本机须先确保 python 可执行。
# v3：不隐藏失败码，不在 PowerShell 中重复实现 Scan 或 ATPG。
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python scripts/run_all.py @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
