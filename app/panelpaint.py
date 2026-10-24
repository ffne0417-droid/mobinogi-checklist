# -*- coding: utf-8 -*-
"""펼친 판 둘을 **그림 한 장씩으로 그린다** — 밴드·토스트와 같은 방식.

위젯으로 쌓으면 둥근 모서리가 계단으로 남고 테두리가 곡선을 못 따라간다 (밴드에서 겪은 그대로).
`paint32` 로 그리면 GDI+ 가 안티에일리어싱해 주고, 배경만 반투명하게 둘 수 있다.

돌려주는 것은 `(폭, 높이, 적중 사각형)`. 적중 사각형은 `[(열쇠, x, y, w, h)]` 이고 판 왼쪽 위
기준이다 — 위젯이 없으므로 누르기·커서·관통 예외를 전부 이 목록으로 판정한다.
"""

import bandpaint

UI = bandpaint.UI_FAMILY
MONO = bandpaint.MONO_FAMILY
# 자물쇠·톱니는 **이모지가 아니라 아이콘 글꼴**로 그린다 — 맑은 고딕에 `🔒`·`⚙` 글리프가 없어
# 네모로 나온다 (실측). Windows 10 부터 있는 글꼴이고, 없으면 paint32 가 알아서 떨어진다.
ICON_FAMILY = "Segoe MDL2 Assets"
ICON_LOCK, ICON_UNLOCK, ICON_GEAR = "", "", ""


# 머리줄 위 여백. 0 으로 두면 글자가 테두리에 붙는다 — 아래 가로선까지가 머리줄이다.
HEAD_TOP = 6.0

# 시설 알약 치수 — 아이콘 14px · 이름 23px 고정폭 · 상태 점 5px · 시간 43px
# 우측정렬(000:00 기준) · 칸 막대 3×14px 최대 7개. 막대 치수는 `bandpaint.SLOT_*`. 디자인 px.
FAC_ICON = 14.0
FAC_NAME_W = 23.0
FAC_DOT = 5.0
FAC_TIME_W = 43.0
FAC_SLOT_MAX = 7
FAC_BADGE_D = 15.0       # 우상단 주황 배지 지름

# 컨트롤 줄 첫 알약 `⏎` — 폭 30 · 높이 26 · 곡률 8 (다른 알약은 13 = 완전한 알약).
FRONT_W = 62.0
FRONT_R = 8.0
FRONT_GLYPH = "앱 열기"

# 「전체 수령」이 0건일 때의 흐린 색 — 완료 0건이면 흐리게(비활성) 그린다.
# 팔레트(`overlay.COLORS`)에 없으면 이 값으로 떨어진다: 초록 버튼을 판 배경 위에 .4 로 얹은 값.
COLLECT_DIM_BG = "#1b3a28"
COLLECT_DIM_FG = "#5a8a68"

# 「스마트 관통 중」 활성 색 — 골드: rgba(226,184,102,.12) 배경 · .45 테두리.
# 판 배경(#090c11) 위에 얹어 환산한 값. 팔레트에 `goldbg`·`goldline` 이 없으면 이 값.
GOLD_BG = "#232119"
GOLD_LINE = "#6b5937"


def _f(key, text, sc):
    return bandpaint.font_of(key, text, sc)


def pill(surf, x, y, text, fg, bg, border, sc, h=26.0, pad=11.0, radius=13.0, bold=True,
         key=None, icon="", width=None) -> tuple:
    """컨트롤 줄의 알약 하나. 돌려주는 것: (폭, 적중 사각형 또는 None).
    `icon` 은 아이콘 글꼴로 앞에 붙는 글리프 (자물쇠·톱니).
    `width` 를 주면 글자 폭과 상관없이 그 폭(디자인 px)으로 굳힌다 — `⏎`(30×26)."""
    fam, size, bd = _f("pill", text, sc)
    isz = max(1, int(round(13 * sc)))
    # **자리는 advance, 가운데는 잉크.** 둘을 섞으면 안 된다:
    #  · 자리를 잉크 폭으로 잡으면 알약이 디자인보다 좁아진다 (실측 −7~−12px). 디자인은 CSS
    #    기준이고 CSS 는 글자를 advance 로 눕힌다.
    #  · 가운데를 metric 으로 잡으면 아이콘이 뜬다 — `Segoe MDL2 Assets` 에는 `text_h` 가
    #    재는 「가Ag」가 없어 대체 글꼴 값이 나온다. 톱니가 1.2px 위로 뜬다.
    # 아이콘 뒤 여백은 **글자가 있을 때만** 준다 (없으면 그만큼 왼쪽으로 쏠린다).
    iadv = float(surf.measure(icon, ICON_FAMILY, isz, False)) if icon else 0.0
    iw = (iadv + (5 * sc if text else 0)) if icon else 0.0
    tw = surf.measure(text, fam, size, bd) if text else 0.0
    w = width * sc if width else max(h * sc, iw + tw + pad * 2 * sc)
    hh = h * sc
    if bg:
        surf.round_rect(x, y, w, hh, radius * sc, fill=bg)
    if border:
        surf.round_rect(x, y, w, hh, radius * sc, outline=border, width=max(1.0, sc))
    cx = x + w / 2.0 - (iw + tw) / 2.0
    if icon:
        surf.icon(cx + iadv / 2.0, y + hh / 2.0, icon, ICON_FAMILY, isz, fg)
        cx += iw
    if text:
        surf.text(cx, y + hh / 2.0, text, fam, size, fg, bd)
    return w, ((key, x, y, w, hh) if key else None)


