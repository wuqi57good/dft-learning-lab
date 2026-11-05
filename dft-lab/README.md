# DFT Lab 七周完整教学工程

从现有 v0 功能设计继续完成真实网表解析、基础 DRC、293 位扫描插入、四链与 Lock-up、Memory 测试控制、局部锥 ATPG 和全 DUT 向量回放。课程为小江这样的计算机背景新人设计；按 7 周、每周约 10 小时学习。

## 从哪里开始

双击 `web/dft_course.html` 阅读。页面是单文件，无 CDN、外部字体或网络依赖，所有源码、文件档案与报告均内嵌。外部参考链接只在主动打开时访问。

左栏搜索或 Ctrl/Cmd+K 可检索课程与代码，代码命中会定位到实际行。首页“我的学习记录”可保存笔记并导出/导入 JSON 备份；导入合并已完成项、保留已有笔记。学习记录与工程验收报告各自独立。

工程需要 Python 3、Icarus Verilog（`iverilog` / `vvp`）与 Yosys。已验证 Icarus 13.0、YoWASP Yosys 0.70；平台安装方式不同，请先查工具帮助，不在没有安装工具时把浏览器动画当作硬件验收。

```sh
python scripts/run_all.py
# 若安装的是 YoWASP，显式选择其命令：
python scripts/run_all.py --yosys yowasp-yosys
# 不在 PATH 时可分别传 --iverilog / --vvp / --yosys 的可执行文件路径。
```

Windows 可用 `run.ps1`，Linux 的 `make all` 调用相同 Python 流程。脚本从自身位置定位工程，内部不依赖本机绝对路径。`reports/validation-full.json` 是完整流水线结果，某个必要步骤失败会写 FAIL 并退出，不能用旧报告代替本次通过。

## 单独复现各周

| 阶段 | 命令 | 主要证据 |
|---|---|---|
| 第 1–2 周 | `python scripts/run.py sim`、`python scripts/run.py structures` | `PASS FUNCTIONAL_V0`、`PASS STRUCTURES_V0` 与 VCD |
| 第 2 周 | `python scripts/study_report.py` | 19 个真实波形快照，保留 X |
| 第 3 周 | `python scripts/run.py synth` | Yosys JSON/Verilog、冗余靶点和 memory 黑盒检查 |
| 第 3–5 周 | `python scripts/run_scan.py` | v0/v1/v2 DRC、单链/四链、功能回归与错误变异 |
| 第 6 周 | `python scripts/run_atpg.py --scan-replay` | D-cube 回溯、704 次 HDL 对照、全 DUT Shift/Capture/Shift-Out |
| 第 7 周 | `python dft_tools/cost_timing.py` | 实际单元统计、明确标为示例的时序/坐标预算 |
| 网页重建 | `python web/build.py` | 将当前源文件及报告重新嵌入单文件 HTML |

`run_scan.py` 在插入前重新读取当前 `netlist/v0/design.json`。修改 RTL 后应先综合，或者直接运行完整流水线。ATPG 的全链回放依赖前一步的链映射与 v2 网表。

完整流水线还运行 `tests/test_drc.py`、`tests/test_atpg_replay.py`、`tests/test_pipeline.py` 和 `tests/test_web_build.py`，合计 39 项回归。它们分别核对连接变异、逐故障回放、失败状态与构建证据。网页构建核对已验源码和生成物的完整文件集合及原始字节哈希，拒绝新增未验文件、修改后的网表/报告、缺失的向量，以及失败的必要子报告。独立重跑 Scan 或完整 ATPG 回放也会立即使各自旧 PASS 失效。

浏览器回归独立运行：安装 Python Playwright 与其 Chromium 后，执行 `python tests/test_learning_ui.py` 检查搜索定位、学习记录合并、错误文件处理、键盘和手机布局；再执行 `python web/build.py` 嵌入该结果，运行 `python tests/test_web_ui.py` 检查全部内嵌源码/报告一致性和原有交互。最后再次构建，将两份浏览器报告一起保存到网页。两项测试均可用 `--browser` 指定本机 Edge/Chromium 可执行文件；完整网页回归可用 `--screenshots` 指定截图目录。报告分别为 `reports/validation-learning-ui.json` 与 `reports/validation-web.json`。

