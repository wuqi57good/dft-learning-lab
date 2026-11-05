// 用途：跨测试时钟域的串行数据隔离；C 是上游正沿 launch 时钟。
// C=0 时透明，C=1 时关闭。源正沿更新Q后，锁存器继续保存旧位到下一低相。
// 🔧 接收时钟稍晚到达时不会提前吞掉源新位；透明方向不能随意反写。
// ★ 只在本课设定的两个正沿时钟相位关系下成立；必须对 duty/skew 做真实 STA。
// 它不是 scan FF，不增加一个 pattern 位，也不能解决异步功能 CDC 的亚稳态。
module dft_lockup_latch(input wire C,D, output reg Q);
 always @* if (!C) Q = D;
endmodule
