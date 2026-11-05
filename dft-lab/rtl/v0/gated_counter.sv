// 用途：用低电平锁存的门控时钟统计提交次数，展示 ICG 的等价行为结构。
// 输入：sys_clk、commit、rst_n；输出：计数值。
// v0：没有 TE 端；v1 的工业映射需要真正库 ICG 的测试使能端及工具识别。
// 此 RTL 只模拟正沿时钟的 latch + AND；不是已做时序签核的工艺 ICG。
module gated_counter (
    input wire clk, rst_n, enable,
    output reg [15:0] count
);
    reg enable_latched;
    wire gated_clk;
    // 🔧 锁存器在低电平透明，高电平关住 enable，避免高电平中途截断时钟。
    // 不在这个锁存器上加异步清零：高电平清零会立刻截断 gated_clk。
    always @* if (!clk) enable_latched = enable;
    assign gated_clk = clk & enable_latched;
    always @(posedge gated_clk or negedge rst_n)
        if (!rst_n) count <= 0;
        else count <= count + 1'b1;
    // ⚠ 测试时 enable=0 会停止 scan cell 的时钟；后续版本用 TE 打开门控。
endmodule
