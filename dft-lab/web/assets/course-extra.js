// 16 个非折叠节点故障；所有向量和覆盖率都通过双电路穷举计算。
const vectors=Array.from({length:16},(_,i)=>({a:(i>>3)&1,b:(i>>2)&1,c:(i>>1)&1,d:i&1}));
const faults=['n','m','r','t','u','v','y','z'].flatMap(node=>[0,1].map(sa=>({node,sa})));
function evaluateCircuit(v,force={}){
 const n=force.n??(v.a&v.b),m=force.m??((1-v.a)&v.c),r=force.r??(v.c&v.d);
 const t=force.t??(v.c|r),u=force.u??(n^v.d),vv=force.v??(u&m),y=force.y??(vv|t),z=force.z??(n|m);
 return {n,m,r,t,u,v:vv,y,z};
}
function detectedFaults(vector,observed){
 const good=evaluateCircuit(vector),found=[];
 faults.forEach((fault,i)=>{const bad=evaluateCircuit(vector,{[fault.node]:fault.sa});if(observed.some(n=>good[n]!==bad[n]))found.push(i);});
 return found;
}
const baseObs=['y','z'],fullObs=['y','z','n','m','u','v'];
// 固定 LCG seed 使每次离线打开仍能重现同一条随机前缀。
let seed=29;
const patternOrder=[];
for(let i=0;i<6;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;patternOrder.push((seed>>>24)&15);}
const known=new Set(patternOrder.flatMap(i=>detectedFaults(vectors[i],fullObs)));
while(patternOrder.length<16){
 let chosen=0,gain=-1;
 for(let i=0;i<16;i++){const count=detectedFaults(vectors[i],fullObs).filter(f=>!known.has(f)).length;if(count>gain){gain=count;chosen=i;}}
 if(gain===0)chosen=patternOrder.length%16;
 patternOrder.push(chosen);detectedFaults(vectors[chosen],fullObs).forEach(f=>known.add(f));
}
function coveredAt(k,observed){return new Set(patternOrder.slice(0,k).flatMap(i=>detectedFaults(vectors[i],observed)));}
function drawCoverage(){
 const k=Number($('#coverage-range').value),base=coveredAt(k,baseObs),full=coveredAt(k,fullObs),x=i=>60+i*39,y=n=>215-n/16*180;
 $('#pattern-count').textContent=k+' / 16';
 $('#coverage-base').textContent=base.size+'/16 = '+(base.size/16*100).toFixed(2)+'%';
 $('#coverage-fixed').textContent=full.size+'/16 = '+(full.size/16*100).toFixed(2)+'%';
 let svg='';
 [0,25,50,75,100].forEach(p=>{const yy=215-p*1.8;svg+='<path d="M60 '+yy+'H700" stroke="#e8ded0"/>'+textSVG(14,yy+4,p+'%','font-size="10" fill="#998974"');});
 [0,4,8,12,16].forEach(i=>svg+=textSVG(x(i),236,i,'text-anchor="middle" font-size="10" fill="#998974"'));
 svg+='<path d="M'+x(6)+' 22V215" stroke="#c9ab83" stroke-dasharray="4 4"/>'+textSVG(65,20,'固定随机前缀','fill="#98836b" font-size="11"')+textSVG(x(6)+10,20,'穷举选择新覆盖最多的向量','fill="#728363" font-size="11"');
 [[baseObs,'#b77b61'],[fullObs,'#788c65']].forEach(([obs,color])=>{
   let path='';for(let i=0;i<=k;i++)path+=(i?'L':'M')+x(i)+' '+y(coveredAt(i,obs).size)+' ';
   svg+='<path d="'+path+'" fill="none" stroke="'+color+'" stroke-width="3"/><circle cx="'+x(k)+'" cy="'+y(coveredAt(k,obs).size)+'" r="5" fill="'+color+'"/>';
 });
 svg+=textSVG(392,254,'陶土：主输出  /  绿色：增加观察点','fill="#91816c" font-size="11"');
 $('#coverage-svg').innerHTML=svg;
 const totalTestable=new Set(vectors.flatMap(v=>detectedFaults(v,fullObs)));
 $('#coverage-note').textContent=(k?'当前向量 abcd='+patternOrder[k-1].toString(2).padStart(4,'0')+'；':'尚未应用向量；')+
 '增加观察点后穷举可检测 '+totalTestable.size+'/16 个故障。r/SA0 受吸收律屏蔽，不能靠增加向量检测。分母始终固定为 16。';
}
$('#coverage-range').oninput=drawCoverage;
$('#coverage-reset').onclick=()=>{$('#coverage-range').value=0;drawCoverage();};drawCoverage();

