// 用途：把 Python 从真实 fault_cone 求出的每个可测故障向量装入完整 v2 DUT。
// 输入：每例独立的 scan_input.mem 与由 scan_chains.json 生成的位置映射。
// 输出：真实 VCD 与 PASS；依赖 Icarus、SDFF/lockup 模型及生成的 v2 网表。
// v3增强：两颗 DUT 接收相同链输入；坏机在当前真实stem位置注入SA0或SA1。
// ⚠ 不 force 寄存器值来绕过装载；所有293个寄存器先经真实4条链移入。
`timescale 1ns/1ps
module atpg_pattern_tb;
  `include "atpg_mapping.svh"
  reg sys_clk=0, aux_clk=0, rst_n_ext=1;
  reg test_mode=1, test_rst_n=1, scan_clk=0, scan_clk_aux=0;
  reg scan_en=1, test_te=1;
  reg [3:0] scan_in=0;
  wire [3:0] good_so,bad_so;
  reg [3:0] stimulus[0:SCAN_CYCLES-1];
  // 捕获快照只用于验证完整卸载位序；目标响应另与Python独立故障仿真比较。
  reg [SCAN_CYCLES-1:0] captured_good[0:3], captured_bad[0:3];
  integer cycle;
  reg seen=0;
  dft_demo_top_v2 good(.sys_clk(sys_clk),.aux_clk(aux_clk),.rst_n_ext(rst_n_ext),
    .cfg_valid(1'b0),.cfg_write(1'b0),.cfg_addr(8'b0),.cfg_wdata(32'b0),
    .data_valid(1'b0),.data_in(32'b0),.test_mode(test_mode),.test_rst_n(test_rst_n),
    .scan_clk(scan_clk),.scan_clk_aux(scan_clk_aux),.scan_en(scan_en),.test_te(test_te),
    .scan_in(scan_in),.scan_out(good_so),.test_bypass_data(32'b0));
  dft_demo_top_v2 bad(.sys_clk(sys_clk),.aux_clk(aux_clk),.rst_n_ext(rst_n_ext),
    .cfg_valid(1'b0),.cfg_write(1'b0),.cfg_addr(8'b0),.cfg_wdata(32'b0),
    .data_valid(1'b0),.data_in(32'b0),.test_mode(test_mode),.test_rst_n(test_rst_n),
    .scan_clk(scan_clk),.scan_clk_aux(scan_clk_aux),.scan_en(scan_en),.test_te(test_te),
    .scan_in(scan_in),.scan_out(bad_so),.test_bypass_data(32'b0));

  `include "atpg_checks.svh"
  // 主时钟上升后1ns才到aux；低透明lockup隔离主域本拍新Q。
  // 每完整周期先正沿再负沿，链中负沿段位于正沿段之前。
  task pulse;
    begin #4; scan_clk=1; #1; scan_clk_aux=1;
          #4; scan_clk=0; #1; scan_clk_aux=0; #2; end
  endtask
  initial begin
    // 三种反例各用独立文件，绝不能覆盖任何一个通过案例的VCD。
    `ifdef OMIT_ATPG_FAULT
      $dumpfile("build/atpg/negative_no_injection.vcd");
    `elsif WRONG_ATPG_INPUT
      $dumpfile("build/atpg/negative_wrong_input.vcd");
    `elsif WRONG_ATPG_OBSERVATION
      $dumpfile("build/atpg/negative_wrong_observation.vcd");
    `else
      $dumpfile(`WAVE_FILE);
    `endif
    $dumpvars(0,atpg_pattern_tb);
    $readmemb(`INPUT_FILE,stimulus);
    `ifdef WRONG_ATPG_INPUT
      stimulus[INPUT_CORRUPT_CYCLE][INPUT_CORRUPT_CHAIN] =
        ~stimulus[INPUT_CORRUPT_CYCLE][INPUT_CORRUPT_CHAIN];
    `endif
    // 主动产生复位下降沿，避免仿真初始化顺序掩盖状态来源。
    #2; test_rst_n=0; #2; test_rst_n=1; #2;
    for(cycle=0;cycle<SCAN_CYCLES;cycle=cycle+1) begin
      scan_in=stimulus[cycle]; pulse;
    end
    // 每个FF都必须经真实SI移到目标状态；不能只检查低5位碰巧正确。
    check_loaded;
    $display("PASS ATPG_SCAN_LOAD cells_per_dut=293");
    // 故障是组合网线的物理 stuck-at 模型，未修改 ATPG 的正确响应。
    // OMIT_ATPG_FAULT 专用于反例回归：移除故障必须被下方检测断言拒绝。
    `ifndef OMIT_ATPG_FAULT
      force bad.`FAULT_NET=FAULT_VALUE;
    `endif
    #2; scan_en=0;
    pulse;
    // 目标可为reconv或redundant，对应neg_status[1]或[2]；映射按当前故障推导。
    // Capture后解除故障再开始Shift，避免PI stem强制值持续干扰扫描状态卸载。
    `ifndef OMIT_ATPG_FAULT
      release bad.`FAULT_NET;
    `endif
    #2; snapshot_capture;
    scan_en=1; scan_in=0; #2;
    for(cycle=0;cycle<SCAN_CYCLES;cycle=cycle+1) begin
      // 两颗完整DUT的每个捕获位都经SO读回，与捕获快照对应，短链末尾不越界。
      compare_shift;
      if(cycle==OBS_CYCLE) begin
        $display("ATPG_SCAN_OBS cycle=%0d chain=%0d good=%b bad=%b",cycle,OBS_CHAIN,good_so[OBS_CHAIN],bad_so[OBS_CHAIN]);
        `ifdef WRONG_ATPG_OBSERVATION
        if(good_so[(OBS_CHAIN+1)%4]!==EXPECTED_GOOD || bad_so[(OBS_CHAIN+1)%4]!==EXPECTED_BAD)
        `else
        if(good_so[OBS_CHAIN]!==EXPECTED_GOOD || bad_so[OBS_CHAIN]!==EXPECTED_BAD)
        `endif
          $fatal(1,"ATPG_CAPTURE_OR_SHIFT_MISMATCH");
        seen=1;
      end
      pulse;
    end
    if(!seen) $fatal(1,"ATPG_OBSERVATION_NOT_REACHED");
    $display("PASS ATPG_SCAN_UNLOAD cells_per_dut=293 compared_so_bits=586");
    $display("PASS ATPG_FULL_DUT_SCAN");
    $finish;
  end
  initial begin #100000; $fatal(1,"ATPG_TIMEOUT"); end
endmodule
