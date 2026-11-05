// 用途：集中生成 /4 时钟和内部低有效异步复位，故意保留 DFT 障碍。
// 输入：外部时钟/复位与 cfg 的 soft_reset；输出：div_clk、core_rst_n。
// v0：无 test_mode 接管；v1 将引入受约束的测试时钟/复位选择。
// ⚠ 易错点：功能可仿真不代表具备无毛刺切换或复位撤销的物理保证。
module clock_reset_mgr (
    input wire sys_clk, rst_n_ext, soft_reset,
    output wire div_clk, core_rst_n
);
    reg [1:0] divider;
    // 分频器自己只接受外部复位，否则 core_reset 可能同时改变时钟与被复位寄存器。
    always @(posedge sys_clk or negedge rst_n_ext)
        if (!rst_n_ext) divider <= 0;
        else divider <= divider + 1'b1;
    assign div_clk = divider[1];
    // ⚠ 易错点：组合内部复位对 scan 不可控；移位中的任意清零会破坏整条链状态。
    // 功能 TB 只在边沿之外释放复位；真实设计还要验证 recovery/removal 与同步撤销。
    assign core_rst_n = rst_n_ext & ~soft_reset;
endmodule
