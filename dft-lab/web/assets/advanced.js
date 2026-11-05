// 第三至七周的证据全部读取构建时嵌入的实际 JSON；页面不启动 EDA 进程。
const evidence=DATA.evidence;
const report=(name)=>evidence[name];
const table=(headers,rows)=>'<div class="table-scroll"><table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
const metric=(name,value,detail)=>'<div class="proof-card"><span>'+esc(name)+'</span><b>'+esc(value)+'</b><p>'+esc(detail)+'</p></div>';
function reportDetails(name){return '<details class="accordion evidence-json"><summary>打开原始报告 · '+esc(name)+'</summary><pre>'+esc(JSON.stringify(report(name),null,2))+'</pre><button class="btn" data-report="'+esc(name)+'">导出 JSON</button></details>';}

const inv=report('drc/inventory.json');
$('#w3-evidence').innerHTML='<div class="three-col">'+metric('真实触发器',inv.register_count,'按实例展开；使能类型计入 DFF')+metric('时钟连接组',inv.clock_groups.length,'不是全部互相异步；仍要追溯来源')+metric('负沿 / Memory',inv.negative_edge_count+' / '+inv.memory_instances.length,'门控使能 latch 不算扫描触发器')+'</div>'+table(['时钟网线别名','触发器数量'],inv.clock_groups.map(g=>[g.aliases[0],g.count]))+table(['复位网线别名','触发器数量'],inv.reset_groups.map(g=>[g.aliases[0],g.count]))+reportDetails('drc/inventory.json');

function drcView(version){
 const r=report('drc/'+version+'.json'),groups={};
 r.violations.forEach(v=>{groups[v.rule]=(groups[v.rule]||0)+1;});
 const audit=r.functional_preservation;
 return '<div class="evidence-banner"><b>'+esc(version)+' 基础 DRC：'+r.counts.errors+' error / '+r.counts.warnings+' warning</b><p>'+esc(r.scope)+'</p>'+(audit?'<p>以原始 v0 为参考，已逐个核对 '+audit.register_count+' 个 FF 的 Q、D、enable、复位值、触发沿及功能时钟/复位支路。此项连接核对不等价于整芯片形式等价证明。</p>':'')+'</div>'+table(['规则','命中实例 / 条目数'],Object.entries(groups).length?Object.entries(groups):[['本检查器已实现规则','未发现违例']])+reportDetails('drc/'+version+'.json');
}
$('#w3-evidence').insertAdjacentHTML('beforeend',drcView('v0'));

