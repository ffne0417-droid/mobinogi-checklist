"""Per-game-instance launcher. No game commands, injection, or repeated relaunches."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import json
import os
import socket
import struct
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
GAME_EXE = 'mabinogimobile.exe'  # Same exact process as overlay.py / folio engine.

def processes():
    """PID -> (executable basename, creation FILETIME), no command lines."""
    class Entry(ctypes.Structure):
        _fields_ = [('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),
                    ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),
                    ('cntThreads',wintypes.DWORD),('th32ParentProcessID',wintypes.DWORD),
                    ('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)]*4
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    result = {}
    try:
        item = Entry(); item.dwSize = ctypes.sizeof(item)
        kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        more = kernel.Process32FirstW(snapshot, ctypes.byref(item))
        while more:
            created = 0
            if item.szExeFile.lower() == GAME_EXE:
                handle = kernel.OpenProcess(0x1000, False, item.th32ProcessID)
                if handle:
                    values = [wintypes.FILETIME() for _ in range(4)]
                    if kernel.GetProcessTimes(handle, *[ctypes.byref(v) for v in values]):
                        created = values[0].dwLowDateTime | values[0].dwHighDateTime << 32
                    kernel.CloseHandle(handle)
            result[item.th32ProcessID] = (item.szExeFile.lower(), created)
            more = kernel.Process32NextW(snapshot, ctypes.byref(item))
    finally: kernel.CloseHandle(snapshot)
    return result

def port_owned_by(port, pid):
    """Require local listening port owner PID to match the lite.json PID."""
    api = ctypes.WinDLL('iphlpapi').GetExtendedTcpTable
    api.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                    wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
    size = wintypes.DWORD()
    api(None, ctypes.byref(size), False, 2, 3, 0)  # IPv4, OWNER_PID_LISTENER
    buffer = ctypes.create_string_buffer(size.value)
    if api(buffer, ctypes.byref(size), False, 2, 3, 0): return False
    count = struct.unpack_from('<I', buffer, 0)[0]
    for i in range(count):
        state, addr, local_port, _, _, owner = struct.unpack_from('<6I', buffer, 4 + 24*i)
        if state == 2 and socket.ntohs(local_port & 0xffff) == port and owner == pid: return True
    return False

def app_healthy(current):
    try:
        import datadir
        fixed = datadir.configured_base(str(ROOT/'app'))
        path = (Path(fixed) if fixed else Path(os.environ['LOCALAPPDATA'])/'MobiWorks')/'lite.json'
        info = json.loads(path.read_text(encoding='utf-8'))
        pid, port = int(info['pid']), int(info['port'])
        if current.get(pid, ('', 0))[0] not in ('pythonw.exe', 'python.exe') or not 1 <= port <= 65535:
            return False
        if not port_owned_by(port, pid): return False
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
            return json.load(response).get('app') == 'mobiworks'
    except (OSError, ValueError, KeyError, TypeError): return False

class GameLaunchState:
    def __init__(self): self.seen = set()
    def update(self, current, healthy, launch):
        active = {(pid, created) for pid, (name, created) in current.items() if name == GAME_EXE}
        fresh = active - self.seen
        self.seen = active
        if fresh and not healthy:
            launch()  # Mark seen first, including failed launches: no endless prompt/relaunch.
            return True
        return False

def launch_app():
    subprocess.Popen([str(ROOT/'python'/'pythonw.exe'), str(ROOT/'app'/'server.py')],
                     cwd=str(ROOT), creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)

def main():
    if os.name != 'nt': return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    mutex = kernel.CreateMutexW(None, False, 'Local\\MobiWorksGameAutostart')
    if not mutex: raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183: return
    state = GameLaunchState()
    try:
        while True:
            try:
                current = processes()
                state.update(current, app_healthy(current), launch_app)
            except (OSError, ValueError): pass
            time.sleep(3)
    finally:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(mutex)

if __name__ == '__main__': main()
