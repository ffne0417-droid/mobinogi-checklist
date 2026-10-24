"""Read-only local log auditor. Does not import app modules or send game calls."""
import argparse, collections, json, re
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('logs',nargs='+',type=Path,help='Log files ordered oldest to newest')
parser.add_argument('--pid',type=int,help='Analyze only one known app process')
parser.add_argument('--start',help='First HH:MM:SS in selected process, optional')
parser.add_argument('--end',help='Last HH:MM:SS; earlier than start means next day')
args=parser.parse_args()
def seconds(value):
    h,m,s=map(int,value.split(':'))
    if not(0<=h<24 and 0<=m<60 and 0<=s<60):raise ValueError('Invalid clock time')
    return h*3600+m*60+s
start=seconds(args.start) if args.start else None
end=seconds(args.end) if args.end else None
if start is not None and end is not None and end<start:end+=86400
states={}
for path in args.logs:
    for line in path.read_text(encoding='utf-8-sig',errors='replace').splitlines():
        match=re.match(r'^\[(\d\d:\d\d:\d\d) (\d+)\] (.*)',line)
        if not match:continue
        clock,pid,message=match.groups();pid=int(pid)
        if args.pid is not None and pid!=args.pid:continue
        state=states.setdefault(pid,{'day':0,'last':None,'pending':{},'commands':collections.defaultdict(lambda:{'calls':0,'seconds':0.0}),'quiet':None,'windows':[],'limits':[],'unmatched':0})
        now=seconds(clock)
        if state['last'] is not None and now<state['last']-43200:state['day']+=1
        state['last']=now;now+=state['day']*86400
        inside=(start is None or now>=start) and (end is None or now<=end)
        admitted=re.search(r'\[connector-traffic\] admitted id=(\d+) command=(\w+)',message)
        if admitted:state['pending'][admitted[1]]=(admitted[2],now)
        finished=re.search(r'\[connector-traffic\] finished id=(\d+).*seconds=([\d.]+)',message)
        if finished:
            command,began=state['pending'].pop(finished[1],('unmatched',now))
            if inside:
                value=state['commands'][command];value['calls']+=1;value['seconds']+=float(finished[2])
                if command=='unmatched':state['unmatched']+=1
        if '[connector-traffic] quiet-ready' in message:
            state['quiet']={'start':now,'admitted':0,'finished':0,'suppressed':0}
        elif '[connector-traffic] quiet-ended' in message:
            window=state['quiet']
            if window:
                window={**window,'end':now,'duration':now-window['start']}
                if inside and(start is None or window['start']>=start):state['windows'].append(window)
            state['quiet']=None
        elif state['quiet']:
            for event in ('admitted','finished','suppressed'):
                if f'[connector-traffic] {event}' in message:state['quiet'][event]+=1
        if inside and 'kind=continuous_run_limit' in message:state['limits'].append(now)
output=[]
for pid,state in states.items():
    commands={key:{**value,'seconds':round(value['seconds'],3)}for key,value in state['commands'].items()}
    action=sum(value['seconds']for key,value in commands.items()if key in {'execute_gathering','execute_crafting','execute_altering','complete_altering_work'})
    output.append({'pid':pid,'commands':commands,'observedActionSeconds':round(action,3),'quietWindows':state['windows'],'limitEvents':state['limits'],'unmatchedFinished':state['unmatched'],'pendingIds':len(state['pending']),'unfinishedQuiet':bool(state['quiet'])})
print(json.dumps({'scope':'this app log only; elapsed calls are not game timer; clock dates require caller validation','results':output},ensure_ascii=False,indent=2))