def fac_chip(surf, f, x, y, sc, C, svg_polylines, slot_style) -> tuple:
    """시설 알약 하나 (가공 펼침 판의 3열 격자). 돌려주는 것: (폭, 높이)."""
    pad = 7 * sc
    # 아이콘 14 · 이름 23 고정폭 · 상태 점 5 · 시간 43 우측정렬(000:00 기준).
    icon, name_w, dot, gap = FAC_ICON * sc, FAC_NAME_W * sc, FAC_DOT * sc, 5 * sc
    sw, sgap, sh = bandpaint.SLOT_W * sc, bandpaint.SLOT_GAP * sc, bandpaint.SLOT_H * sc
    slots_w = FAC_SLOT_MAX * sw + (FAC_SLOT_MAX - 1) * sgap      # 막대 최대 7개
    time_w = FAC_TIME_W * sc
    w = pad * 2 + icon + gap + name_w + gap + dot + 6 * sc + time_w + sc + slots_w + 20 * sc
    h = 20 * sc
    surf.round_rect(x, y, w, h, 7 * sc, fill=f["bg"])
    surf.round_rect(x, y, w, h, 7 * sc, outline=f["border"], width=max(1.0, sc))
    mid = y + h / 2.0

    cx = x + pad
    for seg in svg_polylines(f["icon"], icon):
        for i in range(len(seg) - 1):
            surf.line(cx + seg[i][0], mid - icon / 2.0 + seg[i][1],
                      cx + seg[i + 1][0], mid - icon / 2.0 + seg[i + 1][1],
                      f["iconColor"], max(1.0, sc))
    cx += icon + gap
    fam, size, bd = _f("badge", f["key"], sc)
    surf.text(cx, mid, f["key"], fam, size, f["nameColor"], bd)
    cx += name_w + gap
    if f.get("selected"):
        fam_check, size_check, bold_check = _f("badge", "✓", sc)
        surf.text(cx - 2 * sc, mid, "✓", fam_check, size_check, C["oktext"], True)
    else:
        surf.ellipse(cx, mid - dot / 2.0, dot, dot, f["dotColor"])

    sx = x + w - pad - slots_w - 20 * sc
    fam, size, bd = _f("pmonob", f["time"], sc)
    surf.text(sx - 2 * sc, mid, f["time"], fam, size, f["timeColor"], bd, anchor="e")
    for sl in f["slots"]:
        track, fill = slot_style.get(sl["kind"], slot_style["none"])
        surf.rect(sx, mid - sh / 2.0, sw, sh, track)
        if fill:
            fh = sh if sl["kind"] == "done" else 2 * sc
            surf.rect(sx, mid + sh / 2.0 - fh, sw, fh, fill)
        sx += sw + sgap
    if f["badge"]:
        r = FAC_BADGE_D / 2.0 * sc      # 우상단 주황 배지 지름 15
        bx = x + w - 24 * sc
        surf.ellipse(bx - r, y - r + 3 * sc, r * 2, r * 2, C["warn"])
        fam, size, bd = _f("badge", f["badge"], sc)
        surf.text(bx - surf.measure(f["badge"], fam, size, bd) / 2.0, y + 3 * sc,
                  f["badge"], fam, size, C["facbadgefg"], bd)
    surf.icon(x + w - 10 * sc, mid, "", ICON_FAMILY, max(1, round(12 * sc)), C["fg2"])
    return w, h


def controls(surf, x, y, sc, C, locked: bool, through: bool, quick=False) -> tuple:
    """컨트롤 줄 (펼친 판 맨 아래줄). 돌려주는 것: (폭, 높이, 적중 사각형들)."""
    hits, gap = [], 6 * sc
    cx = x
    # 첫 알약 `⏎` = 앱 창 앞으로 (`overlay.PANEL_ACTS["front"]`). 30×26 · 곡률 8.
    w, hit = pill(surf, cx, y, "⏎ 앱 열기" if quick else FRONT_GLYPH, C["fg2"], "", C["sep"], sc,
                  pad=10 if quick else 0, radius=FRONT_R, key="front", width=None if quick else FRONT_W)
    hits.append(hit)
    cx += w + gap
    # 위치 잠금과 같은 중립 스타일. 상태는 글자로만 구분한다.
    items = [
        ("lock", f"위치 {'고정됨' if locked else '풀림'}", C["fg2"], "", C["sep"],
         ICON_LOCK if locked else ICON_UNLOCK),
        ("reset", "↻ 위치 초기화", C["fg2"], "", C["sep"], ""),
        ("through", f"↗ 스마트 관통 {'켜짐' if through else '꺼짐'}",
         C["fg2"], C["bg"], C["sep"], ""),
    ]
    for key, text, fg, bg, bd, ic in items:
        w, hit = pill(surf, cx, y, text, fg, bg, bd, sc, key=key, icon=ic)
        hits.append(hit)
        cx += w + gap
    if quick:
        return cx - gap - x, 26 * sc, hits
    w, hit = pill(surf, cx, y, "", C["fg2"], "", C["sep"], sc, pad=0, key="gear", icon=ICON_GEAR)
    hits.append(hit)
    return cx + w - x, 26 * sc, hits


