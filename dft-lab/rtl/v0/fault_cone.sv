// 用途：明确保留一个重汇聚锥和一个冗余故障靶点，供后续 ATPG 对照。
// 输入 a/b/c/d/e 来自已锁存的数据；输出送入可读状态，避免整锥因无观察端被删除。
// v0 使用 keep 保护结构；是否真的保留必须查看实际 JSON，不能只相信属性。
// synth_v0.ys 用 -noabc，避免后续布尔映射再次把冗余关系整体化简。
module fault_cone (
    input wire a, b, c, d, e,
    output wire reconv, redundant
);
    // 🔧 重汇聚：a 同时沿直通和取反支路到达 reconv。
    // q/SA1 可先用 a=1 激活 q=0；传播需 p=0，若先选 a=0 会冲突，回退改选 b=0。
    (* keep = 1 *) wire p = a & b;
    (* keep = 1 *) wire q = ~a & c;
    assign reconv = p | q;
    // ⚠ 易错点：r 是冗余支路；redundant = d | (d & e) 恒等于 d。
    // 另用 d/e，避免 r 与 p 被公共子表达式优化合并，从 reconv 意外观察到 r。
    // r/SA0 不可检测：d=0 时 r 本来为 0；d=1 时输出被直通的 d 固定为 1。
    // r/SA1 却可检测：令 d=0，正常输出 0、故障输出 1。不可一概说整锥不可测。
    (* keep = 1 *) wire r = d & e;
    assign redundant = d | r;
endmodule
