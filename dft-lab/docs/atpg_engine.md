# ATPG 故障仿真与全 DUT 扫描回放

这一阶段让同一组故障从网表结构、约束搜索、独立仿真走到真实扫描链。输入是 `netlist/v0/design.json` 中保留下来的 `fault_cone`；该组合锥在完整 DUT 中由 `word_q[4:0]` 驱动，并由 `neg_status[2:1]` 捕获。

运行顺序是先生成 v1/v2 扫描网表，再执行：

```text
python scripts/run_atpg.py --scan-replay
python tests/test_atpg_replay.py
```

Icarus 不在 PATH 时传 `--iverilog` 与 `--vvp`。脚本把工具所在目录加入子进程 PATH，以便 Windows 下的 `ivl` 找到配套 DLL。命令可从任何目录启动，工程路径从脚本本身定位。

## 实际范围

本模型有 5 个 PI、6 个门、11 条唯一逻辑线。对每条线注入 SA0 和 SA1，合计 **22 个未折叠 stem 故障**。一个 stem 故障影响该线全部扇出，不等同于只影响某一个接收端的 branch 故障。别名共享同一个 Yosys bit，不能多次计入故障分母。

本模型不包括 SDFF 内部、时钟、复位、memory 阵列、其余组合锥、bridge 和 transition 故障。下文的 86.36% 是该组合 cut 的实测 fault coverage，不是全芯片覆盖率。

`fault_sim.py` 按 `cells[*].connections` 构建门连接，先进行拓扑排序，再执行 AND/OR/NOT。它拒绝未知门类型、宽总线与组合环，不用名字猜测布尔表达式。Yosys 隐藏的反相器输出也计入故障列表，显示为 `net_10`；它对应 `~a`，不是额外虚构的一条信号。

## 算法与回溯

`atpg.py` 实现简化 D-cube 搜索：

1. 激活故障，让正常值等于 stuck 值的反值。
2. 枚举故障到观察端的候选传播路径，使路径上 AND 的旁输入为 1、OR 的旁输入为 0。
3. 用门的 singular cover 逆向解释内部目标。例如 AND=0 有两个选择 `0X` 与 `X0`，不能强制两个输入都为 0。
4. 把解释逐层下推至 PI。两条路径对同一个 PI 提出矛盾要求时，撤销该 cube 的局部分支并尝试下一种解释。
5. 每次 PI 赋值后前向蕴涵，显示好/坏值形成的 0、1、D、D̅、X。补齐未约束 PI 后，用独立双电路仿真确认确实观察到差异。

这是“路径敏化 + D-cube justification”的教学子集，没有实现完整工业 D/J-frontier、学习、复杂代价函数和任意多路径证明，也不是 PODEM。只有经过独立穷举核对，本 cut 的搜索耗尽才在报告中升级为 `PROVEN_UNTESTABLE_IN_CUT`。对其他电路，搜索失败只能叫 `SEARCH_EXHAUSTED`。

**实际 q/SA1 回溯：**激活需要 q=0。q 是 `~a & c`，先选 `~a=0`，因此 a=1。传播经过 OR 时要求 p=0；p 是 `a & b`，第一种解释要求 a=0，与已确定的 a=1 冲突。算法撤销这一解释，改选 b=0，得到向量 **a=1、b=0、c=0、d=0、e=0**。正常 q=0、故障 q=1，reconv 也形成 D̅。`reports/atpg/summary.json` 的 `trace_demo.trace` 保存全部 objective、justify、assign、imply、conflict、backtrack、fill、detect 事件。

对 CS 学员而言，内部目标相当于约束条件，门 cover 相当于可选的推理规则，PI 字典是当前部分赋值，递归返回则撤销该分支。此实现用小字典副本提高可读性；大网表通常用 implication trail 记录和撤销赋值，以减少复制开销。

## 独立核对与不可测证明

ATPG 生成向量时不读取穷举结果。运行器在生成后遍历全部 32 个输入组合，以独立 `fault_sim.py` 核对每个故障是否存在检测向量；在两个观察集合下分别核对 22 个故障。随后导出实际 JSON 门连接为 Verilog，让 Icarus 独立计算全部 **32 × 22 = 704** 组好/坏输出，再逐项与 Python 核对。

现有两个输出下有 19 个可测故障、3 个不可测故障：

