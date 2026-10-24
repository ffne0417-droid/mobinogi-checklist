"""모비웍스 전용 Chromium 프로필의 창만 찾아 정상적으로 닫는다."""
import ctypes
import os
import re
import time
from ctypes import wintypes as w


def _command_line(pid):
    k = ctypes.WinDLL("kernel32")
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return ""
    try:
        nt = ctypes.WinDLL("ntdll")
        query = nt.NtQueryInformationProcess
        query.argtypes = [w.HANDLE, w.ULONG, ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)]
        query.restype = ctypes.c_long
        needed = w.ULONG()
        query(h, 60, None, 0, ctypes.byref(needed))
        if not 0 < needed.value < 1_000_000:
            return ""
        buf = ctypes.create_string_buffer(needed.value)
        if query(h, 60, buf, len(buf), ctypes.byref(needed)) < 0:
            return ""
        class UnicodeString(ctypes.Structure):
            _fields_ = [("length", w.USHORT), ("maximum", w.USHORT), ("buffer", ctypes.c_void_p)]
        text = UnicodeString.from_buffer(buf)
        start = ctypes.addressof(buf)
        if not text.buffer or not start <= text.buffer <= start + len(buf) - text.length:
            return ""
        return ctypes.wstring_at(text.buffer, text.length // 2)
    finally:
        k.CloseHandle(h)


def profile_matches(command, profile):
    match = re.search(r'--user-data-dir=(?:"([^"]+)"|(\S+))', command)
    if not match or "--app=http://127.0.0.1:" not in command:
        return False
    actual = match.group(1) or match.group(2)
    return os.path.normcase(os.path.abspath(actual)) == os.path.normcase(os.path.abspath(profile))


def windows(profile):
    if os.name != "nt":
        return []
    u = ctypes.WinDLL("user32")
    u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
    u.IsWindowVisible.argtypes = [w.HWND]
    found, owners = [], {}

    @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def visit(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        cls = ctypes.create_unicode_buffer(120)
        u.GetClassNameW(hwnd, cls, len(cls))
        if cls.value != "Chrome_WidgetWin_1":
            return True
        pid = w.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in owners:
            try:
                owners[pid.value] = profile_matches(_command_line(pid.value), profile)
            except OSError:
                owners[pid.value] = False
        if owners[pid.value]:
            found.append(int(hwnd))
        return True

    u.EnumWindows(visit, 0)
    return found


def close_all(profile, timeout=3.0):
    handles = windows(profile)
    if not handles:
        return 0
    u = ctypes.WinDLL("user32")
    u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    u.IsWindow.argtypes = [w.HWND]
    for hwnd in handles:
        u.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE: 창을 정상 종료한다.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and any(u.IsWindow(h) for h in handles):
        time.sleep(0.1)
    return len(handles)
