// 用途：第二周的结构实验，直接例化已有 v0 模块并检查五类 DFT 教学对象。
// 输入：rtl/v0/*.sv；输出：build/v0/structures.vcd 和项目自定义 PASS 标记。
// 依赖：Icarus Verilog；入口 python scripts/run.py structures。
// 演进：v0 结构审读。本文件不修改 DUT，也不声称完成 scan、ATPG 或工艺签核。
// 时序：所有 # 延迟都是 TB 示例值。force 只用于明确的故障注入，正常结果单独保存。
`timescale 1ns/1ps
module structures_tb;
    // 10ns/14ns 是两个独立源的示例周期；非任意事件频率下无损的 CDC 证明。
    reg clk=0, aux_clk=0, rst_n=0;
    always #5 clk=~clk;
    always #7 aux_clk=~aux_clk;
    reg [4:0] abcde=0;
    wire reconv, redundant;
    fault_cone cone(.a(abcde[4]),.b(abcde[3]),.c(abcde[2]),
        .d(abcde[1]),.e(abcde[0]),.reconv(reconv),.redundant(redundant));
    reg gate_enable=0;
    wire [15:0] good_count;
    gated_counter gate(.clk(clk),.rst_n(rst_n),.enable(gate_enable),.count(good_count));
    // ⚠ 故意的反例：高相位改变 enable 会让 bad_clk 出现额外上升沿。
    wire bad_clk=clk & gate_enable;
    reg [15:0] bad_count;
    always @(posedge bad_clk or negedge rst_n)
        if(!rst_n) bad_count<=0; else bad_count<=bad_count+1'b1;
    reg soft_reset=0;
    wire div_clk, core_rst_n;
    wire [15:0] slow_ticks;
    clock_reset_mgr clocks(.sys_clk(clk),.rst_n_ext(rst_n),.soft_reset(soft_reset),
        .div_clk(div_clk),.core_rst_n(core_rst_n));
    rate_counter slow(.div_clk(div_clk),.rst_n(core_rst_n),.ticks(slow_ticks));
    reg [3:0] status=0;
    wire [3:0] neg_sample;
    neg_capture negative(.clk(clk),.rst_n(core_rst_n),.status(status),.sampled(neg_sample));
    wire event_pulse;
    event_sync cdc(.sys_clk(clk),.aux_clk(aux_clk),.rst_n(rst_n),.event_pulse(event_pulse));
    reg mem_we=0;
    reg [4:0] mem_waddr=3,mem_raddr=3;
    reg [31:0] mem_wdata=0;
    wire [31:0] mem_rdata;
    wire shadow;
    packet_mem memory(.clk(clk),.we(mem_we),.waddr(mem_waddr),
        .wdata(mem_wdata),.raddr(mem_raddr),.rdata(mem_rdata));
    memory_shadow boundary(.clk(clk),.rst_n(rst_n),.rdata(mem_rdata),.parity_q(shadow));
    integer i, r_sa0_detect=0,r_sa1_detect=0,q_sa1_detect=0;
    integer source_events=0,target_events=0;
    reg good_reconv,good_redundant;
    reg fault_done=0,gate_done=0,memory_done=0,clock_done=0,cdc_done=0;
    time first_div_edge;

    initial begin
        $dumpfile("build/v0/structures.vcd");$dumpvars(0,structures_tb);
        // 显式低沿初始化异步复位；12ns 释放，不与 clk/aux 的采样边沿重合。
        #1 rst_n=1;#1 rst_n=0;#10 rst_n=1;
    end

    initial begin
        // 穷举五个输入的 32 种组合，比较正常与强制单节点故障后的模块输出。
        // 单个故障结束后必须 release；否则后面的正常基准也会被污染。
        for(i=0;i<32;i=i+1) begin
            abcde=i;#1;
            good_reconv=reconv;good_redundant=redundant;
            if(good_reconv !== ((abcde[4]&abcde[3])|(~abcde[4]&abcde[2])))
                $fatal(1,"reconvergent functional mismatch");
            if(good_redundant !== abcde[1]) $fatal(1,"redundant identity mismatch");
            force cone.r=1'b0;#1;
            if(redundant !== good_redundant) r_sa0_detect=r_sa0_detect+1;
            release cone.r;#1;
            force cone.r=1'b1;#1;
            if(redundant !== good_redundant) r_sa1_detect=r_sa1_detect+1;
            release cone.r;#1;
            force cone.q=1'b1;#1;
            if(reconv !== good_reconv) q_sa1_detect=q_sa1_detect+1;
            release cone.q;#1;
        end
        // 这些是检测该故障的输入组合数；不是覆盖了多少个故障的 coverage。
        if(r_sa0_detect!=0 || r_sa1_detect!=16 || q_sa1_detect!=16)
            $fatal(1,"fault detection counts differ: %0d %0d %0d",r_sa0_detect,r_sa1_detect,q_sa1_detect);
        $display("PASS W2_FAULT_TRUTH vectors=32 r_sa0=0 r_sa1=16 q_sa1=16");
        fault_done=1;
    end

    initial begin
        // clk 在 15ns 上升；17ns enable 才变高，直连 AND 会制造一个不该有的边沿。
        #17 gate_enable=1;#1;
        if(good_count!==0 || bad_count!==1) $fatal(1,"gate did not isolate high-phase enable");
        $display("OBS W2_GATE ns=18 latched=0 direct=1");
        // 20ns 低相位 latch 打开，到 25ns 合法边沿才让 good_count 增加。
        #8;
        if(good_count!==1 || bad_count!==2) $fatal(1,"gated edge mismatch");
        #1 gate_enable=0;#1;
        if(gate.gated_clk!==1'b1 || bad_clk!==1'b0) $fatal(1,"direct clock should truncate at 27ns");
        $display("PASS W2_ICG latched_count=1 direct_count=2");
        gate_done=1;
    end

    initial begin
        // 写前输出未知；35ns 同址写入 1，read-first 仍输出旧 X。
        #30;
        if((^mem_rdata)!==1'bx || shadow!==1'bx) $fatal(1,"expected memory X before write");
        mem_we=1;mem_wdata=32'h1;#6;
        if((^mem_rdata)!==1'bx) $fatal(1,"memory must be read-first");
        $display("OBS W2_MEMORY ns=36 rdata=X shadow=X");
        #4 mem_we=0;#6;
        if(mem_rdata!==32'h1 || shadow!==1'bx) $fatal(1,"memory read latency mismatch");
        $display("OBS W2_MEMORY ns=46 rdata=00000001 shadow=X");
        #10;
        if(shadow!==1'b1) $fatal(1,"shadow should observe parity one cycle later");
        $display("OBS W2_MEMORY ns=56 rdata=00000001 shadow=1");
        $display("PASS W2_MEMORY read_first=1 shadow_extra_cycle=1");
        memory_done=1;
    end

    initial begin
        wait(rst_n===1'b1); // 时零的小脉冲还未产生 /4 正沿，不影响后面的观察。
        @(posedge div_clk);first_div_edge=$time;
        @(posedge div_clk);
        if($time-first_div_edge!=40) $fatal(1,"divider is not /4");
        // 66ns 状态输入改变，70ns 负沿采样；67ns 尚不能提前更新。
        #1 status=4'ha;#1;
        if(neg_sample!==0) $fatal(1,"negedge sample moved too early");
        #4;
        if(neg_sample!==4'ha) $fatal(1,"missing negedge sample");
        // 72ns 异步拉低内部复位，无需等待任何正/负时钟沿。
        #1 soft_reset=1;#1;
        if(core_rst_n!==0 || neg_sample!==0 || slow_ticks!==0) $fatal(1,"asynchronous reset not effective");
        $display("OBS W2_RESET ns=73 core_rst_n=0 neg_sample=0 slow_ticks=0");
        #1 soft_reset=0;#7;
        if(neg_sample!==4'ha) $fatal(1,"reset release did not restore operation");
        $display("PASS W2_CLOCK_RESET divider_period_ns=40 negedge_value=A");
        clock_done=1;
    end

    // 在仿真终点比较事件数，单独统计源 toggle 与目标采样到的脉冲。
    // 该检查仅证明本例时钟比下的数字行为；不是 MTBF 或任意异步相位证明。
    always @(cdc.toggle) if(rst_n===1'b1) source_events=source_events+1;
    always @(posedge clk) if(rst_n===1'b1 && event_pulse===1'b1) target_events=target_events+1;
    initial begin
        #1000;
        if(source_events!=4 || target_events!=4) $fatal(1,"event count mismatch: %0d/%0d",source_events,target_events);
        $display("PASS W2_CDC source_events=4 target_events=4");
        cdc_done=1;
    end
    initial begin
        wait(fault_done && gate_done && memory_done && clock_done && cdc_done);
        $display("PASS STRUCTURES_V0");$finish;
    end
    initial begin #2000;$fatal(1,"structure test timeout");end
endmodule