| 故障 | 为什么不可测 | 证明范围 |
|---|---|---|
| e/SA0 | e 只影响 r=d&e；d=0 时 r 被置0，d=1 时 redundant 的直通 d 把输出固定为1 | 32 个输入组合穷举 |
| e/SA1 | 与上项相同，e 的变化被吸收律屏蔽 | 32 个输入组合穷举 |
| r/SA0 | 正常 r=1 必须 d=1，而 redundant=d OR r 已被 d 固定为1 | 32 个输入组合穷举 |

r/SA1 可测：d=0 时正常输出0，故障输出1。不能因为一条支路冗余就说其两种 stuck-at 都不可测。

已有输出全部可测故障被检测后，fault coverage 为 **19/22 = 86.36%**；排除已证明不可测故障后的 test coverage 为 **19/19 = 100%**。两种指标分开保存，图表分母一直是22。

## 覆盖率改善与 X 边界

曲线使用固定随机种子 `20261105` 的前6个向量，然后选取仍未覆盖故障的真实 ATPG 向量。第6个向量后为16/22；第7个确定性向量后为19/22。曲线每个点都由故障仿真累计，未手填预期高度。

新增 r 观察点的组合模型对照可达到22/22。它代表为这个冗余锥添加可观察端的效果，**并不意味着 v2 已插入 r 的扫描观察寄存器**。v2 的 memory bypass 与 shadow parity 观察属于其他结构，不得把两者混在同一个覆盖率数字中。

X 对照把该 cut 的 a 边界设为未知。在 a=X、b=1、c=0 时，p/SA0 的正常输出不确定，因此不能算检测。将 a 通过已知边界控制为1后才可检测。这个实验解释 memory X 如何阻断判断，但不产生 memory 阵列故障覆盖率。

## 完整 DUT 回放

`scan_replay()` 读取 `reports/scan_chains.json`，找到实际 `u_ingress.word_q[4:0]` 所在链和位置，把 ATPG 五位向量序列化到所有 **293 个 DFF** 的4条真实扫描链中。链长为74、73、73、73；短链在输入开头补位，保证相同总周期后每个目标位置对齐。

本 cut 的 **19 个可测故障各运行一次独立完整 DUT 仿真**；每例保存自己的输入、映射、日志和 VCD。3 个已穷举证明不可测的故障不伪造检测回放。故障位置通过原始 cut 网名追踪到 v2 展开网表的真实 bit，包含隐藏的 `~a` 节点；每例分别选择实际 stem 和 SA0/SA1 极性。

TB 实例化好机和坏机两颗完整 v2 网表。所有状态先经 SI 装载，再检查两颗 DUT 各 **293 个状态位**；不通过 force 寄存器绕过装载。故障只在 Capture 窗口施加，Capture 后解除，再进行 Shift-Out。PI stem 与驱动它的扫描 Q 共用展开网线，注入会影响该真实网线的全部扇出，因此这一窗口限制很重要：本实验验证组合 cut 响应通过扫描链可观察，不把扫描链自身的永久 stuck-at 故障混入同一模型；不覆盖 scan cell 内部故障或 Shift 期间的故障。

Capture 时关闭 SE，保持功能输入 valid=0，使刚装载的 word_q 不被功能写入覆盖。正沿后再产生负沿，`neg_status[1]` 捕获 reconv，`neg_status[2]` 捕获 redundant。每例从独立故障仿真确定有差异的输出，再由真实链映射定位该输出的 SO 周期。Capture 后检查全状态快照没有 X，并将之后移出的全部 **293 × 2 = 586 位** SO 与快照逐位核对；19 例合计 **11,134 次 SO 位比较**。观察位另外与独立计算的好/坏期望值核对，快照检查只证明卸载位序，不能替代检测响应的验证。

保留 q/SA1 作为网页代表波形：在 **第2条链（零基索引1）、移出周期72（零基）** 观察到好机0、坏机1。该检测经过真正的 Shift-In → Capture → Shift-Out。`reports/atpg/scan_replay.json` 的 `cases` 保存全部19例，顶层 `waveform` 保留 q/SA1 的 VCD 提取数据；代表原始波形仍为 `build/atpg/scan_atpg.vcd`。其他案例波形位于 `build/atpg/cases/<故障名>/scan_atpg.vcd`。

测试时主扫描时钟先上升，aux 扫描时钟晚1ns到达；主时钟下降后aux下降。锁存器的功能来自 `rtl/v2/lockup_latch.sv`。这是明确受控的时钟协议，不代表所有 skew 或工艺条件下都已完成 STA。

## 错误写法与可见症状

