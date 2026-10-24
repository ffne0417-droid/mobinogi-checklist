"""Prevent our overlay UI thread from taking activation or keyboard focus.

This is a thread-local hook in this process, never a hook in the game.
WS_EX_NOACTIVATE alone does not veto explicit activation by Tk/WebView.
"""
import ctypes
import os
from ctypes import wintypes as w


class ActivationGuard:
    def __init__(self, blocked, log=lambda message: None):
        self.u = ctypes.WinDLL('user32', use_last_error=True)
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.blocked, self.log = blocked, log
        self.count = 0
        self.hook = None
        self.u.GetAncestor.argtypes = [w.HWND, w.UINT]
        self.u.GetAncestor.restype = w.HWND
        self.u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
        self.u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self.u.CallNextHookEx.argtypes = [w.HANDLE, ctypes.c_int, w.WPARAM, w.LPARAM]
        self.u.CallNextHookEx.restype = ctypes.c_ssize_t
        self.u.UnhookWindowsHookEx.argtypes = [w.HANDLE]
        callback = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, w.WPARAM, w.LPARAM)
        self.callback = callback(self._call)
        self.u.SetWindowsHookExW.argtypes = [ctypes.c_int, callback, w.HINSTANCE, w.DWORD]
        self.u.SetWindowsHookExW.restype = w.HANDLE
        self.k.GetCurrentThreadId.restype = w.DWORD
        self.hook = self.u.SetWindowsHookExW(5, self.callback, None, self.k.GetCurrentThreadId())
        if not self.hook:
            raise ctypes.WinError(ctypes.get_last_error())

    def _call(self, code, target, data):
        if code in (5, 9) and target:  # HCBT_ACTIVATE / HCBT_SETFOCUS
            try:
                pid = w.DWORD()
                self.u.GetWindowThreadProcessId(target, ctypes.byref(pid))
                root = self.u.GetAncestor(target, 2) or target
                name = ctypes.create_unicode_buffer(128)
                self.u.GetClassNameW(root, name, len(name))
                # Windows file-open/save dialogs must receive focus and input.
                # The game-focus guard applies to our overlay, not these modals.
                if pid.value == os.getpid() and name.value != '#32770' and self.blocked(root):
                    self.count += 1
                    if self.count <= 8:
                        self.log(f'[focus guard] blocked {"activate" if code == 5 else "focus"} hwnd={target} root={root}')
                    return 1
            except Exception as error:
                self.log(f'[focus guard] {type(error).__name__}: {error}')
        return self.u.CallNextHookEx(self.hook, code, target, data)

    def close(self):
        if self.hook:
            self.u.UnhookWindowsHookEx(self.hook)
            self.hook = None
