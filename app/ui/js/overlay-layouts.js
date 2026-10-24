(()=>{
 let busy=false;
 async function load(){const r=await MW.api('/api/overlay/layouts');const select=document.getElementById('ovLayoutSelect');if(!select||!r?.ok)return;select.replaceChildren();for(const name of Object.keys(r.layouts||{})){const o=document.createElement('option');o.value=o.textContent=name;select.append(o);}}
 async function act(op){if(busy)return;const name=op==='layout_save'?document.getElementById('ovLayoutName').value:document.getElementById('ovLayoutSelect').value;const note=document.getElementById('ovLayoutNote');busy=true;try{
  const r=await MW.api('/api/overlay',{op,name});if(!r?.ok)throw new Error(r?.message||'배치를 처리하지 못했습니다.');
  if(r.settings){S.settings=r.settings;window.MWTheme?.fromSettings(S.settings);if(typeof ovFill==='function')ovFill(S.settings);}
  await load();note.textContent=op==='layout_save'?'현재 위치·크기·테마를 저장했습니다.':op==='layout_apply'?'저장된 배치를 적용했습니다.':'저장된 배치를 삭제했습니다.';
 }catch(error){note.textContent=error.message;}finally{busy=false;}}
 function mount(){const tab=document.getElementById('tabOverlay');if(!tab||!tab.children.length||document.getElementById('ovLayoutPanel'))return;
  const box=document.createElement('section');box.id='ovLayoutPanel';box.className='card';box.style='padding:12px;margin-top:10px';
  box.innerHTML='<b>오버레이 배치 저장</b><p class="muted small-t">위치·창 크기·가로/세로·테마를 함께 기억합니다.</p><div class="row" style="flex-wrap:wrap;gap:6px"><input id="ovLayoutName" aria-label="새 배치 이름" maxlength="40" placeholder="예: 음악용 세로"><button data-layout="layout_save">현재 배치 저장</button></div><div class="row" style="flex-wrap:wrap;gap:6px;margin-top:8px"><select id="ovLayoutSelect" aria-label="저장한 배치"></select><button data-layout="layout_apply">불러오기</button><button data-layout="layout_delete">삭제</button></div><p id="ovLayoutNote" role="status" class="muted small-t"></p>';
  tab.append(box);box.querySelectorAll('[data-layout]').forEach(b=>b.onclick=()=>act(b.dataset.layout));load();
 }
 setInterval(mount,700);mount();
})();
