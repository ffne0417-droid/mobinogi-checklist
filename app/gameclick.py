"""Observe left-button presses without suppressing or injecting any input."""
import ctypes
from ctypes import wintypes as wt
from collections import deque
import threading

class ClickWatcher:
    def __init__(self):
        self.points=deque(maxlen=64)
        self.active=False
        self.error=''
        self.thread_id=0
        self.ready=threading.Event()
        self.thread=threading.Thread(target=self._run,name='overlay-game-click',daemon=True)
        self.thread.start()

    def drain(self):
        out=[]
        while self.points:
            try:out.append(self.points.popleft())
            except IndexError:break
        return out

    def close(self):
        if self.thread_id:
            self.user.PostThreadMessageW(self.thread_id,0x0012,0,0)

    def _run(self):
        u=ctypes.WinDLL('user32',use_last_error=True)
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.user=u
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,wt.WPARAM,wt.LPARAM)
        class MouseInfo(ctypes.Structure):
            _fields_=[('point',wt.POINT),('data',wt.DWORD),('flags',wt.DWORD),('time',wt.DWORD),('extra',ctypes.c_size_t)]
        u.SetWindowsHookExW.argtypes=[ctypes.c_int,callback_type,wt.HINSTANCE,wt.DWORD]
        u.SetWindowsHookExW.restype=ctypes.c_void_p
        u.CallNextHookEx.argtypes=[ctypes.c_void_p,ctypes.c_int,wt.WPARAM,wt.LPARAM]
        u.CallNextHookEx.restype=ctypes.c_ssize_t
        u.UnhookWindowsHookEx.argtypes=[ctypes.c_void_p]
        u.GetMessageW.argtypes=[ctypes.POINTER(wt.MSG),wt.HWND,wt.UINT,wt.UINT]
        u.PostThreadMessageW.argtypes=[wt.DWORD,wt.UINT,wt.WPARAM,wt.LPARAM]
        k.GetModuleHandleW.argtypes=[wt.LPCWSTR];k.GetModuleHandleW.restype=wt.HMODULE
        k.GetCurrentThreadId.restype=wt.DWORD
        self.thread_id=k.GetCurrentThreadId()
        msg=wt.MSG()
        u.PeekMessageW(ctypes.byref(msg),None,0,0,0)
        def observe(code,message,info):
            if code>=0 and message==0x0201:  # WM_LBUTTONDOWN only; no movement/keyboard recording.
                p=ctypes.cast(info,ctypes.POINTER(MouseInfo)).contents.point
                self.points.append((p.x,p.y))
            return u.CallNextHookEx(None,code,message,info)
        self.callback=callback_type(observe)
        hook=u.SetWindowsHookExW(14,self.callback,k.GetModuleHandleW(None),0)
        if not hook:
            self.error=str(ctypes.get_last_error());self.ready.set();return
        self.active=True;self.ready.set()
        try:
            while u.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                u.TranslateMessage(ctypes.byref(msg));u.DispatchMessageW(ctypes.byref(msg))
        finally:
            u.UnhookWindowsHookEx(hook);self.active=False
