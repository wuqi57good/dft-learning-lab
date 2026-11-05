// 用途：32×32 同步读写存储宏的接口与功能模型。
// 输入：clk、we、waddr/wdata、raddr；输出：同步读 rdata。
// v0 仿真编译下面数组；Yosys 定义 SYNTHESIS 后只读取 blackbox 端口壳。
// 未写地址与初始 rdata 故意为 X，符合未初始化 memory 的测试风险。
`ifdef SYNTHESIS
(* blackbox *)
`endif
module packet_mem (
    input wire clk, we,
    input wire [4:0] waddr, raddr,
    input wire [31:0] wdata,
    output reg [31:0] rdata
);
`ifndef SYNTHESIS
    reg [31:0] storage [0:31];
    // 同址读写采用 read-first：非阻塞 RHS 在写入生效前取旧内容。
    // 不给数组加 reset：那会改变宏接口，也掩盖 X 传播的真实教学对象。
    always @(posedge clk) begin
        if (we) storage[waddr] <= wdata;
        rdata <= storage[raddr];
    end
`endif
endmodule
