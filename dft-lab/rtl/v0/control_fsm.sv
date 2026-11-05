// 用途：一笔输入用 IDLE → EXEC → COMMIT 三个状态完成。
// 输入：clk/rst_n 与 in_valid；输出：ready/execute/commit。
// v0：一笔事务独占流水线；输出没有 backpressure，接收方必须总能接收。
// 依赖：无。状态编码属于实现细节，TB 只观察协议，不硬编码内部状态位。
module control_fsm (
    input wire clk, rst_n, in_valid,
    output wire ready, execute, commit
);
    localparam IDLE=2'b00, EXEC=2'b01, COMMIT=2'b10;
    reg [1:0] state;
    // ready 是组合的状态译码；上游必须保持 data，直到有效握手正沿。
    assign ready = (state == IDLE);
    assign execute = (state == EXEC);
    assign commit = (state == COMMIT);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else case (state)
            IDLE: if (in_valid) state <= EXEC;
            EXEC: state <= COMMIT;
            COMMIT: state <= IDLE;
            // 非法状态回到安全等待态；这不等于实现了安全认证机制。
            default: state <= IDLE;
        endcase
    end
endmodule
