/* Native overlay adapter. The UI and all add/edit/group handlers remain drawer.js. */
window.MW.railReady=()=>true;
const overlayNetUrl=NET.url;
NET.url=p=>overlayNetUrl(p==='/api/queue'?p+'?overlay=1':p);
window.overlayDismissed=false;
function overlaySyncDismissed(){
  // Dialog close events are queued: an old view may close after the next opens.
  window.overlayDismissed=!['drawer','ovManagement','ovLibrary','ovMusic'].some(id=>$(id)?.open);
}
window.overlayBooted=false;
window.overlayErrors=[];
let overlayQueueCommandBusy=false;
function overlayQueueButtons(){
  if(!$('ovQueueStart')){
    const start=document.createElement('button'),stop=document.createElement('button');
    start.id='ovQueueStart';start.className='pri';start.textContent='▶ 시작';
    stop.id='ovQueueStop';stop.className='stopb';stop.textContent='■ 정지';
    let bar=$('ovTaskRunbar');
    if(!bar){bar=document.createElement('div');bar.id='ovTaskRunbar';bar.className='ov-task-runbar';dwEl().querySelector('.dw-hdr').after(bar);}
    bar.append(start,stop);
    start.onclick=()=>overlayQueueCommand('start');stop.onclick=()=>overlayQueueCommand('stop');
  }
  const q=MW.boardState()||{},items=q.items||[],running=!!q.running;
  const ready=items.some(x=>x.type==='group'?(x.items||[]).length>0&&(colOf(x)==='wait'||x.status==='waiting'||(x.status==='pending'&&(x.items||[]).some(k=>k.status==='waiting'))):(colOf(x)==='wait'||x.status==='waiting'));
  const editing=dwEl().classList.contains('ov-preset-picking');
  $('ovQueueStart').disabled=overlayQueueCommandBusy||running||!ready||editing;
  $('ovQueueStop').disabled=overlayQueueCommandBusy||!running||editing;
  $('ovQueueStart').title=running?'이미 실행 중입니다':!ready?'실행할 대기 작업이 없습니다':'현재 대기열 전체를 시작합니다';
}
async function overlayQueueCommand(command){
  if(overlayQueueCommandBusy)return;
  overlayQueueCommandBusy=true;overlayQueueButtons();
  try{
    const r=await api('/api/queue/'+command,command==='start'?{confirm:true}:{});
    if(!r||!r.ok)toast((r&&(r.message||r.error))||'요청하지 못했습니다.');
    else toast(command==='start'?'대기열을 시작했습니다.':'정지를 요청했습니다.');
    await MW.refreshQueue();
  }catch(e){toast('연결 오류로 요청 결과를 확인하지 못했습니다.');}
  finally{overlayQueueCommandBusy=false;overlayQueueButtons();}
}
const OPRESET={rows:[],selected:'',busy:false,error:''};
// Preserve existing group actions and busy-group protection inside a compact menu.
const overlayTargetButtons=dwRenderTargets;
dwRenderTargets=function(){
  if($('dwTargetMenu')?.open)return;
  overlayTargetButtons();
  const box=$('dwTgts');if(!box)return;
  const menu=document.createElement('details');menu.id='dwTargetMenu';menu.className='ov-choice';
  const label=document.createElement('summary');label.textContent=dwTargetName();label.setAttribute('aria-label','담을 곳 선택');
  const options=document.createElement('span');options.className='ov-choice-options';
  while(box.firstChild)options.append(box.firstChild);
  menu.append(label,options);box.append(menu);
  options.addEventListener('click',e=>{if(e.target.closest('button'))menu.open=false;});
};
let overlayPresetDragging=false;
const overlayPresetOriginalBody=dwRenderBody;
dwRenderBody=function(){overlayPresetOriginalBody();overlayPresetRender();};
MW.dwRenderBody=dwRenderBody;
function overlayPresetRender(){
  if($('ovPresetMenu')?.open)return;
  if(overlayPresetDragging)return;
  let row=$('ovPresets');
  const scroll=row?.querySelector('.ov-preset-list')?.scrollLeft||0;
  if(!row){row=document.createElement('div');row.id='ovPresets';row.className='ov-presets';dwEl().querySelector('.dw-chain').before(row);}
  const visible=OPRESET.rows.filter(r=>DW.type==='all'||(r.kinds||[]).includes(DW.type));
  if(!visible.some(r=>r.id===OPRESET.selected))OPRESET.selected='';
  row.innerHTML=`<span class="lb">프리셋</span><details id="ovPresetMenu" class="ov-choice"><summary aria-label="프리셋 선택">${esc(visible.find(r=>r.id===OPRESET.selected)?.name||'선택하세요')}</summary><span class="ov-preset-list ov-choice-options">${visible.length?visible.map(r=>`<span class="ov-group${r.id===OPRESET.selected?' selected':''}"><button data-opselect="${esc(r.id)}" class="${r.id===OPRESET.selected?'on':''}" title="${esc(r.name)} · 작업 ${r.cards}개">${esc(r.name)}</button><span class="ov-group-actions"><button data-opedit="${esc(r.id)}" aria-label="프리셋 편집" title="프리셋 편집">✎</button><button data-opdelete="${esc(r.id)}" aria-label="프리셋 삭제" title="프리셋 삭제">×</button></span></span>`).join(''):'<span class="muted">해당 프리셋 없음</span>'}</span></details><button class="new" id="ovPresetSave">＋ 저장</button><button class="new" id="ovPresetNew">＋ 새 프리셋</button><button id="ovPresetLoad"${!OPRESET.selected||OPRESET.busy?' disabled':''}>대기열에 담기</button>${OPRESET.error?`<span class="ov-preset-error">${esc(OPRESET.error)}</span>`:''}`;
  row.querySelectorAll('[data-opselect]').forEach(b=>b.onclick=()=>{OPRESET.selected=b.dataset.opselect;OPRESET.error='';$('ovPresetMenu').open=false;overlayPresetRender();});
  const list=row.querySelector('.ov-preset-list');list.scrollLeft=scroll;
  list.tabIndex=0;list.setAttribute('aria-label','프리셋 목록 · 좌우 드래그 · 길게 눌러 순서 변경');
  let drag=null,suppressClick=false;
  list.addEventListener('pointerdown',e=>{
    if(e.button!==0)return;
    suppressClick=false;overlayPresetDragging=true;
    const button=e.target.closest('[data-opselect]');
    drag={id:e.pointerId,x:e.clientX,left:list.scrollLeft,moved:false,preset:button?.dataset.opselect};
    drag.events=new AbortController();
    window.addEventListener('pointerup',endDrag,{signal:drag.events.signal});
    window.addEventListener('pointercancel',endDrag,{signal:drag.events.signal});
    window.addEventListener('blur',()=>{if(drag)endDrag({pointerId:drag.id,type:'pointercancel'});},{signal:drag.events.signal});
    if(button&&!OPRESET.busy)drag.timer=setTimeout(()=>{
      if(!drag||drag.moved)return;
      drag.reorder=true;list.setPointerCapture(drag.id);button.classList.add('ov-reordering');
    },450);
  });
  list.addEventListener('pointermove',e=>{
    if(!drag||drag.id!==e.pointerId)return;
    const dx=e.clientX-drag.x;
    if(drag.reorder){
      e.preventDefault();
      const bounds=list.getBoundingClientRect();
      if(e.clientX<bounds.left+25)list.scrollLeft-=12;
      if(e.clientX>bounds.right-25)list.scrollLeft+=12;
      const candidates=[...list.querySelectorAll('[data-opselect]')].filter(b=>b.dataset.opselect!==drag.preset);
      list.querySelectorAll('.ov-drop-before,.ov-drop-after').forEach(b=>b.classList.remove('ov-drop-before','ov-drop-after'));
      let target=candidates.find(b=>e.clientX<b.getBoundingClientRect().right)||candidates.at(-1);
      if(target){const rect=target.getBoundingClientRect();drag.target=target.dataset.opselect;drag.before=e.clientX<rect.left+rect.width/2;target.classList.add(drag.before?'ov-drop-before':'ov-drop-after');}
      return;
    }
    if(!drag.moved&&Math.abs(dx)>6){clearTimeout(drag.timer);drag.moved=true;list.setPointerCapture(e.pointerId);list.classList.add('dragging');}
    if(drag.moved){e.preventDefault();list.scrollLeft=drag.left-dx;}
  });
  const endDrag=e=>{
    if(!drag||drag.id!==e.pointerId)return;
    const ended=drag;clearTimeout(ended.timer);ended.events.abort();suppressClick=ended.moved||ended.reorder;drag=null;overlayPresetDragging=false;
    list.classList.remove('dragging');list.querySelectorAll('.ov-reordering,.ov-drop-before,.ov-drop-after').forEach(b=>b.classList.remove('ov-reordering','ov-drop-before','ov-drop-after'));
    if(list.hasPointerCapture(e.pointerId))list.releasePointerCapture(e.pointerId);
    if(e.type==='pointerup'&&ended.reorder&&ended.target)overlayPresetOp({op:'preset_reorder',id:ended.preset,target:ended.target,before:ended.before});
  };
  list.addEventListener('pointerup',endDrag);list.addEventListener('pointercancel',endDrag);
  list.addEventListener('click',e=>{if(suppressClick){e.preventDefault();e.stopImmediatePropagation();suppressClick=false;}},true);
  list.addEventListener('keydown',e=>{if(e.target===list&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();list.scrollBy({left:e.key==='ArrowLeft'?-150:150,behavior:'smooth'});}});
  $('ovPresetSave').disabled=OPRESET.busy;$('ovPresetSave').onclick=overlayPresetSave;
  $('ovPresetNew').onclick=()=>MW.overlayPresetEdit();
  row.querySelectorAll('[data-opedit]').forEach(b=>b.onclick=()=>MW.overlayPresetEdit(b.dataset.opedit));
  $('ovPresetLoad').onclick=()=>overlayPresetPreflight(OPRESET.selected);
  row.querySelectorAll('[data-opdelete]').forEach(b=>b.onclick=async()=>{
    const r=OPRESET.rows.find(r=>r.id===b.dataset.opdelete);if(!r||OPRESET.busy)return;
    if(await askOk(`「${r.name}」 저장본을 삭제합니다. 이미 담은 대기열은 유지됩니다.`,{title:'프리셋 삭제',ok:'삭제'}))await overlayPresetOp({op:'preset_delete',id:r.id});
  });
}
// Read-only review before the single queue-write step. Calculations deliberately
// share the editor's catalogue/stock helpers; no execution-time estimate is invented.
function overlayPresetReview(spec){
  const totals=new Map(),items=[],warnings=[];
  const kinds={a:'alter',c:'craft',g:'gather'},labels={a:'가공',c:'제작',g:'채집',k:'수령',p:'연주',b:'알림'};
  function visit(card,multiplier=1){
    if(card.t==='G'){for(const child of card.i||[])visit(child,multiplier*Math.max(1,Number(card.r)||1));return;}
    const kind=kinds[card.t],recipes=S.snap?.[kind]||[];
    let rec=card.r?recipes.find(r=>rid(kind,r)===card.r):null;
    if(!rec&&!card.r){const matches=recipes.filter(r=>r.name===card.n);if(matches.length===1)rec=matches[0];}
    let runs=Math.max(1,Number(card.q)||1)*multiplier;
    let detail=card.t==='g'?`${fmtN((Number(card.q)||0)*multiplier)}개 목표`:['a','c'].includes(card.t)?`${fmtN(runs)}회`:multiplier>1?`${fmtN(multiplier)}회 반복`:'';
    if(['a','c'].includes(card.t)&&card.z){
      const bag=bagOf(rec?.name||card.n),target=Math.max(1,Number(card.q)||1);
      if(multiplier!==1){warnings.push(`${card.n}: 총 보유 목표와 그룹 반복은 함께 계산할 수 없습니다.`);detail=`총 보유 목표 ${fmtN(target)}개 · 반복 확인 필요`;}
      else if(bag==null||!rec){warnings.push(`${card.n}: 완제품 보유량 또는 레시피 미확인`);detail=`총 보유 목표 ${fmtN(target)}개 · 보유량 미확인`;}
      else{const have=bag+storeOf(rec.name),short=Math.max(0,target-have);runs=Math.ceil(short/Math.max(1,Number(rec.per)||1));detail=`보유 ${fmtN(have)} / 목표 ${fmtN(target)}개 → ${runs?`${fmtN(runs)}회 제작`:'목표 충족 · 담기 제외'}`;}
    }
    items.push({name:card.n||'이름 없음',kind:labels[card.t]||'작업',detail});
    if(!['a','c'].includes(card.t))return;
    if(!rec){warnings.push(`${card.n}: 레시피 미확인`);return;}
    if(rec.blocked)warnings.push(`${card.n}: 제작 조건 확인 필요`);
    const rows=planRows(rec);if(!rows.length&&runs>0)warnings.push(`${card.n}: 재료 정보 미확인`);
    for(const row of rows){const calc=planCalc(row,runs),old=totals.get(row.name);if(old)old.req+=calc.req;else totals.set(row.name,{name:row.name,req:calc.req,have:calc.have});}
  }
  for(const card of spec.i||[])visit(card);
  function preparable(name,need,path=[]){
    const bag=bagOf(name);if(bag==null)return false;
    const short=Math.max(0,need-bag-storeOf(name));if(!short)return true;
    const {source,sourceId}=planSource(name);if(source==='gather')return true;
    if(!['craft','alter'].includes(source)||path.includes(sourceId)||path.length>=4)return false;
    const rec=(S.snap?.[source]||[]).find(r=>rid(source,r)===sourceId);
    if(!rec||rec.blocked)return false;
    const rows=planRows(rec),runs=Math.ceil(short/Math.max(1,Number(rec.per)||1));
    return rows.length>0&&rows.every(r=>preparable(r.name,r.perCount*runs,[...path,sourceId]));
  }
  const possible=[],manual=[],unknown=[];
  for(const item of totals.values()){
    if(item.have==null){unknown.push(item.name);continue;}
    item.short=Math.max(0,item.req-item.have);
    if(item.short>0)(preparable(item.name,item.req)?possible:manual).push(item);
  }
  if(unknown.length)warnings.push(`재료 보유량 미확인: ${unknown.join(' · ')}`);
  return {items,possible,manual,warnings:[...new Set(warnings)],autoPrepare:spec.autoPrepare===true,allowPartial:spec.allowPartial===true};
}
async function overlayPresetPreflight(id){
  if(OPRESET.busy||!id)return;
  let d=$('ovPresetReview');if(!d){d=document.createElement('dialog');d.id='ovPresetReview';document.body.append(d);}
  if(d.open)return;
  let submitted=false;
  const close=()=>{if(!submitted)d.close();};
  const header='<div class="dlg-h"><b>프리셋 담기 전 확인</b><span class="grow"></span><button id="ovReviewClose" aria-label="담기 전 확인 닫기">×</button></div>';
  d.innerHTML=header+'<div class="dlg-b" role="status">저장본과 보유량을 확인하고 있습니다…</div>';
  $('ovReviewClose').onclick=close;d.showModal();
  try{
    const r=await api('/api/presets?id='+encodeURIComponent(id));
    if(!d.open)return;
    if(!r?.ok||!r.spec)throw new Error(r?.message||'저장본을 불러오지 못했습니다. 닫고 다시 시도해주세요.');
    const review=overlayPresetReview(r.spec);
    const shortage=(title,list)=>`<section class="ov-review-section"><b>${title}</b><div class="ov-material-chips">${list.length?list.map(x=>`<span class="ov-material-chip short">${esc(x.name)} ${fmtN(x.short)}개 부족</span>`).join(''):'<span class="muted">없음</span>'}</div></section>`;
    d.innerHTML=header+`<div class="dlg-b"><h3>${esc(r.spec.n||'프리셋')}</h3><p class="muted">현재 대기열 뒤에 추가합니다. 저장본은 유지되며 자동으로 시작하지 않습니다.</p><div class="ov-review-items">${review.items.map(x=>`<div><span class="badge">${esc(x.kind)}</span><b>${esc(x.name)}</b><span>${esc(x.detail)}</span></div>`).join('')||'<p class="muted">담을 항목이 없습니다.</p>'}</div><section class="ov-review-section"><b>예상 소요 시간</b><span class="muted">미확인 · 레시피별 확정 시간과 가공소 대기 시간을 확인할 수 없어 계산하지 않습니다.</span></section>${shortage('자동 준비 가능한 부족 재료'+(review.autoPrepare?' · 자동 준비 켜짐':' · 자동 준비 꺼짐'),review.possible)}${shortage('직접 준비가 필요한 부족 재료',review.manual)}<p class="ov-review-options">부족 재료 자동 준비: ${review.autoPrepare?'켜짐':'꺼짐'}<br>준비 불가 재료는 가능한 만큼 제작: ${review.allowPartial?'켜짐':'꺼짐'}</p>${review.warnings.length?`<div class="ov-review-warnings" role="status">${review.warnings.map(w=>`<p>${esc(w)}</p>`).join('')}</div>`:''}<p class="muted">현재 보유량(가방+창고) 기준 · 앞 작업의 채집·생산 결과 미반영<br>재료 준비는 원래 목표량 기준입니다. 실제 준비 경로·최종 제작량은 담을 때 다시 계산합니다.</p><p id="ovReviewError" role="alert"></p></div><div class="dlg-f"><button id="ovReviewCancel">취소</button><span class="grow"></span><button id="ovReviewConfirm" class="pri"${review.items.length?'':' disabled'}>확인 후 대기열에 담기</button></div>`;
    $('ovReviewClose').onclick=close;$('ovReviewCancel').onclick=close;
    $('ovReviewConfirm').onclick=async()=>{
      if(submitted||OPRESET.busy)return;submitted=true;
      $('ovReviewConfirm').disabled=true;$('ovReviewCancel').disabled=true;$('ovReviewClose').disabled=true;
      const result=await overlayPresetOp({op:'preset_load',id,mode:'append'});
      if(result)d.close();else{$('ovReviewError').textContent=OPRESET.error;$('ovReviewConfirm').disabled=false;}
      submitted=false;$('ovReviewCancel').disabled=false;$('ovReviewClose').disabled=false;
    };
  }catch(e){if(d.open){d.innerHTML=header+`<div class="dlg-b"><p role="alert">${esc(e.message||'확인하지 못했습니다.')}</p></div>`;$('ovReviewClose').onclick=close;}}
  d.oncancel=e=>{if(submitted)e.preventDefault();};
}
async function overlayPresetRefresh(){
  const r=await api('/api/presets');
  if(r&&r.ok){OPRESET.rows=r.presets||[];OPRESET.error='';}else OPRESET.error='프리셋 목록을 불러오지 못했습니다.';
  overlayPresetRender();
}
async function overlayPresetOp(payload){
  if(OPRESET.busy)return null;
  OPRESET.busy=true;OPRESET.error='';overlayPresetRender();
  let r;
  try{r=await api('/api/queue',payload);
    if(!r||!r.ok){OPRESET.error=(r&&(r.message||r.error))||'처리하지 못했습니다.';return null;}
    if(r.presets)OPRESET.rows=r.presets;
    if(r.preset)OPRESET.selected=r.preset.id;
    if(r.state&&MW.applyQueueState)MW.applyQueueState(r.state);
    if(payload.op==='preset_load'){
      await MW.refreshQueue();dwRenderTargets();dwCartRender();
      const skipped=r.skipped||[];
      OPRESET.error=skipped.length?`담지 못한 ${skipped.length}개: `+skipped.map(x=>`${x.name} (${x.message||x.error})`).join(' · '):'';
      const adjusted=(r.adjusted||[]).map(x=>`${x.name} ${x.requested}→${x.count}회 (${x.reason||'재료 보유량 기준'})`).join(' · ');
      if(adjusted)OPRESET.error=[OPRESET.error,`가능한 만큼 조정: ${adjusted}`].filter(Boolean).join(' · ');
      toast(`${r.added||0}개를 대기열에 담았습니다.${(r.satisfied||[]).length?` 이미 목표 충족 ${(r.satisfied||[]).length}개는 제외했습니다.`:''} 시작은 별도로 눌러주세요.`);
    }else toast(payload.op==='preset_reorder'?'프리셋 순서를 저장했습니다.':payload.op==='preset_update'||payload.op==='preset_save'?'프리셋을 저장했습니다.':'프리셋 저장본을 삭제했습니다.');
    return r;
  }catch(e){OPRESET.error='연결 오류: 다시 확인해주세요.';return null;}
  finally{OPRESET.busy=false;overlayPresetRender();}
}
function overlayPresetSave(){
  const group=DW.target!=='root'?MW.gFind(DW.target):null;
  let d=$('ovPresetDialog');if(!d){d=document.createElement('dialog');d.id='ovPresetDialog';document.body.append(d);}
  d.innerHTML=`<div class="dlg-h"><b>프리셋 저장</b></div><div class="dlg-b"><p>${group?`선택한 그룹 「${esc(group.name)}」만 저장합니다.`:'현재 대기열 전체 구성을 저장합니다.'}</p><input id="ovPresetName" maxlength="60" aria-label="프리셋 이름" placeholder="예: 강철괴 10시간" value="${esc(group?group.name:'')}"><p class="muted">대기열을 비워도 저장본은 남습니다. 같은 이름은 덮어씁니다.</p><span id="ovPresetSaveError"></span></div><div class="dlg-f"><span class="grow"></span><button id="ovPresetCancel">취소</button><button class="pri" id="ovPresetConfirm">저장</button></div>`;
  $('ovPresetCancel').onclick=()=>d.close();
  $('ovPresetConfirm').onclick=async()=>{
    const name=$('ovPresetName').value.trim();if(!name){$('ovPresetSaveError').textContent='이름을 입력해주세요.';return;}
    if(OPRESET.rows.some(r=>r.name===name)&&!await askOk(`「${name}」 저장본을 현재 구성으로 바꿉니다.`,{title:'프리셋 덮어쓰기',ok:'덮어쓰기'}))return;
    $('ovPresetConfirm').disabled=true;
    const r=await overlayPresetOp({op:'preset_save',name,...(group?{group:group.id}:{})});
    if(r)d.close();else{$('ovPresetSaveError').textContent=OPRESET.error;$('ovPresetConfirm').disabled=false;}
  };
  d.showModal();$('ovPresetName').focus();
}
const overlayGroupRender=gRender;
gRender=function(){
  overlayGroupRender();
  const footer=gEl().querySelector('.dlg-f');if(!footer)return;
  const remove=document.createElement('button');remove.id='gDelete';remove.textContent='그룹 삭제';
  remove.disabled=gRunning(G.g);
  remove.onclick=async()=>{
    const id=G.id,name=G.draft.name||G.g.name;
    if(!await askOk(`「${name}」 그룹과 안의 모든 항목을 삭제합니다.`,{title:'그룹을 삭제할까요?',ok:'삭제'}))return;
    await MW.gRemove(id);
    if(!MW.gFind(id)){DW.target='root';dwRenderTargets();dwFoot();toast('그룹을 삭제했습니다');}
  };
  footer.insertBefore(remove,footer.firstChild);
};
MW.gRender=gRender;
window.addEventListener('error',e=>window.overlayErrors.push(e.message));
window.addEventListener('unhandledrejection',e=>window.overlayErrors.push(String(e.reason)));
const overlayApplySnap=applySnap;
applySnap=function(s){
  const order=window.MW_OVERLAY_ORDER||{},facs=Object.keys(order);
  const rank=r=>{
    let f=facs.find(k=>order[k].includes(r.name))||String(r.facility||r.cat||'').split(' ')[0];
    const a=order[f]||[],pos=a.map((n,i)=>n===r.name?i:-1).filter(i=>i>=0);
    const v=Math.max(0,Number(r.variant||1)-1);
    return [facs.includes(f)?facs.indexOf(f):99,pos.length?pos[Math.min(v,pos.length-1)]:a.length+1,v];
  };
  if(s&&Array.isArray(s.alter))s.alter.sort((a,b)=>{const x=rank(a),y=rank(b);return x[0]-y[0]||x[1]-y[1]||x[2]-y[2];});
  overlayApplySnap(s);
};
let overlayLastWorkTab='tasks';
try{if(localStorage.getItem('mobiworks.overlay.workTab')==='queue')overlayLastWorkTab='queue';}catch{}
function overlayRememberWorkTab(active){overlayLastWorkTab=active;try{localStorage.setItem('mobiworks.overlay.workTab',active);}catch{}}
function overlayWorkTabs(host,active){
  const head=host.querySelector('.dw-hdr,.ov-management-head');
  if(!head)return;
  let tabs=head.querySelector('.ov-work-tabs');
  if(!tabs){
    tabs=document.createElement('span');tabs.className='seg ov-work-tabs';
    tabs.innerHTML='<button data-work="tasks">작업</button><button data-work="queue">관리</button>';
    const title=head.querySelector('b');if(title)title.replaceWith(tabs);else head.prepend(tabs);
    tabs.querySelectorAll('button').forEach(b=>b.onclick=()=>overlayOpen(b.dataset.work));
  }
  tabs.querySelectorAll('button').forEach(b=>b.classList.toggle('on',b.dataset.work===active));
}
function overlayManagement(){
  let d=$('ovManagement');if(d)return d;
  d=document.createElement('dialog');d.id='ovManagement';
  d.innerHTML='<div class="ov-management-head"><b>관리</b><span class="muted">기존 큐 · 오류 작업은 ↺ 대기로 되돌린 뒤 시작</span><button id="ovManagementClose">Esc · 닫기</button></div>';
  document.body.append(d);
  d.append($('runbar'),$('tabQueue'));
  overlayWorkTabs(d,'queue');
  overlayResizeHandle(d);
  $('ovManagementClose').onclick=()=>d.close();
  d.addEventListener('close',overlaySyncDismissed);
  return d;
}
function overlayLibraryOpen(kind,tab){
  let d=$('ovLibrary');
  if(!d){
    d=document.createElement('dialog');d.id='ovLibrary';
    d.innerHTML='<div class="ov-management-head"><b id="ovLibraryTitle"></b><span class="seg" id="ovSettingsTabs"><button data-pref="stock">재고</button><button data-pref="dict">사전</button><button data-pref="overlay">오버레이</button><button data-pref="settings">설정</button></span><span class="grow"></span><button id="ovLibraryClose">Esc · 닫기</button></div><div class="ov-library-body"></div>';
    document.body.append(d);
    const body=d.querySelector('.ov-library-body');
    for(const id of ['tabStock','tabDict','tabOverlay','tabSettings'])body.append($(id));
    $('ovLibraryClose').onclick=()=>d.close();d.addEventListener('close',overlaySyncDismissed);
    d.querySelectorAll('[data-pref]').forEach(b=>b.onclick=()=>overlayLibraryOpen('preferences',b.dataset.pref));
    overlayResizeHandle(d);
  }
  for(const dialog of document.querySelectorAll('dialog[open]'))if(dialog!==d)dialog.close();
  window.overlayDismissed=false;
  const preferences=kind==='preferences',selected=preferences?(tab||d.dataset.pref||'overlay'):kind;
  if(preferences)d.dataset.pref=selected;
  $('ovLibraryTitle').hidden=true;
  $('ovSettingsTabs').hidden=false;
  d.querySelectorAll('[data-pref]').forEach(b=>b.classList.toggle('on',b.dataset.pref===selected));
  switchTab(selected,false);
  if(!d.open)d.showModal();
  if(selected==='stock'||selected==='dict')loadDict();
}
function overlayMusicOpen(){
  let d=$('ovMusic');
  if(!d){
    d=document.createElement('dialog');d.id='ovMusic';
    d.innerHTML='<div class="ov-management-head"><b>음악</b><span class="grow"></span><button id="ovMusicClose">Esc · 닫기</button></div><iframe title="모비폴리오 음악" src="/folio/?overlay=1"></iframe>';
    document.body.append(d);
    $('ovMusicClose').onclick=()=>d.close();
    d.addEventListener('close',overlaySyncDismissed);
    overlayResizeHandle(d);
    const frame=d.querySelector('iframe');
    d.querySelectorAll('[data-music-view]').forEach(b=>b.onclick=()=>frame.contentWindow.postMessage({type:'mobiworks-music-view',view:b.dataset.musicView},location.origin));
    let last='';
    addEventListener('message',e=>{
      if(e.origin!==location.origin||e.source!==frame.contentWindow||!d.open)return;
      if(e.data?.type==='mobiworks-music-play-request'){
        d.close();overlaySyncDismissed();
        api('/api/overlay',{op:'close_music'}).catch(()=>{});
        return;
      }
      if(e.data?.type!=='mobiworks-music-state')return;
      const data=e.data;
      if(!['list','compact','expanded'].includes(data.view))return;
      d.dataset.view=data.view;
      d.querySelectorAll('[data-music-view]').forEach(b=>b.classList.toggle('on',b.dataset.musicView===(data.view==='list'?'list':'compact')));
      const payload={op:'music_layout',view:data.picker?'expanded':data.view,input:!!data.input};
      const key=JSON.stringify(payload);
      if(key!==last){last=key;api('/api/overlay',payload);}
    });
    d.addEventListener('close',()=>{last='';});
  }
  for(const other of document.querySelectorAll('dialog[open]'))if(other!==d)other.close();
  window.overlayDismissed=false;
  if(!d.open)d.showModal();
  const musicFrame=d.querySelector('iframe');
  let musicPage=false;
  try{const url=new URL(musicFrame.contentWindow.location.href);musicPage=url.origin===location.origin&&url.pathname==='/folio/'&&url.searchParams.get('overlay')==='1';}catch{}
  if(!musicPage)musicFrame.src='/folio/?overlay=1';
  else musicFrame.contentWindow.postMessage({type:'mobiworks-music-status'},location.origin);
}
let overlayRefreshing=false;
async function overlayRefresh(){
  if(overlayRefreshing)return;
  overlayRefreshing=true;
  const buttons=[...document.querySelectorAll('[data-overlay-refresh]')];
  buttons.forEach(b=>{b.disabled=true;b.textContent='갱신 중…';});
  try{
    const workResult=await api('/api/sync',{});
    if(workResult?.error==='busy')throw new Error(workResult.message);
    const musicResult=await api('/api/folio/sync',{});
    await loadWork();await MW.refreshQueue();
    if($('tabStock')?.classList.contains('on')||$('tabDict')?.classList.contains('on')||$('ovLibrary')?.open)await loadDict();
    $('ovMusic')?.querySelector('iframe')?.contentWindow.postMessage({type:'mobiworks-music-refresh'},location.origin);
    if(workResult?.ok&&musicResult?.ok)toast('새로고침 완료 · 악기, 악보, 재고, 레시피, 가공 상태를 갱신했습니다.');
    else toast('일부 정보를 갱신하지 못했습니다. 게임 연결 상태를 확인해주세요.');
  }catch(error){toast(error.message||'새로고침하지 못했습니다.');}
  finally{overlayRefreshing=false;buttons.forEach(b=>{b.disabled=false;b.textContent='↻ 새로고침';});}
}
function overlayRefreshButton(host){
  const head=host.querySelector('.dw-hdr,.ov-management-head');
  if(!head||head.querySelector('[data-overlay-refresh]'))return;
  const button=document.createElement('button');button.type='button';button.dataset.overlayRefresh='';button.textContent='↻ 새로고침';button.title='게임에서 악기·악보·재고·레시피·가공 상태 다시 읽기';button.onclick=overlayRefresh;
  head.insertBefore(button,head.lastElementChild);
}
function overlayResizeHandle(host){
  overlayRefreshButton(host);
  if(host.querySelector('.ov-resize-handle'))return;
  const grip=document.createElement('button');grip.className='ov-resize-handle';grip.type='button';grip.textContent='◢';grip.title='드래그하여 창 크기 조절';grip.setAttribute('aria-label','창 크기 조절');host.append(grip);
  let drag=null,pending=null,sending=false,timer=null;
  const flush=async()=>{
    clearTimeout(timer);timer=null;if(sending||!pending)return;
    const size=pending;pending=null;sending=true;
    try{const r=await api('/api/overlay',{op:'resize_drawer',...size});if(!r?.ok){pending=null;toast(r?.message||'창 크기를 조절하지 못했습니다.');}}
    finally{sending=false;if(pending)timer=setTimeout(flush,40);}
  };
  const move=e=>{if(!drag||e.pointerId!==drag.id)return;e.preventDefault();pending={width:Math.round(drag.w+e.screenX-drag.x),height:Math.round(drag.h+e.screenY-drag.y)};if(!timer)timer=setTimeout(flush,40);};
  grip.onpointerdown=e=>{if(e.button!==0)return;e.preventDefault();e.stopPropagation();drag={id:e.pointerId,x:e.screenX,y:e.screenY,w:window.innerWidth,h:window.innerHeight};grip.setPointerCapture(e.pointerId);};
  grip.onpointermove=move;
  grip.onpointerup=e=>{move(e);drag=null;if(grip.hasPointerCapture(e.pointerId))grip.releasePointerCapture(e.pointerId);flush();};
  grip.onpointercancel=()=>{drag=null;flush();};
  grip.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();pending={width:innerWidth+(e.key==='ArrowRight'?20:e.key==='ArrowLeft'?-20:0),height:innerHeight+(e.key==='ArrowDown'?20:e.key==='ArrowUp'?-20:0)};flush();};
}
const overlayOriginalOpenDrawer=openDrawer;
// Programmatic focus (dialog opening / auto-search focus) must not activate
// the native host. Arm keyboard input only when the user chooses an editor.
let overlayKeyboardInput=false;
function overlayEditable(target){return target instanceof Element&&target.matches('textarea,[contenteditable="true"],input:not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="button"]):not([type="submit"]):not([type="hidden"])');}
function overlayKeyboard(enabled){
  if(enabled===overlayKeyboardInput)return;
  overlayKeyboardInput=enabled;
  api('/api/overlay',{op:'keyboard_input',enabled});
}
document.addEventListener('pointerdown',e=>{if(e.isTrusted)overlayKeyboard(overlayEditable(e.target));},true);
document.addEventListener('focusout',()=>setTimeout(()=>{if(!overlayEditable(document.activeElement))overlayKeyboard(false);},0));
window.addEventListener('blur',()=>overlayKeyboard(false));
openDrawer=function(opts){for(const id of ['ovManagement','ovLibrary','ovMusic'])if($(id)?.open)$(id).close();window.overlayDismissed=false;return overlayOriginalOpenDrawer(opts);};
MW.openDrawer=openDrawer;
const overlayOriginalBindRunbar=bindRunbar;
bindRunbar=function(){
  overlayOriginalBindRunbar();
  if(!$('ovManagement'))return;
  const st=$('rbStart'),q=MW.boardState()||{};
  if(st){st.disabled=overlayQueueCommandBusy||!!q.running||!(q.items||[]).some(x=>colOf(x)==='wait'||x.status==='waiting');st.title='현재 대기열을 바로 시작합니다';st.onclick=()=>overlayQueueCommand('start');}
};
window.overlayOpen=function(kind,category){
  if(!window.overlayBooted){window.overlayPending=[kind,category];return;}
  if(kind==null)kind=overlayLastWorkTab;
  window.overlayDismissed=false;
  const d=dwEl();
  if(kind==='music'){overlayMusicOpen();return;}
  if($('ovMusic')?.open)$('ovMusic').close();
  if(['stock','dict','preferences'].includes(kind)){overlayLibraryOpen(kind,category);return;}
  if($('ovLibrary')?.open)$('ovLibrary').close();
  if(kind==='queue'){
    overlayRememberWorkTab('queue');
    if(d.open)d.close();
    const management=overlayManagement();switchTab('queue',false);window.overlayDismissed=false;
    overlayWorkTabs(management,'queue');
    if(!management.open)management.showModal();
    MW.renderBoard();MW.refreshQueue();
    return;
  }
  if($('ovManagement')?.open)$('ovManagement').close();
  window.overlayDismissed=false;
  overlayRememberWorkTab('tasks');
  if(kind&&kind!=='tasks'){DW.type=kind;DW.cart=false;if(category&&category!=='전체'){DW.q=category;$('dwQ').value=category;}}
  if(!d.open)d.showModal();
  overlayWorkTabs(d,'tasks');
  dwRenderTargets();dwRenderBody();
  overlayPresetRefresh();
};
(async()=>{
  try{
    const settings=await api('/api/settings?nocli=1');S.settings=settings&&settings.settings||{};
    window.MWTheme?.fromSettings(S.settings);
    await loadWork();await mwRefreshQueue();
    openDrawer();
    await overlayPresetRefresh();
    const d=dwEl();d.addEventListener('close',overlaySyncDismissed);
    overlayResizeHandle(d);
    $('dwGo').textContent='닫기';$('dwGo').onclick=()=>d.close();
    overlayQueueButtons();
    setInterval(()=>{if(d.open&&!document.hidden)overlayQueueButtons();},400);
    window.overlayBooted=true;
    const p=window.overlayPending;if(p)window.overlayOpen(...p);
    setInterval(()=>{if(!document.hidden)loadWork();},15000);
  }catch(e){window.overlayErrors.push(String(e));toast('작업 목록을 불러오지 못했습니다. 닫았다 다시 열어주세요.');}
})();
