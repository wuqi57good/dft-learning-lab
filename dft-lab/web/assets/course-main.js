// 页面状态只保存在当前浏览器；实验与源码不请求网络。
const DATA=JSON.parse(document.getElementById('embedded-data').textContent);
const files=DATA.files,cards=DATA.cards,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
$$('nav a i').forEach((node,i)=>node.textContent=String(i+1).padStart(2,'0'));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(m){$('#toast').textContent=m;$('#toast').classList.add('show');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),1800);}
async function copyText(t){try{await navigator.clipboard.writeText(t);toast('已复制');}catch{const a=document.createElement('textarea');a.value=t;document.body.append(a);a.select();const ok=document.execCommand('copy');a.remove();toast(ok?'已复制':'请选中代码手动复制');}}
function downloadText(name,text){const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);}
$$('.copy-command').forEach(b=>b.onclick=()=>copyText(b.closest('.command').dataset.command));
$('#menu-toggle').onclick=()=>{const open=$('#sidebar').classList.toggle('mobile-open');$('#menu-toggle').setAttribute('aria-expanded',String(open));};
$$('nav a').forEach(a=>a.onclick=()=>{$('#sidebar').classList.remove('mobile-open');$('#menu-toggle').setAttribute('aria-expanded','false');});
const checks=$$('[data-check],[data-stage-check]');
checks.forEach((c,i)=>{if(!c.dataset.check)c.dataset.check=c.dataset.checkId||'w'+c.dataset.stageCheck+'-'+i;});
function progress(save){
 const weeks=Array.from({length:7},(_,i)=>{const list=checks.filter(c=>Number(c.dataset.stageCheck||c.dataset.week||1)===i+1);return {total:list.length,done:list.filter(c=>c.checked).length};});
 const percent=weeks.reduce((s,w)=>s+(w.total?w.done/w.total:0),0)/7*100;
 $('#progress').style.width=percent+'%';
 $('#progress-caption').textContent='学习自评 '+Math.round(percent)+'% · '+checks.filter(c=>c.checked).length+'/'+checks.length+' 项';
 const w=weeks[1];$('#w2-progress').textContent='第二周 · '+w.done+' / '+w.total+' 项完成。勾选记录自评，不替代实验。';
 if(save)try{checks.forEach(c=>localStorage.setItem('dft-check-'+c.dataset.check,c.checked?'1':'0'));}catch{}
}
try{checks.forEach(c=>c.checked=localStorage.getItem('dft-check-'+c.dataset.check)==='1');}catch{}
checks.forEach(c=>c.onchange=()=>progress(true));progress(false);
const observer=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting)$$('nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id));}),{rootMargin:'-10% 0px -70%'});
$$('.chapter,#start').forEach(s=>observer.observe(s));
const textSVG=(x,y,t,attrs='')=>'<text x="'+x+'" y="'+y+'" '+attrs+'>'+esc(t)+'</text>';
const labelStyle='fill="#756b60" font-size="12" font-family="sans-serif"';

// 从同一份旧 Q 快照产生新 Q，不能原地覆盖而串成组合传播。
const scan={q:[0,0,0,0],step:0,out:[],timer:null};
function stopScan(){clearInterval(scan.timer);scan.timer=null;$('#scan-play').textContent='播放';}
function drawScan(){
 const next=scan.step<4?'Shift-In':scan.step===4?'Capture':scan.step<9?'Shift-Out':'完成';
 const current=scan.step<=4?0:scan.step===5?1:2,en=current===1?0:1;
 let svg='<path d="M28 98H708" stroke="#c8b5a1" stroke-width="2" fill="none"/>'+textSVG(15,85,'SI',labelStyle)+textSVG(704,85,'SO',labelStyle);
 [130,290,450,610].forEach((x,i)=>{
 svg+='<rect x="'+(x-55)+'" y="49" width="110" height="96" rx="13" fill="#fffdf9" stroke="#c3ab93"/>'+
 '<path d="M'+(x-38)+' 78L'+(x-13)+' 86V114L'+(x-38)+' 122Z" fill="#f0e7d9" stroke="#baa284"/>'+
 '<path d="M'+(x-45)+' '+(en?98:116)+'H'+(x-35)+'L'+(x-15)+' 100H'+(x+4)+'" stroke="'+(en?'#b77b61':'#778a66')+'" stroke-width="3" fill="none"/>'+
 '<circle cx="'+(x+24)+'" cy="100" r="20" fill="'+(scan.q[i]?'#deead2':'#f4eadd')+'" stroke="#a4b28e"/>'+
 textSVG(x+24,106,scan.q[i],'text-anchor="middle" fill="#59694a" font-size="19" font-family="monospace"')+
 textSVG(x-49,66,'SDFF '+i,labelStyle)+textSVG(x-50,133,'D',labelStyle)+textSVG(x+15,133,'Q'+i,labelStyle);
 });
 $('#scan-svg').innerHTML=svg;$('#scan-state').textContent=scan.q.join('');$('#scan-out').textContent=scan.out.join('')||'—';$('#scan-phase').textContent=next;
 $$('#scan-phases span').forEach((p,i)=>p.classList.toggle('active',i===current));
 let wave=textSVG(8,27,'CLK',labelStyle)+textSVG(8,76,'SCAN_EN',labelStyle);
 for(let i=0;i<9;i++){const x=100+i*68,active=i<scan.step,y=i===4?86:65;
 wave+='<path d="M'+x+' 38h15v-22h26v22h27" fill="none" stroke="'+(active?'#b77b61':'#e5d9cb')+'" stroke-width="2"/>'+
 '<path d="M'+x+' '+y+'h68" fill="none" stroke="'+(active?'#778a66':'#e5d9cb')+'" stroke-width="2"/>';
 if(active&&(i===4||i===5))wave+='<path d="M'+x+' 65V86" stroke="#778a66" stroke-width="2"/>';
 wave+=textSVG(x+30,100,i+1,'text-anchor="middle" fill="#938574" font-size="10"');}
 $('#scan-wave').innerHTML=wave;$('#scan-next').disabled=scan.step===9;
}
function nextScan(){
 if(scan.step>=9){stopScan();return;}const old=[...scan.q];
 if(scan.step<4){const incoming=[1,0,1,1][scan.step];scan.q=[incoming,...old.slice(0,3)];$('#scan-note').textContent='Shift-In 第 '+(scan.step+1)+' 拍：SI='+incoming+'，Q='+scan.q.join('')+'（Q0→Q3）；旧 Q3='+old[3]+' 被移出。';}
 else if(scan.step===4){scan.q=[0,1,0,1];$('#scan-note').textContent='第 5 拍 Capture：SCAN_EN=0，MUX 选择功能 D；Q0→Q3 同时更新为 0101。';}
 else{scan.out.push(old[3]);scan.q=[0,...old.slice(0,3)];$('#scan-note').textContent='Shift-Out 第 '+(scan.step-4)+' 拍：先读旧 Q3='+old[3]+'，再移位。累计 SO='+scan.out.join('')+'。';}
 scan.step++;drawScan();if(scan.step===9){stopScan();$('#scan-note').textContent+=' 完整移出 1010（Q3→Q0）；与 Capture 的 0101 对应。';}
}
function playScan(){if(scan.timer){stopScan();return;}if(scan.step===9){toast('请重置后开始下一轮');return;}scan.timer=setInterval(nextScan,Number($('#scan-speed').value));$('#scan-play').textContent='暂停';}
$('#scan-next').onclick=()=>{stopScan();nextScan();};$('#scan-play').onclick=playScan;
$('#scan-speed').onchange=()=>{if(scan.timer){stopScan();playScan();}};
$('#scan-reset').onclick=()=>{stopScan();Object.assign(scan,{q:[0,0,0,0],step:0,out:[]});drawScan();$('#scan-note').textContent='初始 Q=0000。按下一拍，依次装载 1、0、1、1。';};
drawScan();$('#scan-note').textContent='每次下一拍代表一个时钟脉冲；波形深色部分对应已执行拍。';

// 正常/故障双电路模拟。Capture 是采样动作，节点点击才改变故障位置。
const fault={a:1,b:1,c:0,node:'n',sa:0,captured:null};
function faultValues(){const n=fault.a&fault.b,y=n|fault.c,fn=fault.node==='n'?fault.sa:n,fy=fault.node==='Y'?fault.sa:(fn|fault.c);return {n,y,fn,fy};}
const symbol=(good,bad)=>good===bad?String(good):good===1?'D':'D̅';
function drawFault(){
 const v=faultValues(),activated=fault.node==='n'?v.n!==v.fn:v.y!==v.fy,prop=v.y!==v.fy;
 $$('[data-pi]').forEach(b=>{const k=b.dataset.pi;b.textContent=k.toUpperCase()+' = '+fault[k];b.classList.toggle('on',!!fault[k]);});
 $('#fault-svg').innerHTML='<path d="M55 40H150V58H180 M55 90H150V76H180 M55 130H410V90 M270 68H410V69 M500 80H610" fill="none" stroke="#baa58c" stroke-width="2"/>'+
 textSVG(15,44,'A='+fault.a,labelStyle)+textSVG(15,94,'B='+fault.b,labelStyle)+textSVG(15,134,'C='+fault.c,labelStyle)+
 '<g role="button" tabindex="0" aria-label="在 n 节点注入故障" data-fault-node="n" style="cursor:pointer"><rect x="180" y="43" width="90" height="50" rx="12" fill="'+(fault.node==='n'?'#f3d9c7':'#f5efe4')+'" stroke="#b77b61"/>'+
 textSVG(225,63,'AND · n','text-anchor="middle" '+labelStyle)+textSVG(225,84,symbol(v.n,v.fn),'text-anchor="middle" fill="#8f5e4c" font-size="19"')+'</g>'+
 '<g role="button" tabindex="0" aria-label="在 Y 节点注入故障" data-fault-node="Y" style="cursor:pointer"><rect x="410" y="55" width="90" height="50" rx="12" fill="'+(fault.node==='Y'?'#f3d9c7':'#e8efdf')+'" stroke="#8b9d78"/>'+
 textSVG(455,76,'OR · Y','text-anchor="middle" '+labelStyle)+textSVG(455,98,symbol(v.y,v.fy),'text-anchor="middle" fill="#677a57" font-size="19"')+'</g>'+
 '<rect x="610" y="55" width="102" height="50" rx="12" fill="#fffaf3" stroke="#c1b09b"/>'+textSVG(661,76,'观察 FF','text-anchor="middle" '+labelStyle)+textSVG(661,98,fault.captured?symbol(...fault.captured):'未采样','text-anchor="middle" '+labelStyle)+
 (prop?'<path class="signal-flow" d="M500 80H610" stroke="#80956b" stroke-width="3" stroke-dasharray="7 6"/>':'');
 $$('[data-fault-node]').forEach(node=>{const change=()=>{fault.node=node.dataset.faultNode;fault.captured=null;drawFault();};node.onclick=change;node.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();change();}};});
 $('#fault-act').textContent=activated?'已激活：正常与故障值不同':'未激活：正常值等于固定值';
 $('#fault-prop').textContent=prop?'Y='+symbol(v.y,v.fy)+'：差异到达输出':activated?'差异被 OR 的 C=1 屏蔽':'先激活故障，再设置传播条件';
 $('#fault-obs').textContent=fault.captured?(fault.captured[0]!==fault.captured[1]?'已采到 '+symbol(...fault.captured)+'：检测成立':'FF 两个值相同：未检测'):'等待点击 Capture 采样';
 $('#fault-note').textContent='目标 '+fault.node+'/SA'+fault.sa+'。n='+v.n+'/'+v.fn+'，Y='+v.y+'/'+v.fy+'（正常/故障）。D=1/0；D̅=0/1。';
}
$$('[data-pi]').forEach(b=>b.onclick=()=>{fault[b.dataset.pi]^=1;fault.captured=null;drawFault();});
$('#fault-type').onchange=()=>{fault.sa=Number($('#fault-type').value);fault.captured=null;drawFault();};
$('#fault-capture').onclick=()=>{const v=faultValues();fault.captured=[v.y,v.fy];drawFault();};drawFault();

