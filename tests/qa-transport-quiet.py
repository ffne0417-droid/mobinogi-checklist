"""No real CLI: verify global admission/draining/cancellation and metadata logging."""
import pathlib, sys, threading, time
from unittest.mock import patch

root=pathlib.Path(str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app'))
sys.path.insert(0,str(root))
import transportquiet as gate
import cli_transport as cli

events=[]
gate.configure(events.append)
stop=threading.Event()
entered=threading.Event()
release=threading.Event()
ready=threading.Event()
def active():
    with gate.admission('get_activity') as (allowed,_):
        assert allowed
        entered.set()
        release.wait(2)
def rest():
    assert gate.begin(stop)
    ready.set()
t=threading.Thread(target=active);t.start();assert entered.wait(1)
r=threading.Thread(target=rest);r.start()
time.sleep(.05);assert not ready.is_set(), 'must drain existing request'
with patch.object(cli,'_call_unpaused') as raw:
    for command in ('status','capabilities','get_activity','get_items','execute_gathering','stop_action'):
        result=cli.call(command,{'private':'NEVER_LOG_THIS'})
        assert result.error=='connector_rest'
    raw.assert_not_called()
release.set();t.join(1);r.join(1);assert ready.is_set()
gate.end()
with patch.object(cli,'_call_unpaused',return_value=cli.CliResult('get_activity',0,ok=True)) as raw:
    assert cli.call('get_activity').ok
    assert raw.call_count==1, 'no replay of suppressed commands'
stop.set();assert not gate.begin(stop);gate.end()
assert not any('NEVER_LOG_THIS' in e for e in events)
for path in (root/'transportquiet.py',root/'cli_transport.py',root/'workqueue.py',root/'server.py'):
    compile(path.read_text(encoding='utf-8'),str(path),'exec')
print('PASS: drain, block all CLI entry calls, cancellation, resume without replay, metadata-only audit, syntax')
