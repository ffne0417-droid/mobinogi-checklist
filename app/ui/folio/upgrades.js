/* Local music conveniences; no game-changing command is sent by this module. */
(()=>{
 function dialog(title){const d=document.createElement('dialog');d.className='music-upgrade-dialog';d.style='position:fixed;inset:8px;width:calc(100% - 16px);max-width:600px;max-height:calc(100% - 16px);padding:16px;border:1px solid var(--ctl);border-radius:12px;background:var(--bar);color:var(--row);z-index:40';
  const h=document.createElement('h3');h.textContent=title;h.style='font-size:14px;margin:0 0 12px';const body=document.createElement('div');body.style='max-height:55vh;overflow:auto';const note=document.createElement('p');note.setAttribute('role','status');note.style='font-size:11px;color:var(--row-sub);overflow-wrap:anywhere';const actions=document.createElement('div');actions.style='display:flex;gap:8px;justify-content:flex-end;margin-top:12px';
  const cancel=button('취소',()=>d.close());actions.append(cancel);d.append(h,body,note,actions);document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();return {d,body,note,actions,cancel};
 }
 function button(text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.style='padding:7px 10px;border:1px solid var(--ctl);border-radius:7px;color:var(--row);background:var(--inset)';b.onclick=fn;return b;}
 window.musicRelink=async it=>{
  if(REMOTE)return;const box=dialog('이름을 바꾼 이전 악보 연결');box.note.textContent='자동 추측하지 않습니다. 같은 악보의 이전 이름을 직접 골라주세요. 곡 번호·즐겨찾기·악기·커버·재생목록을 함께 옮깁니다.';
  try{const r=await api('/api/scores?relink=1');const rows=r?.items||[];let selected='';
   const search=document.createElement('input');search.placeholder='이전 이름 검색';search.setAttribute('aria-label','이전 악보 이름 검색');search.style='width:100%;padding:8px;margin-bottom:8px';const list=document.createElement('div');box.body.append(search,list);
   function render(){list.replaceChildren();for(const old of rows.filter(x=>(x.title||x.song||'').toLowerCase().includes(search.value.toLowerCase()))){const b=button(`${songTag(old.id)} ${old.title||old.song}`,()=>{selected=old.key;render();});b.style+=';display:block;width:100%;text-align:left;margin-bottom:5px;white-space:normal';b.setAttribute('aria-pressed',String(selected===old.key));if(selected===old.key)b.style.borderColor='var(--gold)';list.append(b);}if(!list.children.length)list.textContent='연결할 이전 악보 기록이 없습니다.';}
   search.oninput=render;render();const apply=button('선택한 이전 설정 연결',async()=>{if(!selected){box.note.textContent='이전 악보를 먼저 선택해주세요.';return;}apply.disabled=true;try{const out=await api('/api/song/inst',{op:'relink',oldKey:selected,key:it.key});if(!out?.ok){box.note.textContent=out?.message||'연결하지 못했습니다.';return;}box.d.close();await loadAll();detailRefresh();toast('이전 곡의 설정과 기록을 연결했습니다',2500,'ok');}catch{box.note.textContent='연결 중 오류가 발생했습니다. 새로고침 후 기록을 확인해주세요.';}finally{apply.disabled=false;}});box.actions.append(apply);
  }catch{box.note.textContent='이전 악보 목록을 불러오지 못했습니다.';}
 };
 window.musicRenameCover=async name=>{
  if(REMOTE)return;const box=dialog('이미지 이름 변경'),input=document.createElement('input');input.value=name.replace(/\.[^.]+$/,'');input.maxLength=120;input.setAttribute('aria-label','새 이미지 이름');input.style='width:100%;padding:9px';box.body.append(input);box.note.textContent='원본 파일과 확장자는 유지합니다. 사용하는 모든 곡의 커버 연결도 갱신됩니다.';
  const save=button('저장',async()=>{save.disabled=true;try{const r=await api('/api/covers',{op:'rename',name,stem:input.value});if(!r?.ok){box.note.textContent=r?.message||'변경하지 못했습니다.';return;}box.d.close();await loadAll();if(coverFor){const f=coverFor;await pickCover(S.byKey.get(f.key)||f);}toast('이미지 이름과 연결을 변경했습니다',2000,'ok');}catch{box.note.textContent='연결 오류가 발생했습니다.';}finally{save.disabled=false;}});box.actions.append(save);
 };
 window.musicRecropCover=async value=>{
  if(REMOTE||!coverFor)return;const c=(S.coverD?.mine||[]).find(x=>x.value===value);if(!c)return;
  try{const response=await fetch(c.url,{headers:{'X-MobiWorks-Token':TOKEN}});if(!response.ok)throw new Error();const blob=await response.blob();if(blob.size>8*1024*1024)throw new Error();await openCoverCrop(new File([blob],c.name,{type:blob.type||'image/jpeg'}),coverFor);}catch{toast('이미지를 열지 못했습니다. 원본 8MB 이하 이미지를 다시 선택해주세요.');}
 };
 if(!REMOTE){
  const row=document.createElement('div');row.id='musicAutoRefresh';row.style='display:flex;align-items:center;gap:8px;padding:5px 12px;font-size:10px;color:var(--row-sub);flex-shrink:0';const state=document.createElement('span');state.style='flex:1';const toggle=button('자동 갱신',async()=>{const enabled=S.settings.folio_auto_sync===false;const r=await api('/api/settings',{settings:{folio_auto_sync:enabled}});if(r?.settings)S.settings=r.settings;paint();});toggle.style.fontSize='10px';row.append(state,toggle);$('list').before(row);
  let outcome='';
  function paint(){const enabled=S.settings.folio_auto_sync!==false;toggle.textContent='자동 갱신 '+(enabled?'켜짐':'꺼짐');toggle.setAttribute('aria-pressed',String(enabled));
    const observed=S.scoreObservation,stamp=observed?.fetchedAt?new Date(observed.fetchedAt*1000).toLocaleTimeString('ko-KR'):'미확인';
    state.textContent=`마지막 악보 조회 ${stamp}${observed?` · 지원 악보 ${observed.connectorScores}개 / 가방 ${observed.bagScores}개`:''} · ${!enabled?'자동 확인 꺼짐':outcome||'작업·연주가 없을 때 자동 확인'}`;
  }
  let busy=false;async function poll(){paint();if(busy||document.hidden||S.settings.folio_auto_sync===false||$('cropSheet')&&!$('cropSheet').hidden||document.activeElement?.matches('input,textarea'))return;busy=true;try{const r=await api('/api/sync',{auto:true});if(r?.ok&&!r.deferred){await loadAll();if($('isheet').classList.contains('open'))renderInstSheet(false);outcome=r.changed?'가방 변경 반영 완료':'가방 악보 자동 확인 완료';}else if(r?.ok===false){outcome=r.message||'자동 확인 실패 — 기존 목록 유지';}}catch{outcome='연결 확인 지연 — 기존 목록 유지';}finally{busy=false;paint();}}
  setInterval(paint,3000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
  setInterval(poll,15000);setTimeout(poll,0);paint();
 }
})();
