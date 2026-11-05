// 用途：在下降沿保存功能状态，为正负沿混串提供真实负沿 DFF。
// 输入：sys_clk/core_rst_n 与 status；输出：sampled。
// v0 仅功能采样；v2 的混边沿顺序依赖 shift 波形定义，不能机械套口诀。
module neg_capture (
    input wire clk, rst_n,
    input wire [3:0] status,
    output reg [3:0] sampled
);
    // ★经验点：同相 shift 时钟的常见选择是负沿段 → 正沿段。
    // 它会改变半拍预算与末端采样时刻；最终必须按具体边沿与 skew 检查。
    always @(negedge clk or negedge rst_n)
        if (!rst_n) sampled <= 0;
        else sampled <= status;
endmodule