function mountChain(target,version){
 const model=report('scan_chains.json')[version],node=$(target),prefix=version+'-chain';
 node.innerHTML=drcView(version)+'<article class="lab-card"><div class="lab-heading"><span>ACTUAL NETLIST / '+version.toUpperCase()+'</span><h3>沿着真实链映射，找到一个状态位</h3><p>以下顺序为 SI → SO。Lock-up latch 不计入扫描位数；完整边沿协议见报告。</p></div><div class="chain-bars">'+model.chains.map(c=>'<div><span>Chain '+c.index+'</span><i style="width:'+c.length/Math.max(...model.chains.map(x=>x.length))*100+'%"></i><b>'+c.length+' 位</b></div>').join('')+'</div><div class="controls"><label>选择链 <select id="'+prefix+'-select">'+model.chains.map(c=>'<option value="'+c.index+'">Chain '+c.index+' · '+c.length+' 位</option>').join('')+'</select></label><label>查找状态 <input type="search" id="'+prefix+'-search" placeholder="word_q / lane / sampled…"></label></div><div id="'+prefix+'-cells" class="chain-cells" aria-label="可选择的扫描单元"></div><div id="'+prefix+'-detail" class="line-explain" aria-live="polite"></div><p class="annotation">'+esc(model.shift_protocol)+'</p></article>'+reportDetails('scan_chains.json');
 function showCell(cell){
  $('#'+prefix+'-detail').innerHTML='<b>第 '+cell.position+' 位 · '+esc(cell.instance)+'</b><p>'+esc(cell.aliases.join(' · '))+'</p><p>'+esc(cell.edge==='negative'?'负沿':'正沿')+' / '+esc(cell.clock_domain)+' 域；Q = bit '+cell.q+'；SI = bit '+cell.si+'。<br>功能 D = bit '+cell.d+'；原复位 = bit '+cell.reset+'。</p>';
  $$('#'+prefix+'-cells button').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.position)===cell.position)));
 }
 function renderCells(){
  const chain=model.chains[Number($('#'+prefix+'-select').value)],query=$('#'+prefix+'-search').value.toLowerCase();
  const cells=chain.cells.filter(c=>(c.aliases.join(' ')+' '+c.name+' '+c.position).toLowerCase().includes(query));
  $('#'+prefix+'-cells').innerHTML=cells.map(c=>'<button class="'+(c.edge==='negative'?'negative':'')+'" data-position="'+c.position+'" title="'+esc(c.aliases.join(' · '))+'">'+c.position+'<small>'+esc(c.aliases[0]||c.instance)+'</small></button>').join('')||'<p>没有匹配的状态位。</p>';
  $$('#'+prefix+'-cells button').forEach(b=>b.onclick=()=>showCell(chain.cells[Number(b.dataset.position)]));
  if(cells.length)showCell(cells[0]);else $('#'+prefix+'-detail').textContent='换一个状态名继续查找。';
 }
 $('#'+prefix+'-select').onchange=renderCells;$('#'+prefix+'-search').oninput=renderCells;renderCells();
}
mountChain('#w4-evidence','v1');mountChain('#w5-evidence','v2');
$('#w5-evidence').insertAdjacentHTML('beforeend',reportDetails('scan/validation.json'));
// 同一 DUT 的好/坏 VCD 窗口，按实际采样时间回放，不用预算曲线代替仿真。
const lockWave=report('scan/lockup_wave.json');
$('#w5-evidence').insertAdjacentHTML('beforeend','<article class="lab-card"><div class="lab-heading"><span>REAL VCD / CHAIN '+lockWave.chain+'</span><h3>这一位，在 669 ns 走向不同结果</h3><p>'+esc(lockWave.scope)+'</p></div><div class="controls"><button class="btn" id="lock-real-prev">上一步</button><button class="btn" id="lock-real-next">下一步</button><button class="btn" id="lock-real-reset">重置</button><output id="lock-real-time"></output></div><div class="diagram-scroll" tabindex="0" role="region" aria-label="实验图表，可横向滚动"><svg id="lock-real-svg" viewBox="0 0 740 280" role="img" aria-label="真实DUT有无Lock-up的VCD对照"></svg></div><div id="lock-real-readout" class="two-col"></div><p class="annotation">曲线来自 VCD 的离散时刻。这里证明给定偏斜下的串位差异，不能从零延迟模型推算物理 Hold slack。</p></article>'+reportDetails('scan/lockup_wave.json'));
let lockRealStep=0;
function drawLockReal(){
 const rows=lockWave.with_lockup,bad=lockWave.without_lockup,t=rows[lockRealStep].ns,x=n=>150+(n-664)*44;
 const traces=[['源时钟',rows,'source_clock'],['目的时钟',rows,'destination_clock'],['源新值 Q',rows,'source_q'],['Latch Q',rows,'held_q'],['有 Latch · 目的 Q',rows,'destination_q'],['无 Latch · 目的 Q',bad,'destination_q']];
 let svg='';traces.forEach(([label,data,key],i)=>{const base=38+i*36,color=i===5?'#b77b61':i===4?'#789b83':'#9b967f';let path='';data.forEach((r,j)=>{const yy=base-(r.signals[key]==='1'?18:0);path+=(j?'H'+x(r.ns)+'V':'M'+x(r.ns)+' ')+yy;});svg+=textSVG(7,base-4,label,'font-size="11" fill="#81786e"')+'<path d="'+path+'" stroke="'+color+'" fill="none" stroke-width="2"/>';});
 svg+='<path d="M'+x(t)+' 6V245" stroke="#c99b5e" stroke-dasharray="4 3"/>';[664,667,669,672,676].forEach(ns=>svg+=textSVG(x(ns),265,ns+'ns','font-size="10" text-anchor="middle" fill="#81786e"'));$('#lock-real-svg').innerHTML=svg;
 $('#lock-real-time').textContent=t+' ns';$('#lock-real-prev').disabled=lockRealStep===0;$('#lock-real-next').disabled=lockRealStep===rows.length-1;
 $('#lock-real-readout').innerHTML=metric('有 Lock-up · 目的 Q',rows[lockRealStep].signals.destination_q,'源正沿产生的新位先被锁存器挡住')+metric('移除 Lock-up · 目的 Q',bad[lockRealStep].signals.destination_q,t>=669?'目的晚到边沿吞入源新位，和预期旧位不同':'目的时钟尚未采到这次新位');
}
$('#lock-real-prev').onclick=()=>{lockRealStep--;drawLockReal();};$('#lock-real-next').onclick=()=>{lockRealStep++;drawLockReal();};$('#lock-real-reset').onclick=()=>{lockRealStep=0;drawLockReal();};drawLockReal();

