# 用途：v2移位模式两测试时钟的相位意图；没有执行OpenSTA或任何物理签核。
# TB中main正沿为3ns，aux正沿晚2ns；负沿分别为8/10ns，周期12ns。
# ★ lockup低透明方向取决于launch沿；这组数字是教学协议，不是通用skew容限。
create_clock -name SCAN_MAIN -period 12 -waveform {3 8} [get_ports scan_clk]
create_clock -name SCAN_AUX -period 12 -waveform {5 10} [get_ports scan_clk_aux]
set_case_analysis 1 [get_ports test_mode]
set_case_analysis 1 [get_ports test_te]
set_case_analysis 1 [get_ports test_rst_n]
set_case_analysis 1 [get_ports scan_en]
# ⚠ 这里两时钟有已定义的测试相位关系，不应set_clock_groups -asynchronous掩盖hold路径。
# 真实实现要确认ICG、lockup、MUX时钟传播、占空比、OCV、布线与ATE时间约束。
# 功能sys/aux CDC与测试shift跨域是两种不同问题；lockup不能解决功能亚稳态。
# 需用目标STA的help确认命令支持，并检查所有未约束端点；读入SDC不等于时序通过。
