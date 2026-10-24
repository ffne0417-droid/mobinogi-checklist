"""Persistent result history + conservative retry. All disk and game IO mocked."""
import sys, copy
from unittest.mock import patch
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
import workqueue as w
disk = {}
def load(name, default): return copy.deepcopy(disk.get(name, default))
def save(name, value): disk[name] = copy.deepcopy(value)
def cli(*args, **kwargs): raise AssertionError('No real or simulated game command should be issued')
with patch.object(w.store, 'load', side_effect=load), patch.object(w.store, 'save', side_effect=save):
    q = w.Queue(cli, say=lambda *a: None)
    safe = {'id':'safe','name':'철괴','type':'alter','status':'error','error':'material_shortage',
            'count':10,'collect':'none','progress':{'done':3,'got':0,'passes':3},'log':[]}
    uncertain = dict(safe, id='unknown', error='timeout', progress={'done':2})
    q.items = [safe, uncertain]
    q._event('error', 'safe', '재료 부족')
    q._event('done', 'unknown', 'test snapshot')
    assert q.history()['items'][0]['id'] == 'unknown'
    q.history()['items'][0]['progress']['done'] = 999
    assert q.history()['items'][0]['progress']['done'] == 2
    q.running = True
    assert q.retry_failed()['error'] == 'running'
    q.running = False
    q.state = lambda: {'mock':True}
    result = q.retry_failed()
    assert result['retried'] == ['safe'] and result['skipped'][0]['id'] == 'unknown', result
    assert safe['status'] == 'pending' and safe['progress']['done'] == 3
    assert uncertain['status'] == 'error'
    assert not q.retry_failed([])['retried']
    assert q.retry_failed('safe')['error'] == 'bad_ids'
    limited = dict(safe,id='limit',status='error',error='blocked',message='kind=continuous_run_limit',progress={'done':9},log=[])
    q.items.append(limited)
    assert not q.resume_after_connector_confirm(False)['ok']
    assert limited['status']=='error'
    result=q.resume_after_connector_confirm(True)
    assert result['retried']==['limit'] and limited['progress']['done']==9
    assert uncertain['status']=='error', 'Other blocked/uncertain work must not be recovered'
    safe.update(status='running')
    q._alter_full_stop(safe, '', 0)
    assert safe['status'] == 'waiting' and safe['progress']['done'] == 3
    assert safe['recovery']['kind'] == 'close_modal_then_resume'
    assert q._stop.is_set()
    assert q.history(1)['items'][0]['recovery']['automatic'] is False
    q.items = []
    q._save()
    restored = w.Queue(cli, say=lambda *a: None)
    assert len(restored.history()['items']) == 3
    for i in range(510): restored._event('stop', None, str(i))
    assert len(restored.history(999)['items']) == 500
    assert restored.history(1)['items'][0]['msg'] == '509'
print('PASS history persistence/clear/restart/bounds/copy; safe retry preserves progress; uncertain failures skipped; no commands')
