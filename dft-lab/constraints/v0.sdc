# 用途：第二周的功能时钟意图草案，解释 STA 应知道什么；不是 Yosys 综合输入。
# 输入：已经 link 的 dft_demo_top 网表；输出：STA 会话中的两个主时钟定义。
# 依赖：支持 SDC 的 STA 环境（如 OpenSTA）；本批未执行 OpenSTA，不宣称时序签核。
# v0：只为稳定的顶层端口写约束；派生/门控路径需在映射后的网表确认时钟引脚。
# 单位：10/14 对应本实验的 ns 示例；实际工具 time_unit 必须通过库/工具帮助确认。

# ★经验点：先核对主时钟端口，避免空集合被脚本静默接受。
set sys_port [get_ports {sys_clk}]
set aux_port [get_ports {aux_clk}]
if {[llength $sys_port] != 1 || [llength $aux_port] != 1} {
    error "v0.sdc: expected sys_clk and aux_clk ports after link_design"
}
create_clock -name SYS -period 10 -waveform {0 5} $sys_port
create_clock -name AUX -period 14 -waveform {0 7} $aux_port

# ⚠ 不在这里直接 false-path 两个域：先完成 CDC 审核，再在 STA 工具中约束对应路径。
# /4 意图：周期 40ns。具体 generated-clock target 必须是最终网表中的真实引脚。
# 门控意图：保留 sys 的周期与相位，检查 ICG/latch-and-AND 识别及门控检查。
# 负沿寄存器仍使用 SYS 时钟的下降沿，不新建一个“负沿异步时钟”。
# 尚缺：经过验证的 generated clocks、I/O delay、uncertainty、复位恢复/移除约束。
# 确认路径：先查 STA 的 help create_clock / help create_generated_clock，再查看
# 时钟报告和未约束端点报告。实际报告命令名/字段需按安装版本帮助确认。
# 切勿把这个意图草案称为完整约束，亦勿因读入成功就声称 setup/hold 满足。
