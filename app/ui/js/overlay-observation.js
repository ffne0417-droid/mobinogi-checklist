/* Observation and UI preferences only. Never starts, stops or retries work. */
function overlayEvents(q){
  const rows=[];
  function visit(items){for(const it of items||[]){
    for(const event of it.log||[])if(Number.isFinite(Number(event.t)))rows.push({t:Number(event.t),msg:String(event.msg||''),name:it.name||'작업'});
    visit(it.items);
  }}
  visit(q.items);
  return rows.sort((a,b)=>b.t-a.t);
}
function overlayRunStatus(q,now=Date.now()/1000){
  const br=q.connectorBreak||{};
  if(!q.running&&q.connectorUsage?.awaitingConfirmation)return '게임 직접 확인 필요 · 확인 후 작업 복구 → 시작 · 진행량 유지';
  if(q.running&&br.paused)return `자동 휴식 중${br.remainingRestSeconds==null?'':` · 약 ${Math.ceil(br.remainingRestSeconds/60)}분 후 재개 예정`} · 게임 제한 초기화는 미검증`;
  if(!q.running&&q.lastError)return `오류로 중단 · ${q.lastError.short||q.lastError.message||q.lastError.code||'원인 확인 필요'} · 자동 재개 안 함`;
  if(!q.running&&q.stopReason==='user')return '사용자 정지 · 자동 재개 안 함';
  const events=overlayEvents(q),last=events[0];
  if(!q.running){
    if(last?.msg.includes('대기 상한'))return '가공 완료 전 앱 대기 상한에 도달 · 실행 정지 · 자동 재개 안 함';
    return (q.items||[]).some(i=>['waiting','pending','stopped'].includes(i.status))?'실행 정지 · 대기 작업 있음 · 자동 재개 안 함':'실행 정지 · 최근 작업 기록 확인 가능';
  }
  if(q.hold)return '정상 대기 · 연주/현재 동작이 끝나기를 기다리는 중';
  const current=q.current;
  const active=events.find(e=>!current||findCurrent(q.items,current)?.name===e.name);
  const wait=active?.msg.match(/완료 대기 — (\d+)초 남음/);
  if(wait){const remaining=Math.max(0,Number(wait[1])-Math.max(0,now-active.t));return remaining>0?`정상 가공 대기 · 다음 완료까지 약 ${Math.ceil(remaining/60)}분 (마지막 관찰 기준)`:'정상 대기 · 완료 시각 경과, 다음 조회 확인 중';}
  return `실행 중${q.currentCard?.name?' · '+q.currentCard.name:''} · ${last?.msg||'상태 확인 중'}`;
}
function findCurrent(items,id){for(const it of items||[]){if(it.id===id)return it;const child=findCurrent(it.items,id);if(child)return child;}return null;}
function connectorUsageStatus(q){
  const u=q?.connectorUsage;if(!u)return '명령 시간 관찰 준비 중 · 게임 타이머 아님';
  const fmt=v=>{const n=Math.floor(Math.max(0,Number(v)||0));return `${Math.floor(n/60)}분 ${n%60}초`;};
  const seconds=u.sinceConfirmationSeconds;
  let text=seconds==null?`측정 시작 후 명령 누적 ${fmt(u.completedSeconds)}`:`직접 확인 후 명령 누적 ${fmt(seconds)}`;
  if(u.inFlightCount)text+=` · 현재 호출 대기 약 ${fmt(u.inFlightSeconds)} (별도)`;
  if(u.awaitingConfirmation)text+=' · 게임 직접 확인 필요';
  else if(seconds!=null&&Number(seconds)>=3300)text+=' · 1시간 기준 주의';
  if(u.incomplete||u.overlapObserved)text+=' · 누락/중복 가능';
  return text+' · 채집·제작·가공·수령 호출 소요시간 관찰값, 게임 타이머 아님';
}
(()=>{
  let ready=false,saved='',prefs={},timer,historyKey='';
  const preferenceKey='mw.overlayChoices';
  function choices(){return {target:DW.target||'root',preset:OPRESET.selected||''};}
  async function restore(){
    try{const r=await api('/api/ui/state');prefs=r.ui?.prefs||r.prefs||{};
      const raw=prefs[preferenceKey];if(raw){const c=JSON.parse(raw);
        if(c.target==='root'||dwGroups().some(g=>g.id===c.target&&!g.running))DW.target=c.target;
        if(OPRESET.rows.some(p=>p.id===c.preset))OPRESET.selected=c.preset;
        dwRenderTargets();overlayPresetRender();dwFoot();
      }
    }catch{}finally{saved=JSON.stringify(choices());ready=true;}
  }
  function save(){if(!ready)return;const value=JSON.stringify(choices());if(value===saved)return;
    saved=value;try{localStorage.setItem(preferenceKey,value);}catch{}
    clearTimeout(timer);timer=setTimeout(async()=>{
      try{const r=await api('/api/ui/state');const current=r.ui?.prefs||r.prefs||prefs;
        const result=await api('/api/ui/state',{prefs:{...current,[preferenceKey]:value}});
        if(result?.ok===false)saved='';
      }catch{saved='';}
    },350);
  }
  function render(){
    if(!window.overlayBooted)return;
    const q=MW.boardState()||{};
    for(const [host,id] of [[$('ovTaskRunbar'),'ovRunStatus'],[$('ovManagement')?.querySelector('.ov-management-head'),'ovManageStatus']]){
      if(!host)continue;let el=$(id);if(!el){el=document.createElement('span');el.id=id;el.className='ov-run-status';el.setAttribute('role','status');host.append(el);}
      const text=overlayRunStatus(q);if(el.textContent!==text)el.textContent=text;
    }
    const management=$('ovManagement');
    if(management){let panel=$('ovWorkHistory');if(!panel){panel=document.createElement('details');panel.id='ovWorkHistory';panel.innerHTML='<summary>작업 기록 · 등록 / 수령 / 휴식 / 중단</summary><p class="muted">현재 대기열에 보존된 로그 · 삭제한 카드의 기록은 포함하지 않습니다.</p><ol></ol>';management.querySelector('.ov-management-head').after(panel);}
      let usage=$('ovConnectorUsage');if(!usage){usage=document.createElement('p');usage.id='ovConnectorUsage';usage.className='muted';usage.setAttribute('role','status');panel.querySelector('summary').after(usage);}
      const usageText=connectorUsageStatus(q);if(usage.textContent!==usageText)usage.textContent=usageText;
      const events=overlayEvents(q).filter(e=>/등록|수령|휴식|중단|종료|오류|제한|대기 상한/.test(e.msg)).slice(0,100);
      const key=JSON.stringify(events);if(historyKey!==key){historyKey=key;panel.querySelector('ol').innerHTML=events.map(e=>`<li><time>${esc(new Date(e.t*1000).toLocaleString('ko-KR'))}</time> <b>${esc(e.name)}</b> ${esc(e.msg)}</li>`).join('')||'<li>보존된 기록이 없습니다.</li>';}
    }
    let summary=$('ovDestinationSummary');if(!summary&&$('ovPresets')){summary=document.createElement('span');summary.id='ovDestinationSummary';summary.className='ov-choice-summary';$('ovPresets').append(summary);}
    if(summary){const p=OPRESET.rows.find(p=>p.id===OPRESET.selected);summary.hidden=true;summary.textContent=p?`${p.cards}개 작업`:'';
      summary.title=p?`프리셋 ${p.name} · 대기열 뒤에 추가 · 자동 시작 안 함`:'';
      $('dwTgts').title=`개별 작업을 담을 곳: ${dwTargetName()}`;
      if($('ovPresetLoad'))$('ovPresetLoad').title=p?`${p.name} · ${p.cards}개 작업 · 대기열 뒤에 추가 · 담기 전 검토`:'프리셋을 선택하세요';
      if($('ovPresetLoad'))$('ovPresetLoad').textContent=p?`담기 · ${p.cards}개`:'대기열에 담기';
    }
    save();
  }
  const boot=setInterval(()=>{if(!window.overlayBooted)return;clearInterval(boot);restore();render();setInterval(render,1000);},200);
})();