def paint_apanel(surf, data, sc, C, svg_polylines, slot_style, locked, through) -> tuple:
    """Read-only processing overview; actions live in Work/Management."""
    works = data.get('works') or []
    keys = ['금속','목재','가죽','옷감','약품','식재']
    grouped = {k: [] for k in keys}
    for work in works:
        key = str(work.get('facility') or '').split(' ')[0]
        key = {'식재료': '식재'}.get(key, key)
        if key and key not in grouped:
            grouped[key] = []; keys.append(key)
        if key:
            grouped[key].append(work)
    available = max(280, int(data.get('availableWidth') or 900))
    cols = min(len(keys), max(1, int((available - 14*sc)//(101*sc))))
    cw = min(96*sc, (available-14*sc-(cols-1)*5*sc)/cols)
    pad, gap, head, card_h = 7*sc, 5*sc, 29*sc, 112*sc
    rows = (len(keys)+cols-1)//cols
    width = int(2*pad+cols*cw+(cols-1)*gap)
    height = int(head+rows*card_h+(rows-1)*gap+pad)
    surf.resize(width,height);surf.clear()
    surf.round_rect(.5,.5,width-1,height-1,12*sc,fill=C['bg'],alpha=240)
    surf.round_rect(.5,.5,width-1,height-1,12*sc,outline=C['line'],width=max(1,sc))
    # Match the task drawer: 13px primary type, 12px supporting type.
    # Keep card geometry compact; strengthen text instead of enlarging the panel.
    fam,size,bold = _f('bold','가공기 현황',sc)
    size = 13*sc
    surf.text(pad,head/2,'가공기 현황',fam,size,C['fg'],bold)
    done_count=sum(1 for w in works if w.get('done'))
    surf.text(width-34*sc,head/2,f'수령 가능 {done_count}건',fam,max(1,size-sc),C['oktext'] if done_count else C['fg2'],True,anchor='e')
    surf.icon(width-15*sc,head/2,'×',fam,size,C['sub'])
    for i,key in enumerate(keys):
        x=pad+(i%cols)*(cw+gap);y=head+(i//cols)*(card_h+gap)
        items=grouped[key];ready=[w for w in items if w.get('done')];running=[w for w in items if not w.get('done') and not w.get('wait')];waiting=[w for w in items if w.get('wait') and not w.get('done')]
        surf.round_rect(x,y,cw,card_h,7*sc,fill=C['facbg'],outline=C['okline'] if ready else C['sep'],width=max(1,sc))
        tx=x+8*sc
        surf.text(tx,y+17*sc,key,fam,size,C['oktext'] if ready else C['fg'],True)
        by=y+34*sc
        if not items:
            surf.text(tx,by,'비어 있음',fam,max(1,size-sc),C['fg2'])
            surf.text(tx,by+25*sc,'—',fam,size,C['gold'])
        else:
            names=[]
            for w in running+waiting+ready:
                name=str(w.get('name') or '이름 미확인')
                if name not in names:names.append(name)
            for j,name in enumerate(names[:2]):
                label=fit_text(surf,name,fam,max(1,size-sc),True,cw-16*sc)
                surf.text(tx,by+j*16*sc,label,fam,max(1,size-sc),C['fg'],True)
            if len(names)>2:surf.text(x+cw-8*sc,y+17*sc,f'+{len(names)-2}',fam,max(1,size-2),C['sub'],anchor='e')
            if running:
                left=min(max(0,int(w.get('left') or 0)) for w in running)
                time_text=f'{left//3600}시간 {(left%3600)//60}분' if left>=3600 else f'{left//60:02d}:{left%60:02d}'
                surf.text(tx,y+75*sc,time_text,fam,size,C['warn'],True)
            elif ready:
                surf.text(tx,y+75*sc,'완료',fam,size,C['oktext'],True)
            else:surf.text(tx,y+75*sc,'시작 대기',fam,size,C['fg2'],True)
        surf.rect(tx,y+90*sc,cw-16*sc,max(1,sc),C['sep'])
        status=f'진행 {len(running)} · 대기 {len(waiting)}' if running or waiting else f'수령 {len(ready)}건' if ready else '등록 0건'
        surf.text(tx,y+102*sc,status,fam,max(1,size-2*sc),C['oktext'] if ready else C['fg2'])
    return width,height,[('aexpand',width-29*sc,0,29*sc,head)]


def paint_apanel_legacy(surf, data, sc, C, svg_polylines, slot_style, locked, through) -> tuple:
    """가공 펼침 판 — 머리 · 시설 격자 3열 · 전체 수령 · 컨트롤 줄."""
    pad = 8 * sc
    facs = data["facs"]
    # 먼저 크기를 잰다 (알약 하나를 시험 삼아 그려 폭을 얻는다)
    surf.resize(1200, 400)
    surf.clear()
    fw, fh = (fac_chip(surf, facs[0], -5000, -5000, sc, C, svg_polylines, slot_style) if facs else (120 * sc, 20 * sc))
    cols = min(3, max(1, len(facs))) if facs else 1
    rows = (len(facs) + 2) // 3 if facs else 1
    grid_w = cols * fw + (cols - 1) * 4 * sc
    options_open = bool(data.get("optionsOpen"))
    cw, ch, _ = controls(surf, -5000, -5000, sc, C, locked, through)
    top = HEAD_TOP * sc
    head_h = 28 * sc
    bar_h = 22 * sc + 3 * sc + 24 * sc   # 담기 결과 한 줄은 고정 높이로 유지한다.
    w = int(round(max(grid_w, cw) + pad * 2))
    options_h = pad + 1 + pad + 26 * sc if options_open else 0
    detail_works = data.get("detailWorks") or []
    slot_count = max(1, len(detail_works))
    detail_rows = (slot_count + 2) // 3
    editor_recipes = (data.get("editor") or {}).get("recipes") or []
    list_rows = (min(9, len(editor_recipes)) + 2) // 3
    list_h = list_rows * 28 * sc
    editor_h = 132 * sc + list_h if data.get("editor") is not None else 0
    detail_h = (pad + 28 * sc + detail_rows * 54 * sc + editor_h) if data.get("detailKey") else 0
    h = int(round(top + head_h + 1 + pad + rows * fh + (rows - 1) * 3 * sc + bar_h
                  + options_h + detail_h + pad))
    surf.resize(w, h)
    surf.clear()
    r = 14 * sc
    surf.round_rect(0.5, 0.5, w - 1, h - 1, r, fill=C["bg"], alpha=217)
    surf.round_rect(0.5, 0.5, w - 1, h - 1, r, outline=data.get("frame") or C["warnline2"],
                    width=max(1.0, sc))
    hits = []

    # 머리줄
    fam, size, bd = _f("boldxs", "가공기 현황", sc)
    y = top + head_h / 2.0
    tw = surf.text(10 * sc, y, "가공기 현황", fam, size, data.get("titleColor") or C["gold"], True)
    cx = 10 * sc + tw + 7 * sc
    if data["collect"]:
        pw, hit = pill(surf, cx, y - 9 * sc, f"수령 {data['collect']}건", C["collectfg"],
                       C["collectbg"], "", sc, h=18, pad=8, radius=9)
    elif data.get("note"):
        fam2, s2, b2 = _f("xs", data["note"], sc)
        surf.text(cx, y, data["note"], fam2, s2, C["faint"])
    fam2, s2, b2 = _f("xs", "▴", sc)
    surf.text(w - 10 * sc, y, "▴", fam2, s2, C["faint"], anchor="e")
    hits.append(("aexpand", w - 24 * sc, 0, 24 * sc, top + head_h))
    surf.rect(0, top + head_h, w, 1, C["sepfaint"])

    # 시설 격자
    gy = top + head_h + 1 + pad
    for i, f in enumerate(facs):
        fx = pad + (i % 3) * (fw + 4 * sc)
        fy = gy + (i // 3) * (fh + 3 * sc)
        fac_chip(surf, f, fx, fy, sc, C, svg_polylines, slot_style)
        hits.append(("detail:" + f["key"], fx + fw - 20 * sc, fy, 20 * sc, fh))
        hits.append(("facility:" + f["key"], fx, fy, fw - 20 * sc, fh))
    gy += rows * fh + (rows - 1) * 3 * sc
    if not facs:
        fam2, s2, b2 = _f("xs", "등록된 가공이 없습니다", sc)
        surf.text(pad, gy - fh / 2.0, "등록된 가공이 없습니다", fam2, s2, C["faint"])

    # 전체 수령 — 그리드 전폭, 완료 0건이면 흐리게(비활성).
    # 0건이어도 자리는 남기되 흐리게 그리고 **적중 사각형을 내놓지 않는다** —
    # 눌러도 아무 일도 없어야 하고(수령 요청이 나가면 안 된다) 손 모양 커서도 뜨면 안 된다.
    n = int(data.get("selectedCollect", 0) or 0)
    by = gy + 3 * sc
    bh = 22 * sc
    bg = C["collectbg"] if n else C.get("collectbgdim", COLLECT_DIM_BG)
    fg = C["collectfg"] if n else C.get("collectfgdim", COLLECT_DIM_FG)
    start_w = (w - pad * 2 - 12 * sc) / 3
    collect_w = start_w
    surf.round_rect(pad, by, collect_w, bh, 6 * sc, fill=bg)
    txt = "담는 중…" if data.get("collectBusy") else f"선택 담기 {n}건" if n else "시설 선택 후 담기"
    fam2, s2, b2 = _f("pill", txt, sc)
    surf.text(pad + collect_w / 2.0 - surf.measure(txt, fam2, s2, b2) / 2.0, by + bh / 2.0,
              txt, fam2, s2, fg, b2)
    if n and not data.get("collectBusy"):
        hits.append(("collect", pad, by, collect_w, bh))
    sx = pad + collect_w + 6 * sc
    running = bool(data.get("running"))
    start_on = not running and bool(data.get("canStart"))
    surf.round_rect(sx, by, start_w, bh, 6 * sc, fill=C["run"] if start_on else C["facbg"])
    start_text = "▶ 시작"
    surf.text(sx + start_w / 2.0 - surf.measure(start_text, fam2, s2, b2) / 2.0,
              by + bh / 2.0, start_text, fam2, s2, "#ffffff" if start_on else C["dim"], b2)
    if start_on:
        hits.append(("start", sx, by, start_w, bh))
    stop_x = sx + start_w + 6 * sc
    surf.round_rect(stop_x, by, start_w, bh, 6 * sc, fill=C["bad"] if running else C["facbg"])
    stop_text = "■ 정지"
    surf.text(stop_x + start_w / 2.0 - surf.measure(stop_text, fam2, s2, b2) / 2.0,
              by + bh / 2.0, stop_text, fam2, s2, "#ffffff" if running else C["dim"], b2)
    if running:
        hits.append(("stop", stop_x, by, start_w, bh))
    message = str(data.get("collectFeedback") or "담으면 여기에 담긴 시설과 건수가 표시됩니다")
    fam_msg, size_msg, bold_msg = _f("xs", message, sc)
    while message and surf.measure(message, fam_msg, size_msg, bold_msg) > w - pad * 2:
        message = message[:-2].rstrip("…") + "…"
    surf.text(pad, by + bh + 12 * sc, message, fam_msg, size_msg,
              C["bad"] if data.get("collectFeedbackBad") else C["fg2"], bold_msg)
    gy = by + bh + 24 * sc

    if data.get("detailKey"):
        dy = gy + pad
        surf.rect(pad, dy, w - pad * 2, 1, C["sepfaint"])
        key = data["detailKey"]
        title = (detail_works[0].get("facility") if detail_works else "") or (key + " 가공 시설")
        title += " · 등록 " + str(len(detail_works)) + "건"
        fam3, sz3, bd3 = _f("boldxs", title, sc)
        surf.text(pad, dy + 14 * sc, title, fam3, sz3, C["strong"], bd3)
        surf.text(w - pad, dy + 14 * sc, "닫기", fam3, sz3, C["fg2"], anchor="e")
        hits.append(("detail:" + key, w - pad - 38 * sc, dy, 38 * sc, 28 * sc))
        card_y = dy + 28 * sc
        card_w = (w - pad * 2 - 12 * sc) / 3
        for idx, work in enumerate(detail_works):
            x = pad + (idx % 3) * (card_w + 6 * sc)
            y = card_y + (idx // 3) * 54 * sc
            done, waiting = bool(work.get("done")), bool(work.get("wait"))
            color = C["oktext"] if done else C["faint"] if waiting else C["warn"]
            surf.round_rect(x, y, card_w, 48 * sc, 7 * sc, fill="#ffffff", outline=C["sep"], width=max(1., sc))
            name = str(work.get("name") or "이름 없음")
            fam4, sz4, bd4 = _f("xs", name, sc)
            surf.text(x + 8 * sc, y + 14 * sc, fit_text(surf, name, fam4, sz4, bd4, card_w - 16 * sc), fam4, sz4, C["strong"], bd4)
            left = max(0, int(work.get("left") or 0))
            label = "완료 · 수령 대기" if done else "대기 중" if waiting else f"진행 중 · {left // 60:02d}:{left % 60:02d}"
            surf.text(x + 8 * sc, y + 34 * sc, label, fam4, sz4, color)
        if not detail_works:
            fam4, sz4, bd4 = _f("xs", "등록된 작업이 없습니다", sc)
            surf.text(pad + 8 * sc, card_y + 24 * sc, "등록된 작업이 없습니다", fam4, sz4, C["faint"])
        editor = data.get("editor")
        if editor is not None:
            ey = card_y + detail_rows * 54 * sc
            fam4, sz4, bd4 = _f("xs", "가공 등록", sc)
            surf.text(pad, ey + 12 * sc, "가공 등록 · 품목과 횟수를 선택하세요", fam4, sz4, C["strong"], True)
            surf.text(w - pad, ey + 12 * sc, "접기", fam4, sz4, C["fg2"], anchor="e")
            hits.append(("alteredit:close", w - pad - 36 * sc, ey, 36 * sc, 24 * sc))
            recipes = editor.get("recipes") or []
            index = min(max(0, int(editor.get("index") or 0)), max(0, len(recipes) - 1))
            recipe = recipes[index] if recipes else None
            label = (str(recipe["name"]) + f"  ({index + 1}/{len(recipes)})") if recipe else "이 시설의 품목 정보가 없습니다 · 정보 갱신 필요"
            surf.round_rect(pad, ey + 28 * sc, w - 2 * pad, 30 * sc, 6 * sc, fill="#ffffff", outline=C["sep"], width=max(1., sc))
            surf.text(pad + 38 * sc, ey + 43 * sc, fit_text(surf, label, fam4, sz4, False, w - 2 * pad - 76 * sc), fam4, sz4, C["strong"])
            for action, x, glyph in (("prev", pad, "◀"), ("next", w - pad - 30 * sc, "▶")):
                surf.text(x + 10 * sc, ey + 43 * sc, glyph, fam4, sz4, C["fg2"])
                if recipes:
                    hits.append(("alteredit:" + action, x, ey + 28 * sc, 30 * sc, 30 * sc))
            start = (index // 9) * 9
            choice_w = (w - pad * 2 - 8 * sc) / 3
            for offset, option in enumerate(recipes[start:start + 9]):
                choice = start + offset
                x = pad + (offset % 3) * (choice_w + 4 * sc)
                y = ey + 62 * sc + (offset // 3) * 28 * sc
                surf.round_rect(x, y, choice_w, 24 * sc, 5 * sc,
                                fill=C["facbgok"] if choice == index else "#ffffff",
                                outline=C["okline"] if choice == index else C["sep"], width=max(1., sc))
                name = str(option["name"])
                surf.text(x + 6 * sc, y + 12 * sc, fit_text(surf, name, fam4, sz4, False, choice_w - 12 * sc), fam4, sz4, C["strong"])
                hits.append(("alteredit:recipe:" + str(choice), x, y, choice_w, 24 * sc))
            ey += list_h
            surf.text(pad + 35 * sc, ey + 80 * sc, str(editor.get("count", 1)) + " 회", fam4, sz4, C["strong"])
            for action, x, glyph in (("minus", pad, "−"), ("plus", pad + 100 * sc, "+")):
                surf.text(x + 10 * sc, ey + 80 * sc, glyph, fam4, sz4, C["fg2"])
                hits.append(("alteredit:" + action, x, ey + 65 * sc, 30 * sc, 30 * sc))
            bx = w - pad - 120 * sc
            surf.round_rect(bx, ey + 65 * sc, 120 * sc, 30 * sc, 6 * sc, fill=C["run"] if recipes else C["facbg"])
            surf.text(bx + 12 * sc, ey + 80 * sc, "담는 중…" if editor.get("busy") else "등록 작업 담기", fam4, sz4, "#ffffff" if recipes else C["dim"])
            if recipes and not editor.get("busy"):
                hits.append(("alteredit:add", bx, ey + 65 * sc, 120 * sc, 30 * sc))
            message = editor.get("message") or "담은 작업은 위의 시작 버튼으로 실행합니다."
            surf.text(pad, ey + 112 * sc, fit_text(surf, message, fam4, sz4, False, w - pad * 2), fam4, sz4, C["fg2"])
        gy += detail_h

    # 상세 옵션은 머리줄 톱니바퀴를 눌렀을 때만 펼친다.
    if options_open:
        ly = gy + pad
        surf.rect(0, ly, w, 1, C["sepfaint"])
        ly += pad
        _cw, _ch, chits = controls(surf, pad, ly, sc, C, locked, through)
        hits += chits
    return w, h, [x for x in hits if x]


def paint_alter_picker(surf, data, sc, C) -> tuple:
    """빈 슬롯 클릭으로만 여는 가공 품목 선택 화면. 현황 화면 아래에 붙이지 않는다."""
    editor = data["editor"]
    recipes = editor.get("recipes") or []
    index = min(max(0, int(editor.get("index") or 0)), max(0, len(recipes) - 1))
    page = index // 9
    options = recipes[page * 9:page * 9 + 9]
    rows = max(1, (len(options) + 2) // 3)
    pad, width = 10 * sc, 460 * sc
    height = (64 + rows * 52 + 100) * sc
    w, h = round(width), round(height)
    surf.resize(w, h)
    surf.clear()
    surf.round_rect(.5, .5, w - 1, h - 1, 14 * sc, fill=C["bg"], alpha=245)
    surf.round_rect(.5, .5, w - 1, h - 1, 14 * sc, outline=C["warnline2"], width=max(1., sc))
    title = data.get("detailKey", "") + " · 가공 등록"
    fam, size, bold = _f("xs", title, sc)
    surf.text(pad, 20 * sc, title, fam, size, C["strong"], True)
    surf.text(w - pad, 20 * sc, "돌아가기", fam, size, C["fg2"], anchor="e")
    hits = [("alteredit:close", w - pad - 65 * sc, 4 * sc, 65 * sc, 32 * sc)]
    surf.text(pad, 45 * sc, "등록할 품목을 선택하세요", fam, size, C["fg2"])
    if len(recipes) > 9:
        pages = (len(recipes) + 8) // 9
        surf.text(w - 72 * sc, 45 * sc, f"{page + 1}/{pages}", fam, size, C["fg2"])
        for action, x, glyph in (("pageprev", w - 105 * sc, "◀"), ("pagenext", w - 36 * sc, "▶")):
            surf.text(x + 8 * sc, 45 * sc, glyph, fam, size, C["fg2"])
            hits.append(("alteredit:" + action, x, 32 * sc, 28 * sc, 26 * sc))
    cw = (w - 2 * pad - 12 * sc) / 3
    for offset, recipe in enumerate(options):
        choice = page * 9 + offset
        x, y = pad + (offset % 3) * (cw + 6 * sc), (60 + (offset // 3) * 52) * sc
        selected = choice == index
        surf.round_rect(x, y, cw, 46 * sc, 7 * sc, fill=C["facbgok"] if selected else "#ffffff",
                        outline=C["okline"] if selected else C["sep"], width=max(1., sc))
        name = ("✓ " if selected else "") + str(recipe["name"])
        surf.text(x + 8 * sc, y + 23 * sc, fit_text(surf, name, fam, size, False, cw - 16 * sc), fam, size, C["strong"])
        hits.append(("alteredit:recipe:" + str(choice), x, y, cw, 46 * sc))
    if not recipes:
        surf.text(pad, 82 * sc, "품목 정보가 없습니다. 정보를 갱신해 주세요.", fam, size, C["faint"])
    y = (64 + rows * 52) * sc
    surf.text(pad, y + 18 * sc, "가공 횟수", fam, size, C["fg2"])
    surf.text(pad + 110 * sc, y + 18 * sc, str(editor.get("count", 1)) + " 회", fam, size, C["strong"])
    for action, x, glyph in (("minus", pad + 75 * sc, "−"), ("plus", pad + 170 * sc, "+")):
        surf.text(x + 8 * sc, y + 18 * sc, glyph, fam, size, C["fg2"])
        hits.append(("alteredit:" + action, x, y + 3 * sc, 28 * sc, 30 * sc))
    bx = w - pad - 125 * sc
    enabled = bool(recipes) and not editor.get("busy")
    surf.round_rect(bx, y + 3 * sc, 125 * sc, 32 * sc, 6 * sc, fill=C["run"] if enabled else C["facbg"])
    surf.text(bx + 12 * sc, y + 19 * sc, "담는 중…" if editor.get("busy") else "등록 작업 담기", fam, size, "#ffffff" if enabled else C["dim"])
    if enabled:
        hits.append(("alteredit:add", bx, y + 3 * sc, 125 * sc, 32 * sc))
    message = editor.get("message") or "담은 뒤 돌아가서 ‘시작’을 누르면 실행합니다."
    surf.text(pad, y + 59 * sc, fit_text(surf, message, fam, size, False, w - 2 * pad), fam, size, C["fg2"])
    return w, h, hits


def paint_settings(surf, sc, C, locked, through, theme='classic', orientation='horizontal') -> tuple:
    """최상단 설정 버튼의 독립 드롭다운."""
    pad, top, head = 8 * sc, HEAD_TOP * sc, 28 * sc
    surf.resize(1200, 400)
    surf.clear()
    cw, ch, _ = controls(surf, -5000, -5000, sc, C, locked, through, quick=True)
    w, h = int(round(cw + 2 * pad)), int(round(top + head + 1 + pad + ch + pad + ch + pad + ch + pad + ch + pad))
    surf.resize(w, h)
    surf.clear()
    surf.round_rect(.5, .5, w - 1, h - 1, 14 * sc, fill=C["bg"], alpha=217)
    surf.round_rect(.5, .5, w - 1, h - 1, 14 * sc, outline=C["warnline2"], width=max(1., sc))
    fam, size, bold = _f("boldxs", "오버레이 설정", sc)
    surf.text(10 * sc, top + head / 2, "오버레이 설정", fam, size, C["gold"], bold)
    surf.text(w - 10 * sc, top + head / 2, "▴", fam, size, C["faint"], anchor="e")
    surf.rect(0, top + head, w, 1, C["sepfaint"])
    _, _, hits = controls(surf, pad, top + head + 1 + pad, sc, C, locked, through, quick=True)
    cx, cy = pad, top + head + 1 + pad + ch + pad
    for key, label in [('library:stock','재고'),('library:dict','사전'),('library:overlay','오버레이'),('library:settings','설정'),('quit','종료')]:
        pw, hit = pill(surf, cx, cy, label, C['fg2'], '', C['sep'], sc, key=key, pad=10)
        hits.append(hit)
        cx += pw + 6 * sc
    cy += ch + pad
    surf.text(pad, cy + ch / 2, '테마', fam, size, C['sub'])
    cx = pad + 42 * sc
    for value, label in [('classic', '클래식 골드'), ('night', '나이트 콘솔'), ('slim', '슬림 사이드')]:
        active = theme == value
        pw, hit = pill(surf, cx, cy, ('✓ ' if active else '') + label, (C['bg'] if theme=='night' else '#ffffff') if active else C['fg2'], C['gold'] if active else '', C['sep'], sc, key='skin:' + value, pad=8)
        hits.append(hit)
        cx += pw + 6 * sc
    cy += ch + pad
    surf.text(pad, cy + ch / 2, '배치', fam, size, C['sub'])
    cx = pad + 42 * sc
    for value, label in [('horizontal', '가로'), ('vertical', '세로')]:
        active = orientation == value
        pw, hit = pill(surf, cx, cy, ('✓ ' if active else '') + label, (C['bg'] if theme=='night' else '#ffffff') if active else C['fg2'], C['gold'] if active else '', C['sep'], sc, key='layout:' + value, pad=10)
        hits.append(hit)
        cx += pw + 6 * sc
    hits.append(("options", w - 24 * sc, 0, 24 * sc, top + head))
    return w, h, hits


def fit_text(surf, text, fam, size, bold, max_px) -> str:
    """폭에 맞게 끝을 「…」 로 줄인다 (7일 표의 산출 칸)."""
    t = str(text or "")
    if surf.measure(t, fam, size, bold) <= max_px:
        return t
    while len(t) > 1 and surf.measure(t + "…", fam, size, bold) > max_px:
        t = t[:-1]
    return t.rstrip(" ·") + "…"


def paint_panel(surf, data, sc, C, band_paint_cells, locked, through) -> tuple:
    """펼침 판 (대기 목록과 가공) — 머리(밴드 반복) · 대기 · 가공 · 컨트롤 줄."""
    w = int(round(420 * sc))
    pad = 12 * sc
    top = HEAD_TOP * sc
    head_h = 30 * sc
    line = 18 * sc
    days = data.get("days") or []      # 밴드의 오늘 한 줄을 눌러 열었을 때만
    rows = len(data["waits"]) + (1 if not data["waits"] else 0) + len(data["works"]) + len(days)
    labels = 1 + (1 if data["works"] else 0) + (1 if days else 0)
    h = int(round(top + head_h + 1 + 8 * sc + labels * 17 * sc + rows * line
                  + pad + 1 + pad + 26 * sc + pad))
    surf.resize(w, h)
    surf.clear()
    r = 14 * sc
    surf.round_rect(0.5, 0.5, w - 1, h - 1, r, fill=C["bg"], alpha=217)
    surf.round_rect(0.5, 0.5, w - 1, h - 1, r, outline=C["panelline"], width=max(1.0, sc))
    hits = []

    # 머리줄 — 밴드 칸을 그대로 다시
    band_paint_cells(surf, data.get("head") or [], 10 * sc, top + head_h / 2.0, sc)
    fam, size, bd = _f("xs", "▴", sc)
    surf.text(w - 10 * sc, top + head_h / 2.0, "▴", fam, size, C["faint"], anchor="e")
    hits.append(("expand", w - 24 * sc, 0, 24 * sc, top + head_h))
    surf.rect(0, top + head_h, w, 1, C["sepfaint"])

    y = top + head_h + 1 + 8 * sc

    def label(text):
        nonlocal y
        fam2, s2, b2 = _f("plabel", text, sc)
        surf.text(pad, y + 8 * sc, text, fam2, s2, C["label"])
        y += 17 * sc

    wait_top = y
    label(f"대기 {data['waitTotal']}")
    if not data["waits"]:
        fam2, s2, b2 = _f("p", "대기 중인 항목이 없습니다", sc)
        surf.text(pad, y + line / 2.0, "대기 중인 항목이 없습니다", fam2, s2, C["dim"])
        y += line
    for rw in data["waits"]:
        dim = rw["dim"]
        fam2, s2, b2 = _f("pmono", str(rw["n"]), sc)
        surf.text(pad, y + line / 2.0, str(rw["n"]), fam2, s2, C["dim2"] if dim else C["faint"])
        fam3, s3, b3 = _f("pmono", rw["name"], sc)
        surf.text(pad + 16 * sc, y + line / 2.0, rw["name"], fam3, s3, C["dim2"] if dim else C["fg2"])
        fam4, s4, b4 = _f("pmono", rw["detail"], sc)
        surf.text(w - pad, y + line / 2.0, rw["detail"], fam4, s4,
                  C["dim2"] if dim else C["sub"], anchor="e")
        y += line
    # 대기 구역을 누르면 앱 창의 큐 탭이 열린다
    hits.append(("queue", 0, wait_top, w, y - wait_top))
    if data["works"]:
        label(f"가공 {data['alterDone']}/{data['alterTotal']}")
        for wk in data["works"]:
            name = f"{wk['name']} ×{wk['n']}" if wk["n"] > 1 else wk["name"]
            fam2, s2, b2 = _f("pmono", name, sc)
            surf.text(pad, y + line / 2.0, name, fam2, s2, C["fg2"])
            fam3, s3, b3 = _f("pmonob", wk["text"], sc)
            surf.text(w - pad, y + line / 2.0, wk["text"], fam3, s3, wk["fg"], True, anchor="e")
            y += line
    if days:
        # 7일 표: 날짜 | 날개 | 산출 셋 (「외 n」). 최근 날이 위. 표를 누르면 접힌다.
        day_top = y
        label("최근 7일 · 날개 · 산출")
        # 날짜 | 날개(오른쪽 맞춤) | 실패 N(붉은색, 있는 날이 하나라도 있으면 칸을 연다) | 산출
        has_fail = any(int(d.get("failWings") or 0) for d in days)
        wx = pad + 82 * sc                                # 날개 오른쪽 끝
        fx = wx + 8 * sc                                  # 실패 칸 시작
        ox = (fx + 52 * sc) if has_fail else (wx + 10 * sc)   # 산출 시작
        dx = pad
        for i, d in enumerate(days):
            fg = C["fg2"] if i == 0 else C["sub"]
            fam2, s2, b2 = _f("pmono", d["d"], sc)
            surf.text(dx, y + line / 2.0, d["d"], fam2, s2, C["faint"])
            fw = int(d.get("failWings") or 0)
            wt = f"{d['wings']:,}" if d["wings"] else "—"
            fam3, s3, b3 = _f("pmonob", wt, sc)
            surf.text(wx, y + line / 2.0, wt, fam3, s3, C["gold"] if d["wings"] else C["dim"], True, anchor="e")
            if fw:
                fam5, s5, b5 = _f("pmono", f"실패 {fw:,}", sc)
                surf.text(fx, y + line / 2.0, f"실패 {fw:,}", fam5, s5, C["bad"])
            fam4, s4, b4 = _f("p", d["out"], sc)
            surf.text(ox, y + line / 2.0, fit_text(surf, d["out"], fam4, s4, b4, w - pad - ox),
                      fam4, s4, fg if d["out"] != "—" else C["dim"])
            y += line
        hits.append(("day", 0, day_top, w, y - day_top))

    ly = y + pad
    surf.rect(0, ly, w, 1, C["sepfaint"])
    ly += pad
    _cw, _ch, chits = controls(surf, pad, ly, sc, C, locked, through)
    hits += chits
    return w, h, [x for x in hits if x]
