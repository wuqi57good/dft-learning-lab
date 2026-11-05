# 从真实网表到完整扫描链

本阶段将 v0 综合结果中的 293 个触发器全部接入扫描链，保留原有功能数据、使能、异步复位值和触发沿。v1 是单条 293 位链；v2 是 74、73、73、73 位四条链，另有 4 个跨测试时钟域的 lock-up latch。数字来自本工程实际运行，不是示例规模。

## 文件如何接起来

`dft_tools/netlist_model.py` 读取 `netlist/v0/design.json`，先按父子端口绑定展开层次，再为局部信号分配全局 bit 编号。Yosys bit 编号在每个 module 内有效，不能直接把子模块字典拼在一起。输出与输入的别名也要合并，例如 `cfg_ready` 直接来自 `cfg_valid`。原有 40 事务功能回归会检验这些连接。

`dft_tools/dft_report.py` 输出 `reports/drc/inventory.json`，其中有每个触发器的源名称、D/Q、时钟、复位、enable、沿类型，以及所有可读 RTL 别名。读者可以从 `u_ingress.word_q[0]` 找到具体触发器，再在链报告中找到位置。

`dft_tools/scan_insert.py` 操作上述实际连接。它用显式测试时钟 MUX、测试复位 MUX 和 SDFF 替换原寄存器，不重写功能数据通路。生成的 `netlist/v1/design.v`、`netlist/v2/design.v` 是完整 DUT，不是单独的一组演示移位寄存器。两个目录中的 `design.json` 与 Verilog 由同一份内存模型输出。

`rtl/v1/scan_dff.sv` 定义教学 SDFF、测试门控和原功能 latch 的行为。`rtl/v2/lockup_latch.sv` 定义源时钟低电平透明的锁存器。原功能 latch 与 SRAM 宏没有当普通 DFF 串入链。

`dft_tools/chain_balance.py` 先均衡分配长度，再在每条链内按负沿、正沿及测试域排序。链映射 `reports/scan_chains.json` 中 `cells` 始终是 SI 到 SO 的次序，`position=0` 最接近 SI。`q` 是生成网表中的 `n<编号>`，`instance` 是 `sdff_<链号>_<位置>`。Lock-up latch 不占一个 pattern 位。

`dft_tools/drc.py` 根据真实 pin/bit 连接检查控制锥和扫描拓扑，并从原始 v0 独立核对逐 FF 功能连接。`scripts/run_scan.py` 组织生成、功能回归、扫描回归和故意错误的反例测试，并提取真实波形。

## 每个版本解决什么

v0 中共有 289 个正沿和 4 个负沿触发器，外加一只功能门控 latch。时钟组包括 sys、aux、内部逻辑分频、门控时钟。内部异步复位不是外部直接可控。课程 DRC 对具体触发器逐项报出 278 个错误，并对 memory X 边界报出 1 个警告；这不是 278 种独立问题。

v1 在 test_mode=1 时统一接管到 scan_clk，复位接到 test_rst_n。原 gated_counter 的测试支路经过 test_te 控制的低透明 latch 加 AND。test_te 必须为 1，scan_clk 才能进入这组寄存器。所有功能连接在 test_mode=0 时保持。基础扫描规则为 0 错误；memory 仍有 1 个警告，作为 v2 的明确改进对象。

v2 将原 aux 域的测试时钟接到 scan_clk_aux，其余域接主测试时钟。每条链从主测试域进入 aux 域前放置一个低透明 lock-up latch。v2 同时把 memory 写使能与 `!test_mode` 相与，并用 32 位 test_bypass_data 旁路 memory 输出。保护在整个测试模式有效，不能仅在 scan_en=1 时禁写，否则 Capture 仍可能破坏存储内容。

memory_shadow 的 parity_q 和其他周边状态本来就在 293 个扫描寄存器里，因此旁路后的已知数据可以捕获到 parity_q，再经链移出。旁路没有验证 SRAM 存储阵列本体；本课程不实现 MBIST。

## 扫描时序契约

所有测试时钟从低电平开始。先使 SI 稳定并读取 SO，再产生主时钟正沿、aux 正沿、主时钟负沿、aux 负沿。自检 TB 使用 12 ns 周期，aux 晚 2 ns；这些是教学激励值，不是工业 skew 预算。

在这个“先正后负”的完整周期中，负沿寄存器放在链前面，正沿寄存器放在后面：正沿单元先接收上周期负沿状态，然后负沿单元更新本周期输入。若在没有额外相位处理的情况下把正沿放在负沿之前，下游负沿可能在同一完整周期提前接收新位。

锁存器在源正沿之前透明、正沿之后关闭。源 Q 更新时它仍保持上一位，迟到的 aux 正沿就不会吞掉新位。主时钟下降后它才重新透明。本课真实 DUT 的无 lock-up 反例在第 55 个 shift 周期产生错位；这是数字仿真中明确的时序协议失效，不是一个以 Liberty/SDF 计算出的模拟 hold slack。

Capture 前保持 test_mode=1、test_rst_n=1、test_te=1，把 scan_en 拉低并按相同协议打时钟。v2 用 test_bypass_data=1 检验 shadow_parity 确实捕获为 1。随后恢复 scan_en=1，将捕获后的全体 Q 快照逐位移出。ATPG 的故障锥向量可按 aliases 装入 word_q，捕获到 neg_status，再沿同一链读回。

test_mode 只能在相关时钟停止且无毛刺的条件下切换。普通组合 MUX 不是可在任意活动时刻安全切换的时钟开关。scan_en 也必须满足每个 SDFF 的 setup/hold。零延迟仿真没有证明这些物理条件。

