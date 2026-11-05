// 用途：保存 memory 读数据的奇偶校验，模拟宏周边的 Shadow Logic。
// 输入：rdata，输出：parity_q；每个 sys 正沿计算一次。
// v0 故意没有 bypass/有效位；未初始化 memory 会把 X 写入 parity_q。
// v2 将以可控 bypass 激励外围逻辑，并将观察点纳入测试故障统计。
module memory_shadow (
    input wire clk, rst_n,
    input wire [31:0] rdata,
    output reg parity_q
);
    always @(posedge clk or negedge rst_n)
        if (!rst_n) parity_q <= 0;
        // ⚠ 易错点：只屏蔽输出 X 可以改善波形，但不能证明 memory 周边锥被测试。
        else parity_q <= ^rdata;
endmodule
