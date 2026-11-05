# 用途：v1扫描移位模式的SDC教学意图；不是已完成物理签核的约束集。
# 输入：link后的v1设计；本交付未运行OpenSTA、无Liberty/PVT/寄生RC。
# 示例单位ns，需要确认目标库time_unit。周期12对应本课程scan TB。
# 🔧 测试模式接管时钟/复位并让TE打开门控；功能模式需要单独约束会话。
create_clock -name SCAN -period 12 -waveform {3 8} [get_ports scan_clk]
set_case_analysis 1 [get_ports test_mode]
set_case_analysis 1 [get_ports test_te]
set_case_analysis 1 [get_ports test_rst_n]
set_case_analysis 1 [get_ports scan_en]
# ⚠ scan_in/scan_out时序取决于ATE驱动和采样窗口。不能凭空填I/O delay后宣称通过。
# 补齐库、I/O、uncertainty、generated clock传播与recovery/removal后才可检查时序。
# Capture需切换scan_en=0并重新定义捕获时钟协议；此示例不是at-speed模式。
# 验证命令的具体选项与报告字段：在目标工具中help create_clock / set_case_analysis。
