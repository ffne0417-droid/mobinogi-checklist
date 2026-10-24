"""Request elevation for this application's embedded entry point only."""
import ctypes
import os
import subprocess
import sys


def ensure_admin():
    if os.name != 'nt':
        return
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    if shell.IsUserAnAdmin():
        return
    shell.ShellExecuteW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                   ctypes.c_wchar_p, ctypes.c_wchar_p,
                                   ctypes.c_wchar_p, ctypes.c_int]
    shell.ShellExecuteW.restype = ctypes.c_void_p
    script = os.path.abspath(sys.argv[0])
    args = subprocess.list2cmdline([script, *sys.argv[1:]])
    result = shell.ShellExecuteW(None, 'runas', sys.executable, args,
                                os.path.dirname(os.path.dirname(script)), 0)
    # Cancelled UAC must not silently start a non-admin overlay.
    if not result or result <= 32:
        ctypes.windll.user32.MessageBoxW(None,
            '게임 클릭 감지를 위해 관리자 권한이 필요합니다. 다시 실행하고 권한 요청을 승인해 주세요.',
            '모비웍스', 0x30)
        raise SystemExit(1)
    raise SystemExit(0)
