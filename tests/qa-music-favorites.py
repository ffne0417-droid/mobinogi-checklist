import ast,pathlib,threading,copy
p=pathlib.Path(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app/store.py'))
t=ast.parse(p.read_text(encoding='utf-8'));db={}
ns={'LOCK':threading.RLock(),'_load_dict':lambda f:copy.deepcopy(db.get(f,{})),'save':lambda f,v:db.update({f:copy.deepcopy(v)})}
nodes=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in ('get_music_favorites','set_music_favorite')]
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'favorite-store','exec'),ns)
assert ns['set_music_favorite']('동명 악보#1',True)=={'동명 악보#1':True}
assert ns['get_music_favorites']()=={'동명 악보#1':True}
assert ns['set_music_favorite']('동명 악보#2',True)=={'동명 악보#1':True,'동명 악보#2':True}
assert ns['set_music_favorite']('동명 악보#1',False)=={'동명 악보#2':True}
try:ns['set_music_favorite']('',True);raise AssertionError('invalid input accepted')
except ValueError:pass
assert 'folio/favorites.json' in p.read_text(encoding='utf-8')
print('PASS favorite save/load/remove and duplicate-score key isolation; memory store only')
