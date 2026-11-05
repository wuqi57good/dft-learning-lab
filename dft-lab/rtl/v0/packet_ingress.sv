// 用途：在 ready/valid 握手时保存一整个 32 位输入字，让后级有稳定操作数。
// 输入：sys_clk、低有效异步复位、accept、data_in；输出：word_q。
// 依赖：无；v0 建立功能数据边界，v1 才由网表工具替换内部 DFF。
// 时序假设：功能 Capture 在正沿发生；此文件尚未实现 Scan Shift。
module packet_ingress (
    input wire clk, rst_n, accept,
    input wire [31:0] data_in,
    output reg [31:0] word_q
);
    // accept 只在外部 valid 与内部 ready 同时为 1 时出现。
    // 不可用 valid 单独驱动，否则下游忙碌时也会覆盖正在处理的数据。
    always @(posedge clk or negedge rst_n)
        if (!rst_n) word_q <= 32'b0;
        else if (accept) word_q <= data_in;
endmodule