// 搜索树显示算法保存的动作，不能用手写的成功故事替代回溯日志。
const atpgReport=report('atpg/summary.json'),coverageReport=report('coverage/coverage.json');
$('#w6-evidence').innerHTML='<div class="evidence-banner"><b>'+esc(atpgReport.scope)+'</b><p>'+esc(atpgReport.fault_model)+'</p></div><div class="three-col">'+metric('故障分母',atpgReport.fault_count,'唯一网线 stem × SA0/SA1')+metric('可检测故障',atpgReport.testable,'与 32 个输入组合的独立 oracle 对照')+metric('Fault coverage',coverageReport.fault_coverage.toFixed(2)+'%','本局部锥，非全芯片覆盖率')+'</div><article class="lab-card"><h3>从目标故障，读出一次真实搜索</h3><div class="controls"><label>故障 <select id="actual-fault">'+atpgReport.results.map(r=>'<option value="'+esc(r.fault)+'">'+esc(r.fault)+' · '+esc(r.status)+'</option>').join('')+'</select></label><button class="btn" id="actual-next">下一步</button><button class="btn" id="actual-reset">重置</button></div><p id="actual-pattern" class="annotation"></p><div id="actual-tree" class="actual-tree"></div></article><article class="lab-card"><h3>相同故障集合下，向量如何补齐覆盖</h3><p class="annotation">陶土：已有输出的实际 fault simulation；绿色：额外观察 r 的模型对照。绿色不代表已在 v2 插入 r 观察触发器。</p><div class="controls"><label>向量数 <input id="actual-coverage-range" type="range" min="0" max="'+(coverageReport.points.length-1)+'" value="0"><output id="actual-coverage-count"></output></label><button class="btn" id="actual-coverage-reset">重置</button></div><div class="diagram-scroll" tabindex="0" role="region" aria-label="实验图表，可横向滚动"><svg id="actual-coverage-svg" viewBox="0 0 740 270" role="img" aria-label="实际故障仿真覆盖率曲线"></svg></div><p id="actual-coverage-note" aria-live="polite"></p></article>'+reportDetails('atpg/summary.json')+reportDetails('coverage/coverage.json')+reportDetails('atpg/scan_replay.json');
const replay=report('atpg/scan_replay.json');
const negativeLabels={no_injection:'取消故障注入',wrong_input:'装载位错误',wrong_observation:'观察链错误'};
$('#w6-evidence').insertAdjacentHTML('beforeend','<article class="lab-card" id="full-replay-panel"><div class="lab-heading"><span>FULL DUT / EVERY DETECTABLE FAULT</span><h3>19 个可测故障，逐个走完真实扫描链</h3><p>'+esc(replay.scope)+'</p></div><div class="three-col">'+metric('完整 DUT 回放',replay.detected_replayed_count+' / '+atpgReport.testable,'每个故障独立注入与仿真')+metric('每例装载与卸载',replay.scan_cells+' FF','两颗 DUT 分别逐位核对')+metric('累计 SO 比较',replay.total_compared_so_bits,'19 例 × 293 位 × 正常/故障两颗 DUT')+'</div><p id="replay-selected" class="annotation" aria-live="polite"></p><details class="accordion"><summary>展开逐故障的真实响应与扫描位置</summary>'+table(['故障','输入 a b c d e','观察 FF','链 / 卸载周期¹','正常 / 故障','结果'],replay.cases.map(c=>[c.fault,atpgReport.input_order.map(k=>c.pattern[k]).join(' '),c.observation,c.observation_chain+' / '+c.observation_shift_cycle_zero_based,c.good_bit+' / '+c.bad_bit,c.status]))+'<p class="annotation">¹ 链号与卸载周期均从 0 起计。逐例输入、日志与 VCD 路径见上方 scan_replay.json；q/SA1 的代表波形仍保留在原路径。</p></details><p class="annotation">已证明不可测且未计入检测回放：'+esc(replay.skipped_proven_untestable.join('、'))+'。这仍是同一局部锥的 22 个故障集合。</p>'+table(['主动破坏的条件','实际验收结果'],replay.negative_tests.map(c=>[negativeLabels[c.name],c.status==='EXPECTED_FAILURE'?'已被断言拦截':c.status]))+'</article>');
let actualStep=0;
const actionLabels={path:'传播路径',objective:'目标',assign:'赋值',justify:'逆向解释',conflict:'赋值冲突',backtrack:'回溯',fill:'补齐无关输入',detect:'检测成立',reject:'传播未成立',untestable:'不可测'};
function traceText(t){
 if(t.action==='path')return (t.nodes||[]).join(' → ');
 if(t.action==='conflict')return t.node+' 已为 '+t.existing+'，本分支要求 '+t.requested+'。'+t.reason;
 if(t.action==='justify')return t.node+' ← '+(t.requirements||[]).map(r=>r.node+'='+r.value).join('，');
 if(t.action==='detect')return Object.entries(t.vector||{}).map(([k,v])=>k+'='+v).join('，')+'；'+t.reason;
 if(t.action==='backtrack')return t.node+'：'+t.reason;
 if(t.node!==undefined&&t.value!==undefined)return t.node+' = '+t.value;
 return t.reason||JSON.stringify(t);
}
function drawActualTree(){
 const fault=atpgReport.results.find(r=>r.fault===$('#actual-fault').value),trace=fault.trace||[];
 actualStep=Math.min(actualStep,Math.max(0,trace.length-1));
 $('#actual-pattern').textContent=fault.pattern?'检测向量 '+atpgReport.input_order.map(k=>k+'='+fault.pattern[k]).join('，')+'；'+fault.detecting_vectors+'/32 输入组合可检测。':'没有检测向量；状态 '+fault.status+'。不可测结论由独立完整穷举核对。';
 const replayCase=replay.cases.find(c=>c.fault===fault.fault);
 $('#replay-selected').textContent=replayCase?'当前选择 '+replayCase.fault+'：在 '+replayCase.observation+' 捕获 '+replayCase.cut_output+'；从 chain '+replayCase.observation_chain+' 的第 '+replayCase.observation_shift_cycle_zero_based+' 个卸载周期（从 0 起计）读到正常 '+replayCase.good_bit+' / 故障 '+replayCase.bad_bit+'。':'当前选择 '+fault.fault+'：在此局部锥的观察边界下不可测，没有可计入的检测回放。';
 $('#actual-tree').innerHTML=trace.map((t,i)=>'<button class="tree-node '+(i<=actualStep?'visible ':'')+(t.action==='conflict'?'conflict':t.action==='detect'?'success':'')+'" aria-expanded="'+(i<=actualStep)+'" data-actual-step="'+i+'"><b>'+i+' · '+esc(actionLabels[t.action]||t.action)+'</b>'+(i<=actualStep?'<small>'+esc(traceText(t))+'</small>':'')+'</button>').join('');
 $$('[data-actual-step]').forEach(b=>b.onclick=()=>{actualStep=Number(b.dataset.actualStep);drawActualTree();});
 $('#actual-next').disabled=actualStep>=trace.length-1;
}
$('#actual-fault').value='q/SA1';$('#actual-fault').onchange=()=>{actualStep=0;drawActualTree();};$('#actual-next').onclick=()=>{actualStep++;drawActualTree();};$('#actual-reset').onclick=()=>{actualStep=0;drawActualTree();};drawActualTree();
function drawActualCoverage(){
 const k=Number($('#actual-coverage-range').value),point=coverageReport.points[k],x=i=>62+i*610/(coverageReport.points.length-1),y=n=>225-n/coverageReport.denominator*190;
 let svg='';[0,25,50,75,100].forEach(p=>{const yy=225-p*1.9;svg+='<path d="M62 '+yy+'H690" stroke="#e5dccf"/>'+textSVG(12,yy+4,p+'%','font-size="11" fill="#81786e"');});
 [['detected','#b77b61'],['with_observe','#789b83']].forEach(([field,color])=>{svg+='<path d="'+coverageReport.points.slice(0,k+1).map((p,i)=>(i?'L':'M')+x(i)+' '+y(p[field])).join(' ')+'" fill="none" stroke="'+color+'" stroke-width="3"/><circle cx="'+x(k)+'" cy="'+y(point[field])+'" r="5" fill="'+color+'"/>';});
 coverageReport.points.forEach((p,i)=>svg+=textSVG(x(i),247,i,'text-anchor="middle" font-size="11" fill="#81786e"'));
 $('#actual-coverage-svg').innerHTML=svg;$('#actual-coverage-count').textContent=k+' / '+(coverageReport.points.length-1);
 $('#actual-coverage-note').textContent=(point.phase==='deterministic_atpg'?'确定性 ATPG':point.phase==='initial'?'尚未应用向量':'固定种子的随机前缀')+' · 已检测 '+point.detected+'/'+coverageReport.denominator+' = '+point.percent.toFixed(2)+'%；额外观察 r 的模型 '+point.with_observe+'/'+coverageReport.denominator+'。本步新增：'+(point.new_faults?.join('，')||'无')+'。';
}
$('#actual-coverage-range').oninput=drawActualCoverage;$('#actual-coverage-reset').onclick=()=>{$('#actual-coverage-range').value=0;drawActualCoverage();};drawActualCoverage();

