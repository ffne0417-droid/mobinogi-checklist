"""오버레이 작업 추가: 기존 작업 큐를 쓰는 목록과 입력 변환."""
import work
import workqueue

KINDS = {"gather": "채집", "craft": "제작", "alter": "가공", "collect": "수령", "play": "연주", "notify": "알림"}
# 사용자가 제공한 게임 화면의 시설별 표시 순서. 동명 경로는 id로 따로 유지한다.
from alterfacilities import FACILITY_ORDER


def facility(recipe):
    name = recipe.get("name", "")
    for key, names in FACILITY_ORDER.items():
        if name in names:
            return key
    return str(recipe.get("facility") or recipe.get("cat") or "미분류").split()[0]


def catalog(snap, songs=(), playlists=()):
    rows = []
    for r in snap.get("gather", []):
        rows.append({"key": "gather:" + r["name"], "kind": "gather", "name": r["name"],
                     "category": r.get("skill") or "기타", "description": "도구 준비됨" if r.get("toolOk") else "도구 상태를 확인하세요",
                     "item": {"type": "gather", "name": r["name"]}, "default": 100, "max": 99999, "raw": r})
    for kind in ("craft", "alter"):
        pool = snap.get(kind, [])
        if kind == "alter":
            def rank(r):
                fac = facility(r)
                order = FACILITY_ORDER.get(fac, [])
                positions = [i for i, name in enumerate(order) if name == r.get("name")]
                variant = max(0, int(r.get("variant") or 1) - 1)
                position = positions[min(variant, len(positions)-1)] if positions else len(order) + 1
                return (list(FACILITY_ORDER).index(fac) if fac in FACILITY_ORDER else 99, position, variant)
            pool = sorted(pool, key=rank)
        for r in pool:
            name = r["name"] + (f" · 경로 {r.get('variant', 1)}" if r.get("variants", 1) > 1 else "")
            need = [{"name": n, "required": q} for n, q in (r.get("known") or {}).items()] or r.get("missing") or []
            materials = " · ".join(str(n.get("name", "")) + " " + str(n.get("required", n.get("count", 0))) for n in need)
            rows.append({"key": r["id"], "kind": kind, "name": name,
                         "category": facility(r) if kind == "alter" else r.get("cat") or "기타",
                         "description": (r.get("reasonKo") or "") + (" · 재료: " + materials if materials else ""),
                         "item": {"type": kind, "name": r["name"], "recipeId": r["id"]},
                         "default": 1, "max": 999, "raw": r, "blocked": bool(r.get("blocked")),
                         "materials": work.requirements(r, 1, snap.get("stock", {}), snap.get("storage", {}))})
    by_fac = {}
    for w in snap.get("works", []):
        if w.get("done"):
            by_fac.setdefault(w["facility"], []).append(w)
    for fac, works in by_fac.items():
        rows.append({"key": "collect:" + fac, "kind": "collect", "name": fac,
                     "category": "수령 가능", "description": f"완료 {len(works)}건 · 한 번에 수령 · 날개 0",
                     "item": {"type": "collect", "facility": fac, "name": works[0]["name"]}, "default": 1, "max": 1})
    rows.append({"key": "play:resume", "kind": "play", "name": "지금 연주 대기열 이어서", "category": "대기열 이어서",
                 "description": "폴리오의 현재 대기열을 이어갑니다 · 날개 0",
                 "item": {"type": "play", "mode": "resume"}, "default": 1, "max": 1})
    for song in songs:
        if not song.get("key"):
            continue
        rows.append({"key": "play:song:" + song["key"], "kind": "play", "name": song.get("title") or song["key"],
                     "category": "악보", "description": song.get("artist") or "선택한 곡만 연주 · 날개 0",
                     "item": {"type": "play", "mode": "song", "song": song["key"], "title": song.get("title", "")}, "default": 1, "max": 20})
    for pl in playlists:
        rows.append({"key": "play:list:" + pl["id"], "kind": "play", "name": pl.get("name") or "재생목록",
                     "category": "재생목록", "description": f"{len(pl.get('items') or [])}곡 · 그룹으로 담기 · 날개 0",
                     "item": {"type": "play", "mode": "list", "list": pl["id"], "listName": pl.get("name", "")}, "default": 1, "max": 20})
    rows.append({"key": "notify", "kind": "notify", "name": "작업 도착 알림", "category": "알림",
                 "description": "큐가 이 순서에 도착하면 알림 · 날개 0", "item": {"type": "notify"}, "default": 1, "max": 1})
    return rows


def filter_rows(rows, kind, query="", category="전체"):
    tokens = query.casefold().split()
    return [r for r in rows if (kind == "all" or r["kind"] == kind)
            and (category == "전체" or r["category"] == category)
            and all(t in (r["name"] + " " + r.get("description", "") + " " + r["category"]).casefold() for t in tokens)]


def payload(row, count, collect="none", chain=False, group="", text="", sound=True):
    try:
        count = int(count)
    except (TypeError, ValueError):
        raise ValueError("수량은 정수로 입력하세요.")
    if not 1 <= count <= row.get("max", 99999):
        raise ValueError(f"수량은 1~{row.get('max', 99999):,} 사이로 입력하세요.")
    item = dict(row["item"])
    if row["kind"] == "gather":
        item["target"] = count
    elif row["kind"] in ("craft", "alter", "play"):
        item["count"] = count
    if row["kind"] == "alter":
        item["collect"] = collect
    if row["kind"] == "notify":
        item.update(text=text.strip()[:80], sound=bool(sound))
    return {"item": item, "chain": bool(chain) and row["kind"] in ("craft", "alter"), "group": group}


def queue_rows(state):
    result = []
    def walk(items, parent=""):
        for item in items:
            if item.get("type") == "group":
                walk(item.get("items") or [], item.get("name") or "그룹")
            else:
                result.append(dict(item, groupName=parent))
    walk(state.get("items") or [])
    return result


def describe(row, count):
    """카드별 예상은 기존 큐 계산식을 사용한다. 선행 재료 작업은 담은 뒤 합계에 포함된다."""
    try:
        n = int(count)
        if not 1 <= n <= row.get("max", 99999):
            return "수량을 허용 범위 안으로 입력하세요."
    except (ValueError, TypeError):
        return "수량은 정수로 입력하세요."
    kind, raw = row["kind"], row.get("raw", {})
    if kind in ("craft", "alter"):
        calls = n if kind == "alter" else workqueue.craft_plan({**row["item"], "count": n})
        head = f"예상 생산 {n * (raw.get('per') or 1):,}개 · 이 작업 날개 약 {calls * workqueue.WINGS_PER_CALL:,}"
        mats = row.get("materials") or []
        detail = " · ".join(f"{m['name']} {m['owned']:,}/{m['requiredPer'] * n:,}" for m in mats[:3])
        if len(mats)>3:
            detail += f" · 외 {len(mats)-3}종"
        return head + "\n" + ("재료 보유/필요: " + detail if mats else "재료 정보가 없습니다. 갱신 후 확인하세요.") + "\n" + ("부족 재료 작업은 별도 소모 · 담은 뒤 합계 확인" if mats else "")
    if kind == "gather":
        return f"{n:,}개 채집 · 예상 {(n+99)//100}회 · 날개 약 {((n+99)//100)*workqueue.WINGS_PER_CALL:,}\n" + row.get("description", "")
    return row.get("description", "")