// 与实际重汇聚锥一致的约束搜索轨迹，不冒充完整 PODEM。
const treeSteps=[
 ['目标：q/SA1','初始 a,b,c=X。q=~a&c；要激活 SA1，正常 q 必须为 0。',''],
 ['决定 a=1','q=0，不论 c 取何值。故障 q=1，差异 D̅ 已形成。',''],
 ['传播需 p=0；先试 a=0','p=a&b=0 可由 a=0 或 b=0 满足。先选 a=0，与已有 a=1 冲突。','conflict'],
 ['Backtrack：撤销 a=0，改 b=0','保留 a=1；另一种满足 p=0 的选择 b=0 没有冲突。',''],
 ['取 c=0：完整向量 a,b,c=100','正常 p=0,q=0,y=0；故障 p=0,q=1,y=1。D̅ 抵达观察点。','success']
];let treeStep=0;
function drawTree(){
 $('#tree').innerHTML=treeSteps.map((s,i)=>'<button type="button" class="tree-node '+(i<=treeStep?'visible ':'')+s[2]+'" data-tree-step="'+i+'" aria-expanded="'+(i<=treeStep)+'"><b>'+(i+1)+'. '+esc(s[0])+'</b>'+(i<=treeStep?'<small>'+esc(s[1])+'</small>':'')+'</button>').join('');
 $$('[data-tree-step]').forEach(b=>b.onclick=()=>{treeStep=Number(b.dataset.treeStep);drawTree();});
 $('#tree-note').textContent=treeStep===4?'已核算向量 100：正常 y=0，q/SA1 下 y=1。':'当前展开前 '+(treeStep+1)+' 步。点击节点可跳转；本例只演示约束回溯。';$('#tree-next').disabled=treeStep===4;
}
$('#tree-next').onclick=()=>{treeStep=Math.min(4,treeStep+1);drawTree();};$('#tree-reset').onclick=()=>{treeStep=0;drawTree();};drawTree();

