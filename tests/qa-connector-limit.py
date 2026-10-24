import ast,pathlib,threading,types
p=pathlib.Path(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app/workqueue.py'))
t=ast.parse(p.read_text(encoding='utf-8'))
f=next(n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name=='_exec_failed')
ns={'BLOCKED_KIND_KO':{'continuous_run_limit':'confirm manually'},'store':types.SimpleNamespace(get_settings=lambda:{})}
exec(compile(ast.Module(body=[f],type_ignores=[]),'qa','exec'),ns)
it={'progress':{'done':9},'status':'running'}
def fail(it,error,message):it.update(status='error',error=error,message=message)
q=types.SimpleNamespace(_stop=threading.Event(),_fail=fail,_log=lambda *a:None,stop_reason=None)
ns['_exec_failed'](q,it,types.SimpleNamespace(error='blocked'),{'kind':'continuous_run_limit'})
assert q._stop.is_set() and q.stop_reason=='continuous_run_limit'
assert it['progress']['done']==9 and it['recovery']['automatic'] is False
print('PASS connector limit stops follow-up commands, preserves progress, requires manual confirmation')
