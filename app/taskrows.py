"""Reference-style, bounded task sheet with controls on each catalog row."""
import tkinter as tk
from tkinter import ttk
import overlaytasks as model

WHITE, BG, TEXT, SUB, GOLD, LINE = '#ffffff', '#eef0f3', '#1b2230', '#5d6979', '#946b0f', '#d3d9e2'
KCOL = {'gather':'#1e9772','craft':'#3567c9','alter':'#c46a12','collect':'#7a4fd6','play':GOLD,'notify':'#3567c9'}


class RowSheet:
    def __init__(self, owner):
        self.o = owner
        self.quantities, self.modes, self.controls = {}, {}, {}
        self.limit = 30
        self.last_filter = None
        self.frame = tk.Frame(owner.window, bg=WHITE)
        self.frame.pack(fill='both', expand=True)
        head = tk.Frame(self.frame, bg=WHITE, padx=8, pady=4); head.pack(fill='x')
        self.title = self.label(head, '작업 추가', fg='#2f2406', bold=True); self.title.pack(side='left')
        self.count = self.label(head, '', size=8); self.count.pack(side='left', padx=8)
        owner.button(head, 'Esc · 닫기', owner.hide).pack(side='right')
        owner.button(head, '갱신', owner.sync).pack(side='right', padx=4)
        tk.Frame(self.frame,bg=LINE,height=1).pack(fill='x')
        search = tk.Frame(self.frame,bg=WHITE,padx=8,pady=10);search.pack(fill='x')
        owner.search = tk.Entry(search,textvariable=owner.query,bg=BG,fg=TEXT,relief='flat',
                                highlightthickness=1,highlightbackground='#dcc48c',highlightcolor=GOLD,
                                font=('맑은 고딕',10),width=28)
        owner.search.pack(side='left',fill='x',expand=True,ipady=7,padx=(0,10))
        owner.search.bind('<Escape>',lambda e:owner.hide())
        owner.tabs = {}
        for kind,label in [('all','전체'),('gather','채집'),('craft','제작'),('alter','가공'),('collect','수령'),('play','연주'),('notify','알림')]:
            b=owner.button(search,label,lambda k=kind:owner.switch(k));b.pack(side='left',padx=1)
            owner.tabs[kind]=b
        target=tk.Frame(self.frame,bg=BG,padx=8,pady=6);target.pack(fill='x')
        self.label(target,'담을 곳',bg=BG).pack(side='left',padx=(0,8))
        self.targets=tk.Frame(target,bg=BG);self.targets.pack(side='left')
        tk.Checkbutton(target,text='부족 재료 함께 제안',variable=owner.chain,bg=BG,fg=GOLD,
                       font=('맑은 고딕',9)).pack(side='right')
        filters=tk.Frame(self.frame,bg=WHITE,padx=8,pady=3);filters.pack(fill='x')
        self.category=ttk.Combobox(filters,textvariable=owner.category,state='readonly',width=14,font=('맑은 고딕',9))
        self.category.pack(side='right');self.category.bind('<<ComboboxSelected>>',lambda e:owner.render())
        self.label(filters,'레시피·채집물 이름 / 재료로 찾기',size=8).pack(side='left')
        self.headers=tk.Frame(self.frame,bg=WHITE,padx=8);self.headers.pack(fill='x')
        self.layout(self.headers)
        for col,text in enumerate(['종류','이름','×산출','상태','재료 (가방+창고 / 필요)','수량','단위','담기']):
            self.label(self.headers,text,size=8).grid(row=0,column=col,sticky='w',pady=5)
        tk.Frame(self.frame,bg=LINE,height=1).pack(fill='x')
        # Bottom bars are packed before the expanding list so actions never disappear.
        foot=tk.Frame(self.frame,bg='#e9edf2',padx=8,pady=6);foot.pack(side='bottom',fill='x')
        owner.button(foot,'담은 작업',lambda:owner.switch('queue')).pack(side='left',padx=(0,8))
        self.label(foot,'',variable=owner.summary,bg='#e9edf2',size=8).pack(side='left')
        owner.stop_button=owner.button(foot,'■ 정지',lambda:owner.run('stop_queue'));owner.stop_button.pack(side='right')
        owner.start_button=owner.button(foot,'▶ 시작',lambda:owner.run('start_queue'),primary=True);owner.start_button.pack(side='right',padx=4)
        self.label(self.frame,'',variable=owner.note,bg='#e9edf2',size=9,wrap=870).pack(side='bottom',fill='x',ipady=4)
        box=tk.Frame(self.frame,bg=WHITE);box.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(box,bg=WHITE,highlightthickness=0)
        self.scroll=ttk.Scrollbar(box,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side='left',fill='both',expand=True);self.scroll.pack(side='right',fill='y')
        self.content=tk.Frame(self.canvas,bg=WHITE)
        self.inner=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.inner,width=e.width))
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        owner.window.bind('<MouseWheel>',self.wheel,add='+')
        self.target_buttons=[]

    def wheel(self,event):
        if isinstance(event.widget, (tk.Entry,tk.Spinbox,ttk.Combobox)):
            return
        self.canvas.yview_scroll(-int(event.delta/120),'units')
        return 'break'

    @staticmethod
    def label(parent,text,fg=SUB,bg=WHITE,size=9,bold=False,variable=None,wrap=0):
        return tk.Label(parent,text=text,textvariable=variable,fg=fg,bg=bg,font=('맑은 고딕',size,'bold' if bold else 'normal'),
                        anchor='w',justify='left',wraplength=wrap,bd=0)

    @staticmethod
    def layout(frame):
        for col,width in enumerate([54,154,43,62,0,132,34,68]):
            frame.grid_columnconfigure(col,minsize=width,weight=1 if col==4 else 0)

    def state(self):
        if getattr(self,'creating',False):return
        o=self.o
        current=o.target_box.current()
        signature=(tuple(o.target_box['values']),current)
        if signature==getattr(self,'target_signature',None):return
        self.target_signature=signature
        for b in self.targets.winfo_children():b.destroy()
        values=o.target_box['values']
        for i,name in enumerate(values):
            if i>3:break
            text='대기열' if i==0 else '그룹 · '+str(name)[:13]
            b=o.button(self.targets,text,lambda n=i:self.target(n),primary=i==current)
            b.pack(side='left',padx=1)
        if len(values)>4:
            combo=ttk.Combobox(self.targets,values=values,state='readonly',width=16)
            combo.current(current);combo.pack(side='left');combo.bind('<<ComboboxSelected>>',lambda e:self.target(combo.current()))
        o.button(self.targets,'+ 새 그룹',self.new_group).pack(side='left',padx=4)

    def new_group(self):
        if self.o.busy:return
        self.creating=True
        for w in self.targets.winfo_children():w.destroy()
        entry=tk.Entry(self.targets,width=18,font=('맑은 고딕',9));entry.pack(side='left',ipady=4);entry.focus_set()
        def cancel():
            self.creating=False;self.target_signature=None;self.state()
        def submit():
            name=entry.get().strip()
            if not name:self.o.note.set('그룹 이름을 입력하세요.');return
            self.o.busy=True
            def done(result):
                self.o.busy=False;cancel()
                self.o.action_done(result)
            self.o.async_call('new-group',lambda:self.o.call('task_group_create',name),done)
        self.o.button(self.targets,'만들기',submit,primary=True).pack(side='left',padx=2)
        self.o.button(self.targets,'취소',cancel).pack(side='left')
        entry.bind('<Return>',lambda e:submit())

    def target(self,index):
        self.o.target_box.current(index);self.state()

    def render(self):
        o=self.o
        signature=(o.kind,o.query.get(),o.category.get())
        if signature!=self.last_filter:
            self.limit=30;self.canvas.yview_moveto(0);self.last_filter=signature
        y=self.canvas.yview()[0]
        for qty in self.quantities.values():
            previous=getattr(qty,'_row_trace',None)
            if previous:
                qty.trace_remove('write',previous);qty._row_trace=None
        for w in self.content.winfo_children():w.destroy()
        self.controls={}
        self.count.configure(text=f'{len(o.filtered):,}건')
        for kind,b in o.tabs.items():
            n=sum(1 for r in o.rows if kind=='all' or r['kind']==kind)
            title='전체' if kind=='all' else model.KINDS[kind]
            b.configure(text=title+(f' {n:,}' if kind in ('all','gather','craft','alter','collect') else ''),
                        bg=GOLD if kind==o.kind else BG,fg=WHITE if kind==o.kind else KCOL.get(kind,SUB),padx=5)
        self.category.configure(values=o.category_box['values'],state='disabled' if o.kind=='queue' else 'readonly')
        if not o.filtered:
            self.label(self.content,'목록을 불러오는 중…' if o.loading else '해당하는 작업이 없습니다. 검색어와 분류를 확인하세요.').pack(padx=20,pady=40)
        for row in o.filtered[:self.limit]:self.row(row)
        if len(o.filtered)>self.limit:
            o.button(self.content,f'더 보기 · {self.limit:,} / {len(o.filtered):,}',self.more).pack(fill='x',pady=8)
        self.canvas.configure(scrollregion=(0,0,900,len(self.content.winfo_children())*38))
        self.canvas.yview_moveto(y)

    def more(self):
        self.limit+=30;self.render()

    def row(self,row):
        o=self.o;queued=o.kind=='queue'
        kind=row.get('type') if queued else row['kind'];key=row['id'] if queued else row['key']
        raw=row.get('raw') or {}
        qty=self.quantities.setdefault(key,tk.StringVar(value=str(row.get('target',row.get('count',1)) if queued else row.get('default',1))))
        mode=self.modes.setdefault(key,tk.StringVar(value='none'))
        frame=tk.Frame(self.content,bg=WHITE,padx=8,height=76);frame.pack(fill='x');frame.pack_propagate(False)
        self.layout(frame)
        self.label(frame,model.KINDS.get(kind,''),fg=KCOL.get(kind,SUB)).grid(row=0,column=0,sticky='w',pady=15)
        name=tk.Frame(frame,bg=WHITE);name.grid(row=0,column=1,sticky='w')
        self.label(name,row.get('name') or '알림',fg=TEXT,bold=True,wrap=148).pack(anchor='w')
        self.label(name,row.get('groupName','') if queued else row['category'],size=8).pack(anchor='w')
        self.label(frame,'×'+str(raw.get('per',1)) if kind in ('craft','alter') and not queued else '—',fg=TEXT).grid(row=0,column=2,sticky='w')
        status=row.get('status') if queued else ('조건 확인' if row.get('blocked') else '가능')
        badge=self.label(frame,{'pending':'대기','running':'실행 중','waiting':'가공 중','done':'완료','error':'실패','stopped':'중단'}.get(status,status),
                         fg='#b5651d' if status=='조건 확인' else '#178043',bg='#e2f1e7',size=8)
        badge.grid(row=0,column=3,sticky='w')
        material=self.label(frame,'',fg=TEXT,size=8,wrap=230);material.grid(row=0,column=4,sticky='w',padx=(0,5))
        def mats(*args):
            try:n=max(1,int(qty.get()))
            except ValueError:n=1
            items=row.get('materials') or []
            if items:
                text='  ·  '.join(f"{m['name']} {m['owned']:,}/{m['requiredPer']*n:,}" for m in items[:2])
                if len(items)>2:text+=f'  외 {len(items)-2}종'
                short=any(m['owned']<m['requiredPer']*n for m in items)
                material.configure(text=text,fg='#b5651d' if short else SUB)
            else:material.configure(text=(row.get('message') or '') if queued else row.get('description',''),fg=SUB)
        mats()
        # Traces belong to each persistent quantity, not to destroyed row widgets.
        previous=getattr(qty,'_row_trace',None)
        if previous:qty.trace_remove('write',previous)
        qty._row_trace=qty.trace_add('write',mats)
        controls=tk.Frame(frame,bg=WHITE);controls.grid(row=0,column=5,padx=2,pady=4)
        if kind=='alter' and not queued:
            choice=tk.Frame(controls,bg=BG);choice.pack(fill='x')
            buttons=[]
            def choose(value):
                mode.set(value)
                for b,v in buttons:b.configure(fg='#c46a12' if v==value else SUB,bg='#f5e7d8' if v==value else BG)
            for text,value in [('걸기만','none'),('수령까지','later')]:
                b=o.button(choice,text,lambda v=value:choose(v));b.configure(font=('맑은 고딕',8),padx=2,pady=0)
                b.pack(side='left');buttons.append((b,value))
            choose(mode.get())
        free=kind in ('collect','notify') or (row.get('mode') if queued else row.get('item',{}).get('mode'))=='resume'
        stepper=tk.Frame(controls,bg=LINE);stepper.pack(pady=1)
        upper=row.get('max',20 if kind=='play' else 99999 if kind=='gather' else 999)
        def change(delta):
            try:n=int(qty.get())
            except ValueError:n=1
            qty.set(str(min(upper,max(1,n+delta*(100 if kind=='gather' else 1)))))
        minus=o.button(stepper,'−',lambda:change(-1));minus.configure(padx=5,pady=3);minus.pack(side='left')
        step=tk.Entry(stepper,textvariable=qty,width=5,font=('맑은 고딕',9),justify='center',relief='flat',bg=BG)
        step.pack(side='left',ipady=4,padx=1)
        plus=o.button(stepper,'+',lambda:change(1));plus.configure(padx=5,pady=3);plus.pack(side='left')
        if free:
            for w in (minus,step,plus):w.configure(state='disabled')
        if kind in ('craft','alter') and not queued:
            b=o.button(controls,'최대',lambda:self.maximum(row,qty));b.configure(pady=0,font=('맑은 고딕',8));b.pack()
        self.label(frame,'개' if kind=='gather' else '회',size=8).grid(row=0,column=6)
        actions=tk.Frame(frame,bg=WHITE);actions.grid(row=0,column=7,sticky='e')
        editable=not queued or row.get('status') in ('pending','stopped','error')
        b=o.button(actions,'적용' if queued else '담기',lambda:self.add(row,qty,mode),primary=True)
        b.configure(state='normal' if editable and not (free and queued) and not o.busy else 'disabled');b.pack()
        if queued:
            delete=o.button(actions,'삭제',lambda:self.delete(row));delete.configure(pady=1,state='normal' if editable and not o.busy else 'disabled');delete.pack()
        if kind=='notify' and not queued:
            notify=tk.Frame(material.master,bg=WHITE);notify.grid(row=0,column=4,sticky='w')
            tk.Entry(notify,textvariable=o.notice_text,width=20,font=('맑은 고딕',9)).pack(side='left')
            tk.Checkbutton(notify,text='소리',variable=o.sound,bg=WHITE,font=('맑은 고딕',8)).pack(side='left')
        self.controls[key]={'quantity':qty,'mode':mode,'add':b,'material':material,'plus':plus,'minus':minus}
        tk.Frame(self.content,bg=LINE,height=1).pack(fill='x')

    def select(self,row,qty=None,mode=None):
        o=self.o;key=row['id'] if o.kind=='queue' else row['key']
        o.tree.selection_set(key);o.select()
        if qty is not None:o.qty.set(qty.get())
        if mode is not None:o.collect.set('완료 후 수령까지' if mode.get()=='later' else '걸기만')

    def add(self,row,qty,mode):
        if self.o.busy:return
        self.select(row,qty,mode);self.o.add();self.lock()

    def delete(self,row):
        if self.o.busy:return
        self.select(row);self.o.remove();self.lock()

    def maximum(self,row,qty):
        if self.o.busy:return
        key=row['key'];self.o.busy=True;self.lock()
        def done(result):
            self.o.busy=False
            if result and result.get('maxSuggested'):qty.set(str(min(row['max'],result['maxSuggested'])))
            self.o.note.set('보유 재료와 시설 상한으로 계산했습니다.' if result and result.get('maxSuggested') else '보유 재료로 만들 수 있는 수량이 없습니다.')
            self.render()
        self.o.async_call('row-max',lambda:self.o.call('task_max',key),done)

    def lock(self):
        for c in self.controls.values():c['add'].configure(state='disabled')
