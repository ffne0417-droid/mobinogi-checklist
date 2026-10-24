"""Isolated storage validation; never imports real store or user data."""
import importlib.util
import sys
import threading
import types

SOURCE = str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app/workfavorites.py')
data = {}
writes = []
fake = types.SimpleNamespace(LOCK=threading.RLock(), _load_dict=lambda _: dict(data))
def save(path, value):
    assert path == 'work-favorites.json'
    data.clear()
    data.update(value)
    writes.append(dict(value))
fake.save = save
sys.modules['store'] = fake
spec = importlib.util.spec_from_file_location('workfavorites', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.get_favorites() == {}
assert module.set_favorite('craft:카레라이스#2', True) == {'craft:카레라이스#2': True}
module.set_favorite('alter:철괴', True)
module.set_favorite('gather:쌀', True)
assert list(module.get_favorites()) == ['craft:카레라이스#2', 'alter:철괴', 'gather:쌀']
assert 'alter:철괴' not in module.set_favorite('alter:철괴', False)
for key, enabled in [('', True), ('play:곡', True), ('craft:', True), ('craft:\nfoo', True), (1, True), ('craft:a', 1), ('craft:'+'a'*1001, True)]:
    try:
        module.set_favorite(key, enabled)
        raise AssertionError('invalid favorite accepted')
    except ValueError:
        pass
data.clear();data.update({'craft:'+str(i): True for i in range(5001)})
data['gather:bad-value'] = 1
assert len(module.get_favorites()) == 5000
try:
    module.set_favorite('gather:new', True)
    raise AssertionError('limit not enforced')
except ValueError:
    pass
module.set_favorite('craft:0', False)
assert len(module.set_favorite('gather:new', True)) == 5000
assert 'gather:new' in data
print('PASS task favorites isolated save/remove/order/type/prefix/control-char/limit validation; no real data writes')
