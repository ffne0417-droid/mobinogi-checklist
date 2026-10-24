import sys, threading
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
import presets, workqueue

food={'id':'craft:food','kind':'craft','name':'음식','per':1,'known':{'고기':10,'양파':2,'소스':1}}
sauce={'id':'alter:sauce','kind':'alter','name':'소스','per':3,'known':{'허브':2}}
snap={'craft':[food],'alter':[sauce],'stock':{'고기':5},'storage':{'고기':50},'fetchedAt':{'items':1}}
owned={'고기':55}
def source(n):
    return {'양파':('gather',None),'허브':('gather',None),'소스':('alter','alter:sauce')}.get(n,(None,None))
card={'t':'c','n':'음식','r':'craft:food','q':24,'z':True}
p=presets.prepare_plan(card,snap,owned,source,True,True)
assert p['count']==5 and p['requested']==24,p
assert [(i['type'],i['name']) for i in p['items']]==[('gather','양파'),('gather','허브'),('alter','소스'),('craft','음식')],p
assert p['items'][2]['collect']=='wait' and p['items'][-1]['count']==5
assert p['items'][0]['target']==48 and p['items'][1]['target']==16,p
assert p['items'][2]['count']==8 and p['owned']['소스']==19,p
assert p['owned']['고기']==5 and owned=={'고기':55}
assert presets.prepare_plan(card,snap,owned,source,False,True)['count']==0
try: presets.prepare_plan(card,snap,owned,source,True,False)
except ValueError: pass
else: raise AssertionError('unobtainable meat accepted')
full={**owned,'고기':240}
assert presets.prepare_plan(card,snap,full,source,True,True)['count']==24
assert presets.prepare_plan(card,snap,{**full,'음식':24},source,True,True)['items']==[]
# Shared ingredient consumption across target and subrecipe; no double spending.
shared={**snap,'craft':[{**food,'known':{'허브':5,'소스':1}}]}
p=presets.prepare_plan(card,shared,{'허브':12},lambda n:source(n) if n!='허브' else (None,None),True,True)
assert p['count']==0 and p['items'][0]['count']==6 and p['owned']['허브']==0,p
# Cyclic routes terminate and refuse unsupported production.
cycle={**snap,'alter':[{**sauce,'known':{'소스':1}}]}
cyclic=presets.prepare_plan(card,cycle,full,source,True,True)
assert cyclic['count']==0 and cyclic['items'][0]['type']=='gather'
spec={'v':1,'n':'검수','i':[card],'autoPrepare':True,'allowPartial':True}
assert presets.decode(presets.encode(presets.validate(spec)))['allowPartial'] is True
q=workqueue.Queue.__new__(workqueue.Queue);q.running=False;q.lock=threading.RLock()
calls=[];q.add=lambda item,*a,**kw:(calls.append(item) or {'ok':True});q._save=lambda:None;q.state=lambda:{}
r=q.preset_apply({**spec,'i':[card,{**card,'n':'음식','z':False}]},snap,{},source_fn=source)
assert r['adjusted'][0]['count']==5,r
assert next(x for x in calls if x['type']=='craft')['count']==5
assert len([x for x in calls if x['type']=='craft'])==1,r
assert r['skipped'],r
assert q.preset_apply(spec,snap,{},source_fn=source)['ok']
calls.clear()
zero={**snap,'stock':{'고기':0},'storage':{},'fetchedAt':{'items':1}}
r=q.preset_apply(spec,zero,{},source_fn=source)
assert r['added']==3 and len(calls)==3 and all(x['name']!='음식' for x in calls),r
assert calls[0]['target']==48 and calls[2]['count']==8
print('PASS automatic gather/recursive craft/alter wait, partial cap by meat, shared stock, zero/satisfied, cycle refusal, flags roundtrip and queue integration; all queue writes mocked')
