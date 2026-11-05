// 全文检索与学习记录只使用已内嵌内容和本地存储；没有网络请求或账号。
// 搜索索引区分课程与源码；源码结果定位到实际文件行，避免“搜到了却找不到”。
const learningDialog=$('#learning-search-dialog');
let learningOpener=null;
const learningEntries=[];
$$('section.chapter').forEach(section=>{
 const heading=section.querySelector('h2');
 if(heading)learningEntries.push({kind:'课程',title:heading.textContent.trim(),text:(section.querySelector('.section-intro')||heading).textContent.trim(),target:section});
 section.querySelectorAll('.lesson,.pitfalls article,.lab-card,.note-card,.final-exam details').forEach(node=>{
  const title=node.querySelector('h3,summary');if(!title)return;
  learningEntries.push({kind:'课程',title:title.textContent.trim(),text:node.textContent.replace(/\s+/g,' ').trim(),target:node});
 });
});
Object.entries(files).forEach(([path,source])=>learningEntries.push({kind:'代码',title:path,text:source,path}));

function learningSnippet(text,terms){
 const lower=text.toLowerCase(),positions=terms.map(t=>lower.indexOf(t)).filter(i=>i>=0),index=positions.length?Math.min(...positions):0;
 return (index>35?'…':'')+text.slice(Math.max(0,index-35),index+125).replace(/\s+/g,' ')+'…';
}
function learningHighlight(text,term){
 const i=text.toLowerCase().indexOf(term);return i<0?esc(text):esc(text.slice(0,i))+'<mark>'+esc(text.slice(i,i+term.length))+'</mark>'+esc(text.slice(i+term.length));
}
function visitLearningResult(entry,terms){
 learningOpener=null;
 learningDialog.close();
 if(entry.path){
  openFile(entry.path);
  const positions=terms.map(t=>entry.text.toLowerCase().indexOf(t)).filter(i=>i>=0);
  const line=positions.length?entry.text.slice(0,Math.min(...positions)).split('\n').length:1;
  explainLine(line);
  const row=$('#code-lines [data-line="'+line+'"]');
  row.scrollIntoView({block:'center',behavior:'auto'});row.focus({preventScroll:true});
 }else{
  // 同时展开命中段内的答案和它的祖先，避免搜索到的文字仍被折叠。
  let node=entry.target;
  while(node&&node!==document.body){if(node.tagName==='DETAILS')node.open=true;node=node.parentElement;}
  entry.target.querySelectorAll('details').forEach(detail=>{if(terms.some(term=>detail.textContent.toLowerCase().includes(term)))detail.open=true;});
  entry.target.scrollIntoView({block:'start',behavior:'auto'});
  const focus=entry.target.querySelector('summary,h3,h2')||entry.target;
  focus.setAttribute('tabindex','-1');focus.focus({preventScroll:true});
 }
}
function searchLearning(){
 const query=$('#learning-search-input').value.trim().toLowerCase(),scope=$('#learning-search-scope').value;
 if(!query){$('#learning-search-count').textContent='输入概念、命令或文件名，例如 Lock-up、scan_en、atpg.py。';$('#learning-search-results').innerHTML='';return;}
 const terms=query.split(/\s+/),matches=learningEntries.filter(e=>(scope==='全部'||e.kind===scope)&&terms.every(t=>(e.title+' '+e.text).toLowerCase().includes(t)));
 matches.sort((a,b)=>Number(!terms.every(t=>a.title.toLowerCase().includes(t)))-Number(!terms.every(t=>b.title.toLowerCase().includes(t))));
 const shown=matches.slice(0,30);
 $('#learning-search-count').textContent=matches.length?'找到 '+matches.length+' 项'+(matches.length>30?'，显示前 30 项；可增加关键词缩小范围。':'。'):'没有匹配结果，试试英文术语或文件名。';
 $('#learning-search-results').innerHTML=shown.map((e,i)=>'<button type="button" data-learning-result="'+i+'"><small>'+esc(e.kind)+'</small><b>'+learningHighlight(e.title,terms[0])+'</b><span>'+learningHighlight(learningSnippet(e.text,terms),terms[0])+'</span></button>').join('');
 $$('[data-learning-result]').forEach((button,i)=>button.onclick=()=>visitLearningResult(shown[i],terms));
}
function openLearningSearch(){learningOpener=document.activeElement;if(!learningDialog.open)learningDialog.showModal();$('#learning-search-input').focus();}
$('#open-learning-search').onclick=openLearningSearch;$('#mobile-learning-search').onclick=openLearningSearch;
$('#close-learning-search').onclick=()=>learningDialog.close();
learningDialog.addEventListener('close',()=>learningOpener?.focus());
$('#learning-search-input').oninput=searchLearning;$('#learning-search-scope').onchange=searchLearning;
$('#learning-search-input').onkeydown=e=>{if(e.key==='ArrowDown'){$('[data-learning-result]')?.focus();e.preventDefault();}else if(e.key==='Enter'){$('[data-learning-result]')?.click();e.preventDefault();}};
$('#learning-search-results').onkeydown=e=>{if(!['ArrowDown','ArrowUp'].includes(e.key))return;const buttons=$$('[data-learning-result]'),i=buttons.indexOf(document.activeElement);if(i>=0){buttons[Math.max(0,Math.min(buttons.length-1,i+(e.key==='ArrowDown'?1:-1)))].focus();e.preventDefault();}};
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openLearningSearch();}});
searchLearning();