// 显式数值模型；负 hold slack 表示不满足约束，理想数字模型不模拟亚稳态。
let holdTime=6,holdFrame=null;
function drawHold(){
 const skew=Number($('#skew').value),raw=.3-skew-.1,safe=5.1-skew-.1,x=t=>145+t*75;
 $('#skew-value').textContent=skew.toFixed(1)+' ns';$('#hold-raw').textContent=(raw>=0?'+':'')+raw.toFixed(1)+' ns';$('#hold-safe').textContent='+'+safe.toFixed(1)+' ns';
 let svg='';
 [['源 CLK',42,0],['目的 CLK',86,skew],['直连新数据',130,.3],['Latch 后新数据',174,5.1]].forEach(([label,y,edge],i)=>{
 svg+=textSVG(8,y-5,label,labelStyle)+'<path d="M145 '+y+'H'+x(edge)+'V'+(y-20)+'H'+x(i<2?5+edge:7)+(i<2?'V'+y+'H700':'')+'" fill="none" stroke="'+(i===2?'#b77b61':i===3?'#7d9468':'#b5a38d')+'" stroke-width="2"/>';
 });
 svg+='<path d="M'+x(skew)+' 10V192" stroke="#c99754" stroke-dasharray="4 4"/><path d="M'+x(holdTime)+' 12V193" stroke="#656f59" stroke-width="2" opacity=".6"/>'+textSVG(x(skew)+5,17,'目的采样',labelStyle);
 for(let t=0;t<=7;t++)svg+=textSVG(x(t),207,t+'ns','font-size="10" fill="#91816e" text-anchor="middle"');
 $('#hold-svg').innerHTML=svg;
 const rawRead=skew>.3?'新值 1（旧位被跳过）':Math.abs(skew-.3)<.001?'边沿重合，不可靠':'旧值 0';
 $('#hold-note').textContent='播放位置 '+holdTime.toFixed(1)+' ns。'+(holdTime>=skew?'目的 FF：直连读到'+rawRead+'；Lock-up 路径读到旧值 0。':'尚未到目的采样边沿。')+(raw<0?'直连 Hold 裕量为负。':'直连满足本例 Hold 条件。');
}
$('#skew').oninput=drawHold;$('#hold-play').onclick=()=>{cancelAnimationFrame(holdFrame);const start=performance.now();const frame=t=>{holdTime=Math.min(6,(t-start)/500);drawHold();if(holdTime<6)holdFrame=requestAnimationFrame(frame);};holdFrame=requestAnimationFrame(frame);};drawHold();

