# 用途：为习惯 make 的 Linux/WSL 用户提供短入口；Windows 可直接运行 Python。
# 输入/输出/工具由 scripts/run.py 定义，此文件不重复维护命令细节。
# v0 提供 sim / synth / structures；structures 是第二周结构实验。
PYTHON ?= python3
.PHONY: all sim synth structures scan atpg
all:
	$(PYTHON) scripts/run_all.py
sim:
	$(PYTHON) scripts/run.py sim
synth:
	$(PYTHON) scripts/run.py synth
structures:
	$(PYTHON) scripts/run.py structures
# v3 扩展：Python 检查实际依赖并保存日志；此处不重复工具流程。
scan:
	$(PYTHON) scripts/run_scan.py
atpg:
	$(PYTHON) scripts/run_atpg.py