// 备份的是个人学习记录，不包含或改写硬件验收报告。
const learningNotes=$('#learning-notes');
try{learningNotes.value=localStorage.getItem('dft-course-notes')||'';}catch{}
function saveLearningNotes(){try{localStorage.setItem('dft-course-notes',learningNotes.value);$('#learning-record-status').textContent='笔记已保存在当前浏览器。';}catch{$('#learning-record-status').textContent='当前浏览器不能保存，请导出学习记录。';}}
learningNotes.oninput=saveLearningNotes;
function learningRecord(){return {schema:'dft-lab.learning.v1',exportedAt:new Date().toISOString(),checks:Object.fromEntries(checks.map(c=>[c.dataset.check,c.checked])),notes:learningNotes.value,week2Notes:$('#w2-notes').value};}
$('#export-learning-record').onclick=()=>downloadText('DFT-学习记录.json',JSON.stringify(learningRecord(),null,2));
function validateLearningRecord(value){
 if(!value||value.schema!=='dft-lab.learning.v1'||!value.checks||Array.isArray(value.checks)||typeof value.checks!=='object'||typeof value.notes!=='string'||typeof value.week2Notes!=='string'||Object.values(value.checks).some(v=>typeof v!=='boolean'))throw new Error('文件格式不正确，需要本课程导出的学习记录 JSON。');
 return value;
}
function mergeLearningNotes(current,incoming){
 if(!incoming.trim()||current===incoming||current.includes(incoming))return current;
 return current.trim()?current+'\n\n—— 导入笔记 ——\n'+incoming:incoming;
}
$('#import-learning-record').onchange=async e=>{
 const input=e.target,file=input.files[0];if(!file)return;
 try{
  // 先完整校验，再改界面；解析失败不得留下半份导入结果。
  const imported=validateLearningRecord(JSON.parse(await file.text()));
  let added=0;checks.forEach(c=>{if(imported.checks[c.dataset.check]===true&&!c.checked){c.checked=true;added++;}});
  learningNotes.value=mergeLearningNotes(learningNotes.value,imported.notes);
  $('#w2-notes').value=mergeLearningNotes($('#w2-notes').value,imported.week2Notes);
  progress(true);saveLearningNotes();$('#w2-notes').dispatchEvent(new Event('input'));
  $('#learning-record-status').textContent='已合并学习记录：新增 '+added+' 个完成项。原有笔记保留，相同笔记不会重复添加。';
 }catch(error){$('#learning-record-status').textContent='未导入：'+error.message;}
 input.value='';
};