const costs=report('timing/cost_timing.json');
$('#w7-evidence').innerHTML=table(['网表版本','叶单元实例数','统计来源'],Object.entries(costs.counts).map(([v,d])=>[v,d.leaf_instances,d.source]))+'<p class="annotation">'+esc(costs.area_note)+' SDFF 的 MUX 封装在单元内部；叶单元增加量不是等效门面积增加量。</p>'+reportDetails('timing/cost_timing.json');
$('#cost-lab').innerHTML='<article class="lab-card"><h3>改变周期与偏斜，分别看 Setup 和 Hold</h3><p>示例值，单位 ns；不是工艺 STA。tCQ_min=0.2、数据最小延迟=0.1、tHold=0.1；tCQ_max=0.6、最大数据延迟=7.9、tSetup=0.3；两种检查的不确定性均示例取 0.2。</p><div class="controls"><label>周期 T <input id="budget-period" type="range" min="6" max="20" step="0.5" value="10"><output id="budget-period-value"></output></label><label>正 skew <input id="budget-skew" type="range" min="0" max="3" step="0.1" value="0.8"><output id="budget-skew-value"></output></label></div><div class="three-col" id="budget-results"></div><p class="annotation">正 skew 表示目的时钟晚到。Lock-up 示例采用低电平透明、50% 占空比；仍需单独检查 latch→目的 FF 的 Setup 与时钟关系。</p></article><article class="lab-card"><h3>重排让连线变短，协议边界仍要保留</h3><p>六个同域同边沿状态位的示例坐标；长度为 Manhattan 代理指标，没有执行布局布线。</p><label><input type="checkbox" id="reorder-toggle"> 在允许的组内按坐标重排</label><div class="diagram-scroll" tabindex="0" role="region" aria-label="实验图表，可横向滚动"><svg id="reorder-svg" viewBox="0 0 740 190" role="img" aria-label="扫描顺序与连线长度对照"></svg></div><p id="reorder-note"></p></article>';
function drawBudget(){const T=Number($('#budget-period').value),skew=Number($('#budget-skew').value),values=[['Capture setup',T+skew-.6-7.9-.3-.2,'T + skew − 0.6 − 7.9 − 0.3 − 0.2'],['直接 Shift hold',.2+.1-skew-.1-.2,'0.2 + 0.1 − skew − 0.1 − 0.2'],['Lock-up hold',T/2+.1-skew-.1-.2,'T/2 + 0.1 − skew − 0.1 − 0.2']];$('#budget-period-value').textContent=T.toFixed(1)+' ns';$('#budget-skew-value').textContent=skew.toFixed(1)+' ns';$('#budget-results').innerHTML=values.map(([n,v,f])=>metric(n,(v>=0?'+':'')+v.toFixed(2)+' ns',f)).join('');}
$('#budget-period').oninput=drawBudget;$('#budget-skew').oninput=drawBudget;drawBudget();
function drawReorder(){const r=costs.reordering,on=$('#reorder-toggle').checked,order=on?r.after:r.before,x=i=>60+r.points[i][0]*66,y=i=>60+r.points[i][1]*70;let svg='<path d="'+order.map((v,i)=>(i?'L':'M')+x(v)+' '+y(v)).join(' ')+'" fill="none" stroke="'+(on?'#789b83':'#b77b61')+'" stroke-width="3"/>';r.points.forEach((_,i)=>svg+='<circle cx="'+x(i)+'" cy="'+y(i)+'" r="18" fill="#fffdf8" stroke="#b77b61"/>'+textSVG(x(i),y(i)+4,'Q'+i,'font-size="11" text-anchor="middle" fill="#6e6151"'));$('#reorder-svg').innerHTML=svg;$('#reorder-note').textContent='SI → '+order.map(i=>'Q'+i).join(' → ')+' → SO；长度 '+(on?r.length_after:r.length_before)+'。重排后须同步更改 chain map 与 pattern 比特顺序并回归。';}
$('#reorder-toggle').onchange=drawReorder;drawReorder();

const release=report('validation-full.json');
$('#release-evidence').innerHTML='<div class="evidence-banner"><b>完整流水线 · '+esc(release.status)+'</b><p>下面记录工具执行与断言结果。个人学习复选框不会改变报告。</p></div>'+table(['检查阶段','结果'],release.steps.map(s=>[s.name,s.status]))+reportDetails('validation-full.json');
$$('[data-report]').forEach(b=>b.onclick=()=>downloadText(b.dataset.report.replaceAll('/','-'),JSON.stringify(report(b.dataset.report),null,2)));
