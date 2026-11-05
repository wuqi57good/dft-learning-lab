// 自动生成自检TB：链映射来自真实插入结果，shift期有独立序列化参考模型。
// CLK先正后负，SO正沿前采样。aux晚2ns；N单元位于P单元之前。
// Capture后保存实际Q快照再移出，另用已知旁路奇偶值验证v2捕获不是空操作。
`timescale 1ns/1ps
module scan_v1_tb;
reg sys_clk=0,aux_clk=0,rst_n_ext=1,cfg_valid=0,cfg_write=0,data_valid=0;
reg [7:0] cfg_addr=0; reg [31:0] cfg_wdata=0,data_in=0;
wire [31:0] cfg_rdata,data_out; wire cfg_ready,data_ready,data_out_valid,irq; wire [15:0] slow_ticks;
reg test_mode=1,test_rst_n=0,scan_clk=0,scan_clk_aux=0,scan_en=1,test_te=1;
reg [31:0] test_bypass_data=1;
reg [0:0] scan_in=0; wire [0:0] scan_out;
reg [31:0] random_state=32'h1a2b3c4d;
integer step,i;
reg [292:0] expected_0;
initial expected_0 = 293'b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001000000000000000000000000000000000000000000000000000000000000;
dft_demo_top_v1 dut(.sys_clk(sys_clk),.aux_clk(aux_clk),.rst_n_ext(rst_n_ext),
.cfg_valid(cfg_valid),.cfg_write(cfg_write),.cfg_addr(cfg_addr),.cfg_wdata(cfg_wdata),
.cfg_rdata(cfg_rdata),.cfg_ready(cfg_ready),.data_valid(data_valid),.data_in(data_in),
.data_ready(data_ready),.data_out_valid(data_out_valid),.data_out(data_out),.irq(irq),.slow_ticks(slow_ticks),
.test_mode(test_mode),.test_rst_n(test_rst_n),.scan_clk(scan_clk),.scan_en(scan_en),
.test_te(test_te),.scan_in(scan_in),.scan_out(scan_out));
task cycle;
begin
  #3 scan_clk=1; sys_clk=1;
  #2 scan_clk_aux=1; aux_clk=1;
  #3 scan_clk=0; sys_clk=0;
  #2 scan_clk_aux=0; aux_clk=0;
  #2;
end
endtask
task shift_once;
begin
  if(scan_out[0] !== expected_0[292]) $fatal(1,"SO mismatch chain=0 step=%0d", step);
  expected_0 = {expected_0[291:0],scan_in[0]};
  cycle;
  if({dut.n341,dut.n340,dut.n339,dut.n334,dut.n356,dut.n162,dut.n161,dut.n160,dut.n159,dut.n158,dut.n157,dut.n156,dut.n155,dut.n154,dut.n153,dut.n152,dut.n151,dut.n150,dut.n149,dut.n148,dut.n147,dut.n300,dut.n1627,dut.n1626,dut.n1625,dut.n1624,dut.n1623,dut.n1622,dut.n1621,dut.n1620,dut.n1619,dut.n1618,dut.n1617,dut.n1616,dut.n1615,dut.n1614,dut.n1613,dut.n1612,dut.n1611,dut.n1610,dut.n1609,dut.n1608,dut.n1607,dut.n1606,dut.n1605,dut.n1604,dut.n1603,dut.n1602,dut.n1601,dut.n1600,dut.n1599,dut.n1598,dut.n1597,dut.n1596,dut.n1563,dut.n1562,dut.n1561,dut.n1560,dut.n1559,dut.n1558,dut.n1557,dut.n1556,dut.n1555,dut.n1554,dut.n1553,dut.n1552,dut.n1551,dut.n1550,dut.n1549,dut.n1548,dut.n1547,dut.n1546,dut.n1545,dut.n1544,dut.n1543,dut.n1542,dut.n1541,dut.n1540,dut.n1539,dut.n1538,dut.n1537,dut.n1536,dut.n1535,dut.n1534,dut.n1533,dut.n1532,dut.n1659,dut.n1658,dut.n1657,dut.n1656,dut.n1655,dut.n1654,dut.n1653,dut.n1652,dut.n1651,dut.n1650,dut.n1649,dut.n1648,dut.n1647,dut.n1646,dut.n1645,dut.n1644,dut.n1643,dut.n1642,dut.n1641,dut.n1640,dut.n1639,dut.n1638,dut.n1637,dut.n1636,dut.n1635,dut.n1634,dut.n1633,dut.n1632,dut.n1631,dut.n1630,dut.n1629,dut.n1628,dut.n146,dut.n145,dut.n144,dut.n143,dut.n142,dut.n141,dut.n140,dut.n139,dut.n138,dut.n137,dut.n136,dut.n135,dut.n134,dut.n133,dut.n132,dut.n131,dut.n130,dut.n129,dut.n128,dut.n127,dut.n126,dut.n125,dut.n124,dut.n123,dut.n122,dut.n121,dut.n120,dut.n119,dut.n118,dut.n117,dut.n116,dut.n115,dut.n1595,dut.n1594,dut.n1593,dut.n1592,dut.n1591,dut.n1590,dut.n1589,dut.n1588,dut.n1587,dut.n1586,dut.n1585,dut.n1584,dut.n1583,dut.n1582,dut.n1581,dut.n1580,dut.n1579,dut.n1578,dut.n1577,dut.n1576,dut.n1575,dut.n1574,dut.n1573,dut.n1572,dut.n1571,dut.n1570,dut.n1569,dut.n1568,dut.n1567,dut.n1566,dut.n1565,dut.n1564,dut.n333,dut.n332,dut.n331,dut.n330,dut.n329,dut.n328,dut.n327,dut.n326,dut.n325,dut.n324,dut.n323,dut.n322,dut.n321,dut.n320,dut.n319,dut.n318,dut.n317,dut.n316,dut.n315,dut.n314,dut.n313,dut.n312,dut.n311,dut.n310,dut.n309,dut.n308,dut.n307,dut.n306,dut.n305,dut.n304,dut.n303,dut.n302,dut.n296,dut.n295,dut.n294,dut.n293,dut.n292,dut.n291,dut.n290,dut.n289,dut.n288,dut.n287,dut.n286,dut.n285,dut.n284,dut.n283,dut.n282,dut.n281,dut.n207,dut.n114,dut.n297,dut.n205,dut.n602,dut.n239,dut.n238,dut.n237,dut.n236,dut.n235,dut.n234,dut.n233,dut.n232,dut.n231,dut.n230,dut.n229,dut.n228,dut.n227,dut.n226,dut.n225,dut.n224,dut.n223,dut.n222,dut.n221,dut.n220,dut.n219,dut.n218,dut.n217,dut.n216,dut.n215,dut.n214,dut.n213,dut.n212,dut.n211,dut.n210,dut.n209,dut.n208,dut.n276,dut.n275,dut.n274,dut.n273,dut.n272,dut.n301,dut.n353,dut.n355,dut.n354,dut.n178,dut.n177,dut.n176,dut.n175,dut.n174,dut.n173,dut.n172,dut.n163,dut.n195,dut.n194,dut.n193,dut.n192,dut.n186,dut.n280,dut.n279,dut.n278,dut.n277} !== expected_0) $fatal(1,"state mismatch chain=0 step=%0d", step);
end
endtask
initial begin
  $dumpfile("build/scan/v1.vcd"); $dumpvars(0,scan_v1_tb);
  // 创建确定的复位事件；RTL reg初值不能替代一个真实reset脉冲。
  #1 test_rst_n=1; #1 test_rst_n=0; #2 test_rst_n=1;
  
  for(step=0;step<586;step=step+1) begin
    random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
    scan_in=random_state; shift_once;
  end
  $display("PASS SHIFT_V1 cells=293 cycles=586");
  // 扫入全零，避免功能enable/地址随机状态干扰可解释的capture实验。
  scan_in=0;
  for(step=0;step<293;step=step+1) shift_once;
  scan_en=0; cycle;
  
  expected_0 = {dut.n341,dut.n340,dut.n339,dut.n334,dut.n356,dut.n162,dut.n161,dut.n160,dut.n159,dut.n158,dut.n157,dut.n156,dut.n155,dut.n154,dut.n153,dut.n152,dut.n151,dut.n150,dut.n149,dut.n148,dut.n147,dut.n300,dut.n1627,dut.n1626,dut.n1625,dut.n1624,dut.n1623,dut.n1622,dut.n1621,dut.n1620,dut.n1619,dut.n1618,dut.n1617,dut.n1616,dut.n1615,dut.n1614,dut.n1613,dut.n1612,dut.n1611,dut.n1610,dut.n1609,dut.n1608,dut.n1607,dut.n1606,dut.n1605,dut.n1604,dut.n1603,dut.n1602,dut.n1601,dut.n1600,dut.n1599,dut.n1598,dut.n1597,dut.n1596,dut.n1563,dut.n1562,dut.n1561,dut.n1560,dut.n1559,dut.n1558,dut.n1557,dut.n1556,dut.n1555,dut.n1554,dut.n1553,dut.n1552,dut.n1551,dut.n1550,dut.n1549,dut.n1548,dut.n1547,dut.n1546,dut.n1545,dut.n1544,dut.n1543,dut.n1542,dut.n1541,dut.n1540,dut.n1539,dut.n1538,dut.n1537,dut.n1536,dut.n1535,dut.n1534,dut.n1533,dut.n1532,dut.n1659,dut.n1658,dut.n1657,dut.n1656,dut.n1655,dut.n1654,dut.n1653,dut.n1652,dut.n1651,dut.n1650,dut.n1649,dut.n1648,dut.n1647,dut.n1646,dut.n1645,dut.n1644,dut.n1643,dut.n1642,dut.n1641,dut.n1640,dut.n1639,dut.n1638,dut.n1637,dut.n1636,dut.n1635,dut.n1634,dut.n1633,dut.n1632,dut.n1631,dut.n1630,dut.n1629,dut.n1628,dut.n146,dut.n145,dut.n144,dut.n143,dut.n142,dut.n141,dut.n140,dut.n139,dut.n138,dut.n137,dut.n136,dut.n135,dut.n134,dut.n133,dut.n132,dut.n131,dut.n130,dut.n129,dut.n128,dut.n127,dut.n126,dut.n125,dut.n124,dut.n123,dut.n122,dut.n121,dut.n120,dut.n119,dut.n118,dut.n117,dut.n116,dut.n115,dut.n1595,dut.n1594,dut.n1593,dut.n1592,dut.n1591,dut.n1590,dut.n1589,dut.n1588,dut.n1587,dut.n1586,dut.n1585,dut.n1584,dut.n1583,dut.n1582,dut.n1581,dut.n1580,dut.n1579,dut.n1578,dut.n1577,dut.n1576,dut.n1575,dut.n1574,dut.n1573,dut.n1572,dut.n1571,dut.n1570,dut.n1569,dut.n1568,dut.n1567,dut.n1566,dut.n1565,dut.n1564,dut.n333,dut.n332,dut.n331,dut.n330,dut.n329,dut.n328,dut.n327,dut.n326,dut.n325,dut.n324,dut.n323,dut.n322,dut.n321,dut.n320,dut.n319,dut.n318,dut.n317,dut.n316,dut.n315,dut.n314,dut.n313,dut.n312,dut.n311,dut.n310,dut.n309,dut.n308,dut.n307,dut.n306,dut.n305,dut.n304,dut.n303,dut.n302,dut.n296,dut.n295,dut.n294,dut.n293,dut.n292,dut.n291,dut.n290,dut.n289,dut.n288,dut.n287,dut.n286,dut.n285,dut.n284,dut.n283,dut.n282,dut.n281,dut.n207,dut.n114,dut.n297,dut.n205,dut.n602,dut.n239,dut.n238,dut.n237,dut.n236,dut.n235,dut.n234,dut.n233,dut.n232,dut.n231,dut.n230,dut.n229,dut.n228,dut.n227,dut.n226,dut.n225,dut.n224,dut.n223,dut.n222,dut.n221,dut.n220,dut.n219,dut.n218,dut.n217,dut.n216,dut.n215,dut.n214,dut.n213,dut.n212,dut.n211,dut.n210,dut.n209,dut.n208,dut.n276,dut.n275,dut.n274,dut.n273,dut.n272,dut.n301,dut.n353,dut.n355,dut.n354,dut.n178,dut.n177,dut.n176,dut.n175,dut.n174,dut.n173,dut.n172,dut.n163,dut.n195,dut.n194,dut.n193,dut.n192,dut.n186,dut.n280,dut.n279,dut.n278,dut.n277};
  scan_en=1;
  for(step=0;step<293;step=step+1) shift_once;
  
  $display("PASS CAPTURE_AND_SHIFT_OUT_V1");
  $display("PASS SCAN_V1"); $finish;
end
initial begin #100000; $fatal(1,"scan watchdog"); end
endmodule
