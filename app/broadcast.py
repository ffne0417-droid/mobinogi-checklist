# -*- coding: utf-8 -*-
"""방송 모드 — 스트리머 PC 쪽 방 상태 (docs/handoff/broadcast-api.md).

손님은 스트리머 PC 의 Quick Tunnel 로 바로 붙는다. 우편함 Worker 는 **코드 → 터널 주소**만 건넨다.
이 모듈은 표준 라이브러리만 쓰고, 바깥(터널·우편함·폴리오 엔진·창 띄우기)은 전부 `configure()` 로 받는다 —
검사는 가짜를 꽂아 실제 cloudflared·우편함·게임 CLI 를 건드리지 않는다.

지키는 것 (계약 §7):
  · 손님이 보낸 글(이름)은 게임 채팅·연주 인사로 나가지 않는다 — 이 모듈은 그런 길을 부르지 않는다.
    이름은 방 상태와 대기열의 표시 칸(`_Q["req"]`)에만 들어간다.
  · 손님은 공개 목록 안의 key 만 신청한다. 자유 입력 없음.
  · 손님 토큰은 `secrets.token_urlsafe(18)` · 방송을 끄면 전부 무효.
  · CLI 를 부르지 않는다 — 「지금 연주 중」은 엔진이 이미 들고 있는 값(`_NOW`)에서 읽는다.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
import unicodedata
import urllib.error
import urllib.request

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # 헷갈리는 글자(0 O 1 I) 뺀 32자
CODE_LEN = 8                   # 새 코드 길이 (표시 XXXX-XXXX). 우편함 Worker 가 같은 길이로 만든다
CODE_RX = re.compile(r"^(?:[{a}]{{6}}|[{a}]{{8}})$".format(a=ALPHABET))   # 8자 + 옛 6자 (만료 전까지) · 7자는 거절
NAME_MAX = 12                  # 손님 이름 상한 (자른다)
NAME_DEFAULT = "익명"
MINE_MAX = 20                  # 손님 「내 신청」 최근 개수
DONE_MAX = 20                  # 스트리머 「처리됨」 최근 개수
JOIN_PER_MIN = 3               # 같은 곳(IP)에서 들어가기 — 분당
JOIN_ALL_PER_MIN = 60          # 들어가기 합계 — 분당 (어디서 왔든)
REQ_PER_MIN = 6                # 손님 한 명의 신청 — 분당 (간격 규칙과 별개) · 토큰과 보낸 곳 두 바구니로 센다
GUESTS_MAX = 500               # 손님 기록 상한 — 넘치면 가장 오래 안 본 손님부터 걷는다
GUEST_GC_SEC = 30 * 60.0       # 이만큼 안 보인 손님 기록은 감시가 걷는다
MAILBOX_REFRESH_SEC = 6 * 3600.0   # 우편함 코드 수명(12시간)을 이 주기로 다시 적어 늘린다
LIVE_MAX_SEC = 12 * 3600.0     # 방송 한 번의 최대 길이 — 넘으면 저절로 끈다
MB_WRITES_PER_MIN = 4          # 우편함 쓰기(POST /bc · PUT /bc) — 분당. 우편함 한도(같은 IP 분당 5)보다 하나 적게
MB_BACKOFF = (5, 10, 20, 40, 80, 160, 300)   # 우편함 쓰기가 실패했을 때 다음 시도까지(초) — 실패할수록 길게
MB_ERRORS = {                  # 우편함 오류 → 방송 창 안내
    "not_mobiworks": "우편함이 이 PC 에 아직 닿지 못해 코드를 받지 못했습니다 — 터널이 열리는 중일 수 있어요. 잠시 뒤 다시 시도합니다.",
    "budget": "우편함의 하루 한도를 다 써서 코드를 받지 못했습니다 — 한 시간 뒤 다시 시도합니다.",
    "rate": "우편함에 너무 자주 요청해 코드를 받지 못했습니다 — 잠시 뒤 다시 시도합니다.",
    "too_large": "우편함이 요청을 받지 않았습니다 — 코드를 받지 못했습니다.",
    "mailbox": "우편함에 닿지 못해 코드를 받지 못했습니다 — 잠시 뒤 다시 시도합니다.",
}
APPENDED_KEEP = 200           # 「담겼고 아직 차례가 오지 않은 신청」 기억 상한 (대기 상한 최대 99 보다 넉넉히)
RETRY_MAX = 5                  # 터널이 끊겼을 때 다시 잇는 횟수
TICK_SEC = 2.0                 # 감시 주기
GUEST_ALIVE_SEC = 30.0         # 손님 수 — 이 안에 한 번이라도 두드린 손님만 센다 (손님 화면은 5초마다 읽는다)
INTERVAL_RANGE = (1, 30)       # 1인 신청 간격(분)
CAP_RANGE = (1, 99)            # 대기 신청 상한

_DROP_CATS = {"Cc", "Cf", "Cs", "Co", "Cn"}          # 제어·서식(방향 표식 포함)·대리·사용자 정의·미할당
_BLANK_LOOKS = {"\u3164", "\uffa0", "\u115f", "\u1160", "\u2800"}   # 글자로 분류되지만 빈칸으로 보이는 것 (한글 채움·점자 빈칸)
_MARKS_RUN = 2                                        # 결합 기호는 한 글자에 이만큼까지


def clean_name(v) -> str:
    """손님 이름 — NFC 로 맞추고, 보이지 않는 글자(제어·서식·방향 표식·채움 글자)를 빼고,
    겹겹이 쌓인 결합 기호를 줄이고, 12자로 자른다. 글자·숫자가 하나도 없으면 「익명」."""
    s = unicodedata.normalize("NFC", v if isinstance(v, str) else "")
    out, run = [], 0
    for ch in s:
        cat = unicodedata.category(ch)
        if cat in _DROP_CATS or ch in _BLANK_LOOKS:
            continue
        if cat in ("Mn", "Me"):
            run += 1
            if run > _MARKS_RUN:
                continue
        else:
            run = 0
        out.append(" " if cat[0] == "Z" else ch)
    s = re.sub(r"\s+", " ", "".join(out)).strip()[:NAME_MAX].strip()
    if not any(unicodedata.category(c)[0] in "LN" for c in s):
        return NAME_DEFAULT
    return s


def norm_code(v) -> str:
    """입력 코드 — 대소문자·`-`·공백 무시."""
    return re.sub(r"[\s\-]", "", v if isinstance(v, str) else "").upper()[:16]


def show_code(code: str) -> str:
    """`7K2Q9MXP` → `7K2Q-9MXP` · 옛 6자 `7K2Q9M` → `7K2Q-9M` (4자 + `-` + 나머지)."""
    return f"{code[:4]}-{code[4:]}" if code else ""


# ── 바깥 ────────────────────────────────────────────────────────────────
def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 15.0) -> dict:
    """우편함 부르기. 답이 JSON 객체가 아니면 ok:false.
    오류 답(4xx·5xx)도 몸의 `error` 를 읽어 그대로 올린다 — `not_mobiworks`·`budget`·`too_large`·`rate` 등.
    `Retry-After` 가 있으면 `retry_after`(초)로 싣는다."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", "User-Agent": "MobiWorks"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read(4096).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        got = {}
        try:
            got = json.loads(e.read(4096).decode("utf-8", "replace"))
        except Exception:
            pass
        err = got.get("error") if isinstance(got, dict) and isinstance(got.get("error"), str) else ""
        if not err:
            err = "rate" if e.code == 429 else "budget" if e.code == 503 else "too_large" if e.code == 413 else "mailbox"
        out = {"ok": False, "error": err[:40], "status": e.code}
        try:
            ra = int(e.headers.get("Retry-After") or 0)
        except (TypeError, ValueError):
            ra = 0
        if ra > 0:
            out["retry_after"] = min(ra, 24 * 3600)
        return out
    except Exception as e:
        return {"ok": False, "error": "mailbox", "message": f"{type(e).__name__}"}
    return out if isinstance(out, dict) else {"ok": False, "error": "mailbox"}


