import sys,threading,types,ast,pathlib
root=pathlib.Path(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
sys.path.insert(0,str(root))
from connectorbreak import BoundaryBreak
import transportquiet
clock=[0.0]; timer=BoundaryBreak(lambda:clock[0])
assert not timer.due(False,2700)
assert not timer.due(True,2700)
clock[0]=2699;assert not timer.due(True,2700)
clock[0]=2700;assert timer.due(True,2700)
began=timer.begin();assert timer.snapshot()['paused']
clock[0]+=120;timer.finish(began)
assert timer.count==1 and timer.last_rest==120 and not timer.due(True,2700)
clock[0]+=2700;assert timer.due(True,2700)
began=timer.begin();clock[0]+=2;timer.finish(began,True)
assert timer.count==1 and not timer.paused
tree=ast.parse((root/'workqueue.py').read_text(encoding='utf-8'))
fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_connector_checkpoint')
cfg={'connector_break_experiment':True,'connector_break_interval_min':45,'connector_break_rest_sec':120}
ns={'store':types.SimpleNamespace(get_settings=lambda:cfg), 'transportquiet':transportquiet}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'qa','exec'),ns)
logs=[];waits=[]
stop=types.SimpleNamespace(is_set=lambda:False,wait=lambda n:waits.append(n) or False)
q=types.SimpleNamespace(_stop=stop,_executing=False,_orphan_alive=lambda:False,_connector_break_lock=threading.Lock(),_connector_break=timer,_log=lambda *a:logs.append(a))
q._executing=True;ns['_connector_checkpoint'](q,{});assert not waits
q._executing=False;q._orphan_alive=lambda:True;ns['_connector_checkpoint'](q,{});assert not waits
q._orphan_alive=lambda:False;ns['_connector_checkpoint'](q,{})
assert waits==[120] and timer.count==2 and len(logs)==2
assert timer.snapshot()['verifiedReset'] is False
print('PASS boundary schedule, no mid-action/orphan interruption, stop cancellation, no game commands, honest unverified status')
