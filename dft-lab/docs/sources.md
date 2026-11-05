# 知识来源与结论边界

核对日期：2026-11-05。技术资料优先使用工具维护者、厂商、原始论文与授课机构。页面中的项目数量、检测结果、PASS和反例来自本地实际报告，不从产品宣传页推算。下列链接仅在主动打开时联网；离线课程本身不依赖它们加载。

| 来源 | 版本/性质 | 支持的内容 | 不支持的外推 |
|---|---|---|---|
| [Yosys write_json说明](https://yosyshq.readthedocs.io/projects/yosys/en/v0.56/cmd/index_backends.html#write-json-write-design-to-a-json-file) | 固定v0.56文档，核对格式语义 | bit身份、端口、单元、参数、连接与常量表达 | 不证明本项目DRC/ATPG正确；本地工具版本以运行日志为准 |
| [Yosys JSON backend源码](https://github.com/YosysHQ/yosys/blob/main/backends/json/json.cc) | 官方维护源码 | JSON输出结构、别名和连接编码 | main分支可能更新，不能代替保存输入文件 |
| [Icarus命令行说明](https://steveicarus.github.io/iverilog/usage/command_line_flags.html) | 官方用户文档 | 编译选项、顶层与语言模式的确认入口 | 不代表任意SystemVerilog特性均支持 |
| [Siemens扫描插入技术说明](https://blogs.sw.siemens.com/tessent/2017/04/24/scan-insertion-for-better-atpg/) | 2017历史技术文章 | 规则分析、扫描替换/串链、时钟边沿与Lock-up的工程位置 | 不推断2026特定版本命令/GUI/报告字段 |
| [Synopsys TestMAX DFT](https://www.synopsys.com/implementation-and-signoff/test-automation/testmax-dft.html) | 当前公开产品页面 | 商业能力与scan、test point、压缩、层次及访问的关系 | 不说明本机有license，不证明自研代码等价 |
| [Synopsys TestMAX ATPG](https://www.synopsys.com/implementation-and-signoff/test-automation/testmax-atpg.html) | 当前公开产品页面 | ATPG与fault simulation产品范围 | 不提供本项目工业合格率阈值或覆盖率承诺 |
| [OpenSTA官方仓库](https://github.com/The-OpenROAD-Project/OpenSTA) | 官方说明与代码 | Liberty、Verilog、SDC、SDF、SPEF等输入及STA职责 | 本项目没有据此声称已跑物理STA |
| [NPTEL D-Algorithm课程](https://archive.nptel.ac.in/content/storage2/courses/106103016/module9/lec2/1.html) | 授课机构原始课程材料 | 门cube、D值与D算法背景 | 不把有限路径敏化实现称为完整工业算法 |
| [Roth原始论文 DOI](https://doi.org/10.1147/rd.104.0278) | 1966，Diagnosis of Automata Failures: A Calculus and a Method | D算法历史与正式出处 | 出版社全文可能受访问限制；不作为本项目运行证据 |
| [Goel原始论文 DOI](https://doi.org/10.1109/TC.1981.1675757) | 1981，An Implicit Enumeration Algorithm to Generate Tests for Combinational Logic Circuits | PODEM原始出处与算法身份对照 | 当前实现不是PODEM，不能用论文名称给DFS贴标签 |

Roth与Goel的论文题名、年份和DOI已通过DOI注册元数据核对；正文算法讲解同时使用可访问的课程材料和本地实现。DOI提供稳定文献定位，不承诺无需订阅即可获取全文。

## 本地实测证据

- `reports/netlist_inventory.json`：v0通用单元和黑盒统计。
- `reports/drc/v0.json`、`v1.json`、`v2.json`：本项目规则范围内的诊断。字段是自研schema，不伪造商业输出。
- `reports/scan_chains.json`、`reports/scan/validation.json`：原FF位置、链长、功能/扫描与反例结果。
- `reports/atpg/summary.json`：22故障的生成、分类与q/SA1回溯。
- `reports/fault/fault_list.json`、`reports/fault/fault_results.csv`：具体故障与检测证据。
- `reports/coverage/coverage.json`：同一22故障分母下的曲线；直接观察r仅为Python模型对照。
- `reports/atpg/scan_replay.json`与`build/atpg/scan_atpg.vcd`：完整293FF DUT的真实SO检测。

## 修正的易误导表述

“scan≈双向链表”改为单向串行状态快照；“所有N状态控制都是严格O(2^N)”改为依设计可能出现指数规模；“负沿永远在正沿前”改为绑定测试波形的顺序；“跨域一定插一个latch就安全”改为相位与setup/hold约束；“有X差异就检测”改为已知响应比较；“未搜到就是不可测”改为证明与未解决分开；“generic cells等于等效门”明确禁止。

没有引用未经证实的通用工业链长范围。4条链、示例10ns周期及示例时序参数均作为本实验选择，不暗示业界统一推荐。