class OfflineTunnel:
    """개발·검사용 가짜 터널 — cloudflared 를 띄우지 않는다. 주소는 닿지 않는 이름이다 (이 PC 안에서 손님 길을 시험할 때만)."""
    HOST = "bc-offline.trycloudflare.com"

    def __init__(self):
        self._on = False

    def start(self, port, on_url=None) -> dict:
        self._on = True
        if on_url:
            on_url("https://" + self.HOST)
        return {"ok": True}

    def stop(self) -> dict:
        self._on = False
        return {"ok": True}

    def state(self) -> dict:
        return {"ok": True, "running": self._on, "url": ("https://" + self.HOST) if self._on else "",
                "busy": "", "ready": self._on, "error": ""}


def offline_http(method: str, url: str, body: dict | None = None, **_kw) -> dict:
    """개발·검사용 가짜 우편함 — 밖으로 나가지 않고 코드만 만든다."""
    if method == "POST" and url.endswith("/bc"):
        return {"ok": True, "code": "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN)),
                "secret": secrets.token_urlsafe(18), "ttl": 43200}
    return {"ok": True}


HOOKS: dict = {
    "mailbox": lambda: "https://link.mobimml.com",   # 우편함 뿌리 주소 (server.MAILBOX)
    "http": _http_json,                               # (method, url, body) → dict
    "tunnel": None,                                   # () → 터널 (start(port, on_url) · stop() · state())
    "port": lambda: 0,
    "on_url": None,                                   # 터널 주소가 나왔을 때 (server._tunnel_got_url)
    "remote_in_use": lambda: False,                   # 원격 리모컨이 터널을 쓰는가 (끌 때 터널을 닫을지)
    "activity": lambda: None,                         # 손님 요청을 터널 활동으로 센다 (유휴 자동 닫기)
    "engine": None,                                   # () → 폴리오 엔진 모듈
    "settings": None,                                 # () → 설정 dict
    "save": None,                                     # (patch) → 설정 저장
    "open_window": lambda: {"ok": False, "error": "no_window"},
    "say": lambda msg: None,
    "thread": False,                                  # 감시 스레드를 띄울지 (검사는 끄고 tick() 을 직접 부른다)
}


def configure(**kw) -> None:
    for k, v in kw.items():
        if k not in HOOKS:
            raise KeyError(k)
        HOOKS[k] = v


def _say(msg: str) -> None:
    try:
        HOOKS["say"](msg)
    except Exception:
        pass


def _clamp(v, lo, hi, dflt):
    if isinstance(v, bool):
        return dflt
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return dflt
    return max(lo, min(hi, n))


