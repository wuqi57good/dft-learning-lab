// 用途：保留原 DFF 的触发沿、异步复位值与功能 enable，增加高优先级扫描 MUX。
// 输入：C 时钟、R 低有效复位、D 功能数据、E 功能使能、SE 扫描选择、SI串行输入。
// 输出 Q 为原寄存器状态。v1/v2 共用；并非工艺库 SDFF 的时序/面积模型。
// 🔧 Shift 时必须先判断 SE，不能让原功能 enable=0 阻塞扫描链。
// ⚠ 切换 test_mode/SE/复位必须遵守外部测试协议；零延迟模型不能证明 setup/hold。
module dft_scan_dff #(parameter NEGATIVE=0, RESET_VALUE=0)
 (input wire C,R,D,E,SE,SI, output reg Q);
 generate if (NEGATIVE) begin: neg
   always @(negedge C or negedge R)
     if (!R) Q <= RESET_VALUE;
     else if (SE) Q <= SI;
     else if (E) Q <= D;
 end else begin: pos
   always @(posedge C or negedge R)
     if (!R) Q <= RESET_VALUE;
     else if (SE) Q <= SI;
     else if (E) Q <= D;
 end endgenerate
endmodule

// 原功能门控 clk 保持不动；这条独立的教学门控路径只处理测试时钟。
// TE 在低电平锁存，随后与 scan_clk 相与；高电平中途更改 TE 不截短脉冲。
// 工业实现要替换为受库/STA识别的 ICG。test_mode MUX 只能在停钟时切换。
module dft_test_gate(input wire CK,TE,output wire Q);
 reg latched_te;
 always @* if (!CK) latched_te = TE;
 assign Q = CK & latched_te;
endmodule

// 保留 v0 中的低透明门控 latch；它是时钟控制状态，不当普通 DFF 扫描。
module dft_level_latch(input wire D,E, output reg Q);
 always @* if (!E) Q = D;
endmodule
