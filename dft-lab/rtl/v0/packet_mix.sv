// 用途：四路滚动签名累加器，用于包流摘要；不是 CRC，也不提供密码学安全。
// 输入：已锁存的 word、稳定的 key、execute；输出：本笔结果 result_q。
// v0：四个 32 位状态寄存器和加法器构成有意义的数据通路。
// 测试背景：scan 之后能直接装载 lane 状态，避免靠长输入序列凑内部状态。
module packet_mix (
    input wire clk, rst_n, execute,
    input wire [31:0] word, key,
    output reg [31:0] result_q
);
    reg [31:0] lane0, lane1, lane2, lane3;
    wire [31:0] n0 = lane0 + (word ^ key);
    wire [31:0] n1 = lane1 + {word[23:0], word[31:24]};
    wire [31:0] n2 = lane2 + (word ^ 32'h9e3779b9);
    wire [31:0] n3 = lane3 + {word[15:0], word[31:16]};
    // 四路结果异或后输出。32 位溢出按模 2^32 自然截断，TB 使用同样的接口规格。
    wire [31:0] mixed = n0 ^ n1 ^ n2 ^ n3;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lane0 <= 0; lane1 <= 0; lane2 <= 0; lane3 <= 0;
            result_q <= 0;
        end else if (execute) begin
            // 非阻塞赋值保证四路都使用本拍之前的状态，而不是顺序更新后的值。
            lane0 <= n0; lane1 <= n1; lane2 <= n2; lane3 <= n3;
            result_q <= mixed;
        end
    end
endmodule