# ── 방 ──────────────────────────────────────────────────────────────────
class Room:
    """방송 하나 (앱에 하나). 모든 바꿈은 `_lock` 안에서, 바깥 부르기(우편함·터널)는 자물쇠 밖에서."""

    def __init__(self):
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_end: dict | None = None   # 저절로 꺼진 까닭 (방송 창 안내) — reset 이 지우지 않는다. 켜면 지운다
        self.mb_writes: list = []     # 우편함 쓰기 시각 — 우편함 한도는 IP 단위라 껐다 켜도 이어서 센다
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.on = False
            self.since = 0.0
            self.code = ""
            self.secret = ""
            self.url = ""                 # 우편함에 적어 둔 터널 주소
            self.reg_at = 0.0             # 우편함에 코드를 마지막으로 적은 시각 (수명 늘리기)
            self.mb_fails = 0             # 우편함 쓰기 연속 실패 수
            self.mb_next = 0.0            # 이 시각 전에는 우편함에 다시 쓰지 않는다 (실패 뒤 기다림)
            self.mb_err = ""              # 마지막 우편함 오류 (방송 창 안내) — 성공하면 지운다
            self.guests: dict = {}        # 토큰 → {name, who, blocked, last_req, req_times, seen}
            self.who_state: dict = {}     # 보낸 곳 → {last_req, req_times} — 토큰을 여러 개 받아도 같이 센다
            self.blocked_who: set = set() # 끊긴 보낸 곳 — 다시 들어오지 못한다 (방송을 끄면 비운다)
            self.join_all: list = []      # 들어가기 합계 [시각…]
            self.appended: list = []      # 신청으로 담은 곡 [{id, key, idx, gen}] — 아직 차례가 오지 않은 것만 남긴다
            self.wait: list = []          # 대기 신청 (들어온 차례)
            self.done: list = []          # 처리됨 (최근이 앞)
            self.mine: dict = {}          # 토큰 → 그 손님의 신청 id (최근이 앞)
            self.reqs: dict = {}          # id → 신청 (wait·done 모두)
            self.seq = 0
            self.conn = "off"
            self.retry = 0
            self.busy = ""                # 여는 중 (코드가 아직 없다)
            self.ever_ok = False
            self.started = False          # 이번 방송에서 터널을 한 번 열어 봤나
            self.join_hits: dict = {}     # 보낸 곳 → [시각…]
            self.pl_cache = (0.0, "", None)

    # ── 설정 (store 설정에 산다) ──
    def cfg(self) -> dict:
        s = HOOKS["settings"]() if HOOKS["settings"] else {}
        return {"interval_min": _clamp(s.get("bc_interval_min"), *INTERVAL_RANGE, 3),
                "cap": _clamp(s.get("bc_cap"), *CAP_RANGE, 20),
                "auto": bool(s.get("bc_auto"))}

    def _pl_id(self) -> str:
        s = HOOKS["settings"]() if HOOKS["settings"] else {}
        return str(s.get("bc_pl") or "")

    def set_cfg(self, p: dict) -> dict:
        patch = {}
        if "interval_min" in p:
            patch["bc_interval_min"] = _clamp(p.get("interval_min"), *INTERVAL_RANGE, self.cfg()["interval_min"])
        if "cap" in p:
            patch["bc_cap"] = _clamp(p.get("cap"), *CAP_RANGE, self.cfg()["cap"])
        if "auto" in p and isinstance(p.get("auto"), bool):
            patch["bc_auto"] = p["auto"]
        if patch and HOOKS["save"]:
            HOOKS["save"](patch)
        return self.cfg()

    # ── 공개 목록 ──
    def _eng(self):
        return HOOKS["engine"]() if HOOKS["engine"] else None

    def playlists(self) -> list:
        eng = self._eng()
        if eng is None:
            return []
        try:
            return list(eng._lists().get("playlists") or [])
        except Exception:
            return []

    def public(self) -> dict | None:
        """공개 목록 {id, name, songs:[{key,title,artist,sec}]} — 없으면 None. 2초 동안 같은 값을 쓴다."""
        now = time.time()
        pid = self._pl_id()
        at, cid, cached = self.pl_cache
        if cached is not None and cid == pid and now - at < 2.0:
            return cached
        pls = self.playlists()
        pl = next((x for x in pls if x.get("id") == pid), None) or (pls[0] if pls else None)
        out = None
        if pl is not None:
            eng = self._eng()
            by, dur = {}, {}
            try:
                by = {it["key"]: it for it in eng._build_items()}
                dur = eng.store.get_durations()
            except Exception:
                pass
            songs = []
            for it in pl.get("items") or []:
                k = str(it.get("key") or "")
                if not k:
                    continue
                lib = by.get(k) or {}
                t = lib.get("title") or it.get("title") or k
                songs.append({"key": k, "title": str(lib.get("song") or lib.get("cleaned") or t),
                              "artist": str(lib.get("artist") or ""), "sec": dur.get(t)})
            out = {"id": str(pl.get("id") or ""), "name": str(pl.get("name") or ""), "songs": songs}
        self.pl_cache = (now, pid, out)
        return out

    def _queue(self) -> dict:
        eng = self._eng()
        try:
            return eng.queue_state() if eng is not None else {}
        except Exception:
            return {}

    def _now(self, q: dict | None = None) -> dict | None:
        """지금 연주 중 — 엔진이 이미 본 값. CLI 를 부르지 않는다."""
        eng = self._eng()
        now = getattr(eng, "_NOW", None) if eng is not None else None
        if not isinstance(now, dict) or not now.get("playing"):
            return None
        q = q if q is not None else self._queue()
        it = q.get("now") if isinstance(q.get("now"), dict) else None
        title = str(now.get("title") or "")
        seen = float(now.get("at") or 0)
        gone = max(0.0, time.time() - seen) if seen else 0.0      # 감시가 마지막으로 본 뒤 흐른 시간
        left = max(0, int(float(now.get("tot") or 0) - float(now.get("el") or 0) - gone))
        if it and (it.get("title") == title or not title):
            return {"key": it.get("key") or "", "title": it.get("song") or it.get("title") or title,
                    "artist": it.get("artist") or "", "left": left}
        return {"key": "", "title": title, "artist": "", "left": left}

    # ── 상태 ──
    def _guests_alive(self) -> int:
        if self.conn == "down":
            return 0
        cut = time.time() - GUEST_ALIVE_SEC
        return sum(1 for g in self.guests.values() if g["seen"] >= cut)

    def _pos_in_queue(self, q: dict) -> dict:
        """key → 현재 재생목록에서 처음 나오는 자리 (1부터)."""
        out = {}
        for i, it in enumerate(q.get("items") or []):
            out.setdefault(it.get("key"), i + 1)
        return out

    def _held(self, q: dict, playing: bool) -> int:
        """신청으로 담았고 아직 차례가 오지 않은 곡 수 (자동 승인일 때 상한에 센다). 지나간 것은 걷는다.

        자리는 담을 때 받은 차례(`pos`)와 대기열 세대(`gen`)로 기억한다. 대기열이 새로 만들어지면(세대가 바뀌면)
        담긴 곡도 사라진 것이다. 다른 곡이 끼어들거나 차례가 다시 섞여 자리가 밀렸으면, 지금 곡 뒤에서
        같은 key 를 찾아 그 자리로 옮기고, 없으면 지나간 것으로 본다. 지금 곡 자리에 있고 연주 중이면 차례가 온 것이다.
        자물쇠 안에서 부른다."""
        items = q.get("items") if isinstance(q, dict) else None
        if not isinstance(items, list):
            return len(self.appended)             # 대기열을 못 읽었다 — 줄이지 않고 그대로 센다
        pos = q.get("pos") if isinstance(q.get("pos"), int) else -1
        gen = q.get("gen")
        keep = []
        for e in self.appended:
            if e["gen"] != gen:
                continue
            i = e["idx"]
            if not (0 <= i < len(items)) or items[i].get("key") != e["key"]:
                i = next((j for j in range(max(pos + 1, 0), len(items)) if items[j].get("key") == e["key"]), -1)
                if i < 0:
                    continue
                e["idx"] = i
            if i < pos or (i == pos and playing):
                continue
            keep.append(e)
        self.appended = keep
        return len(keep)

    def _is_full(self, cfg: dict, held: int) -> bool:
        """대기 상한 — 대기 수, 자동 승인이면 담겼고 아직 차례가 오지 않은 수도 더한다."""
        return len(self.wait) + (held if cfg["auto"] else 0) >= cfg["cap"]

    def _blocked(self, g: dict) -> bool:
        return bool(g["blocked"]) or g.get("who") in self.blocked_who

    def summary(self) -> dict:
        """본창·오버레이의 「방송 · 신청 n」 — 가볍게."""
        with self._lock:
            return {"on": self.on, "wait": len(self.wait)}

    def state(self) -> dict:
        pub = self.public()
        q = self._queue()
        nowp = self._now(q)
        at_q = self._pos_in_queue(q)
        with self._lock:
            cfg = self.cfg()
            held = self._held(q, nowp is not None)
            out = {"on": self.on, "since": int(self.since) if self.on else 0, "code": self.code,
                   "conn": self.conn if self.on else "off",
                   "guests": self._guests_alive() if self.on else 0,
                   "cfg": cfg, "busy": self.busy if self.on else "",
                   "link": (HOOKS["mailbox"]().rstrip("/") + "/live/?c=" + self.code) if (self.on and self.code) else "",
                   "wait": [{"id": r["id"], "key": r["key"], "title": r["title"], "sec": r["sec"], "who": r["who"],
                             "at": int(r["at"]), "dup": at_q.get(r["key"])} for r in self.wait],
                   "done": [{"id": r["id"], "title": r["title"], "who": r["who"], "state": r["state"],
                             "pos": r.get("pos"), "at": int(r["done_at"])} for r in self.done[:DONE_MAX]],
                   "pl": None, "playlists": [{"id": str(p.get("id") or ""), "name": str(p.get("name") or ""),
                                              "count": len(p.get("items") or [])} for p in self.playlists()]}
            # 덧붙임 — 상한 판정(자동 승인이면 담겼고 아직 차례가 오지 않은 곡도 센다)과 그 수
            out["held"] = held if self.on else 0
            out["full"] = bool(self.on and self._is_full(cfg, held))
            if self.on and self.mb_err:
                # 덧붙임 — 우편함 오류 (방송 창 안내) · next = 다시 시도까지 남은 초
                out["mailbox"] = {"error": self.mb_err, "message": MB_ERRORS.get(self.mb_err, MB_ERRORS["mailbox"]),
                                  "next": max(0, int(self.mb_next - time.time() + 0.999))}
            if not self.on and self.last_end:
                out["ended"] = dict(self.last_end)     # 덧붙임 — 저절로 꺼진 까닭 (방송 창 안내)
            if self.conn == "down" and self.on:
                out["retry"] = {"n": self.retry, "max": RETRY_MAX}
            if pub is not None:
                out["pl"] = {"id": pub["id"], "name": pub["name"], "count": len(pub["songs"]),
                             "songs": [dict(s, playing=bool(nowp and nowp["key"] and s["key"] == nowp["key"]))
                                       for s in pub["songs"]]}
            return out

    # ── 켜고 끄기 ──
    def turn_on(self, pl=None) -> dict:
        if isinstance(pl, str) and pl:
            if not any(p.get("id") == pl for p in self.playlists()):
                return {"ok": False, "error": "not_found", "message": "그 재생목록이 없습니다."}
            if HOOKS["save"]:
                HOOKS["save"]({"bc_pl": pl})
            self.pl_cache = (0.0, "", None)
        elif not self._pl_id():
            pls = self.playlists()
            if pls and HOOKS["save"]:
                HOOKS["save"]({"bc_pl": str(pls[0].get("id") or "")})
        with self._lock:
            if not self.on:
                self.reset()
                self.on, self.since = True, time.time()
                self.conn, self.busy = "ok", "여는 중"
                self.last_end = None
        _say("[bc] 방송을 켭니다")
        self._start_worker()
        self._wake.set()
        return {"ok": True}

    def turn_off(self, why: str = "") -> dict:
        """끈다. `why` 가 있으면(저절로 끈 경우) 방송 창이 그 까닭을 안내한다."""
        with self._lock:
            was_on, code, secret = self.on, self.code, self.secret
            self.reset()
            self.last_end = {"why": why, "at": int(time.time()), "hours": int(LIVE_MAX_SEC // 3600)} \
                if (was_on and why) else None
        if was_on:
            _say(f"[bc] 방송을 끕니다{' (' + why + ')' if why else ''}")
            self._wake.set()
            threading.Thread(target=self._close_out, args=(code, secret), daemon=True).start()
        return {"ok": True}

    def _close_out(self, code: str, secret: str) -> None:
        """끈 뒤처리 — 우편함에서 코드를 지우고, 원격 리모컨이 안 쓰면 터널을 닫는다."""
        if code and secret:
            HOOKS["http"]("DELETE", self._mb(f"/bc/{code}"), {"secret": secret})
        try:
            if not HOOKS["remote_in_use"]() and HOOKS["tunnel"]:
                HOOKS["tunnel"]().stop()
        except Exception as e:
            _say(f"[bc] 터널을 닫지 못했습니다: {type(e).__name__}")

    def shutdown(self) -> None:
        """앱을 끌 때 — 우편함에서 코드를 지운다 (짧게 기다린다. 못 지워도 우편함의 12시간 수명이 거둔다)."""
        with self._lock:
            code, secret, on = self.code, self.secret, self.on
            self.reset()
        if on and code and secret:
            try:
                HOOKS["http"]("DELETE", self._mb(f"/bc/{code}"), {"secret": secret}, timeout=3.0)
            except Exception:
                pass

    def _mb(self, path: str) -> str:
        return HOOKS["mailbox"]().rstrip("/") + path

    def new_code(self) -> dict:
        with self._lock:
            if not self.on:
                return {"ok": False, "error": "ended", "message": "방송이 꺼져 있습니다."}
            url, old, old_secret = self.url, self.code, self.secret
        if not url:
            return {"ok": False, "error": "no_tunnel", "message": "아직 터널 주소가 없습니다. 잠시 뒤에 다시 해 보세요."}
        got, skipped = self._register(url)
        if skipped:
            return {"ok": False, "error": "mailbox_wait",
                    "message": "우편함에 잠시 전에 요청했습니다. 조금 뒤에 다시 해 보세요."}
        if not got:
            with self._lock:
                err = self.mb_err or "mailbox"
            return {"ok": False, "error": err, "message": MB_ERRORS.get(err, MB_ERRORS["mailbox"])}
        with self._lock:
            if not self.on:
                return {"ok": False, "error": "ended"}
            self.code, self.secret, self.url = got["code"], got["secret"], url
            self.reg_at = time.time()
        if old and old_secret:
            HOOKS["http"]("DELETE", self._mb(f"/bc/{old}"), {"secret": old_secret})
        _say("[bc] 코드를 새로 받았습니다")
        return {"ok": True, "code": got["code"]}

    # ── 우편함 쓰기 한도 ──
    # 우편함은 쓰기(POST /bc · PUT /bc 등)를 같은 IP 분당 5번으로 막는다. 켜기·코드 새로 받기·주소 바뀜·
    # 수명 늘리기가 모두 이 한 바구니를 같이 쓰고(분당 MB_WRITES_PER_MIN), 실패하면 MB_BACKOFF 만큼 기다린다.
    def _mb_reserve(self, now: float) -> bool:
        """지금 우편함에 써도 되면 한 칸을 잡는다. 자물쇠 안에서 부른다."""
        self.mb_writes[:] = [t for t in self.mb_writes if now - t < 60.0]
        if now < self.mb_next or len(self.mb_writes) >= MB_WRITES_PER_MIN:
            return False
        self.mb_writes.append(now)
        return True

    def _mb_done(self, ok: bool, out: dict) -> None:
        """쓰기 결과를 적는다 — 실패면 오류 종류와 다음 시도 시각. 자물쇠 안에서 부른다."""
        if ok:
            self.mb_fails, self.mb_next, self.mb_err = 0, 0.0, ""
            return
        self.mb_fails += 1
        err = out.get("error") if isinstance(out, dict) else ""
        err = err if err in MB_ERRORS else "mailbox"
        delay = MB_BACKOFF[min(self.mb_fails, len(MB_BACKOFF)) - 1]
        ra = out.get("retry_after") if isinstance(out, dict) else None
        if err == "budget":
            delay = max(delay, ra if isinstance(ra, int) and ra > 0 else 3600)
        elif isinstance(ra, int) and ra > 0:
            delay = max(delay, ra)
        self.mb_err, self.mb_next = err, time.time() + delay

    def _register(self, url: str) -> tuple:
        """우편함에 코드를 만든다 → (코드·비밀 dict 또는 None, 한도 때문에 건너뛰었나)."""
        with self._lock:
            if not self._mb_reserve(time.time()):
                return None, True
        out = HOOKS["http"]("POST", self._mb("/bc"), {"url": url})
        out = out if isinstance(out, dict) else {"ok": False, "error": "mailbox"}
        code = str(out.get("code") or "").strip().upper()
        secret = out.get("secret")
        good = not (out.get("ok") is False or not CODE_RX.match(code) or not isinstance(secret, str)
                    or not 0 < len(secret) <= 200)
        with self._lock:
            self._mb_done(good, out if out.get("ok") is False else {"error": "mailbox"})
        return ({"code": code, "secret": secret} if good else None), False
    # ── 감시 (터널 · 우편함) ──
    def _start_worker(self) -> None:
        if not HOOKS["thread"]:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="bc-watch")
        self._thread.start()

    def _loop(self) -> None:
        while True:
            self._wake.wait(TICK_SEC)
            self._wake.clear()
            with self._lock:
                if not self.on:
                    self._thread = None
                    return
            try:
                self.tick()
            except Exception as e:
                _say(f"[bc] 감시가 넘어졌습니다: {type(e).__name__}: {e}")

    def tick(self) -> None:
        """한 번 본다: 최대 길이를 넘었나 → 오래된 손님 기록 걷기 → 터널이 살아 있나 → 우편함에 코드가 있나
        → 터널 주소가 바뀌었나 → 우편함 코드 수명 늘리기."""
        now = time.time()
        with self._lock:
            if not self.on:
                return
            over = now - self.since >= LIVE_MAX_SEC
        if over:
            self.turn_off(why="max_hours")
            return
        self._sweep(now)
        if not HOOKS["tunnel"]:
            return
        t = HOOKS["tunnel"]()
        st = t.state()
        if not st.get("running") and not st.get("busy"):
            # 터널이 없다 — 처음이면 연다. 한 번 열었는데 없으면 끊긴 것이다 → 다시 잇기 (RETRY_MAX 번까지)
            with self._lock:
                if self.started:
                    self.conn = "down"
                    if self.retry >= RETRY_MAX:
                        return
                    self.retry += 1
                self.started = True
            HOOKS["activity"]()                       # 유휴 시계를 되감는다 — 다시 연 터널을 곧바로 닫지 않게
            t.start(HOOKS["port"](), on_url=HOOKS["on_url"])
            return
        with self._lock:
            self.started = True
        url = str(st.get("url") or "")
        if not url:
            return                                    # 여는 중 — 주소를 기다린다
        with self._lock:
            code, secret, reg = self.code, self.secret, self.url
        if not code:
            # 터널 주소가 선 뒤에만 코드를 만든다 — 우편함이 그 주소의 /api/health 를 먼저 확인한다
            got, skipped = self._register(url)
            if skipped:
                return                                # 우편함 쓰기 한도·기다림 — 다음 감시 때
            with self._lock:
                if not self.on:
                    return
                if got:
                    self.code, self.secret, self.url = got["code"], got["secret"], url
                    self.reg_at = time.time()
                    self._ok()
                elif self.mb_err == "not_mobiworks" and self.mb_fails <= 3 and not self.ever_ok:
                    self.busy = "우편함 확인 중"         # 막 연 터널이 아직 밖에서 안 닿는다 — 여는 중으로 둔다
                else:
                    self._fail()
            return
        with self._lock:
            stale = now - self.reg_at >= MAILBOX_REFRESH_SEC
            need = url != reg or stale
            go = need and self._mb_reserve(now)
        if need and not go:
            return                                    # 우편함 쓰기 한도·기다림 — 다음 감시 때
        if go:
            # 주소가 바뀌었거나, 우편함 코드 수명(12시간)이 반을 넘었다 — 다시 적는다 (수명이 새로 선다)
            out = HOOKS["http"]("PUT", self._mb(f"/bc/{code}"), {"url": url, "secret": secret})
            out = out if isinstance(out, dict) else {"ok": False, "error": "mailbox"}
            with self._lock:
                self._mb_done(bool(out.get("ok")), out)
                if not self.on or self.code != code:
                    return
                if out.get("ok"):
                    self.url = url
                    self.reg_at = time.time()
                    self._ok()
                else:
                    self._fail()
            return
        with self._lock:
            self._ok()

    def _sweep(self, now: float) -> None:
        """오래 안 보인 손님 기록·보낸 곳 바구니를 걷고, 지나간 신청 곡을 상한 셈에서 뺀다."""
        q = self._queue()
        playing = self._now(q) is not None
        with self._lock:
            if not self.on:
                return
            for tok in [t for t, g in self.guests.items() if now - g["seen"] > GUEST_GC_SEC]:
                self.guests.pop(tok, None)
                self.mine.pop(tok, None)
            keep_s = INTERVAL_RANGE[1] * 60.0
            for w in [w for w, s in self.who_state.items()
                      if now - s["last_req"] > keep_s and not any(now - t < 60.0 for t in s["req_times"])]:
                self.who_state.pop(w, None)
            self._held(q, playing)
            self._gc_reqs()

    def _ok(self) -> None:
        self.conn, self.busy, self.retry, self.ever_ok = "ok", "", 0, True

    def _fail(self) -> None:
        self.conn = "down"
        self.retry = min(RETRY_MAX, self.retry + 1)

    def tunnel_host(self) -> str:
        with self._lock:
            u = self.url
        return u.split("://", 1)[-1].strip("/").lower() if u else ""

    # ── 스트리머 조작 ──
    def _take(self, rid: str):
        r = self.reqs.get(rid)
        if r is None or r["state"] != "wait":
            return None
        self.wait = [x for x in self.wait if x["id"] != rid]
        return r

    def _finish(self, r: dict, state: str, pos=None) -> None:
        r["state"], r["done_at"] = state, time.time()
        if pos is not None:
            r["pos"] = pos
        self.done.insert(0, r)
        del self.done[DONE_MAX * 2:]
        self._gc_reqs()

    def _gc_reqs(self) -> None:
        """대기·처리됨·손님의 「내 신청」 어디에서도 가리키지 않는 신청을 걷는다. 자물쇠 안에서 부른다."""
        live = {x["id"] for x in self.wait} | {x["id"] for x in self.done}
        for ids in self.mine.values():
            live.update(ids)
        for rid in [rid for rid in self.reqs if rid not in live]:
            del self.reqs[rid]

    def approve(self, rid: str) -> dict:
        with self._lock:
            r = self._take(str(rid or ""))
            if r is None:
                return {"ok": False, "error": "not_found", "message": "대기 중인 신청이 아닙니다."}
        return self._append(r)

    def _append(self, r: dict) -> dict:
        eng = self._eng()
        try:
            out = eng.queue_append(r["key"], r["who"]) if eng is not None else {"ok": False}
        except Exception as e:
            out = {"ok": False, "error": type(e).__name__}
        gen = self._queue().get("gen") if out.get("ok") else None
        with self._lock:
            if not out.get("ok"):                    # 담지 못했다 — 대기로 되돌린다
                r["state"] = "wait"
                self.wait.insert(0, r)
                return {"ok": False, "error": out.get("error") or "queue", "message": "재생목록에 담지 못했습니다."}
            pos = int(out.get("pos") or 0)
            if pos > 0:
                self.appended.append({"id": r["id"], "key": r["key"], "idx": pos - 1, "gen": gen})
                del self.appended[:-APPENDED_KEEP]
            self._finish(r, "ok", pos)
        return {"ok": True, "id": r["id"], "pos": r["pos"]}

    def reject(self, rid=None, all_=False) -> dict:
        with self._lock:
            ids = [x["id"] for x in self.wait] if all_ else [str(rid or "")]
            n = 0
            for i in ids:
                r = self._take(i)
                if r is not None:
                    self._finish(r, "no")
                    n += 1
            if not n and not all_:
                return {"ok": False, "error": "not_found", "message": "대기 중인 신청이 아닙니다."}
        return {"ok": True, "n": n}

    def block(self, rid: str) -> dict:
        with self._lock:
            r = self.reqs.get(str(rid or ""))
            if r is None:
                return {"ok": False, "error": "not_found", "message": "그 신청이 없습니다."}
            g = self.guests.get(r["guest"])
            if g is not None:
                g["blocked"] = True
            who = r.get("from")
            if who:
                self.blocked_who.add(who)              # 같은 곳에서 받은 다른 토큰·새로 들어오기도 막는다
            for x in [x for x in self.wait if x["guest"] == r["guest"] or (who and x.get("from") == who)]:
                self._take(x["id"])
                self._finish(x, "cut" if x is r else "no")
        return {"ok": True}

    def set_pl(self, pid) -> dict:
        if not isinstance(pid, str) or not any(p.get("id") == pid for p in self.playlists()):
            return {"ok": False, "error": "not_found", "message": "그 재생목록이 없습니다."}
        if HOOKS["save"]:
            HOOKS["save"]({"bc_pl": pid})
        self.pl_cache = (0.0, "", None)
        return {"ok": True}

    # ── 손님 ──
    def _rate(self, bucket: list, limit: int, now: float) -> bool:
        """분당 상한을 넘었나 (넘지 않았으면 이번 것을 센다)."""
        if self._full_min(bucket, limit, now):
            return True
        bucket.append(now)
        return False

    @staticmethod
    def _full_min(bucket: list, limit: int, now: float) -> bool:
        """분당 상한에 닿았나 — 세지는 않는다 (지난 1분 밖은 걷는다)."""
        bucket[:] = [t for t in bucket if now - t < 60.0]
        return len(bucket) >= limit

    def _src(self, who) -> dict:
        """보낸 곳 바구니 — 같은 곳에서 받은 토큰들이 간격·분당 상한을 같이 쓴다."""
        return self.who_state.setdefault(who, {"last_req": 0.0, "req_times": []})

    def _left(self, g: dict, interval_min: int, now: float) -> int:
        """다음 신청까지 남은 초 — 토큰과 보낸 곳 중 늦은 쪽."""
        s = self.who_state.get(g.get("who"))
        last = max(g["last_req"], s["last_req"] if s else 0.0)
        return max(0, int(last + interval_min * 60 - now + 0.999)) if last else 0

    def join(self, code, name, who: str) -> tuple:
        now = time.time()
        who = str(who or "?")[:80]
        with self._lock:
            if not self.on:
                return 410, {"ok": False, "error": "ended"}
            if who in self.blocked_who:
                return 403, {"ok": False, "error": "blocked"}
            for k in [k for k, v in self.join_hits.items() if not v or now - v[-1] > 60.0]:
                self.join_hits.pop(k, None)
            if self._rate(self.join_hits.setdefault(who, []), JOIN_PER_MIN, now):
                return 429, {"ok": False, "error": "rate", "wait": 60}
            if self._rate(self.join_all, JOIN_ALL_PER_MIN, now):
                return 429, {"ok": False, "error": "rate", "wait": max(1, int(60 - (now - self.join_all[0]) + 0.999))}
            c = norm_code(code)
            if not self.code or not CODE_RX.match(c) or not secrets.compare_digest(c.encode(), self.code.encode()):
                return 403, {"ok": False, "error": "bad_code"}
            while len(self.guests) >= GUESTS_MAX:          # 가장 오래 안 본 손님부터 걷는다
                old = min(self.guests, key=lambda t: self.guests[t]["seen"])
                self.guests.pop(old, None)
                self.mine.pop(old, None)
            tok = secrets.token_urlsafe(18)
            nm = clean_name(name)
            self.guests[tok] = {"name": nm, "who": who, "blocked": False, "last_req": 0.0, "req_times": [], "seen": now}
            self.mine[tok] = []
        HOOKS["activity"]()
        return 200, {"ok": True, "guest": tok, "name": nm}

    def _guest(self, tok):
        if not isinstance(tok, str) or not tok:
            return None
        g = self.guests.get(tok)
        if g is not None:
            g["seen"] = time.time()
        return g

    def room(self, tok) -> tuple:
        pub = self.public()
        q = self._queue()
        nowp = self._now(q)
        with self._lock:
            if not self.on:
                return 410, {"ok": False, "error": "ended"}
            g = self._guest(tok)
            if g is None:
                return 401, {"ok": False, "error": "bad_guest"}
            cfg = self.cfg()
            songs = pub["songs"] if pub else []
            mine = []
            for rid in self.mine.get(tok, [])[:MINE_MAX]:
                r = self.reqs.get(rid)
                if r is None:
                    continue
                st = {"wait": "wait", "ok": "ok"}.get(r["state"], "no")
                row = {"id": r["id"], "key": r["key"], "title": r["title"], "state": st}
                if st == "ok":
                    row["pos"] = r.get("pos")
                mine.append(row)
            held = self._held(q, nowp is not None)
            out = {"ok": True, "name": pub["name"] if pub else "", "count": len(songs), "now": nowp,
                   "songs": [{"key": s["key"], "title": s["title"], "artist": s["artist"], "sec": s["sec"]} for s in songs],
                   "mine": mine, "wait": self._left(g, cfg["interval_min"], time.time()),
                   "full": self._is_full(cfg, held), "blocked": self._blocked(g),
                   "interval_min": cfg["interval_min"], "cap": cfg["cap"]}
        HOOKS["activity"]()
        return 200, out

    def request(self, tok, key) -> tuple:
        pub = self.public()
        q = self._queue()
        playing = self._now(q) is not None
        now = time.time()
        with self._lock:
            if not self.on:
                return 410, {"ok": False, "error": "ended"}
            g = self._guest(tok)
            if g is None:
                return 401, {"ok": False, "error": "bad_guest"}
            if self._blocked(g):
                return 403, {"ok": False, "error": "blocked"}
            song = next((s for s in (pub["songs"] if pub else []) if isinstance(key, str) and s["key"] == key), None)
            if song is None:
                return 404, {"ok": False, "error": "not_in_list"}
            cfg = self.cfg()
            left = self._left(g, cfg["interval_min"], now)
            if left > 0:
                return 429, {"ok": False, "error": "interval", "wait": left}
            if self._is_full(cfg, self._held(q, playing)):
                return 409, {"ok": False, "error": "full"}
            src = self._src(g.get("who"))
            hit = [b for b in (g["req_times"], src["req_times"]) if self._full_min(b, REQ_PER_MIN, now)]
            if hit:
                # 분당 상한 — 손님 화면은 간격 제한과 같은 모양(「n분 뒤에 다시」)으로 받는다
                return 429, {"ok": False, "error": "interval",
                             "wait": max(1, max(int(60 - (now - b[0]) + 0.999) for b in hit))}
            g["req_times"].append(now)
            src["req_times"].append(now)
            self.seq += 1
            r = {"id": f"r{self.seq}", "key": song["key"], "title": song["title"], "sec": song["sec"],
                 "who": g["name"], "guest": tok, "from": g.get("who"), "at": now, "state": "wait"}
            self.reqs[r["id"]] = r
            self.wait.append(r)
            self.mine.setdefault(tok, []).insert(0, r["id"])
            del self.mine[tok][MINE_MAX:]
            g["last_req"] = src["last_req"] = now
            auto = cfg["auto"]
        HOOKS["activity"]()
        if auto:
            with self._lock:
                r2 = self._take(r["id"])
            if r2 is not None:
                self._append(r2)
        return 200, {"ok": True, "id": r["id"]}

    def leave(self, tok) -> tuple:
        with self._lock:
            if not self.on:
                return 410, {"ok": False, "error": "ended"}
            if not isinstance(tok, str) or tok not in self.guests:
                return 401, {"ok": False, "error": "bad_guest"}
            self.guests.pop(tok, None)          # 이미 낸 신청은 스트리머 쪽에 그대로 남는다
            self.mine.pop(tok, None)
            self._gc_reqs()
        return 200, {"ok": True}


ROOM = Room()


def guest(op: str, body: dict, tok: str, who: str) -> tuple:
    """손님 길 네 개 → (상태, 답). `op` = join · room · req · leave."""
    body = body if isinstance(body, dict) else {}
    if op == "join":
        return ROOM.join(body.get("code"), body.get("name"), who)
    if op == "room":
        return ROOM.room(tok)
    if op == "req":
        return ROOM.request(tok, body.get("key"))
    if op == "leave":
        return ROOM.leave(tok)
    return 404, {"ok": False, "error": "not_found"}


def streamer(op: str, p: dict) -> dict:
    """스트리머 길 (`/api/folio/bc/*`) → 답."""
    p = p if isinstance(p, dict) else {}
    if op == "state":
        return {"ok": True, **ROOM.state()}
    if op == "on":
        pl = p.get("pl")
        return ROOM.turn_on(pl if isinstance(pl, str) else None)
    if op == "off":
        return ROOM.turn_off()
    if op == "code":
        return ROOM.new_code()
    if op == "pl":
        return ROOM.set_pl(p.get("id"))
    if op == "cfg":
        return {"ok": True, "cfg": ROOM.set_cfg(p)}
    if op == "ok":
        return ROOM.approve(p.get("id"))
    if op == "no":
        return ROOM.reject(p.get("id"), all_=p.get("all") is True)
    if op == "block":
        return ROOM.block(p.get("id"))
    if op == "window":
        return HOOKS["open_window"]()
    return {"ok": False, "error": "not_found"}
