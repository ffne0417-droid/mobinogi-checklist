"""크기가 늘어나지 않는 오버레이 작업 추가 창. Tk 조작은 Tk 스레드에서만 한다."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
import overlaytasks as model

WHITE, BG, TEXT, MUTED, BLUE = "#ffffff", "#eef0f3", "#1b2230", "#5d6979", "#946b0f"
SELECTED, LINE = "#f4eddd", "#dcc48c"
STATUS = {"pending": "대기", "waiting": "가공 중", "running": "실행 중", "done": "완료", "error": "실패", "stopped": "중단"}


class WorkDrawer:
    def __init__(self, root, call):
        self.root, self.call = root, call
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", False)
        self.window.configure(bg=LINE, borderwidth=1)
        self.window.bind("<Escape>", lambda e: self.hide())
        self.window.bind("<Control-f>", lambda e: self.search.focus_set())
        self.window.bind("<Destroy>", self.destroyed, add="+")
        self.closed = False
        self.events = queue.Queue()
        self.rows, self.filtered, self.jobs, self.state = [], [], [], {}
        self.kind, self.busy, self.loading = "all", False, False
        self.state_loading = False
        self.selected, self.qty_for = None, None
        self.group_ids = [""]
        self.query = tk.StringVar()
        self.category = tk.StringVar(value="전체")
        self.qty = tk.StringVar(value="100")
        self.chain = tk.BooleanVar(value=True)
        self.collect = tk.StringVar(value="걸기만")
        self.sound = tk.BooleanVar(value=True)
        self.notice_text = tk.StringVar()
        self.note = tk.StringVar(value="목록을 불러오는 중…")
        self.description = tk.StringVar(value="")
        self.summary = tk.StringVar(value="")
        style = ttk.Style(root)
        style.configure("MW.Treeview", background=WHITE, fieldbackground=WHITE, foreground=TEXT,
                        rowheight=29, font=("맑은 고딕", 10), borderwidth=0)
        style.configure("MW.Treeview.Heading", font=("맑은 고딕", 9), foreground=MUTED)
        style.map("MW.Treeview", background=[("selected", SELECTED)], foreground=[("selected", "#2f2406")])
        body = tk.Frame(self.window, bg=WHITE, padx=12, pady=10)
        body.pack(fill="both", expand=True)
        head = tk.Frame(body, bg=WHITE)
        head.pack(fill="x")
        tk.Label(head, text="작업 추가", bg=WHITE, fg="#2f2406", font=("맑은 고딕", 11, "bold")).pack(side="left")
        self.button(head, "닫기 ×", self.hide).pack(side="right")
        self.button(head, "정보 갱신", self.sync).pack(side="right", padx=4)
        tabs = tk.Frame(body, bg=WHITE, pady=8)
        tabs.pack(fill="x")
        self.tabs = {}
        for kind, label in [("gather", "채집"), ("craft", "제작"), ("alter", "가공"), ("collect", "수령"), ("play", "연주"), ("notify", "알림"), ("queue", "담은 작업")]:
            b = self.button(tabs, label, lambda k=kind: self.switch(k))
            b.pack(side="left", expand=True, fill="x", padx=1)
            self.tabs[kind] = b
        filters = tk.Frame(body, bg=WHITE)
        filters.pack(fill="x", pady=(0, 6))
        self.search = tk.Entry(filters, textvariable=self.query, font=("맑은 고딕", 10), relief="flat", bd=1,
                               bg=BG, fg=TEXT, highlightthickness=1, highlightbackground=LINE, highlightcolor=BLUE)
        self.search.pack(side="left", fill="x", expand=True, ipady=4)
        self.category_box = ttk.Combobox(filters, textvariable=self.category, state="readonly", width=13, font=("맑은 고딕", 10))
        self.category_box.pack(side="right", padx=(8, 0))
        self.category_box.bind("<<ComboboxSelected>>", lambda e: self.render())
        self.query.trace_add("write", lambda *a: self.render())
        self.qty.trace_add("write", lambda *a: self.describe())
        tk.Label(body, text="이름·재료 검색  /  Ctrl+F", bg=WHITE, fg=MUTED, anchor="w", font=("맑은 고딕", 8)).pack(fill="x")
        box = tk.Frame(body, bg=WHITE)
        box.pack(fill="both", expand=True, pady=5)
        self.tree = ttk.Treeview(box, columns=("kind", "category", "state"), show="tree headings", style="MW.Treeview", selectmode="browse", height=3)
        self.tree.heading("#0", text="작업 / 품목")
        self.tree.heading("kind", text="종류")
        self.tree.heading("category", text="분류")
        self.tree.heading("state", text="상태 / 수량")
        self.tree.column("#0", width=230, minwidth=110, stretch=True)
        self.tree.column("kind", width=48, minwidth=40, stretch=False)
        self.tree.column("category", width=80, minwidth=55, stretch=False)
        self.tree.column("state", width=95, minwidth=70, stretch=False)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.select())
        tk.Label(body, textvariable=self.description, bg=BG, fg=TEXT, anchor="nw", justify="left",
                 wraplength=500, height=3, padx=7, pady=5, font=("맑은 고딕", 9)).pack(fill="x")
        self.options = tk.Frame(body, bg=WHITE, height=36)
        self.options.pack(fill="x", pady=5)
        self.options.pack_propagate(False)
        self.chain_box = tk.Checkbutton(self.options, text="부족 재료도 함께 담기", variable=self.chain, bg=WHITE, font=("맑은 고딕", 9))
        self.collect_box = ttk.Combobox(self.options, textvariable=self.collect, values=("걸기만", "완료 후 수령까지"), state="readonly", width=16)
        self.notice_entry = tk.Entry(self.options, textvariable=self.notice_text, font=("맑은 고딕", 10))
        self.sound_box = tk.Checkbutton(self.options, text="소리", variable=self.sound, bg=WHITE)
        entry = tk.Frame(body, bg=WHITE)
        entry.pack(fill="x", pady=(0, 6))
        self.unit = tk.Label(entry, text="수량 (개)", bg=WHITE, fg=TEXT, font=("맑은 고딕", 9))
        self.unit.pack(side="left")
        self.stepper = tk.Spinbox(entry, from_=1, to=99999, increment=100, textvariable=self.qty, width=8, font=("맑은 고딕", 10))
        self.stepper.pack(side="left", padx=7, ipady=4)
        self.max_button = self.button(entry, "최대", self.set_max)
        self.max_button.pack(side="left")
        self.add_button = self.button(entry, "담기", self.add, primary=True)
        self.add_button.pack(side="right", ipadx=10)
        self.remove_button = self.button(entry, "삭제", self.remove)
        self.remove_button.pack(side="right", padx=5)
        target = tk.Frame(body, bg=WHITE)
        target.pack(fill="x")
        tk.Label(target, text="담을 곳", bg=WHITE, fg=MUTED, font=("맑은 고딕", 9)).pack(side="left")
        self.target_box = ttk.Combobox(target, values=["기본 대기열"], state="readonly", width=22)
        self.target_box.current(0)
        self.target_box.pack(side="left", padx=7)
        tk.Label(body, textvariable=self.note, bg=WHITE, fg=MUTED, anchor="w", justify="left", wraplength=510,
                 height=2, font=("맑은 고딕", 9)).pack(fill="x", pady=3)
        footer = tk.Frame(body, bg=BG, padx=6, pady=6)
        footer.pack(fill="x")
        tk.Label(footer, textvariable=self.summary, bg=BG, fg=TEXT, font=("맑은 고딕", 9)).pack(side="left")
        self.stop_button = self.button(footer, "■ 정지", lambda: self.run("stop_queue"))
        self.stop_button.pack(side="right", padx=3)
        self.start_button = self.button(footer, "▶ 시작", lambda: self.run("start_queue"), primary=True)
        self.start_button.pack(side="right", padx=3)
        # Existing queue operations remain the controller; only the visible sheet changes.
        body.pack_forget()
        import taskrows
        self.rowview = taskrows.RowSheet(self)
        self.after_drain = self.window.after(80, self.drain)
        self.after_poll = self.window.after(1500, self.poll)

    def destroyed(self, event):
        if event.widget != self.window:
            return
        self.closed = True
        for job in (getattr(self, "after_drain", None), getattr(self, "after_poll", None)):
            if job:
                try:
                    self.window.after_cancel(job)
                except tk.TclError:
                    pass

    @staticmethod
    def button(parent, text, command, primary=False):
        return tk.Button(parent, text=text, command=command, bg=BLUE if primary else BG,
                         fg=WHITE if primary else TEXT, activebackground=SELECTED, relief="flat", bd=0,
                         padx=7, pady=6, cursor="hand2", font=("맑은 고딕", 9))

    def show(self, x, y, kind=None, category=None):
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        left, top, right, bottom = 0, 0, screen_w, screen_h
        try:
            import ctypes
            from ctypes import wintypes
            class MonitorInfo(ctypes.Structure):
                _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                            ("work", wintypes.RECT), ("flags", wintypes.DWORD)]
            user = ctypes.windll.user32
            user.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
            user.MonitorFromPoint.restype = wintypes.HANDLE
            user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
            info = MonitorInfo(); info.size = ctypes.sizeof(info)
            monitor = user.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)
            if user.GetMonitorInfoW(monitor, ctypes.byref(info)):
                left, top, right, bottom = info.work.left, info.work.top, info.work.right, info.work.bottom
        except (AttributeError, OSError):
            pass
        screen_w, screen_h = right - left, bottom - top
        width, height = min(920, screen_w - 20), min(580, screen_h - 40)
        x = min(max(left, x), right - width)
        y = min(max(top, y), bottom - height)
        self.window.geometry(f"{width}x{height}{x:+d}{y:+d}")
        self.window.deiconify()
        self.window.update_idletasks()
        try:
            # Tk의 음수 geometry는 화면 오른쪽 기준이다. 왼쪽 보조 모니터는 절대 좌표로 배치한다.
            user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user.GetAncestor.restype = wintypes.HWND
            user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, wintypes.UINT]
            hwnd = user.GetAncestor(self.window.winfo_id(), 2)
            user.SetWindowPos(hwnd, None, int(x), int(y), width, height, 0x14)
        except (NameError, AttributeError, OSError):
            pass
        self.window.lift()
        self.search.focus_set()
        if self.rows and category is None and (kind is None or kind == self.kind):
            self.refresh_state()
            return
        if kind:
            self.kind = kind
        self.requested_category = category
        self.load()

    def hide(self):
        self.window.withdraw()

    def async_call(self, label, fn, callback):
        def worker():
            try:
                result = fn()
            except Exception as exc:
                result = {"ok": False, "message": "처리하지 못했습니다: " + str(exc)}
            self.events.put((label, result, callback))
        threading.Thread(target=worker, name="overlay-task-" + label, daemon=True).start()

    def drain(self):
        try:
            while True:
                label, result, callback = self.events.get_nowait()
                callback(result)
        except queue.Empty:
            pass
        if not self.closed:
            self.after_drain = self.window.after(80, self.drain)

    def load(self):
        if self.loading:
            return
        self.loading = True
        self.note.set("작업 목록을 불러오는 중…")
        self.async_call("catalog", lambda: self.call("task_catalog"), self.loaded)

    def loaded(self, result):
        self.loading = False
        if not isinstance(result, dict) or not result.get("ok"):
            self.note.set((result or {}).get("message") or "목록을 불러오지 못했습니다. 다시 열어 주세요.")
            return
        self.rows = result.get("rows") or []
        self.update_state(result)
        self.switch(self.kind, getattr(self, "requested_category", None))
        self.requested_category = None
        self.note.set(result.get("message") or "품목을 고르고 수량을 정해 담으세요. 담기만으로 실행되지는 않습니다.")

    def switch(self, kind, category=None):
        self.kind, self.selected, self.qty_for = kind, None, None
        self.query.set("")
        values = ["전체"] + sorted({r["category"] for r in self.rows if kind == "all" or r["kind"] == kind})
        self.category_box.configure(values=values, state="disabled" if kind == "queue" else "readonly")
        self.category.set(category if category in values else "전체")
        for key, button in self.tabs.items():
            button.configure(bg=BLUE if key == kind else BG, fg=WHITE if key == kind else MUTED)
        self.description.set("")
        self.render()
        self.configure_options()

    def render(self):
        old = self.tree.selection()
        old = old[0] if old else None
        self.tree.delete(*self.tree.get_children())
        if self.kind == "queue":
            q = self.query.get().casefold()
            self.filtered = [r for r in self.jobs if q in r.get("name", "").casefold()]
            for r in self.filtered:
                self.tree.insert("", "end", iid=r["id"], text=r.get("name") or "알림", values=(model.KINDS.get(r["type"], ""), r.get("groupName") or "기본", STATUS.get(r.get("status"), r.get("status")) + " · " + str(r.get("target", r.get("count", 1)))))
        else:
            self.filtered = model.filter_rows(self.rows, self.kind, self.query.get(), self.category.get())
            for r in self.filtered:
                state = "조건 확인" if r.get("blocked") else ""
                self.tree.insert("", "end", iid=r["key"], text=r["name"], values=(model.KINDS[r["kind"]], r["category"], state))
        if old and self.tree.exists(old):
            self.tree.selection_set(old)
        else:
            self.selected = None
            self.description.set("검색 결과가 없습니다." if not self.filtered else "목록에서 작업을 선택하세요.")
        self.configure_options()
        if getattr(self, "rowview", None):
            self.rowview.render()

    def select(self):
        selection = self.tree.selection()
        if not selection:
            return
        key = selection[0]
        self.selected = next((r for r in self.filtered if r.get("id" if self.kind == "queue" else "key") == key), None)
        if not self.selected:
            return
        r = self.selected
        if self.qty_for != key:
            self.qty.set(str(r.get("target", r.get("count", 1)) if self.kind == "queue" else r.get("default", 1)))
            self.qty_for = key
        if self.kind == "queue":
            self.description.set((r.get("message") or "") + "\n" + ("실행 중 작업은 수정할 수 없습니다." if r.get("status") in ("running", "waiting") else "수량을 바꿔 적용하거나 작업을 삭제할 수 있습니다."))
        else:
            self.describe()
        self.configure_options()

    def describe(self):
        if self.selected and self.kind != "queue":
            self.description.set(model.describe(self.selected, self.qty.get()))

    def configure_options(self):
        for widget in (self.chain_box, self.collect_box, self.notice_entry, self.sound_box):
            widget.pack_forget()
        r = self.selected
        kind = r.get("type") if self.kind == "queue" and r else self.kind
        if kind in ("craft", "alter") and self.kind != "queue":
            self.chain_box.pack(side="left")
        if kind == "alter" and self.kind != "queue":
            self.collect_box.pack(side="right")
        if kind == "notify" and self.kind != "queue":
            self.notice_entry.pack(side="left", fill="x", expand=True)
            self.sound_box.pack(side="right")
        free = kind in ("notify", "collect") or bool(r and r.get("item", {}).get("mode") == "resume")
        self.unit.configure(text="수량 (개)" if kind == "gather" else "회차" if kind == "play" else "가공/제작 횟수")
        self.stepper.configure(state="disabled" if free else "normal", to=20 if kind == "play" else 99999 if kind == "gather" else 999,
                               increment=100 if kind == "gather" else 1)
        self.max_button.configure(state="normal" if kind in ("craft", "alter") and r and self.kind != "queue" else "disabled")
        editable = bool(r) and (self.kind != "queue" or r.get("status") in ("pending", "stopped", "error"))
        self.add_button.configure(text="수량 적용" if self.kind == "queue" else "담기", state="normal" if editable and not self.busy and not (free and self.kind == "queue") else "disabled")
        self.remove_button.configure(state="normal" if self.kind == "queue" and editable and not self.busy else "disabled")

    def set_max(self):
        if self.selected and not self.busy:
            self.busy = True
            self.max_for = self.selected["key"]
            self.configure_options()
            self.async_call("max", lambda row=dict(self.selected): self.call("task_max", row["key"]), self.max_done)

    def max_done(self, result):
        self.busy = False
        if self.qty_for != getattr(self, "max_for", None):
            self.configure_options()
            return
        if result and result.get("maxSuggested"):
            self.qty.set(str(result["maxSuggested"]))
            self.note.set("보유 재료와 시설 상한을 기준으로 계산한 횟수입니다.")
        else:
            self.note.set((result or {}).get("message") or "보유 재료로 만들 수 있는 수량이 없습니다.")
        self.configure_options()

    def add(self):
        if not self.selected or self.busy:
            return
        try:
            if self.kind == "queue":
                count = int(self.qty.get())
                if count < 1:
                    raise ValueError("수량은 1 이상이어야 합니다.")
                patch = {"target" if self.selected["type"] == "gather" else "count": count}
                fn = lambda iid=self.selected["id"], patch=patch: self.call("task_update", iid, patch)
            else:
                group_index = self.target_box.current()
                group = self.group_ids[group_index] if 0 <= group_index < len(self.group_ids) else ""
                p = model.payload(self.selected, self.qty.get(), "later" if self.collect.get() == "완료 후 수령까지" else "none", self.chain.get(), group, self.notice_text.get(), self.sound.get())
                fn = lambda p=p: self.call("task_add", p)
        except (ValueError, TypeError) as exc:
            self.note.set(str(exc))
            return
        self.busy = True
        self.note.set("대기열에 반영하는 중…")
        self.configure_options()
        self.async_call("add", fn, self.action_done)

    def remove(self):
        if self.selected and not self.busy:
            self.busy = True
            self.configure_options()
            self.async_call("remove", lambda iid=self.selected["id"]: self.call("task_remove", iid), self.action_done)

    def action_done(self, result):
        self.busy = False
        result = result or {}
        warnings = result.get("warnings") or []
        unresolved = result.get("unresolved") or []
        if unresolved:
            warnings = ["직접 준비할 재료: " + " · ".join(f"{r['name']} {r['short']}개" for r in unresolved[:3])] + warnings
        message = result.get("message") or ("대기열에 반영했습니다. ‘담은 작업’에서 확인할 수 있습니다." if result.get("ok") else "반영하지 못했습니다. 다시 시도하세요.")
        self.note.set("\n".join(warnings[:2]) if warnings else message)
        self.refresh_state()
        self.configure_options()
        if getattr(self, "rowview", None):
            self.rowview.render()

    def update_state(self, result):
        self.state = result.get("state") or {}
        self.jobs = model.queue_rows(self.state)
        groups = [g for g in self.state.get("items", []) if g.get("type") == "group" and g.get("status") != "running"]
        target_id = self.group_ids[self.target_box.current()] if 0 <= self.target_box.current() < len(self.group_ids) else ""
        self.group_ids = [""] + [g["id"] for g in groups]
        self.target_box.configure(values=["기본 대기열"] + [g.get("name") or "그룹" for g in groups])
        self.target_box.current(self.group_ids.index(target_id) if target_id in self.group_ids else 0)
        preview = result.get("preview") or {}
        pending = sum(r.get("status") in ("pending", "stopped", "waiting") for r in self.jobs)
        rounds_left = any(g.get("status") in ("pending", "stopped") and 0 < g.get("loop", 0) < g.get("repeat", 1)
                          for g in self.state.get("items", []) if g.get("type") == "group")
        running = bool(self.state.get("running"))
        self.summary.set(f"{'실행 중' if running else '대기 ' + str(pending) + '개'} · 예상 날개 {preview.get('wings', '—')}")
        self.start_button.configure(state="normal" if not running and (pending or rounds_left) and not self.busy else "disabled")
        self.stop_button.configure(state="normal" if running else "disabled")
        if self.kind == "queue":
            signature = repr(self.jobs)
            if signature != getattr(self, "_queue_signature", None):
                self._queue_signature = signature
                self.render()
        if getattr(self, "rowview", None):
            self.rowview.state()

    def refresh_state(self):
        if self.state_loading:
            return
        self.state_loading = True
        self.async_call("state", lambda: self.call("task_state"), self.state_done)

    def state_done(self, result):
        self.state_loading = False
        if result and result.get("ok"):
            self.update_state(result)

    def poll(self):
        if self.window.winfo_viewable():
            self.refresh_state()
        if not self.closed:
            self.after_poll = self.window.after(2000, self.poll)

    def run(self, hook):
        if self.busy:
            return
        self.busy = True
        self.start_button.configure(state="disabled")
        self.note.set("시작하는 중…" if hook == "start_queue" else "정지 요청 중…")
        self.async_call("run", lambda: self.call(hook), self.action_done)

    def sync(self):
        if not self.busy and not self.loading:
            self.busy = True
            self.note.set("게임에서 정보를 읽는 중… (실행 중에는 갱신할 수 없습니다)")
            self.async_call("sync", lambda: self.call("task_sync"), self.synced)

    def synced(self, result):
        self.busy = False
        if result and result.get("ok"):
            self.load()
        else:
            self.note.set((result or {}).get("message") or "정보 갱신에 실패했습니다. 연결을 확인하세요.")
        self.configure_options()
