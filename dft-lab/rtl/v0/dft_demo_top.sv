// 用途：可处理 32 位数据流的小型签名/控制子系统，连接全部五类 DFT 教学结构。
// 输入：两个独立功能时钟、外部低有效复位、配置接口、ready/valid 数据接口。
// 输出：签名结果、提交脉冲 IRQ、慢域调试计数。v0 尚无 scan 端口。
// 演进：v1 才增加 scan_clk/scan_en/test_mode；v2 加多链与 memory bypass。
// 门数目标：2,000–5,000 NAND2 等效门；本批无 Liberty 面积签核，禁止写成实测达标。
module dft_demo_top (
    input wire sys_clk, aux_clk, rst_n_ext,
    input wire cfg_valid, cfg_write,
    input wire [7:0] cfg_addr,
    input wire [31:0] cfg_wdata,
    output wire [31:0] cfg_rdata,
    output wire cfg_ready,
    input wire data_valid,
    input wire [31:0] data_in,
    output wire data_ready, data_out_valid,
    output wire [31:0] data_out,
    output wire irq,
    output wire [15:0] slow_ticks
);
    wire soft_reset, core_rst_n, div_clk;
    wire ready, execute, commit, event_pulse;
    wire [31:0] key, word_q, mem_data;
    wire [4:0] mem_raddr;
    wire [15:0] packet_count;
    wire reconv, redundant, shadow_parity;
    wire [3:0] neg_status;
    reg [4:0] write_pointer;
    reg [7:0] events_seen;
    wire [31:0] status = {16'b0, events_seen, neg_status,
                         shadow_parity, redundant, reconv, ready};
    assign data_ready = ready & core_rst_n;
    wire accept = data_valid & data_ready;
    assign data_out_valid = commit;
    assign irq = commit;

    cfg_regfile u_cfg(.clk(sys_clk), .rst_n_ext(rst_n_ext),
        .cfg_valid(cfg_valid), .cfg_write(cfg_write), .cfg_addr(cfg_addr),
        .cfg_wdata(cfg_wdata), .cfg_rdata(cfg_rdata), .cfg_ready(cfg_ready),
        .status(status), .mem_data(mem_data), .packet_count(packet_count),
        .key(key), .soft_reset(soft_reset), .mem_raddr(mem_raddr));
    clock_reset_mgr u_clock(.sys_clk(sys_clk), .rst_n_ext(rst_n_ext),
        .soft_reset(soft_reset), .div_clk(div_clk), .core_rst_n(core_rst_n));
    control_fsm u_control(.clk(sys_clk), .rst_n(core_rst_n), .in_valid(accept),
        .ready(ready), .execute(execute), .commit(commit));
    packet_ingress u_ingress(.clk(sys_clk), .rst_n(core_rst_n),
        .accept(accept), .data_in(data_in), .word_q(word_q));
    packet_mix u_mix(.clk(sys_clk), .rst_n(core_rst_n), .execute(execute),
        .word(word_q), .key(key), .result_q(data_out));
    fault_cone u_fault(.a(word_q[0]), .b(word_q[1]), .c(word_q[2]),
        .d(word_q[3]), .e(word_q[4]),
        .reconv(reconv), .redundant(redundant));
    event_sync u_cdc(.aux_clk(aux_clk), .sys_clk(sys_clk),
        .rst_n(rst_n_ext), .event_pulse(event_pulse));
    gated_counter u_count(.clk(sys_clk), .rst_n(core_rst_n),
        .enable(commit), .count(packet_count));
    rate_counter u_slow(.div_clk(div_clk), .rst_n(core_rst_n), .ticks(slow_ticks));
    neg_capture u_neg(.clk(sys_clk), .rst_n(core_rst_n),
        .status({shadow_parity, redundant, reconv, commit}), .sampled(neg_status));
    // ⚠ v0 写使能没有 test_mode 门控：未来 scan 移位可能误触发 commit 并写坏 memory。
    packet_mem u_memory(.clk(sys_clk), .we(commit), .waddr(write_pointer),
        .wdata(data_out), .raddr(mem_raddr), .rdata(mem_data));
    memory_shadow u_shadow(.clk(sys_clk), .rst_n(core_rst_n),
        .rdata(mem_data), .parity_q(shadow_parity));

    always @(posedge sys_clk or negedge core_rst_n) begin
        if (!core_rst_n) begin write_pointer <= 0; events_seen <= 0; end
        else begin
            // 32 个地址环形覆盖，写指针只在提交正沿推进。
            if (commit) write_pointer <= write_pointer + 1'b1;
            if (event_pulse) events_seen <= events_seen + 1'b1;
        end
    end
endmodule