// 源码浏览器：高亮只处理展示文本，绝不改动复制/下载用的原始代码。
const names=Object.keys(files);
let current='rtl/v0/dft_demo_top.sv';
function lineClass(line){return line.includes('★')?'exp':line.includes('⚠')?'warn':line.includes('🔧')?'dft':'';}
function highlight(line,path){
 const commentStart=path.endsWith('.sv')?'//':'#';
 const index=line.indexOf(commentStart);
 const body=index<0?line:line.slice(0,index),comment=index<0?'':line.slice(index);
 let result='',cursor=0;
 const pattern=/"(?:[^"\\]|\\.)*"|\b(?:module|endmodule|always|posedge|negedge|input|output|wire|reg|assign|if|else|begin|end|case|endcase|localparam|function|endfunction|task|endtask|def|return|import|from|class|for|in|with|as|assert|raise|try|except|True|False|None)\b|\b\d+(?:'[bdh][0-9a-fxz]+)?\b/gi;
 for(const match of body.matchAll(pattern)){
   result+=esc(body.slice(cursor,match.index));
   const token=match[0],type=token.startsWith('"')?'str':/^\d/.test(token)?'num':'kw';
   result+='<span class="syn-'+type+'">'+esc(token)+'</span>';cursor=match.index+token.length;
 }
 result+=esc(body.slice(cursor));return result+(comment?'<span class="syn-comment">'+esc(comment)+'</span>':'');
}
function renderList(){
 const q=$('#file-search').value.toLowerCase();$('#file-list').innerHTML='';
 names.filter(p=>p.toLowerCase().includes(q)).forEach(p=>{const b=document.createElement('button');b.textContent=p;b.title=p;b.className=p===current?'active':'';b.onclick=()=>openFile(p);$('#file-list').append(b);});
 if(!$('#file-list').childElementCount)$('#file-list').textContent='没有匹配的文件';
}
function openFile(path){
 if(!files[path])return;
 current=path;renderList();const card=cards[path];
 $('#file-path').textContent=path;
 $('#file-card').innerHTML='<div class="file-card-info">'+
 '<div><b>为什么存在</b><p>'+esc(card.purpose)+'</p></div>'+
 '<div><b>从上到下的结构</b><p>'+esc(card.layout.join(' → '))+'</p></div>'+
 '<div><b>实际规模 · '+card.lines+' 行</b><p>'+esc(card.scale||'含中文注释和空行。保留单一职责，不为很短的顺序逻辑另建无用子模块。')+'</p></div>'+
 '</div><p class="file-boundary"><b>越界红线：</b>'+esc(card.boundary)+'<br><b>依赖：</b>'+esc(card.dependencies.join(' · '))+'</p>';
 $('#file-decision').innerHTML='<p><b>判断：</b>'+esc(card.decision)+'</p><p><b>备选与代价：</b>'+esc(card.alternate)+'</p><p><b>写错后的症状：</b>'+esc(card.failure)+'</p>';
 const lines=files[path].trimEnd().split('\n');
 $('#file-stage').textContent=card.version;
 $('#line-count').textContent=lines.length+' 行 · '+card.version+' · 点击或悬停查看解释';
 $('#code-lines').innerHTML=lines.map((line,i)=>'<div class="code-line '+lineClass(line)+'" tabindex="0" data-line="'+(i+1)+'"><span class="line-no">'+(i+1)+'</span><code>'+highlight(line,path)+'</code></div>').join('');
 $$('#code-lines .code-line').forEach(row=>{
   const show=()=>explainLine(Number(row.dataset.line));
   row.onclick=show;row.onfocus=show;
   // 搜索或键盘已定位到某行时，滚动后落在鼠标下的另一行不能抢走解释。
   row.onmouseenter=()=>{if(!$('#code-lines').contains(document.activeElement))show();};
 });
 $('#code-scroll').classList.remove('expanded');$('#code-scroll').scrollTop=0;
 $('#expand-code').textContent='展开全文 ↓';explainLine(1);
}
function explainLine(n){
 const lines=files[current].trimEnd().split('\n'),line=lines[n-1],card=cards[current];
 $$('#code-lines .code-line.selected').forEach(el=>el.classList.remove('selected'));
 const row=$('#code-lines [data-line="'+n+'"]');if(row)row.classList.add('selected');
 const preceding=[];
 for(let i=n-2;i>=0&&i>=n-5;i--){if(/^\s*(\/\/|#)/.test(lines[i]))preceding.unshift(lines[i].replace(/^\s*(\/\/|#)\s?/,''));else if(lines[i].trim())break;}
 let explanation='';
 if(/^\s*(\/\/|#)/.test(line))explanation=line.replace(/^\s*(\/\/|#)\s?/,'');
 else if(preceding.length)explanation=preceding.join(' ');
 else if(/negedge.*rst|negedge core_rst/.test(line))explanation='这个敏感列表让低有效复位的下降沿在时钟之外也能清状态。功能上便于初始化，扫描时却可能破坏已装载状态；v1 必须让复位在测试模式可控。';
 else if(/posedge/.test(line))explanation='正沿触发定义状态提交时刻。右侧表达式读取旧状态，非阻塞赋值在当前事件阶段之后生效；不能把它读成顺序执行的软件语句。';
 else if(/negedge/.test(line))explanation='此处使用下降沿。若是 RTL 寄存器，它必须保留负沿特性；若是 TB 驱动，则是为了避开 DUT 的正沿采样，防止 race。';
 else if(/<=/.test(line))explanation='这是非阻塞状态更新：本边沿所有寄存器使用旧状态计算。当前文件的硬件目的为：'+card.purpose;
 else if(/assign|wire .* =/.test(line))explanation='这条组合连接连续反映输入变化，不等待时钟。它的可控性和故障传播取决于整个逻辑锥；边界是：'+card.boundary;
 else if(/\binput\b|\boutput\b/.test(line))explanation='端口定义模块与外部连接的契约。方向和位宽决定哪些值可被驱动/观察；不能因为名字类似就把不同时钟域的信号当作同步数据。';
 else if(/\breg\b/.test(line))explanation='reg 是 Verilog 过程变量类型，不保证最终一定是触发器。是否生成 DFF、锁存器或组合逻辑，要看驱动它的 always 块和综合结果。';
 else if(/\$fatal|\bassert\b|raise/.test(line))explanation='该断言把当前验收条件变成可自动失败的检查；出现错误时停止流程，禁止继续生成“通过”的报告。失败含义：'+card.failure;
 else if(/subprocess|run\(/.test(line))explanation='这里调用真实工具并检查返回码。日志必须原样保存；Python 只组织流程，不能凭期望填出工具结果。';
 else if(/read_verilog|synth|write_json|write_verilog/.test(line))explanation='这条 Yosys 流程操作在真实环境执行，结果由最终结构检查验收。尤其不能把 stat 的通用单元数量当作工艺 NAND2 等效面积。';
 else if(!line.trim())explanation='这条空行分隔不同职责段。它不产生硬件或运行行为。';
 else if(/end|}\s*$|\);\s*$/.test(line))explanation='这一行结束当前结构块；阅读时回到最近的模块、状态机或函数边界。当前文件按以下顺序组织：'+card.layout.join(' → ');
 else explanation='这条语句属于 '+card.layout.join(' → ')+' 的实现。结合本文件判断：'+card.decision+'；错误风险：'+card.failure;
 $('#line-explain').innerHTML='<small>第 '+n+' 行 · 工程笔记</small><p>'+esc(explanation)+'</p>';
}
$('#file-search').oninput=renderList;
$('#copy-file').onclick=()=>copyText(files[current]);
$('#download-file').onclick=()=>downloadText(current.split('/').pop(),files[current]);
$('#expand-code').onclick=()=>{const expanded=$('#code-scroll').classList.toggle('expanded');$('#expand-code').textContent=expanded?'收起全文 ↑':'展开全文 ↓';};
$$('[data-highlight]').forEach(c=>c.onchange=()=>$('#code-scroll').classList.toggle('hide-'+c.dataset.highlight,!c.checked));
$$('[data-open-file]').forEach(b=>b.onclick=()=>{openFile(b.dataset.openFile);$('#sidebar').classList.remove('mobile-open');$('#menu-toggle').setAttribute('aria-expanded','false');$('#source').scrollIntoView({behavior:'smooth'});});
openFile(current);

