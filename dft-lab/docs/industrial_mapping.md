# 开源教学流程与工业DFT流程对照

本地可执行路径只使用开源工具和项目Python脚本。商业工具名称用于定位阶段，不表示本机已有license或已经执行过商业命令。本文没有给出未经真实环境验证的商业参数或报告字段。

公开产品资料核对日期为2026-11-05。蓝图使用DFTCompiler与TetraMAX II等历史流程名称；当前Synopsys公开页面使用TestMAX DFT与TestMAX ATPG。项目对照保留原名帮助阅读旧流程，但不把旧名视为当前命令兼容性承诺。

| 阶段 | 本工程可执行路径 | 工业阶段与工具对照 | 当前差距 |
|---|---|---|---|
| 功能基线 | Icarus编译、vvp运行、VCD与自检查TB | 工业RTL/门级仿真；DFT改造前后基线 | 没有工艺SDF与完整形式等价签核 |
| 综合 | Yosys输出Verilog/JSON | Design Compiler/Genus综合、DFT工具读入 | 当前通用门网表不提供工艺面积达标结论 |
| 结构盘点 | netlist_model.py、dft_report.py | DFTCompiler/Tessent设计和库模型建立 | 只支持本设计门集与显式黑盒边界 |
| DRC | drc.py按连接检查时钟、复位、链和memory策略 | DFTCompiler/Tessent Scan规则分析 | 非工业完整规则、非时序与电源签核 |
| 单链插入 | scan_insert.py逐个替换293FF | Scan replacement与stitching | 教学SDFF非真实库选型，无大规模设计保证 |
| 多链 | chain_balance.py、4条链与Lock-up | Tessent Scan/TestMAX DFT链规划 | 无真实布局、拥塞和寄生优化 |
| Memory边界 | 写门控、输出bypass、Shadow扫描响应 | 宏测试模型与test point分析 | 不实现memory阵列MBIST，不统计阵列coverage |
| ATPG | 实际fault_cone的路径敏化+D-cube求解 | TetraMAX II/Tessent ATPG/TestMAX ATPG | 有限小锥，非完整工业D算法/PODEM和全芯片故障集 |
| Fault simulation | Python双电路、32输入oracle、704组HDL核对 | Fault grading、故障分类与未测分析 | 仅22个stem stuck-at，无transition/bridge/cell-aware |
| Pattern replay | 293FF真实DUT的SI→Capture→SO | Gate-level pattern validation | 自定义JSON/TB，不是已验证ATE STIL/WGL交付 |
| 时序 | 参数透明的setup/hold示例与VCD | PrimeTime/OpenSTA等测试模式STA | 无完整Liberty/SDC/寄生签核结果 |
| 重排 | 示例坐标和距离模型 | 物理感知scan reordering | 模型距离非真实路由长度；重排后仍须更新pattern |

## 商业流程概念示意

以下是阶段关系，不是可直接复制运行的命令：

```text
读入设计和工艺/测试库
→ 建立测试模式、时钟、复位、宏约束
→ 运行扫描前规则检查
→ 规划链/单元/跨域策略并插入扫描结构
→ 运行扫描后规则检查与链追踪
→ 导出最终网表和测试协议
→ ATPG读入、故障建模、模式生成与故障仿真
→ 分析未测、回放模式、更新最终链序与交付格式
```

核对真实命令的顺序：确认产品和版本、license及库；在授权环境中查内置help/man；找对应示例flow；对最小设计运行；保存实际日志与输出字段。没有这些证据，就把商业片段标为概念对照，而不是制造能跑的命令。

## 一页工业全景

MBIST针对memory阵列内部故障，常与存储器测试访问和修复机制集成；本工程旁路只服务外围逻辑。JTAG/IEEE1149.1提供测试访问和边界扫描基础设施，不能等同于内部scan或ATPG。IEEE1500面向嵌入式核测试封装；IJTAG/IEEE1687面向片内测试/监测仪器访问网络。

EDT/测试压缩在外部通道与内部扫描链之间使用刺激解压与响应压缩，降低测试数据和时间；这会增加X管理、模式和诊断复杂度。本工程保持未压缩链以便逐位解释。

Low-power DFT需要处理电源域、隔离、保持和测试切换活动。UPF表达电源意图，不自动证明测试功耗安全。这些技术在本课程只作流程地图，不展开实现，以免偏离Scan+ATPG主线。

## 依据

- [Siemens官方扫描插入说明](https://blogs.sw.siemens.com/tessent/2017/04/24/scan-insertion-for-better-atpg/)：历史技术说明，用于规则、链规划、边沿与Lock-up的阶段映射，不代表当前GUI或参数。
- [Synopsys TestMAX DFT](https://www.synopsys.com/implementation-and-signoff/test-automation/testmax-dft.html)：公开能力范围，包括scan、test point、压缩、层次与访问结构。
- [Synopsys TestMAX ATPG](https://www.synopsys.com/implementation-and-signoff/test-automation/testmax-atpg.html)：公开ATPG与故障仿真范围，不作为本项目覆盖率数字来源。
- [OpenSTA官方仓库](https://github.com/The-OpenROAD-Project/OpenSTA)：输入、能力和构建入口，不表示本项目已执行签核。
