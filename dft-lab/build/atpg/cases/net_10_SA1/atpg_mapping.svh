// 自动取真实链与cut映射；参数用于一个故障的一次完整DUT回放。
localparam SCAN_CYCLES=74, OBS_CHAIN=1, OBS_CYCLE=72;
localparam EXPECTED_GOOD=1'b0, EXPECTED_BAD=1'b1, FAULT_VALUE=1'b1;
localparam INPUT_CORRUPT_CHAIN=0, INPUT_CORRUPT_CYCLE=54;
`define FAULT_NET n648
`define INPUT_FILE "build/atpg/cases/net_10_SA1/scan_input.mem"
`define WAVE_FILE "build/atpg/cases/net_10_SA1/scan_atpg.vcd"
