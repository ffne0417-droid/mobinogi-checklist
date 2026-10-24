"""Named, bounded overlay layout snapshots (no game commands)."""
import copy
import store

FILE = 'overlay-layouts.json'
KEYS = ('overlay_skin','overlay_orientation','overlay_opacity','overlay_lock','overlay_follow_game','overlay_off_x','overlay_off_y','overlay_x','overlay_y')

def read():
    data = store.load(FILE, {})
    return data if isinstance(data, dict) else {}

def save(name, settings, sizes):
    if not isinstance(name,str) or not name.strip() or len(name.strip())>40:
        raise ValueError('배치 이름을 1~40자로 입력해주세요.')
    with store.LOCK:
        data=read();name=name.strip()
        if name not in data and len(data)>=20:
            raise ValueError('배치는 20개까지 저장할 수 있습니다.')
        clean_sizes={}
        for key,pair in (sizes or {}).items():
            if key in ('work','music','library') and isinstance(pair,(list,tuple)) and len(pair)==2:
                clean_sizes[key]=[max(320,min(5000,int(pair[0]))),max(240,min(5000,int(pair[1])))]
        data[name]={'settings':{k:copy.deepcopy(settings[k]) for k in KEYS if k in settings},'sizes':clean_sizes}
        store.save(FILE,data)
        return data

def get(name):
    with store.LOCK:
        value=read().get(name)
        if not isinstance(value,dict):raise ValueError('저장된 배치를 찾지 못했습니다.')
        return copy.deepcopy(value)

def delete(name):
    with store.LOCK:
        data=read()
        if name not in data:raise ValueError('저장된 배치를 찾지 못했습니다.')
        data.pop(name);store.save(FILE,data);return data
