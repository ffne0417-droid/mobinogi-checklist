/* Lazy persistent execution history. This module never starts game work. */
(function () {
  'use strict';
  if (window.MWQueueHistory) return;
  let box, list, notice, retry, usage, pending = false, lastLoad = 0;
  function renderUsage(){
    if(!usage)return;
    const q=window.MW?.boardState?.()||{},u=q.connectorUsage;
    const fmt=v=>{const n=Math.floor(Math.max(0,Number(v)||0));return `${Math.floor(n/60)}분 ${n%60}초`;};
    usage.textContent=!u?'명령 시간 관찰 준비 중 · 게임 타이머 아님':
      `${u.sinceConfirmationSeconds==null?'측정 시작 후':'직접 확인 후'} 명령 누적 ${fmt(u.sinceConfirmationSeconds??u.completedSeconds)}`+
      (u.inFlightCount?` · 현재 호출 대기 약 ${fmt(u.inFlightSeconds)} (별도)`:'')+
      (u.awaitingConfirmation?' · 게임 직접 확인 필요':'')+
      (u.incomplete||u.overlapObserved?' · 누락/중복 가능':'')+' · 게임 타이머 아님';
  }
  function visible() { return box && box.getClientRects().length && !document.hidden; }
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  async function load(force) {
    if (!visible() || !box.open || pending || (!force && Date.now() - lastLoad < 10000)) return;
    pending = true;
    try {
      const result = await MW.api('/api/queue/history');
      if (!result || !result.ok) throw new Error('기록을 불러오지 못했습니다.');
      list.replaceChildren();
      const rows = Array.isArray(result.items) ? result.items.slice(0, 100) : [];
      if (!rows.length) list.append(element('p', '아직 실행 결과가 없습니다.'));
      for (const row of rows) {
        const item = element('li', undefined, 'qh-result qh-' + (row.kind === 'error' ? 'error' : row.kind === 'done' ? 'done' : 'stop'));
        const stamp = new Date(Number(row.t) * 1000);
        item.append(element('small', Number.isNaN(stamp.getTime()) ? '' : stamp.toLocaleString('ko-KR')));
        item.append(element('div', row.msg || row.name || '실행 결과'));
        if (row.recovery && row.recovery.message) item.append(element('p', row.recovery.message, 'qh-guidance'));
        list.append(item);
      }
      lastLoad = Date.now();
      notice.textContent = '';
    } catch (error) { notice.textContent = error.message || '기록을 불러오지 못했습니다.'; }
    finally { pending = false; }
  }
  function mount() {
    const parent = document.getElementById('tabQueue');
    if (!parent || box) return;
    box = element('details', undefined, 'qh-panel');
    box.id = 'queueHistory';
    box.append(element('summary', '실행 결과 기록 · 실패 복구'));
    usage=element('p', '', 'qh-guidance');usage.setAttribute('role','status');box.append(usage);renderUsage();
    const controls = element('div', undefined, 'qh-controls');
    const refresh = element('button', '기록 새로고침');
    refresh.type = 'button'; refresh.onclick = () => load(true);
    retry = element('button', '실패 항목 대기로'); retry.type = 'button';
    retry.onclick = async () => {
      retry.disabled = true;
      try {
        const result = await MW.api('/api/queue', { op: 'retry_failed' });
        if (!result || !result.ok) throw new Error(result && result.message || '대기로 옮기지 못했습니다. 실행 중이면 먼저 정지해 주세요.');
        if (typeof MW.refreshQueue === 'function') await MW.refreshQueue();
        else if (typeof MW.loadQueue === 'function') await MW.loadQueue();
        await load(true);
        notice.textContent = (result.retried || []).length + '개를 대기로 옮겼습니다. 자동으로 시작하지 않습니다.' +
          ((result.skipped || []).length ? ' ' + result.skipped.length + '개는 게임 상태 확인이 필요해 제외했습니다. 개별 항목에서 확인해 주세요.' : '');
      } catch (error) { notice.textContent = error.message; }
      finally { retry.disabled = false; }
    };
    const connector = element('button', '게임 확인 후 작업 복구'); connector.type = 'button';
    connector.onclick = async () => {
      if (!window.confirm('게임의 AI 커넥터 1시간 확인창에서 확인 버튼을 직접 눌렀나요?\n확인한 경우에만 제한으로 멈춘 작업을 대기로 옮깁니다. 자동으로 시작하지 않습니다.')) return;
      connector.disabled = true;
      try {
        const result = await MW.api('/api/queue', {op:'connector_confirmed',confirmed:true});
        if (!result?.ok) throw new Error(result?.message || '작업을 복구하지 못했습니다.');
        if (typeof MW.refreshQueue === 'function') await MW.refreshQueue();
        else if (typeof MW.loadQueue === 'function') await MW.loadQueue();
        notice.textContent = `${(result.retried || []).length}개 작업을 진행량 그대로 대기로 옮겼습니다. 시작을 누르면 이어갑니다.`;
      } catch (error) { notice.textContent = error.message; }
      finally { connector.disabled = false; }
    };
    const experiment = element('button', '자동 휴식 실험 켜기/끄기'); experiment.type = 'button';
    experiment.onclick = async () => {
      experiment.disabled = true;
      try {
        const current = await MW.api('/api/settings');
        if (!current?.ok) throw new Error('설정을 읽지 못했습니다.');
        const enabled = !current.settings.connector_break_experiment;
        const interval=Number(current.settings.connector_break_interval_min)||45,rest=Number(current.settings.connector_break_rest_sec)||120;
        if (!window.confirm(enabled ? `${interval}분마다 작업 경계에서 ${rest/60}분 전체 통신 휴식 실험을 켤까요?\n2분·5분 시험 모두 제한이 재발했습니다. 휴식이 게임 시간을 초기화한다는 근거는 없으며, 제한 발생 시 직접 확인이 필요합니다.` : '자동 휴식 실험을 끌까요? 이미 시작된 휴식은 정지를 눌러 취소할 수 있습니다.')) return;
        const result = await MW.api('/api/settings',{settings:{connector_break_experiment:enabled}});
        if (!result?.ok) throw new Error('설정을 저장하지 못했습니다.');
        notice.textContent = enabled ? `전체 통신 휴식 실험 켜짐 · ${interval}분 / ${rest/60}분 · 제한 초기화 효과 없음/미확인. 설정 시간은 유지합니다.` : '자동 휴식 실험 꺼짐';
      } catch (error) {notice.textContent = error.message;}
      finally {experiment.disabled = false;}
    };
    controls.append(refresh, retry, connector, experiment);
    notice = element('p', '', 'qh-notice'); notice.setAttribute('role', 'status');
    list = element('ol', undefined, 'qh-list');
    box.append(controls, element('p', '최근 100건 표시 · 보드를 비워도 기록은 유지됩니다. 불확실한 실행은 자동 재시도하지 않습니다.', 'qh-guidance'), notice, list);
    box.addEventListener('toggle', () => { if (box.open) load(true); });
    parent.append(box);
  }
  window.MWQueueHistory = { refresh: () => load(true) };
  mount();
  if (!box) document.addEventListener('DOMContentLoaded', mount, { once: true });
  // No history requests while collapsed, hidden, or outside management.
  setInterval(() => { mount(); renderUsage(); load(false); }, 1000);
}());
