// 用途：把 aux 域的一次事件变成 sys 域一个时钟宽度的脉冲。
// 输入：两个时钟、公共外部复位；输出：event_pulse。
// v0 用 toggle 编码，不直接同步一个可能短于 sys 周期的窄脉冲。
// 前置条件：相邻事件间隔足够长，至少允许目标域采样并传播两级同步器。
// 本例 aux 每 16 拍翻转一次，TB 的 aux=14ns/sys=10ns 只是仿真示例值。
module event_sync (
    input wire aux_clk, sys_clk, rst_n,
    output wire event_pulse
);
    reg [3:0] aux_count;
    reg toggle;
    (* async_reg = "true" *) reg sync1, sync2;
    reg previous;
    always @(posedge aux_clk or negedge rst_n) begin
        if (!rst_n) begin aux_count <= 0; toggle <= 0; end
        else begin
            aux_count <= aux_count + 1'b1;
            if (aux_count == 15) toggle <= ~toggle;
        end
    end
    always @(posedge sys_clk or negedge rst_n) begin
        if (!rst_n) begin sync1 <= 0; sync2 <= 0; previous <= 0; end
        else begin
            sync1 <= toggle;
            // 第二级给第一级可能的亚稳态更多恢复时间；数字仿真不能证明 MTBF。
            sync2 <= sync1;
            previous <= sync2;
        end
    end
    assign event_pulse = sync2 ^ previous;
endmodule