## 本次实测口径

- v0：1,760 个通用叶单元，其中 293 个 DFF、4 个负沿 FF、1 个 ICG 使能锁存器、1 个 32×32 Memory 黑盒。
- v1：293 位单链；基础 DRC 0 error，仍有 1 条 Memory 边界 warning。
- v2：4 条链，长度 74/73/73/73，4 个低电平透明 Lock-up；基础 DRC 0 error / 0 warning。
- v1/v2 在功能模式下各通过原来的 40 笔事务及复位后事务，Scan 验证逐位覆盖所有 293 个状态位。
- DRC 拒绝单元输出之间、外部输入与单元输出之间的多驱动；逐个对照真实 v0，核对 v1/v2 全部 FF 的 Q/D/E、复位值、触发沿及功能时钟/复位支路。13 项回归包含故意改错的反例。
- ATPG：实际 DUT 的 `fault_cone` 组合 cut，共 22 个非折叠 stem stuck-at 故障；19 个可检测，3 个在此观察边界下被证明不可测。Fault coverage=19/22=86.36%，可测故障分母下的 test coverage=19/19=100%。两者均不是全芯片覆盖率。
- 全 DUT 回放：19 个可检测故障各自的算法向量经真实 v2 扫描链装载、捕获并移出；reconv/redundant 分别捕获至 neg_status[1]/[2]。每例核对两颗 DUT 的全部 293 位装载与 SO 卸载，合计 11,134 次 SO 位比较。q/SA1 的代表结果仍为正常 0 / 故障 1。漏注入、错误输入位和错误观察链均被断言拦截。

具体断言和反例结果以 `reports/scan/validation.json`、`reports/atpg/summary.json`、`reports/atpg/scan_replay.json` 为准。`reports/validation.json` 与 `validation-week2.json` 是历史批次记录。

## 边界与工程选择

原蓝图的文件名和行数是规划示例。实现保留已有 `packet_mix` 名称，不把普通滚动签名伪称 CRC；不为了凑文件名拆出只含一条表达式的包装模块。Scan 工具直接处理真实门级 JSON，输出同一结构的 JSON 和 Verilog。Memory 不计入扫描位数，门控使能 latch 保留；v2 在整个测试模式保护写使能并提供已知旁路输入。Shadow parity 本身作为真实扫描 FF 被观察。

ATPG 是教学用的 D-cube 路径敏化与逆向解释，不是完整工业 D-Algorithm 或 PODEM；只支持本项目明确的门类型。32 组输入的穷举用作独立 oracle，不冒充搜索算法。新增 r 观察点的 22/22 结果是固定故障集合的组合模型对照，不声称已在 v2 增加 r 观察硬件。

没有执行工艺库映射、OpenSTA、SDF、布局布线或制造签核。2,000–5,000 NAND2 等效门是原始目标，缺少指定 Liberty 面积与宏面积，当前不能宣称达标。`cost_timing.json` 的单元数量为实测；延迟和坐标均显式标为示例值。SDC 为教学约束意图，应用前必须在实际工具与工艺库环境验证。

## 行为契约与目录

原输入为单事务 ready/valid。握手后下一正沿计算，再下一正沿写 memory；接收端必须总能接收，key 仅在 idle 修改。Memory 同步读写、read-first，未写地址初始为 X。aux 每 16 拍发事件，目标 sys 必须有足够采样时间；这不是任意频率关系都无损的 CDC。功能与测试时钟切换须停钟并遵守复位协议。

`rtl/` 是硬件模型，`tb/` 是激励断言，`scripts/` 顺序组织真实工具，`dft_tools/` 实现算法，`tests/` 保存回归检查，`netlist/` 保存生成连接，`patterns/` 保存向量，`reports/` 保存可追溯结果，`build/` 是可再生编译/波形，`constraints/` 是环境意图，`docs/` 解释判断与来源，`web/` 包含网页源码和构建器。详见网页中的目录说明和逐文件工程档案。
