/* Isolated preset draft. Reuse drawer catalogue and original preset validation;
   no queue request is sent when adding/editing draft items. */
(()=>{
 if(!window.MW_OVERLAY)return;
 let draft=null,picking=false,destination=null,previous={};
 const names={a:'가공',c:'제작',g:'채집',k:'수령',p:'연주',b:'알림'};
 const dialog=()=>{let d=$('ovPresetEditor');if(!d){d=document.createElement('dialog');d.id='ovPresetEditor';document.body.append(d);d.addEventListener('cancel',e=>{e.preventDefault();cancel();});}return d;};
 const at=path=>{const p=path.split('.').map(Number);return p.length===1?draft.spec.i[p[0]]:draft.spec.i[p[0]].i[p[1]];};
 const container=path=>path.includes('.')?draft.spec.i[Number(path.split('.')[0])].i:draft.spec.i;
 function materialData(c,multiplier=1){
  if(!['a','c'].includes(c.t))return null;
  const kind=c.t==='a'?'alter':'craft',recipes=(S.snap&&S.snap[kind])||[];
  let rec=c.r?recipes.find(r=>rid(kind,r)===c.r):null;
  if(!rec&&!c.r){const same=recipes.filter(r=>r.name===c.n);if(same.length===1)rec=same[0];}
  if(!rec)return {unknown:true,rows:[]};
  let count=Math.max(1,Number(c.q)||1)*multiplier,goal='';
  if(c.z){
    const bag=bagOf(rec.name),per=Math.max(1,Number(rec.per)||1),target=Math.max(1,Number(c.q)||1);
    if(bag==null)return {unknown:true,rows:[],goal:'완제품 보유량 미확인'};
    if(multiplier>1)return {unknown:true,blocked:true,rows:[],goal:'총 보유량 기준은 그룹 반복을 1회로 설정해주세요.'};
    const have=bag+storeOf(rec.name),short=Math.max(0,target-have);
    count=Math.ceil(short/per);
    goal=`완제품 보유 ${fmtN(have)}/${fmtN(target)} · ${short?`${fmtN(short)}개 부족 → ${fmtN(count)}회 제작${count*per>short?` (${fmtN(count*per)}개 산출)`:''}`:'목표 충족 · 제작 안 함'}`;
  }
  const rows=planRows(rec).map(r=>({r,c:planCalc(r,count)}));
  return {unknown:!rows.length||rows.some(x=>x.c.have==null),blocked:!!rec.blocked,rows,goal};
 }
 function materialChips(rows){return rows.map(({r,c})=>`<span class="ov-material-chip${c.have==null?' unknown':c.short>0?' short':''}" title="가방 ${c.bag==null?'미확인':fmtN(c.bag)} · 창고 ${fmtN(c.sto)}${c.short>0?` · ${fmtN(c.short)}개 부족`:''}">${esc(r.name)} ${c.have==null?'?':fmtN(c.have)}/${fmtN(c.req)}${c.short>0?` · ${fmtN(c.short)} 부족`:''}</span>`).join('');}
 function canPrepare(name,need,path=[]){
  const bag=bagOf(name);if(bag==null)return false;
  const short=Math.max(0,need-bag-storeOf(name));if(!short)return true;
  const {source,sourceId}=planSource(name);
  if(source==='gather')return true;
  if(!['craft','alter'].includes(source)||path.includes(sourceId)||path.length>=4)return false;
  const rec=((S.snap&&S.snap[source])||[]).find(r=>rid(source,r)===sourceId);
  if(!rec)return false;
  const rows=planRows(rec),runs=Math.ceil(short/Math.max(1,Number(rec.per)||1));
  return rows.length>0&&rows.every(r=>canPrepare(r.name,r.perCount*runs,[...path,sourceId]));
 }
 function updateMaterials(){
  if(!draft||!dialog().open)return;
  const totals=new Map();let unknown=false,blocked=false,recipes=0;
  dialog().querySelectorAll('[data-materials]').forEach(el=>{
    const path=el.dataset.materials,c=at(path),multiplier=path.includes('.')?Math.max(1,Number(draft.spec.i[Number(path.split('.')[0])].r)||1):1;
    const data=materialData(c,multiplier);if(!data){el.innerHTML='';return;}
    recipes++;unknown=unknown||data.unknown;blocked=blocked||data.blocked;
    const shortage=data.rows.some(x=>x.c.have!=null&&x.c.short>0);
    const status=data.blocked?'제작 조건 확인 필요':data.unknown?'재료 정보 미확인':shortage?'재료 부족':'재료 충분';
    const note=dialog().querySelector(`[data-goal-note="${path}"]`);if(note)note.textContent=data.goal||'';
    el.innerHTML=`${shortage&&!data.blocked&&!data.unknown?'':`<span class="ov-material-status${shortage||data.blocked?' short':data.unknown?' unknown':' enough'}">${status}</span>`}${materialChips(data.rows)}${multiplier>1?`<span class="muted">반복 ${multiplier}회 합산</span>`:''}`;
    for(const x of data.rows){const old=totals.get(x.r.name);if(old)old.c.req+=x.c.req;else totals.set(x.r.name,{r:x.r,c:{...x.c}});}
  });
  const all=[...totals.values()];for(const x of all)x.c.short=x.c.have==null?0:Math.max(0,x.c.req-x.c.have);
  const lacking=all.filter(x=>x.c.short>0),summary=$('ovMaterialSummary');if(!summary)return;
  if(!recipes){summary.hidden=true;return;}summary.hidden=false;
  const expanded=summary.querySelector('details')?.open;
  const possible=[],impossible=[];
  for(const x of lacking)(canPrepare(x.r.name,x.c.req)?possible:impossible).push(x);
  const shortageLine=(label,items)=>`<div class="ov-shortage-line"><span>${label}</span><span class="ov-shortage-items">${items.length?items.map(x=>`<span>${esc(x.r.name)} ${fmtN(x.c.short)}</span>`).join('<span class="ov-shortage-sep">·</span>'):'<span class="muted">없음</span>'}</span></div>`;
  summary.innerHTML=`<details${expanded?' open':''}><summary><span class="${lacking.length?'ov-shortage-title':''}">${lacking.length?'전체 재료 부족':unknown?'전체 재료 · 미확인 항목 있음':'전체 재료 충분'}</span>${blocked?' · 제작 조건 확인 필요':''}${lacking.length?shortageLine('자동 준비 불가',impossible)+shortageLine('자동 준비 가능',possible):''}</summary><div class="ov-material-chips">${materialChips(all)}</div></details><span class="muted">현재 보유량(가방+창고) 기준 · 앞 작업의 채집·생산 결과 미반영<br>총 보유 목표는 대기열에 담을 때 계산</span>`;
 }
 function cancel(){draft=null;picking=false;dialog().close();restore();}
 function restore(){
  if(!previous.go)return;
  $('dwGo').onclick=previous.go;$('dwEsc').onclick=previous.esc;$('dwCart').onclick=previous.cart;
  DW.chain=previous.chain;$('dwChain').checked=DW.chain;
  dwEl().classList.remove('ov-preset-picking');previous={};dwMsg('');dwRenderTargets();
 }
 function row(c,path){return `<div class="ov-edit-item"><div class="ov-edit-row"><span class="badge">${names[c.t]||c.t}</span><b title="${esc(c.n)}">${esc(c.n)}</b>${['a','c','g'].includes(c.t)?`<input type="number" min="${c.t==='g'?0:1}" max="1000000" data-qty="${path}" value="${c.q??1}" aria-label="${esc(c.n)} 수량"><span>${c.t==='g'?'개':'회'}</span>`:'<span></span><span></span>'}${c.t==='a'?`<select data-mode="${path}" aria-label="가공 수령 방식"><option value="none"${!c.m||c.m==='none'?' selected':''}>걸기만</option><option value="wait"${c.m==='wait'?' selected':''}>수령까지</option><option value="later"${c.m==='later'?' selected':''}>나중에 수령</option></select>`:'<span></span>'}<button data-up="${path}" title="위로 이동">↑</button><button data-down="${path}" title="아래로 이동">↓</button><button data-remove="${path}" aria-label="${esc(c.n)} 삭제">×</button></div><div class="ov-material-chips" data-materials="${path}"></div></div>`;}
 function render(){
  const d=dialog();
  d.innerHTML=`<div class="dlg-h"><span class="badge gold">프리셋</span><input id="ovEditName" maxlength="60" aria-label="프리셋 이름" placeholder="프리셋 이름" value="${esc(draft.spec.n)}"><button id="ovEditClose" class="x">×</button></div><div class="dlg-b"><div class="ov-edit-toolbar"><span class="muted">저장본 편집 · 실제 대기열은 바뀌지 않습니다</span><button id="ovEditAdd">＋ 항목 담기</button></div><div class="ov-edit-items">${draft.spec.i.length?draft.spec.i.map((c,i)=>c.t==='G'?`<section class="ov-edit-group"><div class="ov-edit-toolbar"><b>${esc(c.n)}</b><label>반복 <input type="number" data-repeat="${i}" min="1" max="999" value="${c.r||1}"> 회</label><button data-group-add="${i}">＋ 항목 담기</button><button data-group-remove="${i}" title="그룹과 내부 항목 삭제">×</button></div>${c.i.map((k,j)=>row(k,`${i}.${j}`)).join('')||'<p class="muted">항목이 없습니다.</p>'}</section>`:row(c,String(i))).join(''):'<p class="muted">항목 담기를 눌러 원하는 작업을 추가하세요.</p>'}</div><p id="ovEditError"></p></div><div class="dlg-f"><button id="ovEditCancel">취소</button><span class="grow"></span><button id="ovEditSave" class="pri">저장</button></div>`;
  $('ovEditName').oninput=e=>draft.spec.n=e.target.value;
  const options=document.createElement('div');options.className='ov-total-target';
  options.innerHTML=`<label><input id="ovAutoPrepare" type="checkbox"${draft.spec.autoPrepare?' checked':''}> 부족 재료 자동 준비</label><label><input id="ovAllowPartial" type="checkbox"${draft.spec.allowPartial?' checked':''}> 준비 불가 재료는 가능한 만큼 제작</label><span class="muted">재료 준비는 원래 목표량 기준 · 최종 제작만 축소 · 담을 때 계산 · 반복 그룹은 1회만 지원</span>`;
  d.querySelector('.ov-edit-toolbar').after(options);
  $('ovAutoPrepare').onchange=e=>{draft.spec.autoPrepare=e.target.checked;};
  $('ovAllowPartial').onchange=e=>{draft.spec.allowPartial=e.target.checked;};
  d.querySelectorAll('[data-materials]').forEach(el=>{
    const path=el.dataset.materials,c=at(path);if(!['a','c'].includes(c.t))return;
    const line=document.createElement('div');line.className='ov-total-target';
    line.innerHTML=`<label><input type="checkbox" data-total="${path}"${c.z?' checked':''}> 총 보유량 기준</label><span class="muted" data-goal-note="${path}"></span>`;
    el.before(line);
    const unit=d.querySelector(`[data-qty="${path}"]`).nextElementSibling;unit.textContent=c.z?'개':'회';
    line.querySelector('input').onchange=e=>{c.z=e.target.checked;unit.textContent=c.z?'개':'회';updateMaterials();};
  });
  $('ovEditClose').onclick=cancel;$('ovEditCancel').onclick=cancel;
  $('ovEditAdd').onclick=()=>choose(null);
  d.querySelectorAll('[data-group-add]').forEach(b=>b.onclick=()=>choose(Number(b.dataset.groupAdd)));
  d.querySelectorAll('[data-group-remove]').forEach(b=>b.onclick=()=>{draft.spec.i.splice(Number(b.dataset.groupRemove),1);render();});
  d.querySelectorAll('[data-qty]').forEach(b=>b.onchange=()=>{at(b.dataset.qty).q=Math.max(b.min==='0'?0:1,Math.min(1000000,Math.round(Number(b.value)||0)));b.value=at(b.dataset.qty).q;updateMaterials();});
  d.querySelectorAll('[data-mode]').forEach(b=>b.onchange=()=>at(b.dataset.mode).m=b.value);
  d.querySelectorAll('[data-repeat]').forEach(b=>b.onchange=()=>{draft.spec.i[Number(b.dataset.repeat)].r=Math.max(1,Math.min(999,Math.round(Number(b.value)||1)));b.value=draft.spec.i[Number(b.dataset.repeat)].r;updateMaterials();});
  for(const key of ['remove','up','down'])d.querySelectorAll(`[data-${key}]`).forEach(b=>b.onclick=()=>{
    const path=b.dataset[key],list=container(path),i=Number(path.split('.').at(-1));
    if(key==='remove')list.splice(i,1);else{const next=i+(key==='up'?-1:1);if(next>=0&&next<list.length)[list[i],list[next]]=[list[next],list[i]];}
    render();
  });
  $('ovEditSave').onclick=async()=>{
    if(!draft.spec.n.trim()){$('ovEditError').textContent='이름을 입력해주세요.';return;}
    $('ovEditSave').disabled=true;
    const r=await overlayPresetOp({op:'preset_update',id:draft.id||'',spec:structuredClone(draft.spec)});
    if(r){draft=null;d.close();restore();}else{$('ovEditError').textContent=OPRESET.error;$('ovEditSave').disabled=false;}
  };
  if(!d.open)d.showModal();
  const summary=document.createElement('div');summary.id='ovMaterialSummary';d.querySelector('.ov-edit-toolbar').after(summary);
  updateMaterials();
 }
 async function edit(id){
  if(draft){render();return;}
  if(id){const r=await api('/api/presets?id='+encodeURIComponent(id));if(!r||!r.ok||!r.spec){toast((r&&r.message)||'프리셋을 불러오지 못했습니다.');return;}draft={id,spec:structuredClone(r.spec)};}
  else draft={id:'',spec:{v:1,n:'',i:[]}};
  render();
 }
 function choose(groupIndex){
  destination=groupIndex;picking=true;dialog().close();
  previous={go:$('dwGo').onclick,esc:$('dwEsc').onclick,cart:$('dwCart').onclick,chain:DW.chain};
  openDrawer({target:'root'});DW.chain=false;$('dwChain').checked=false;dwEl().classList.add('ov-preset-picking');
  const back=()=>{picking=false;restore();render();};
  $('dwGo').onclick=back;$('dwEsc').onclick=back;$('dwCart').onclick=back;
  dwRenderTargets();
 }
 function add(c){
  const list=destination===null?draft.spec.i:draft.spec.i[destination].i;
  list.push(c);dwMsg(`프리셋 「${draft.spec.n||'새 프리셋'}」에 ${c.n} 추가 · 하단 닫기를 누르면 편집창으로 돌아갑니다`);
  toast('프리셋 초안에 추가했습니다. 실제 대기열에는 담지 않았습니다.');return {ok:true};
 }
 const originalTargets=dwRenderTargets;
 dwRenderTargets=function(){originalTargets();if(picking&&draft)$('dwTgts').innerHTML=`<span class="ov-preset-destination">프리셋 초안 · ${esc(draft.spec.n||'새 프리셋')}</span>`;};
 MW.dwRenderTargets=dwRenderTargets;
 const originalAdd=dwAdd;
 dwAdd=async function(r,count){if(!picking)return originalAdd(r,count);if(count==='max'){dwMsg('프리셋에는 고정 수량을 입력해주세요.',true);return;}
  const c={t:{alter:'a',craft:'c',gather:'g'}[r.k],n:r.name,q:Number(count)};
  if(r.k!=='gather')c.r=r.id;if(r.k==='alter')c.m=dwMode(r);add(c);dwRowDone(r.id);
 };
 const originalCollect=dwAddCollect;
 dwAddCollect=async function(r){if(!picking)return originalCollect(r);return add({t:'k',n:r.work||r.name,f:r.facility});};
 const originalFree=dwAddFree;
 dwAddFree=async function(item,label){if(!picking)return originalFree(item,label);
  if(item.type==='play')return add({t:'p',n:item.title||item.listName||'연주',d:item.mode,s:item.song||'',l:item.list||'',c:item.count||1});
  return add({t:'b',n:item.name||'알림',x:item.text||'',o:item.sound!==false});
 };
 Object.assign(MW,{overlayPresetEdit:edit});
 setInterval(()=>{if(draft&&!picking&&$('ovPresetEditor')?.open)updateMaterials();},1500);
})();