## 实际运行

在工程根目录执行：

```text
python scripts/run_scan.py
python scripts/run_scan.py --iverilog <iverilog路径> --vvp <vvp路径>
yosys -s scripts/synth_v1.ys
yosys -s scripts/synth_v2.ys
```

本次交付使用实际 Icarus 和 Yosys 运行。Windows 入口会为子进程把 iverilog 所在目录加入 PATH，确保内部编译进程可以加载 DLL。脚本不会把开发者电脑的绝对路径写进工程。

Yosys 复读 Verilog 后执行 hierarchy、proc、check -assert 和 stat。教学 ICG、原 latch、lock-up 的 latch-inferred 警告是有意保留的结构；check 报告 0 problems。另外对生成 JSON 执行 read_json 后重新链接行为单元，检查也通过。这里只验证合法连接和综合语义，没有做工艺映射或时序签核。

## 验收证据

`reports/scan/validation.json` 保存本项目检查结果。v1、v2 分别重用原完整功能 TB，包含 40 笔事务、busy 隔离、32 地址环形存储读回、门控计数、CDC 活动与软复位恢复。两版都通过。

扫描 TB 用独立的串行参考模型逐拍检查全部 293 个 Q 和 SO。v1 先运行 586 个随机移位周期，v2 先运行 148 个；随后分别清零加载、Capture、完整移出。v2 还在测试过程中让功能 memory 时钟活动，并确认预置的 32 个地址内容未变化。

三种错误在复制网表中注入，交付网表保持正确：

| 错误 | 连接级 DRC | HDL 自检表现 |
|---|---|---|
| 某个 SI 接成常 0 | SCAN_LINK_BROKEN | chain 0 第 3 拍状态不符 |
| 绕过跨域 lock-up | LOCKUP_MISSING | chain 1 第 55 拍状态不符 |
| memory 写使能恒 1 | MEMORY_WRITE_UNGUARDED | memory 地址 0 内容被破坏 |

正确版波形是 `build/scan/v1.vcd`、`build/scan/v2.vcd`。反例分别保存同目录独立波形，不能覆盖正确证据。`reports/scan/lockup_wave.json` 从正确与无 lock-up 的全 DUT VCD 中提取 664–676 ns 的同一窗口，可以看到接收 Q 在迟到的 aux 正沿之后发生分歧。

## 工程判断与边界

增强检查首先收集一根网线的全部驱动。旧实现用 `drivers[bit]=cell` 保存单个驱动，给 v2 中某根组合线增加第二个输出后，后一个会覆盖前一个，原检查仍返回 0 错误。现在 `MULTIPLE_DRIVERS` 明确列出所有源；出现争用的 bit 不参与控制锥的确定值推导。顶层 input 是外部源，不能再由内部单元驱动；顶层 output 是观察端，网名别名也只是同一根线的名字，两者都不会增加驱动数。本课程只有单向端口，这不是通用三态总线解析器。

`audit_preservation(original, module, mapping)` 用真实 flatten v0 的 FF 对象作独立参考，对每个原 FF 检查 Q、D、功能 enable、异步复位值、正负触发沿，以及时钟/复位 MUX 的功能 A 支路和 test_mode 选择。它不采信 mapping 中保存的 D/E 等黄金值，因此即便错误插入器同时改坏网表和 mapping 元数据，也不能把二者一致当作正确。`drc.py` 主入口自动运行此审计，v1/v2 报告的 `functional_preservation` 字段写明参考文件、寄存器数量及范围。

运行 `python tests/test_drc.py` 可以重现这次增强的 13 项自动检查。错误只发生在网表的内存副本中，交付 JSON 不会被改写。测试包含正确 v0/v1/v2、重复驱动、外部输入争用、合法别名、D/E/Q 错接、复位值错、负沿改变、功能时钟/复位 MUX 支路错、选择信号错以及漏掉原 FF。成功末尾为 `PASS DRC_REGRESSION`。

这里的“功能保留”是逐 FF 的结构契约检查，不是整颗设计的形式等价证明；尚未证明全部组合门的布尔功能、所有模式切换或物理时序。原完整功能 TB 仍需运行，不能被静态审计替代。

没有再复制一份巨大 RTL 顶层：v1/v2 的扫描能力来自 Python 对实际门级网表的修改，行为单元集中在两个小文件中。这样每个 SI、MUX、clock/reset 路径都能在 JSON 中追溯，避免 RTL 顶层与扫描产物分别维护而漂移。

四链把最长移位长度从 293 降为 74，代价是更多 SI/SO 测试管脚、控制布线与 lock-up。这里只做长度平衡，没有布局坐标，也没有假装完成物理 Scan Reordering。真实项目还要看 ATE 通道、测试时间、功耗、时钟域与布线拥塞。

本 DRC 是精确定义的课程子集：检查单向网络多驱动、逐 FF 功能连接和参数、测试控制可达性、链连接、覆盖全部原 DFF、边沿排序、跨测试域 lock-up、memory 写保护与旁路控制。它不证明 scan_en 高扇出能满足时序、不验证模拟时钟毛刺、不估计 metastability/MTBF，也不覆盖工业 ATPG 的全部规则。

`constraints/v1.sdc` 和 `constraints/v2.sdc` 是教学移位模式意图，未执行 OpenSTA。必须补齐工艺库、PVT、寄生、ATE I/O 时序、uncertainty、复位 recovery/removal 和时钟传播等条件，才能讨论 Shift Hold 或 Capture Setup 是否真正收敛。
