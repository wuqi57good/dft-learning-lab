// 第二周只回放内嵌的实际 VCD 快照；不在浏览器伪造 DUT 信号值。
const w2=DATA.week2;
const moduleCards=[
 ['dft_demo_top','连接总图','sys/aux/外部复位 + cfg + data','accept→ingress；execute→mix；commit→memory/count；状态→cfg','只负责组合连接、写指针与事件计数。status[15:8] 是事件数，[7:4] 是负沿状态，[3] 是 shadow，[2:1] 是冗余/重汇聚，[0] 是 ready。','内部写使能与复位由功能状态驱动，后续测试模式要接管。','rtl/v0/dft_demo_top.sv'],
 ['packet_ingress','输入快照','sys 正沿 / core_rst_n','valid & ready → accept → word_q','32 位只在成交边沿保存；busy 时外部总线继续变动，word_q 保持。','只用 valid 作使能会覆盖正在消费的数据。','rtl/v0/packet_ingress.sv'],
 ['control_fsm','事务节拍','sys 正沿 / core_rst_n','IDLE → EXEC → COMMIT → IDLE','ready 译码 IDLE；execute 译码 EXEC；commit 译码 COMMIT。消费者在下一正沿使用这些电平。','功能转移可达不代表任意 scan 状态都安全；非法状态恢复另有明确分支。','rtl/v0/control_fsm.sv'],
 ['packet_mix','四路签名','sys 正沿 / core_rst_n / execute','word_q、key → 四路加法 → 异或 result_q','lane0 加 word^key；lane1 加左转8位；lane2 加 word^0x9E3779B9；lane3 加左转16位。所有更新按模 2³² 截断。','寄存器多但有真实外部用途，后续 scan 可以直接设置 lane；未实现 CRC 或加密。','rtl/v0/packet_mix.sv'],
 ['cfg_regfile','配置与观察','sys 正沿 / rst_n_ext','cfg_addr → key/soft_reset/mem_raddr 或状态读回','外部复位独立于 core。0x04 写1清核心，写0解除；0x10 读同步 memory 输出，要等待其延迟。','把 cfg 也接内部复位可能让 soft_reset 自清；运行中改 key 违背当前协议。','rtl/v0/cfg_regfile.sv'],
 ['fault_cone','重汇聚 / 冗余','组合，无时钟','word[0:2] → p/q → reconv；word[3:4] → r → redundant','a 共扇出重汇聚；r=d&e 被 d 吸收。独立输入避免与 p 共享结构。','必须在 JSON 检查 r 的唯一消费路径；保留网名并不等于保留故障靶点。','rtl/v0/fault_cone.sv'],
 ['clock_reset_mgr','时钟与复位根','sys 正沿 / rst_n_ext','divider[1] → div_clk；rst_n_ext & ~soft_reset → core_rst_n','分频计数器只由外部复位控制；组合内部复位随 soft_reset 立即变化。','逻辑分频不是测试时钟直通；复位释放的物理裕量尚未签核。','rtl/v0/clock_reset_mgr.sv'],
 ['gated_counter','提交计数','gated_clk 正沿 / core_rst_n','低电平 latch(enable) → clk AND → count','enable=commit。低相位可改变下一拍选择，高相位锁住选择以保持完整脉冲。','v0 没有 TE；latch+AND 不是已经映射并签核的库 ICG。','rtl/v0/gated_counter.sv'],
 ['rate_counter','慢速监控','div_clk 正沿 / core_rst_n','/4 clock → ticks → slow_ticks 顶层端口','这是独立暴露的多位调试输出，既不直接控制 sys 域，也不声称跨域读一致。','逻辑分频需要派生时钟关系；多位计数器直接跨域读可能混合新旧位。','rtl/v0/rate_counter.sv'],
 ['event_sync','跨域事件','aux + sys / rst_n_ext','aux_count → toggle → sync1 → sync2 → previous/XOR','aux 每16拍翻转；两级目标同步后与延迟一拍比较，形成目标单周期脉冲。','同步级数不是无损保证；事件过快会抵消，RTL 不模拟 MTBF。','rtl/v0/event_sync.sv'],
 ['neg_capture','负沿快照','sys 下降沿 / core_rst_n','shadow、redundant、reconv、commit → sampled → cfg status','只有负沿或复位事件更新；示例67ns保持0、71ns变A、73ns复位清零。','正负沿串链依赖测试波形定义和采样窗口，不能盲套顺序口诀。','rtl/v0/neg_capture.sv'],
 ['packet_mem','Memory 边界','sys 正沿，无内容复位','commit/data_out/write_pointer → 宏；mem_raddr → rdata','仿真是32×32 read-first 数组；综合定义 SYNTHESIS 时只保留端口黑盒。','未写内容为X；不计入普通DFF；测试写保护和 bypass 留到 v2。','rtl/v0/packet_mem.sv'],
 ['memory_shadow','宏外围观察','sys 正沿 / core_rst_n','rdata → XOR reduction → parity_q → status','与 memory 在同一正沿更新，因此读取旧 rdata，多一拍传播；不把 X 强制变0。','屏蔽X不能自动提高真实可测性，bypass 还需要周边控制/观察路径。','rtl/v0/memory_shadow.sv']
];
let selectedModule=0;
function drawModules(){
 $('#module-tabs').innerHTML=moduleCards.map((m,i)=>'<button data-module="'+i+'" class="'+(i===selectedModule?'active':'')+'" aria-pressed="'+(i===selectedModule)+'"><small>'+String(i+1).padStart(2,'0')+'</small>'+esc(m[0])+'</button>').join('');
 const m=moduleCards[selectedModule];
 $('#module-info').innerHTML='<span class="pill">'+esc(m[1])+'</span><h3>'+esc(m[0])+'</h3>'+
 '<dl><dt>时钟与入口</dt><dd>'+esc(m[2])+'</dd><dt>信号经过的路径</dt><dd class="module-path">'+esc(m[3])+'</dd><dt>内部职责</dt><dd>'+esc(m[4])+'</dd><dt>DFT 审读结论</dt><dd>'+esc(m[5])+'</dd></dl><button id="module-source" class="btn">打开该模块源码 ↗</button>';
 $$('[data-module]').forEach(b=>b.onclick=()=>{selectedModule=Number(b.dataset.module);drawModules();});
 $('#module-source').onclick=()=>{openFile(m[6]);$('#source').scrollIntoView({behavior:'smooth'});};
}
drawModules();
const replayRoutes={
 transaction:{rows:w2.transaction,signals:['valid','ready','data_in','word_q','execute','commit','result','write_pointer','mem_data','shadow'],notes:[
 '80ns：上游送出第一笔 data=0，valid=1；尚未到85ns的握手正沿。',
 '85ns：accept 成交，word_q=0；FSM进入EXEC，ready降为0。执行发生在下一正沿。',
 '90ns：TB在busy时把 data_in 改成全1并保持valid；word_q仍为0，证明握手隔离。',
 '95ns：mix使用已锁存的0和key完成计算；result=0x8D60E266，commit=1。memory尚未消费新commit。',
 '100ns：低相位门控锁存使能看到commit=1，准备让105ns脉冲到达计数器。',
 '105ns：memory写入结果、写指针变1；FSM回IDLE。read-first 读回仍是旧X。',
 '115ns：memory读寄存器得到首笔结果；shadow仍取旧X。',
 '125ns：shadow读取已知结果并计算奇偶校验；外部第二笔事务正同时推进。'
 ]},
 gate:{times:[18,26,28],signals:['clk','enable','gated_clk','direct_clk','good_count','bad_count'],notes:[
 '17ns高相位打开enable。18ns直接AND已产生伪上升沿，bad_count=1；锁存门控保持关闭，good_count=0。',
 '20ns进入低相位后锁存enable；25ns合法上升沿，两计数器各加1，26ns为good=1、bad=2。',
 '27ns高相位关闭enable。28ns直接AND已截断脉冲；锁存门控保持完整高相位直到30ns。'
 ]},
 memory:{times:[36,46,56],signals:['mem_we','mem_rdata','shadow'],notes:[
 '35ns同址写入1：read-first 返回原来的X；36ns rdata与shadow都未知。',
 '45ns memory读寄存器得到1；shadow同沿读取旧X。46ns数据已知但校验仍X。',
 '55ns shadow终于读取到1。56ns parity=1；清楚区分读出延迟与观察寄存器延迟。'
 ]},
 reset:{times:[67,71,73,81],signals:['clk','status','neg_sample','soft_reset','core_rst_n','slow_ticks'],notes:[
 '66ns改变status=A，67ns尚未到下降沿，neg_sample仍为0。',
 '70ns下降沿采样，71ns neg_sample=A。',
 '72ns内部soft_reset=1，不等待时钟就清零。73ns core_rst_n=0、neg_sample=0、slow_ticks=0。',
 '74ns释放内部复位，80ns下降沿恢复采样，81ns neg_sample=A。这里不证明物理撤销时序。'
 ]},
 cdc:{times:[1000],signals:['source_events','target_events'],notes:['到1000ns源事件与目标事件都是4。本例224ns源事件间隔给10ns目标时钟留下充分采样时间；不能推导任意时钟比都无损。']}
};
let replayIndex=0;
function drawReplay(){
 const route=replayRoutes[$('#w2-route').value],rows=route.rows||route.times.map(t=>w2.structures.find(row=>row.ns===t));
 replayIndex=Math.min(replayIndex,rows.length-1);const row=rows[replayIndex];
 $('#w2-time').textContent=row.ns+' ns · '+(replayIndex+1)+'/'+rows.length;
 $('#w2-timeline').innerHTML=rows.map((r,i)=>'<button data-snapshot="'+i+'" class="'+(i===replayIndex?'active':'')+'">'+r.ns+' ns</button>').join('');
 $('#w2-signals').innerHTML=route.signals.map(name=>{const value=row.values[name];return '<div class="signal-readout '+(/[xz]/.test(value.bits)?'unknown':'')+'"><small>'+esc(name)+'</small><b>'+esc(value.display.length>12&&/[XZ]/.test(value.display)?'X（未初始化）':value.display)+'</b><span>'+value.bits.length+' bit</span></div>';}).join('');
 $('#w2-replay-note').textContent=route.notes[replayIndex];
 $('#w2-prev').disabled=replayIndex===0;$('#w2-next').disabled=replayIndex===rows.length-1;
 $$('[data-snapshot]').forEach(b=>b.onclick=()=>{replayIndex=Number(b.dataset.snapshot);drawReplay();});
}
$('#w2-route').onchange=()=>{replayIndex=0;drawReplay();};$('#w2-prev').onclick=()=>{replayIndex--;drawReplay();};$('#w2-next').onclick=()=>{replayIndex++;drawReplay();};$('#w2-replay-reset').onclick=()=>{replayIndex=0;drawReplay();};drawReplay();
$('#w2-log').textContent=w2.log.split('\n').filter(l=>/^(PASS|OBS)/.test(l)).join('\n');
const quizzes=[
 ['95ns进入COMMIT，为什么memory在105ns才写？',['memory有任意10ns模拟延迟','同一正沿memory读取的是更新前的commit','需要再等一个aux_clk'],1,'同一正沿各过程读旧状态，FSM更新后commit才组合变高；下个sys正沿才消费它。不是给memory写了#10，也与aux无关。'],
 ['r=d&e，z=d|r。r/SA0有几个检测组合？',['0：激活时d已屏蔽差异','16：随机试一半即可','32：所有输入都有影响'],0,'r要为1必须d=e=1，此时z由d固定为1；故障r变0仍不可观察。这是无解，不是随机搜索不足。'],
 ['为什么冗余r不复用p的a/b输入？',['Verilog不能复用输入','使用独立输入会消除所有故障','避免综合合并r和p而产生额外观察路径'],2,'综合器可能共享相同AND，r将沿reconv被观察，原证明失效。独立d/e不消除故障，只让预定拓扑更明确；仍需检查JSON。'],
 ['17ns在高相位拉高enable，直接AND有什么风险？',['可能制造额外上升沿','一定要等25ns才变化','能自动同步enable'],0,'组合AND不等时钟；本例17ns立即从0到1。低相位锁存保持旧选择到低相位，才能避免这个事件。'],
 ['两级同步器说明了什么？',['任意速率事件都不会丢','降低亚稳态传播风险，但仍需事件速率/协议约束','可以直接同步任意多位总线'],1,'两级提供恢复时间；toggle过快可抵消，多位总线也可能混合新旧值。需要合理的握手/FIFO与物理MTBF分析。'],
 ['为什么cfg寄存器使用外部复位？',['保证core复位时仍能写0解除soft_reset','让所有时序都自动安全','让memory自动清零'],0,'若复位控制位也被自身清零，可能改变脉冲语义。独立配置复位保持可解除性，但不替代恢复/移除时序检查，也不清memory。'],
 ['46ns rdata=1、shadow=X，合理吗？',['不合理，应强制X=0','合理：shadow在45ns读旧rdata，55ns才读到1','说明整个memory不可用'],1,'两者都是正沿非阻塞更新，shadow额外延迟一拍。未初始化X是模型边界，不要通过强制零掩盖它。'],
 ['本周能否宣布NAND2门数达标、STA通过？',['能，因为已有1760个generic cells','能，因为存在v0.sdc','不能：面积映射和完整STA尚未执行'],2,'generic cell和NAND2面积单位不同。SDC只是意图草案，缺少完整时钟/I/O/库/布线条件，读入成功也不等于签核。']
];
function renderQuiz(){
 $('#w2-quiz-items').innerHTML=quizzes.map((q,i)=>'<fieldset><legend>'+(i+1)+'. '+esc(q[0])+'</legend>'+q[1].map((text,j)=>'<label><input type="radio" name="w2q'+i+'" value="'+j+'"> '+esc(text)+'</label>').join('')+'<p id="w2q-feedback-'+i+'" class="quiz-feedback" hidden></p></fieldset>').join('');
}
renderQuiz();
$('#w2-check-quiz').onclick=()=>{
 let score=0,answered=0;quizzes.forEach((q,i)=>{const choice=$('input[name="w2q'+i+'"]:checked'),ok=choice&&Number(choice.value)===q[2],feedback=$('#w2q-feedback-'+i);if(choice)answered++;if(ok)score++;
 feedback.hidden=false;feedback.className='quiz-feedback '+(ok?'correct':'review');feedback.textContent=(ok?'✓ 判断正确。':choice?'再看一步。':'尚未选择。')+'参考：'+q[1][q[2]]+'。'+q[3];});
 $('#w2-score').textContent=score+'/8 正确 · 已作答 '+answered+'/8';
};
$('#w2-reset-quiz').onclick=()=>{renderQuiz();$('#w2-score').textContent='';};
try{$('#w2-notes').value=localStorage.getItem('dft-week2-notes')||'';}catch{}
$('#w2-notes').oninput=()=>{try{localStorage.setItem('dft-week2-notes',$('#w2-notes').value);$('#w2-note-save').textContent='已保存到当前浏览器';}catch{$('#w2-note-save').textContent='浏览器未允许保存，请立即导出';}};
$('#w2-export-notes').onclick=()=>downloadText('DFT-第二周-我的审读笔记.md','# DFT 第二周审读笔记\n\n'+$('#w2-notes').value+'\n\n实验依据：structures.log / structures.vcd / week2.json。\n');
$('#w2-export-evidence').onclick=()=>downloadText('week2.json',JSON.stringify(w2,null,2));

