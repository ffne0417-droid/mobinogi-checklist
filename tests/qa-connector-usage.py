"""Usage observation and explicit recovery tests. All game/disk IO mocked."""
import copy, math, pathlib, sys, types
from unittest.mock import patch
root=pathlib.Path(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
sys.path.insert(0,str(root))
from connectorusage import UsageObserver
clock=[0.0];wall=[1000.0];saved={}
def persist(data):saved.clear();saved.update(copy.deepcopy(data))
u=UsageObserver(lambda:clock[0],lambda:wall[0]);u.configure({},persist)
assert u.begin('get_activity') is None
t=u.begin('execute_gathering');clock[0]=65
assert u.snapshot()['completedSeconds']==0 and u.snapshot()['inFlightSeconds']==65
u.finish(t,types.SimpleNamespace(elapsed=64.2,error=None,body={}))
assert u.snapshot()['completedSeconds']==64.2 and u.snapshot()['calls']==1
assert u.snapshot()['sinceConfirmationSeconds'] is None
clock[0]+=300
assert u.snapshot()['completedSeconds']==64.2, 'idle/rest cannot add action time'
t=u.begin('execute_crafting');clock[0]+=3600
u.finish(t,types.SimpleNamespace(elapsed=3600,error='blocked',body={'kind':'continuous_run_limit'}))
assert u.snapshot()['awaitingConfirmation']
before=u.snapshot()['completedSeconds'];wall[0]=2000
assert u.acknowledge();assert u.snapshot()['sinceConfirmationSeconds']==0
assert u.snapshot()['completedSeconds']==before and not u.snapshot()['awaitingConfirmation']
t=u.begin('execute_altering');assert not u.acknowledge()
u.finish(t,types.SimpleNamespace(elapsed=1.3,error=None,body={}))
assert u.snapshot()['sinceConfirmationSeconds']==1.3
restored=UsageObserver(lambda:clock[0],lambda:wall[0]);restored.configure(saved)
assert restored.snapshot()['completedSeconds']==u.snapshot()['completedSeconds']
assert restored.snapshot()['processSeconds']==0
assert not restored.snapshot()['gameTimerVerified']
t=u.begin('execute_gathering');crashed=copy.deepcopy(saved)
incomplete=UsageObserver();incomplete.configure(crashed)
assert incomplete.snapshot()['incomplete'], 'in-flight loss must not be presented as complete'
u.finish(t,types.SimpleNamespace(elapsed=float('nan'),error=None,body={}))
assert u.snapshot()['incomplete']
assert math.isfinite(u.snapshot()['completedSeconds'])
bad=UsageObserver();bad.configure({'version':1,'completedSeconds':float('inf'),'byCommand':{'bad':'secret'}})
assert bad.snapshot()['completedSeconds']==0 and bad.snapshot()['byCommand']=={}
disk_fail=UsageObserver();disk_fail.configure({},lambda _:(_ for _ in ()).throw(OSError('test')))
t=disk_fail.begin('execute_altering');disk_fail.finish(t,types.SimpleNamespace(elapsed=2,error=None,body={}))
assert disk_fail.snapshot()['incomplete'] and disk_fail.snapshot()['completedSeconds']==2

import workqueue as w
from connectorusage import observer
disk={}
def load(name,default):return copy.deepcopy(disk.get(name,default))
def save(name,data):disk[name]=copy.deepcopy(data)
def forbidden(*args,**kwargs):raise AssertionError('No game calls allowed')
observer.configure({})
with patch.object(w.store,'load',side_effect=load),patch.object(w.store,'save',side_effect=save):
 q=w.Queue(forbidden,probe_fn=forbidden,say=lambda *a:None)
 limited={'id':'limited','type':'gather','name':'test','status':'error','error':'blocked',
          'message':'kind=continuous_run_limit','target':100,'progress':{'done':37,'have':37,'bag0':0,'passes':1},
          'recovery':{'kind':'confirm_then_resume','automatic':False},'log':[]}
 shortage=dict(limited,id='shortage',error='not_enough_ingredient',recovery={},message='missing')
 q.items=[limited,shortage];q._save()
 new=w.Queue(forbidden,say=lambda *a:None)
 assert all(c['status']=='error' for c in new.items), 'restart is not retry authorization'
 q.last_error={'id':'limited','error':'blocked'};q.stop_reason='continuous_run_limit'
 t=observer.begin('execute_gathering');observer.finish(t,types.SimpleNamespace(elapsed=30,error='blocked',body={'kind':'continuous_run_limit'}))
 assert q.start({})['error']=='connector_confirmation_required', 'must reject before probe/game calls'
 assert not q.resume_after_connector_confirm(False)['ok']
 before_progress=copy.deepcopy(limited['progress'])
 result=q.resume_after_connector_confirm(True)
 assert result['retried']==['limited'] and limited['progress']==before_progress
 assert limited['status']=='pending' and shortage['status']=='error'
 assert q.last_error is None and q.stop_reason is None
 assert q._connector_break.anchor is not None
 assert not observer.snapshot()['awaitingConfirmation'] and observer.snapshot()['completedSeconds']==30
 assert not q.running, 'recovery must never start work automatically'
 assert not q.resume_after_connector_confirm(True)['ok'], 'no arbitrary reset without known limit'
observer.configure({})
for name in ('connectorusage.py','cli_transport.py','workqueue.py','server.py','connectorbreak.py'):
 compile((root/name).read_text(encoding='utf-8'),name,'exec')
print('PASS action-only timing, idle exclusion, persistent totals, incomplete/invalid data, explicit recovery, restart error preservation, no auto-start or game calls')
