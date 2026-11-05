// 用途：简单配置接口，不宣称兼容 APB/AXI；addr 按字节寻址。
// 0x00：key；0x04：soft_reset bit0；0x08：状态；0x0c：memory 读地址。
// 0x10：memory 同步读结果；0x14：门控统计。其他地址读零。
// cfg_valid=1 时 cfg_ready=1，正沿写入；组合读取，memory 本身另有一拍延迟。
// v0：cfg 仅受外部复位，才能在 core soft_reset=1 时把它写回 0。
module cfg_regfile (
    input wire clk, rst_n_ext, cfg_valid, cfg_write,
    input wire [7:0] cfg_addr,
    input wire [31:0] cfg_wdata, status, mem_data,
    input wire [15:0] packet_count,
    output reg [31:0] cfg_rdata,
    output wire cfg_ready,
    output reg [31:0] key,
    output reg soft_reset,
    output reg [4:0] mem_raddr
);
    assign cfg_ready = cfg_valid;
    always @(posedge clk or negedge rst_n_ext) begin
        if (!rst_n_ext) begin key <= 0; soft_reset <= 0; mem_raddr <= 0; end
        else if (cfg_valid && cfg_write) case (cfg_addr)
            8'h00: key <= cfg_wdata;
            8'h04: soft_reset <= cfg_wdata[0];
            8'h0c: mem_raddr <= cfg_wdata[4:0];
            default: ;
        endcase
    end
    always @* begin
        cfg_rdata = 0;
        case (cfg_addr)
            8'h00: cfg_rdata = key;
            8'h04: cfg_rdata = {31'b0, soft_reset};
            8'h08: cfg_rdata = status;
            8'h0c: cfg_rdata = {27'b0, mem_raddr};
            8'h10: cfg_rdata = mem_data;
            8'h14: cfg_rdata = {16'b0, packet_count};
            default: ;
        endcase
    end
endmodule
