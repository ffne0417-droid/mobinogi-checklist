import ast,pathlib,threading,types,sys,copy
root=pathlib.Path(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
sys.path.insert(0,str(root/'folio'))
tree=ast.parse((root/'folio/engine.py').read_text(encoding='utf-8'))
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='auto_sync')
cache={'scores':[{'DisplayTitle':'old','Location':'inventory'}],'instruments':[{'Name':'old'}]};writes=[];busy=[False];music=[False];failure=[False];clock=[1000]
def cli(command,*a,**k):return types.SimpleNamespace(ok=not(failure[0] and command=='get_music_scores'),body=[{'DisplayTitle':'new','Location':'inventory'}] if command=='get_music_scores' else [{'Name':'new'}])
def save(kind,items):writes.append(kind);cache[kind]=items
ns={'_AUTO_REFRESH_LOCK':threading.Lock(),'_AUTO_REFRESH_AT':0,'time':types.SimpleNamespace(time=lambda:clock[0]),'store':types.SimpleNamespace(get_settings=lambda:{'folio_auto_sync':True},folio_cache=lambda k:{'items':cache[k]},set_folio_cache=save),'host_queue_busy':lambda:busy[0],'work_now':lambda:{'busy':music[0]},'_cli_lock':threading.Lock(),'_cli':cli}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'qa','exec'),ns)
busy[0]=True;assert ns['auto_sync']()['deferred'] and not writes;busy[0]=False
music[0]=True;assert ns['auto_sync']()['deferred'] and not writes;music[0]=False
failure[0]=True;old=copy.deepcopy(cache);assert not ns['auto_sync']()['ok'];assert cache==old and not writes
clock[0]+=61;failure[0]=False;assert ns['auto_sync']()['changed'] and writes==['instruments','scores']
assert ns['auto_sync']()['deferred']
clock[0]+=61
ns['_cli']=lambda *a,**k:types.SimpleNamespace(ok=True,body=[])
old=copy.deepcopy(cache);writes.clear()
assert not ns['auto_sync']()['ok'] and cache==old and not writes
print('PASS idle-only refresh, queue/music busy guard, both caches retained on read failure, changed detection, rate limit; CLI mocked')
