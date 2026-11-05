// 用途：在逻辑 /4 时钟域统计运行拍数，作为低速监控状态。
// 输入：div_clk/core_rst_n；输出：ticks。v0 无 scan 接口。
// ticks 不直接作为 sys_clk 域控制信号，避免把未同步多位总线当 CDC 解法。
module rate_counter (
    input wire div_clk, rst_n,
    output reg [15:0] ticks
);
    always @(posedge div_clk or negedge rst_n)
        if (!rst_n) ticks <= 0;
        else ticks <= ticks + 1'b1;
endmodule