| 错误做法 | 后果 | 本项目检查 |
|---|---|---|
| 只激活 q/SA1，不检查 p 的旁路值 | a=b=1 时 p=1 屏蔽差异 | masked 向量必须返回未检测 |
| 把 X 与0的不同算作检测 | 制造虚高覆盖率 | unknown_not_counted_as_detected 断言 |
| 对AND=0强制两个输入都0 | 过度约束，漏掉可测向量 | singular cover 的两个解释分别可回溯 |
| 去掉故障注入，TB仍打印PASS | 无法证明测试真的看到故障 | `OMIT_ATPG_FAULT` 反例必须在观察处失败 |
| 翻转一个 SI 输入位后仍宣称装载正确 | 目标测试向量没有真正进入DUT | `WRONG_ATPG_INPUT` 反例必须触发装载失败 |
| 从相邻链读观察响应 | 可把无关状态误认为故障差异 | `WRONG_ATPG_OBSERVATION` 反例必须在观察处失败 |
| 各短链从第一个周期直接装满再继续移位 | 后续补时钟把已装载数据移走 | 全293位装载检查、完整SO卸载检查与独立逐拍移位模型 |
| 在图中途剔除不可测故障 | 视觉上突然升至100%，但指标已改变 | 每个曲线点保存固定 denominator=22 |

去掉故障注入的反例实际记录 good=0、bad=0，随后触发 `ATPG_CAPTURE_OR_SHIFT_MISMATCH`；错误输入反例触发 `ATPG_LOAD_MISMATCH`；错误观察链反例触发 `ATPG_CAPTURE_OR_SHIFT_MISMATCH`。运行器必须确认三次均非零退出并含对应失败标记。三个反例使用独立日志及 VCD，不覆盖任何通过案例。

`tests/test_atpg_replay.py` 用四项测试核对全部可测故障都有且仅有一次回放、用原 RTL 方程独立计算19例响应、用逐周期移位模型还原全部输入状态，并核对三项反例确实失败。测试不复用 ATPG 或 fault_sim 的门求值函数。

## 产物和验收标记

| 文件 | 用途 |
|---|---|
| `patterns/atpg/detection_patterns.json` | 每个可测故障的实际PI向量与位序 |
| `reports/atpg/summary.json` | 算法范围、完整分类、回溯轨迹、交叉核对 |
| `reports/fault/fault_list.json` | 未折叠故障全集和状态 |
| `reports/fault/fault_results.csv` | 可导入表格的逐故障结果 |
| `reports/coverage/coverage.json` | 固定分母曲线和r观察点对照 |
| `reports/atpg/scan_replay.json` | 19例完整293 DFF扫描检测证据与3项反例结果 |
| `reports/atpg/cases/<故障名>/scan_replay.log` | 除代表例外，每个故障的装载、观察和卸载日志 |
| `reports/atpg/scan_replay.log` | q/SA1代表例的完整日志 |
| `reports/atpg/negative_no_injection.log` | 故意去掉故障后被TB拦截的日志 |
| `reports/atpg/negative_wrong_input.log` | 故意翻转扫描输入位后的装载失败日志 |
| `reports/atpg/negative_wrong_observation.log` | 故意读错观察链后的失败日志 |
| `tests/test_atpg_replay.py` | 全案例覆盖、独立方程、移位模型及负向证据回归 |

成功日志必须同时含 `PASS ATPG_ORACLE`、`PASS ATPG_CUT_HDL`、`PASS COVERAGE_FIXED_DENOMINATOR`；使用 `--scan-replay` 时还必须含 `PASS ATPG_FULL_DUT_SCAN cases=19`。覆盖率仍是原组合 cut 的19/22，扩大回放验证没有扩大故障全集。

## 工业对照与来源

Tessent ATPG 或 Synopsys 的 ATPG 工具会处理大规模网表、扫描协议、库单元、复杂故障模型、压缩和诊断等。本项目覆盖结构解析、可解释的组合故障搜索、独立故障仿真与全部19个可测 cut 故障的完整 DUT 扫描回放；不等同于工业级全芯片 ATPG 或量产测试签核。商业命令不在本地执行，具体命令和许可需查目标版本手册。

2026-11-05 核对的主源：

- Yosys JSON backend 源码，解释 bit 身份、连接、端口方向和别名：[官方源码](https://github.com/YosysHQ/yosys/blob/main/backends/json/json.cc)。
- NPTEL 课程 D-Algorithm，定义 AND/OR singular cover 与 D-frontier：[课程原文](https://archive.nptel.ac.in/content/storage2/courses/106103016/module9/lec2/1.html)。本实现按这些概念裁剪，明确不冒充完整算法。
