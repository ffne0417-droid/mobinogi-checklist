"""Interactive native WebView2 host for the ORIGINAL MobiWorks task drawer."""
import ctypes
import json
import os
import time
from folio import opening_wv as wv

wv.IID.setdefault('ICoreWebView2CreateCoreWebView2ControllerCompletedHandler',
                  '6c4819f3-c9b7-4260-8127-c9f5bde7f68c')


class WorkDrawer(wv.WebOpening):
    def __init__(self, root, call):
        self.window = self
        self.visible = False
        self._shown = False
        self._placement = (20, 70, 840, 464)
        self._size = (840, 464)
        self._sizes = {'work': (840, 464), 'music': (840, 464), 'library': (840, 464)}
        self._music_view = 'list'
        self._workarea = None
        self._requested = (None, None)
        self._dismiss_at = 0
        self._dismiss_pending = False
        self._generation = 0
        self._opening = False
        super().__init__(url=call('task_url'),
                         data_dir=os.path.join(wv.user_data_dir(), 'overlay-tasks'),
                         log=lambda s: call('say', '[overlay tasks] ' + s))
        self.start()

    def winfo_id(self):
        return self.hwnd

    def winfo_viewable(self):
        return self.visible

    def show(self, x, y, kind=None, category=None):
        self._generation += 1
        self._opening = True
        key = 'music' if kind == 'music' else 'work' if kind in (None, 'queue') else 'library'
        self._size = self._sizes.get(key, (840, 464))
        from ctypes import wintypes
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wv.RECT), ('work', wv.RECT), ('flags', wintypes.DWORD)]
        u = ctypes.WinDLL('user32')
        u.MonitorFromPoint.argtypes, u.MonitorFromPoint.restype = [wintypes.POINT, wintypes.DWORD], ctypes.c_void_p
        u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo(); info.size = ctypes.sizeof(info)
        monitor = u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)
        if u.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.work
            self._workarea = (r.left, r.top, r.right, r.bottom)
            width,height = min(self._size[0],r.right-r.left),min(self._size[1],r.bottom-r.top)
            self._placement = (max(r.left,min(int(x),r.right-width)),max(r.top,min(int(y),r.bottom-height)),width,height)
        else:
            self._placement = (int(x),int(y),*self._size)
        if getattr(self, '_dock', None):
            from overlayplacement import popup_rect
            band, game = self._dock
            self._placement = popup_rect(band, self._size, game)
        self._requested = (kind, category)
        self.visible = True
        self._shown = False
        self._wake()

    def hide(self):
        if not self.visible:
            return
        self._generation += 1
        self._opening = False
        self.visible = False
        self._cmds.put((self._hide, None))
        self._wake()

    def resize(self, width, height):
        requested_size = (max(640, int(width)), max(360, int(height)))
        x, y, _, _ = self._placement
        right, bottom = (self._workarea[2:]) if self._workarea else (x + 1920, y + 1080)
        width = max(1, min(max(640, int(width)), right - x))
        height = max(1, min(max(360, int(height)), bottom - y))
        if getattr(self, '_dock', None):
            from overlayplacement import popup_rect
            band, game = self._dock
            x, y, width, height = popup_rect(band, requested_size, game)
        self._size = (width, height)
        if not hasattr(self, '_sizes'):
            self._sizes = {}
        kind = getattr(self, '_requested', (None, None))[0]
        key = 'music' if kind == 'music' else 'work' if kind in (None, 'queue') else 'library'
        self._sizes[key] = self._size
        self._placement = (x, y, width, height)
        def apply():
            if self.hwnd:
                self._u.SetWindowPos(self.hwnd, None, x, y, width, height, wv.SWP_NOZORDER | wv.SWP_NOACTIVATE)
                if self.ctrl:
                    wv.vcall(self.ctrl, 6, (wv.RECT,), wv.RECT(0, 0, width, height))
        self._cmds.put((apply, None))
        self._wake()
        return {'ok': True, 'width': width, 'height': height}

    def dock(self, band, game):
        self._dock = (band, game)
        if not self.visible:
            return
        from overlayplacement import popup_rect
        placement = popup_rect(band, self._size, game)
        if placement == self._placement:
            return
        self._placement = placement
        def apply():
            x, y, width, height = self._placement
            if self.hwnd:
                self._u.SetWindowPos(self.hwnd, None, x, y, width, height, wv.SWP_NOZORDER | wv.SWP_NOACTIVATE)
                if self.ctrl:
                    wv.vcall(self.ctrl, 6, (wv.RECT,), wv.RECT(0, 0, width, height))
        self._cmds.put((apply, None))
        self._wake()

    def move(self, x, y):
        if not self.visible:
            return
        _, _, width, height = self._placement
        self._placement = (int(x), int(y), width, height)
        def apply():
            px, py, _, _ = self._placement
            self._u.SetWindowPos(self.hwnd, None, px, py, 0, 0, wv.SWP_NOZORDER | wv.SWP_NOACTIVATE | 0x0001)
        self._cmds.put((apply, None))
        self._wake()

    def evaluate(self, script, done=None):
        self._cmds.put((lambda: self.execute(script, done), None))
        self._wake()

    def music_layout(self, view, keyboard=False):
        if view not in ('list', 'compact', 'expanded') or not self.visible or self._requested[0] != 'music':
            return {'ok': False}
        self._music_keyboard = keyboard
        self._music_view = view
        x, y, width, _ = self._placement
        sizes = getattr(self, '_sizes', {})
        # Expanding raises a sheet within the current music window; the
        # native window must not shrink and replace the library underneath.
        width, height = sizes.get('music', self._size)
        if view == 'compact':
            height = 198
        if self._workarea:
            height = min(height, self._workarea[3] - y)
        if getattr(self, '_dock', None):
            from overlayplacement import popup_rect
            band, game = self._dock
            x, y, width, height = popup_rect(band, (width, height), game)
        self._placement = (x, y, width, height)
        def apply():
            self._music_focus(keyboard)
            self._u.SetWindowPos(self.hwnd, None, x, y, width, height, wv.SWP_NOZORDER | wv.SWP_NOACTIVATE)
            if self.ctrl:
                wv.vcall(self.ctrl, 6, (wv.RECT,), wv.RECT(0, 0, width, height))
        self._cmds.put((apply, None)); self._wake()
        return {'ok': True, 'height': height}

    def keyboard_input(self, enabled=False):
        if not self.visible:
            return {'ok': False}
        self._cmds.put((lambda: self._music_focus(bool(enabled)), None))
        self._wake()
        return {'ok': True}

    def _music_focus(self, keyboard=False):
        from ctypes import wintypes
        u=self._u
        u.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int];u.GetWindowLongW.restype=ctypes.c_long
        u.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_long]
        style=u.GetWindowLongW(self.hwnd,-20)
        # Shared by every overlay page. Only deliberate text entry may focus
        # the host; task/settings buttons must keep the game foreground.
        self._music_keyboard = bool(keyboard)
        no_activate=not keyboard
        u.SetWindowLongW(self.hwnd,-20,(style|0x08000000) if no_activate else (style&~0x08000000))
        u.GetWindow.argtypes=[wintypes.HWND,ctypes.c_uint];u.GetWindow.restype=wintypes.HWND
        u.SetForegroundWindow.argtypes=[wintypes.HWND]
        if no_activate:
            owner=u.GetWindow(self.hwnd,4)  # owned by the game, not the app browser
            u.GetForegroundWindow.restype=wintypes.HWND
            foreground=u.GetForegroundWindow()
            u.GetAncestor.argtypes=[wintypes.HWND,ctypes.c_uint];u.GetAncestor.restype=wintypes.HWND
            if owner and (foreground==self.hwnd or u.GetAncestor(foreground,2)==self.hwnd):
                u.SetForegroundWindow(owner)
        elif keyboard:
            u.SetForegroundWindow(self.hwnd)
            if self.ctrl:
                wv.vcall(self.ctrl, 12, (ctypes.c_int,), 0)

    def _mouse_input(self, msg, wp, lp):
        """Windowless WebView receives input without activating a child HWND."""
        from ctypes import wintypes
        if not getattr(self, 'comp', 0) or msg not in (*range(0x200, 0x20f), 0x2a3):
            return False
        point = wintypes.POINT(ctypes.c_short(int(lp) & 0xffff).value,
                               ctypes.c_short((int(lp) >> 16) & 0xffff).value)
        keys, data = int(wp) & 0xffff, 0
        if msg in (0x20a, 0x20e):
            self._u.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            self._u.ScreenToClient(self.hwnd, ctypes.byref(point))
            data = (int(wp) >> 16) & 0xffff
            data = ctypes.c_uint(ctypes.c_short(data).value).value
        elif msg in (0x20b, 0x20c, 0x20d):
            data = (int(wp) >> 16) & 0xffff
        elif msg == 0x2a3:
            point, keys = wintypes.POINT(0, 0), 0
            self._mouse_tracking = False
        if msg == 0x200 and not getattr(self, '_mouse_tracking', False):
            class Track(ctypes.Structure):
                _fields_ = [('size', wintypes.DWORD), ('flags', wintypes.DWORD),
                            ('hwnd', wintypes.HWND), ('hover', wintypes.DWORD)]
            track = Track(ctypes.sizeof(Track), 2, self.hwnd, 0)
            self._u.TrackMouseEvent(ctypes.byref(track)); self._mouse_tracking = True
        if msg in (0x201, 0x204, 0x207, 0x20b):
            self._u.SetCapture.argtypes = [wintypes.HWND]
            self._u.SetCapture(self.hwnd)
        wv.check(wv.vcall(self.comp, 5,
            (ctypes.c_int, ctypes.c_int, ctypes.c_uint, wintypes.POINT),
            msg, keys, data, point), 'SendMouseInput')
        if msg in (0x202, 0x205, 0x208, 0x20c):
            self._u.ReleaseCapture()
        return True

    def _make_window(self):
        self._hinst = self._k.GetModuleHandleW(None)
        self._cls = f'MobiWorksTasksWV{id(self):x}'
        self._proc = wv._WNDPROC(self._wndproc)
        wc = wv.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.style = 8  # CS_DBLCLKS: preserve double-click-to-play.
        wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self._proc, self._hinst, self._cls
        if not self._u.RegisterClassExW(ctypes.byref(wc)):
            raise OSError('Cannot register task window')
        self.hwnd = self._u.CreateWindowExW(wv.WS_EX_TOOLWINDOW, self._cls, 'MobiWorks 작업 추가',
            wv.WS_POPUP, wv.OFFSCREEN, wv.OFFSCREEN, 840, 464, None, None, self._hinst, None)
        if not self.hwnd:
            raise OSError('Cannot create task window')
        self.stage = 'window'
        from passivewindow import ActivationGuard
        self._activation_guard = ActivationGuard(
            lambda root: not getattr(self, '_music_keyboard', False),
            self._log)
        self._clip_corners(840, 464)

    def _teardown(self):
        guard = getattr(self, '_activation_guard', None)
        if guard:
            guard.close()
        super()._teardown()

    def _clip_corners(self, width, height):
        # CSS radius alone leaves the opaque WebView host in the corner pixels.
        # Clip the native parent as well so the game shows through outside it.
        from ctypes import wintypes
        g = ctypes.WinDLL('gdi32')
        g.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        g.CreateRoundRectRgn.restype = wintypes.HRGN
        g.DeleteObject.argtypes = [wintypes.HANDLE]
        self._u.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
        self._u.SetWindowRgn.restype = ctypes.c_int
        region = g.CreateRoundRectRgn(0, 0, int(width) + 1, int(height) + 1, 18, 18)
        if region and not self._u.SetWindowRgn(self.hwnd, region, True):
            g.DeleteObject(region)  # Windows owns successful regions.

    def _wndproc(self, hwnd, msg, wp, lp):
        if msg == 0x0021 and not getattr(self, '_music_keyboard', False):
            return 3  # MA_NOACTIVATE: mouse controls must not mute the background game.
        if self._mouse_input(msg, wp, lp):
            return 0
        if msg == 0x0020 and (int(lp) & 0xffff) == 1 and getattr(self, 'comp', 0):
            cursor = ctypes.c_void_p()
            if wv.vcall(self.comp, 7, (ctypes.POINTER(ctypes.c_void_p),), ctypes.byref(cursor)) >= 0:
                self._u.SetCursor.argtypes = [ctypes.c_void_p]
                self._u.SetCursor(cursor)
                return 1
        if msg == 0x0005 and self.hwnd:  # WM_SIZE, including drag resize.
            width, height = int(lp) & 0xffff, (int(lp) >> 16) & 0xffff
            if width and height:
                self._clip_corners(width, height)
        if msg == 0x0010:  # WM_CLOSE: dismiss, do not destroy the saved form.
            self.hide()
            return 0
        return self._u.DefWindowProcW(hwnd, msg, wp, lp)

    def _on_env_(self, hr, env):
        wv.check(hr, 'create task environment')
        self.env = wv.qi(env, 'ICoreWebView2Environment3')
        h = wv.Handler('ICoreWebView2CreateCoreWebView2CompositionControllerCompletedHandler',
                       wv.INV_RESULT, self._on_controller, self._log)
        self._keep.append(h)
        wv.check(wv.vcall(self.env, 9, (ctypes.c_void_p, ctypes.c_void_p),
                         ctypes.c_void_p(self.hwnd), ctypes.c_void_p(h.ptr)), 'create task controller')
        self.stage = 'controller'

    def _on_controller(self, hr, ctrl):
        try:
            wv.check(hr, 'task controller')
            self.comp = wv.qi(ctrl, 'ICoreWebView2CompositionController')
            self.ctrl = wv.qi(ctrl, 'ICoreWebView2Controller')
            self.ctrl2 = wv.qi(ctrl, 'ICoreWebView2Controller2')
            wv.vcall(self.ctrl2, 27, (wv.COLOR,), wv.COLOR(255, 255, 255, 255))
            wv.vcall(self.ctrl, 6, (wv.RECT,), wv.RECT(0, 0, 840, 464))
            wv.vcall(self.ctrl, 4, (ctypes.c_int,), 0)
            self._make_visual()
            core = ctypes.c_void_p()
            wv.check(wv.vcall(self.ctrl, 25, (ctypes.POINTER(ctypes.c_void_p),), ctypes.byref(core)), 'task core')
            self.core = core.value
            self._tune_settings()
            h = wv.Handler('ICoreWebView2NavigationCompletedEventHandler', wv.INV_EVENT, self._on_nav, self._log)
            self._keep.append(h)
            tok = wv.Token()
            wv.check(wv.vcall(self.core, 15, (ctypes.c_void_p, ctypes.POINTER(wv.Token)),
                             ctypes.c_void_p(h.ptr), ctypes.byref(tok)), 'task navigation event')
            self._guard_navigation()
            self.stage = 'page'
            self._navigate()
        except Exception as e:
            self._fail(str(e))

    def execute(self, script, done=None):
        # Keep persistent navigation handlers; release only this completed callback.
        def fin(hr, text):
            try:
                if done:
                    done(hr, text)
            finally:
                self._cmds.put((lambda: self._keep.remove(h) if h in self._keep else None, None))
        h = wv.Handler('ICoreWebView2ExecuteScriptCompletedHandler', wv.INV_SCRIPT, fin, self._log)
        self._keep.append(h)
        wv.check(wv.vcall(self.core, 29, (ctypes.c_wchar_p, ctypes.c_void_p), script, ctypes.c_void_p(h.ptr)), 'task script')

    def _hide(self):
        super()._hide()
        self._shown = False

    def _tick(self):
        super()._tick()
        if not self.ready or not self.visible:
            return
        if not self._shown:
            x,y,width,height = self._placement
            self._music_keyboard = False
            self._music_focus(False)
            self._u.SetWindowPos(self.hwnd, None, x,y,width,height, wv.SWP_NOZORDER | wv.SWP_NOACTIVATE)
            wv.vcall(self.ctrl, 6, (wv.RECT,), wv.RECT(0,0,width,height))
            wv.vcall(self.ctrl, 4, (ctypes.c_int,), 1)
            generation = self._generation
            def opened(hr, text):
                if generation == self._generation:
                    self._opening = False
            self.execute('overlayOpen(' + ','.join(json.dumps(x,ensure_ascii=True) for x in self._requested) + ')', opened)
            self._u.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE for every tab.
            self._shown = True
        now=time.monotonic()
        if not self._opening and now-self._dismiss_at>.25 and not self._dismiss_pending:
            self._dismiss_at=now
            self._dismiss_pending=True
            generation = self._generation
            def dismissed(hr, text):
                self._dismiss_pending=False
                if generation == self._generation and not self._opening and hr>=0 and text=='true':
                    self.visible=False
                    self._hide()
            self.execute('Boolean(window.overlayDismissed)', dismissed)
