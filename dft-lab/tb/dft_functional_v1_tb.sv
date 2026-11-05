// 用途：自检查 DUT v0；输出 PASS 标记与 build/scan/functional_v1.vcd。
// 依赖：Icarus Verilog，根目录运行 scripts/run.py sim。
// 时序：示例 sys 周期 10ns、aux 周期 14ns；TB 在负沿驱动，正沿后延迟 1ns 观察。
// 覆盖：复位、握手/忙时输入隔离、签名输出、memory 读回、X 传播、CDC、分频、软复位。
// 所有 PASS 文本是本项目定义的断言结果，不是任何商业工具的报告字段。
`timescale 1ns/1ps
module dft_functional_v1_tb;
    reg test_mode=0,test_rst_n=1,scan_clk=0,scan_en=0,test_te=0;
    reg scan_clk_aux=0; reg [31:0] test_bypass_data=0;
    reg [0:0] scan_in=0; wire [0:0] scan_out;
    reg sys_clk=0, aux_clk=0, rst_n_ext=0;
    always #5 sys_clk=~sys_clk;
    always #7 aux_clk=~aux_clk;
    reg cfg_valid=0, cfg_write=0;
    reg [7:0] cfg_addr=0;
    reg [31:0] cfg_wdata=0, data_in=0;
    reg data_valid=0;
    wire [31:0] cfg_rdata, data_out;
    wire cfg_ready, data_ready, data_out_valid, irq;
    wire [15:0] slow_ticks;
    reg [31:0] s0=0,s1=0,s2=0,s3=0,expected;
    reg [31:0] key_model=32'h13579bdf;
    reg [31:0] expected_memory[0:31];
    integer sent=0, i;
    dft_demo_top_v1 dut(.*);

    // 配置写在两个负沿之间保持，恰好覆盖一个正沿，不与 DUT 发生驱动竞争。
    task write_cfg(input [7:0] address, input [31:0] value);
        begin
            @(negedge sys_clk); cfg_valid=1; cfg_write=1;
            cfg_addr=address; cfg_wdata=value;
            @(posedge sys_clk); #1;
            if (cfg_ready !== 1'b1) $fatal(1,"cfg handshake failed");
            @(negedge sys_clk); cfg_valid=0; cfg_write=0;
        end
    endtask

    // 软件参考只按事务协议推进，不读取 DUT 的 lane 内部寄存器。
    task send_word(input [31:0] value);
        begin
            @(negedge sys_clk);
            while (!data_ready) @(negedge sys_clk);
            data_valid=1; data_in=value;
            s0=s0+(value^key_model);
            s1=s1+{value[23:0],value[31:24]};
            s2=s2+(value^32'h9e3779b9);
            s3=s3+{value[15:0],value[31:16]};
            expected=s0^s1^s2^s3;
            @(posedge sys_clk); #1;
            if (data_ready !== 0) $fatal(1,"busy not asserted");
            // 忙时故意改变总线且保持 valid，验证入口不会重收第二笔事务。
            @(negedge sys_clk); data_in=~value;
            @(posedge sys_clk); #1;
            if (data_out_valid !== 1 || data_out !== expected || irq !== 1)
                $fatal(1,"result mismatch: expected=%h observed=%h",expected,data_out);
            expected_memory[sent % 32]=expected;
            sent=sent+1;
            @(negedge sys_clk); data_valid=0;
            @(posedge sys_clk); #1;
            if (data_out_valid !== 0) $fatal(1,"commit pulse too long");
        end
    endtask

    initial begin
        $dumpfile("build/scan/functional_v1.vcd"); $dumpvars(0,dft_functional_v1_tb);
        // 除了时零初值，还产生一次真实的复位下降沿，保证事件驱动模型初始化。
        #1 rst_n_ext=1; #1 rst_n_ext=0;
        repeat(3) @(negedge sys_clk); rst_n_ext=1;
        repeat(3) @(posedge sys_clk); #1;
        if (data_ready !== 1 || data_out !== 0) $fatal(1,"reset failed");
        if (dut.n300 !== 1'bx) $fatal(1,"memory X should reach shadow");
        $display("PASS RESET_AND_MEMORY_X");
        write_cfg(8'h00,key_model);
        // 零、全一、进位边界和轮转数据覆盖常见功能错误。
        send_word(32'h00000000); send_word(32'hffffffff);
        send_word(32'h80000001); send_word(32'h12345678);
        for(i=0;i<36;i=i+1) send_word(32'h10203040+i*32'h01010101);
        $display("PASS DATA_PATH_AND_BUSY_HANDSHAKE transactions=%0d",sent);
        // 共 40 笔事务已越过 32 地址边界，验证环形覆盖和读延迟。
        for(i=0;i<32;i=i+1) begin
            write_cfg(8'h0c,i);
            repeat(2) @(posedge sys_clk); #1;
            cfg_addr=8'h10; #1;
            if(cfg_rdata !== expected_memory[i]) $fatal(1,"memory readback addr=%0d",i);
        end
        cfg_addr=8'h14; #1;
        if(cfg_rdata !== sent) $fatal(1,"gated counter mismatch");
        if({dut.n178,dut.n177,dut.n176,dut.n175,dut.n174,dut.n173,dut.n172,dut.n163} == 0 || slow_ticks == 0) $fatal(1,"clock domain inactive");
        $display("PASS MEMORY_WRAP_GATING_AND_CDC");
        write_cfg(8'h04,1);
        if(data_ready !== 0 || data_out !== 0) $fatal(1,"internal async reset failed");
        write_cfg(8'h04,0);
        s0=0;s1=0;s2=0;s3=0;sent=0;
        send_word(32'habcdef01);
        $display("PASS SOFT_RESET_RECOVERY");
        $display("PASS FUNCTIONAL_V1"); $finish;
    end
    // 有界超时使握手死锁变成失败，而不是永远挂着的仿真进程。
    initial begin #20000; $fatal(1,"watchdog timeout"); end
endmodule
