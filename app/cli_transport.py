"""MabinogiMobile_CLI 호출 계층. 규약은 docs/CLI.md §1 참조.

- 비ASCII body 는 통째로 UTF-8 → base64 → "base64:" 접두. JSON body 는 ensure_ascii 로 ASCII 화하면 base64 가 필요 없다.
- stdout 은 바이트로 받아 utf-8 → mbcs 폴백으로 푼다.
- exit 0 이 성공이 아니다: ok = (exit == 0) and ("error" not in body).
- status/capabilities 는 last-response.json 을 갱신하지 않는다 → stdout 만 본다.
- 실행 명령의 상한은 우리가 고른 값이다 (타임아웃 11분). **「최대 9분」은 명세에 없다** — 실측 최대 293초.
- 파이프가 직렬이라 동시 호출이 불가능하다. 잠금은 부르는 쪽(server) 책임.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
import transportquiet
import connectorusage

CREATE_NO_WINDOW = 0x08000000
FROZEN = bool(getattr(sys, "frozen", False))
# 임베디드 판(서명된 pythonw 가 우리 .py 를 돌림)도 배포판이다 — 개발용 환경변수 규칙은 exe 와 같다 (runmode.py)
import runmode  # noqa: E402
_RELEASE = FROZEN or runmode.embed()
_DEV_ENV_OK = (not _RELEASE) or os.environ.get("MOBIW_DEV") == "1"   # 배포판은 개발용 환경변수를 무시

# 데모 모드: 게임·CLI 없이 demo_cli.py 의 가짜 응답으로 UI 를 띄운다 (개발·스크린샷).
# 실제 게임 CLI 를 부르지 않고 개발·검사할 때 이 모드를 쓴다.
DEMO = os.environ.get("MOBIW_DEMO") == "1" and not _RELEASE
# CLI 실행 차단: 실데이터로 화면·서버를 검증할 때 켠다. auto_sync 가 게임 연결을 보고 스스로 /api/sync 를 부르므로
# 부르지 않겠다는 약속만으로는 못 막는다 — 코드에서 프로세스를 아예 띄우지 않는다.
# 배포판은 MOBIW_DEV=1 이 함께 있을 때만 인정한다(다른 개발용 변수와 같은 규칙) — 빌드한 exe 를 게임 켜진 PC 에서 검증할 때 필요하다.
NO_CLI = os.environ.get("MOBIW_NO_CLI") == "1" and _DEV_ENV_OK

EXE_CANDIDATES = [
    os.environ.get("MOBIW_CLI_EXE", "") if _DEV_ENV_OK else "",
    r"C:\Nexon\MabinogiMobile\MabinogiMobile_CLI.exe",
]   # PATH·현재 폴더 탐색(where)은 하지 않는다 — 앱 폴더나 PATH 에 심어 둔 가짜 exe 가 실행되지 않게
LAST_RESPONSE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "MabinogiMobileCLI", "last-response.json")
LOCAL_COMMANDS = {"status", "capabilities"}      # last-response.json 을 갱신하지 않는 명령 (폴백 생략)
EXIT_MEANING = {0: "ok", 2: "usage_error", 3: "canceled", 4: "unknown_command", 5: "disconnected"}

_override: str = ""   # 설정(settings.json)의 cli_exe — server 가 set_exe_override 로 넣는다
# 명령 이름은 카탈로그의 snake_case 뿐이다. `/api/cli/<명령>` 처럼 밖에서 온 글자가 argv 로 가는 자리라
# 모양을 먼저 본다 (빈 글자·NUL·공백·경로 문자는 프로세스를 띄우지 않고 usage_error 로 돌린다).
_COMMAND_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# 게임 응답의 홀로 남은 서로게이트(JSON `\ud800` 이스케이프)는 파이썬 문자열로는 들어오지만 UTF-8 로는
# 못 쓴다 — 캐시 저장(store.save)·API 응답(_json)·write_chat 본문(encode_body)이 UnicodeEncodeError 로
# 죽었다. 응답을 풀자마자 U+FFFD 로 바꾼다.
_NUL_RE = re.compile(r"\x00")
_CLI_BASENAME = "mabinogimobile_cli.exe"


def valid_cli_path(p) -> bool:
    """설정·환경변수로 들어온 CLI 경로가 실행해도 되는 모양인지: 로컬 드라이브 절대 경로, UNC·\\?\\ 아님,
    파일명이 MabinogiMobile_CLI.exe, 실제 파일. (설정에 아무 exe 나 넣어 실행시키는 것을 막는다)"""
    if not isinstance(p, str):
        return False
    p = p.strip()
    if len(p) < 4 or not (p[0].isascii() and p[0].isalpha() and p[1] == ":" and p[2] in "\\/"):
        return False
    if p.startswith("\\\\") or "\\?\\" in p or "\0" in p:
        return False
    if os.path.basename(p).lower() != _CLI_BASENAME:
        return False
    return os.path.isfile(p)


# ── 실행 파일 권한 (다른 로컬 계정이 바꿔 넣을 수 있는가) ──
# CLI 는 15초마다 `status` 로 실행된다. 그 파일이나 폴더를 다른 표준 사용자가 쓸 수 있으면 그 사람이 넣은 프로그램이
# 이 계정 권한으로 돈다. 실행을 막지는 않고 경고만 한다 (게임 설치 프로그램이 정하는 권한이라 우리가 고칠 수 없다).
SID_ADMINS, SID_SYSTEM = "S-1-5-32-544", "S-1-5-18"
SID_TRUSTED_INSTALLER = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
OK_OWNERS = (SID_ADMINS, SID_SYSTEM, SID_TRUSTED_INSTALLER)
# 넓은 무리 — Everyone · Users · Authenticated Users · INTERACTIVE
WIDE_SIDS = {"S-1-1-0": "Everyone", "S-1-5-32-545": "Users", "S-1-5-11": "Authenticated Users", "S-1-5-4": "INTERACTIVE"}
# 내용을 바꾸거나 옆에 파일(DLL)을 넣거나 지우거나 권한을 바꿀 수 있는 권한
WRITE_MASK = (0x0002 | 0x0004 | 0x0040 | 0x00010000 | 0x00040000 | 0x00080000 | 0x40000000 | 0x10000000)
# FILE_WRITE_DATA/ADD_FILE · APPEND/ADD_SUBDIR · DELETE_CHILD · DELETE · WRITE_DAC · WRITE_OWNER · GENERIC_WRITE · GENERIC_ALL
ACCESS_ALLOWED_ACE_TYPE, INHERIT_ONLY_ACE = 0, 0x08


def acl_warning(owner_sid, aces, ok_owners=OK_OWNERS) -> str | None:
    """순수 판정. `aces` 는 (종류, 플래그, 마스크, SID 문자열) 목록이고 None 이면 DACL 이 없다(누구나 전부).
    소유자가 `ok_owners` 밖이거나 넓은 무리에 쓰기 ACE 가 있으면 사유 문자열, 아니면 None."""
    if aces is None:
        return "권한 목록(DACL)이 없어 누구나 바꿀 수 있습니다"
    owner = str(owner_sid or "")
    if owner not in ok_owners:
        return f"소유자가 관리자·시스템이 아닙니다 ({WIDE_SIDS.get(owner, owner or '알 수 없음')})"
    for typ, flags, mask, sid in aces:
        if typ != ACCESS_ALLOWED_ACE_TYPE or flags & INHERIT_ONLY_ACE:
            continue
        if sid in WIDE_SIDS and mask & WRITE_MASK:
            return f"{WIDE_SIDS[sid]} 에게 쓰기 권한이 있습니다"
    return None


def _read_acl(path: str):
    """(소유자 SID, ACE 목록 또는 None). 조회 실패는 OSError."""
    import ctypes
    from ctypes import wintypes as w
    adv = ctypes.WinDLL(os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "advapi32.dll"),
                        use_last_error=True)
    k32 = ctypes.WinDLL(os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32", "kernel32.dll"),
                        use_last_error=True)
    adv.GetNamedSecurityInfoW.argtypes = [w.LPCWSTR, ctypes.c_int, w.DWORD, ctypes.POINTER(ctypes.c_void_p),
                                          ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
                                          ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
    adv.ConvertSidToStringSidW.restype = w.BOOL
    adv.GetAce.argtypes = [ctypes.c_void_p, w.DWORD, ctypes.POINTER(ctypes.c_void_p)]
    adv.GetAce.restype = w.BOOL
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    k32.LocalFree.restype = ctypes.c_void_p

    def sid_str(psid) -> str:
        out = w.LPWSTR()
        if not psid or not adv.ConvertSidToStringSidW(psid, ctypes.byref(out)):
            return ""
        try:
            return out.value or ""
        finally:
            k32.LocalFree(ctypes.cast(out, ctypes.c_void_p))

    owner, dacl, sd = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    # SE_FILE_OBJECT=1 · OWNER_SECURITY_INFORMATION(1) | DACL_SECURITY_INFORMATION(4)
    rc = adv.GetNamedSecurityInfoW(path, 1, 0x1 | 0x4, ctypes.byref(owner), None, ctypes.byref(dacl), None, ctypes.byref(sd))
    if rc != 0:
        raise OSError(rc, "GetNamedSecurityInfoW")
    try:
        if not dacl.value:
            return sid_str(owner), None
        count = ctypes.cast(dacl, ctypes.POINTER(ctypes.c_uint16))[2]     # ACL.AceCount (BYTE, BYTE, WORD, WORD, WORD)
        aces = []
        for i in range(count):
            pace = ctypes.c_void_p()
            if not adv.GetAce(dacl, i, ctypes.byref(pace)):
                continue
            hdr = ctypes.cast(pace, ctypes.POINTER(ctypes.c_ubyte))
            typ, flags = hdr[0], hdr[1]
            if typ != ACCESS_ALLOWED_ACE_TYPE:
                aces.append((typ, flags, 0, ""))
                continue
            mask = ctypes.cast(pace.value + 4, ctypes.POINTER(ctypes.c_uint32))[0]  # ACE_HEADER 4바이트 뒤 Mask
            aces.append((typ, flags, mask, sid_str(pace.value + 8)))              # 그 뒤 SidStart
        return sid_str(owner), aces
    finally:
        k32.LocalFree(sd)


def _my_sid() -> str:
    """이 프로세스 사용자의 SID 문자열 (못 구하면 "")."""
    try:
        import ctypes
        from ctypes import wintypes as w
        adv, k32 = ctypes.windll.advapi32, ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = w.HANDLE
        adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
        adv.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
        adv.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(w.LPWSTR)]
        tok = w.HANDLE()
        if not adv.OpenProcessToken(k32.GetCurrentProcess(), 0x0008, ctypes.byref(tok)):   # TOKEN_QUERY
            return ""
        try:
            buf, n = ctypes.create_string_buffer(256), w.DWORD()
            if not adv.GetTokenInformation(tok, 1, buf, 256, ctypes.byref(n)):              # TokenUser
                return ""
            psid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]                     # TOKEN_USER.User.Sid
            out = w.LPWSTR()
            if not adv.ConvertSidToStringSidW(psid, ctypes.byref(out)):
                return ""
            try:
                return out.value or ""
            finally:
                k32.LocalFree(ctypes.cast(out, ctypes.c_void_p))
        finally:
            k32.CloseHandle(tok)
    except Exception:
        return ""


def exe_writable_by_others(path: str) -> str | None:
    """CLI 실행 파일과 그 폴더를 이 계정 밖 사람이 바꿀 수 있으면 한 줄 경고, 아니면 None.
    소유자는 관리자·SYSTEM·TrustedInstaller 또는 이 계정이어야 한다. 조회하지 못하면 경고로 본다(보수적)."""
    if os.name != "nt" or not path:
        return None
    me = _my_sid()
    owners = OK_OWNERS + ((me,) if me else ())
    for target, what, obj in ((path, "실행 파일", "실행 파일을"), (os.path.dirname(path), "실행 파일 폴더", "실행 파일 폴더를")):
        try:
            owner, aces = _read_acl(target)
        except Exception as e:
            return f"CLI {what}의 권한을 확인하지 못했습니다 ({type(e).__name__})"
        why = acl_warning(owner, aces, owners)
        if why:
            return f"CLI {obj} 다른 사용자 계정이 바꿀 수 있습니다 — {why}"
    return None


_EXE_WARN: dict = {}   # 경로 → 경고 (한 번만 계산한다 — 권한은 실행 중에 거의 바뀌지 않는다)


def exe_warning(path) -> str | None:
    if not path:
        return None
    key = os.path.normcase(str(path))
    if key not in _EXE_WARN:
        try:
            _EXE_WARN[key] = exe_writable_by_others(str(path))
        except Exception as e:
            _EXE_WARN[key] = f"CLI 실행 파일의 권한을 확인하지 못했습니다 ({type(e).__name__})"
    return _EXE_WARN[key]


def set_exe_override(path) -> None:
    global _override
    _override = path.strip() if valid_cli_path(path) else ""


def find_exe() -> str | None:
    """존재하는 실행파일 경로. 설정 지정 > MOBIW_CLI_EXE > 기본 설치 경로."""
    if DEMO:
        return EXE_CANDIDATES[-1]
    if _override and os.path.exists(_override):
        return _override
    for c in EXE_CANDIDATES:
        if c and valid_cli_path(c):
            return c
    return None


def _decode(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return b.decode("mbcs")
        except Exception:
            return b.decode("utf-8", "replace")


def clean_text(s: str) -> str:
    """홀로 남은 서로게이트 → U+FFFD, NUL 제거. argv·UTF-8 로 나가는 글자는 전부 이 모양이어야 한다."""
    if not isinstance(s, str):
        return s
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        s = s.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    return _NUL_RE.sub("", s) if "\x00" in s else s


def scrub(obj):
    """응답(dict/list/str)을 재귀로 훑어 문자열을 clean_text 로 고친다 — 게임이 준 값이 파일·화면·argv 로 가기 전에."""
    if isinstance(obj, str):
        return clean_text(obj)
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {clean_text(k) if isinstance(k, str) else k: scrub(v) for k, v in obj.items()}
    return obj


def encode_body(body: str | dict | list | None) -> str | None:
    """JSON body 는 \\uXXXX 이스케이프로 순수 ASCII 화한다 — 콘솔 코드페이지와 무관하고 base64 도 필요 없다.
    raw 문자열은 비ASCII 일 때만 base64. 어느 쪽이든 NUL·홀로 남은 서로게이트는 먼저 걷어 낸다."""
    if body is None:
        return None
    if isinstance(body, (dict, list)):
        return json.dumps(scrub(body), ensure_ascii=True)
    body = clean_text(body)
    if body == "":
        return ""
    if all(ord(ch) < 128 for ch in body):
        return body
    return "base64:" + base64.b64encode(body.encode("utf-8")).decode("ascii")


@dataclass
class CliResult:
    command: str
    code: int
    body: object = None            # dict | list | None
    ok: bool = False
    error: str | None = None       # cli_not_found / exit 의미 / body.error
    message: str = ""
    raw: str = ""
    elapsed: float = 0.0
    source: str = "stdout"         # stdout | last-response | demo

    def to_dict(self) -> dict:
        return {"command": self.command, "code": self.code, "ok": self.ok, "error": self.error,
                "message": self.message, "body": self.body, "elapsed": round(self.elapsed, 3), "source": self.source}


def _read_last_response(since: float) -> object | None:
    """이번 호출(since) 이후에 갱신된 파일만 믿는다 — 예전 다른 명령의 응답이 이번 결과로 둔갑하지 않게."""
    try:
        if os.path.getmtime(LAST_RESPONSE) < since - 1.0:
            return None
        with open(LAST_RESPONSE, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


def _finish(res: CliResult, parsed: object) -> CliResult:
    """exit 0 이어도 body 에 error 가 있으면 실패다."""
    if isinstance(parsed, dict) and "error" in parsed:
        res.error = str(parsed["error"])
        res.message = str(parsed.get("message", ""))
        return res
    res.ok = True
    if isinstance(parsed, dict):
        res.message = str(parsed.get("message", ""))
    return res


def call(command: str, body: str | dict | list | None = None, timeout: float = 660.0,
         allow_last_response: bool = True) -> CliResult:
    with transportquiet.admission(command if isinstance(command, str) and _COMMAND_RE.match(command) else 'invalid') as (allowed, request_id):
        if not allowed:
            return CliResult('paused', -5, None, False, 'connector_rest',
                             '커넥터 전체 휴식 중 — 요청을 전송하지 않았습니다.')
        started = time.monotonic()
        ticket = connectorusage.observer.begin(command)
        try:
            result = _call_unpaused(command, body, timeout, allow_last_response)
            connectorusage.observer.finish(ticket, result)
            transportquiet.record('finished', id=request_id, ok=result.ok,
                                  error=result.error, seconds=round(time.monotonic()-started, 3))
            return result
        except Exception:
            connectorusage.observer.finish(ticket)
            transportquiet.record('exception', id=request_id)
            raise


def _call_unpaused(command: str, body: str | dict | list | None = None, timeout: float = 660.0,
         allow_last_response: bool = True) -> CliResult:
    """CLI 한 번. `allow_last_response=False` 면 **공용 파일로 답을 메우지 않는다.**

    표준출력이 JSON 이 아닐 때 이 함수는 `last-response.json` 을 읽어 답을 채운다.
    그 파일은 **호출 전체가 같이 쓰는 한 장**이다. 잠금을 건너뛰고 다른 호출과 겹쳐
    나가는 자리(실행이 파이프를 쥔 동안의 읽기)에서는 **남의 답을 집어 올 수 있다.**
    그런 자리는 이 되돌아보기를 끄고, 못 읽으면 **모른다로 둔다.**"""
    if not isinstance(command, str) or not _COMMAND_RE.match(command):
        return CliResult(str(command)[:64], 2, None, False, "usage_error", "명령 이름의 모양이 아닙니다.")
    if DEMO:
        import demo_cli
        t0 = time.time()
        code, parsed = demo_cli.respond(command, body)
        res = CliResult(command, code, parsed, False, None, "",
                        json.dumps(parsed, ensure_ascii=False), time.time() - t0, "demo")
        if code != 0:
            res.error = EXIT_MEANING.get(code, f"exit_{code}")
            return res
        return _finish(res, parsed)
    # 프로세스를 띄우기 전에 끊는다 — 어떤 경로로 불려도 CLI 가 실행되지 않게.
    # **모듈 상수와 살아 있는 환경변수 둘 다 본다.** 검사가 이 모듈을 `importlib.reload` 로
    # 다시 읽으면 상수가 그 순간의 환경으로 굳는데, `mock.patch.dict` 가 환경을 되돌린 뒤에도
    # 상수는 False 로 남았다 → 뒤에 도는 검사가 진짜 CLI 로 `stop_action` 을 보냈다
    # (개발 PC 에는 진짜 CLI 가 있을 수 있다). 환경변수는 되돌려져 있으니 그것을 믿는다.
    if NO_CLI or (os.environ.get("MOBIW_NO_CLI") == "1" and _DEV_ENV_OK):
        return CliResult(command, -4, None, False, "cli_disabled", "MOBIW_NO_CLI=1 — CLI 실행이 차단된 실행입니다.")
    exe = find_exe()
    if exe is None:
        return CliResult(command, -1, None, False, "cli_not_found",
                         "MabinogiMobile_CLI.exe 를 찾지 못했습니다. 게임의 환경 설정 > 게임 > AI 제어에서 "
                         "'마비노기 모바일 AI 커넥터' 를 켜면 설치됩니다.")
    args = [exe, command]
    enc = encode_body(body)
    if enc is not None:
        args.append(enc)
    t0 = time.time()
    try:
        p = subprocess.run(args, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout,
                           creationflags=CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return CliResult(command, -2, None, False, "timeout", f"{timeout:.0f}s 안에 응답이 없습니다.",
                         elapsed=time.time() - t0)
    except (OSError, ValueError) as e:   # ValueError: argv 에 NUL (clean_text 를 거치지 않은 값이 왔을 때의 마지막 방어)
        return CliResult(command, -3, None, False, "spawn_failed", str(e), elapsed=time.time() - t0)
    raw = _decode(p.stdout).strip()
    parsed: object | None = None
    source = "stdout"
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
    if parsed is None and command not in LOCAL_COMMANDS and allow_last_response:
        lr = _read_last_response(t0)
        if lr is not None:
            parsed, source = lr, "last-response"
    parsed = scrub(parsed)   # 게임이 준 글자 — 홀로 남은 서로게이트·NUL 은 여기서 걷어 낸다
    res = CliResult(command, p.returncode, parsed, False, None, "", raw, time.time() - t0, source)
    if p.returncode != 0:
        res.error = EXIT_MEANING.get(p.returncode, f"exit_{p.returncode}")
        res.message = (str(parsed.get("message") or parsed.get("reason") or "") if isinstance(parsed, dict)
                       else (_decode(p.stderr).strip() or raw))
        return res
    return _finish(res, parsed)


# 마지막 probe() 의 답. **폰(밖)은 이것만 본다** — 폰이 열리거나 15초마다 상태를 물어도 PC 의 CLI 가 돌지 않는다
# (폰이 열릴 때 게임을 새로 읽지 않고 PC 가 읽은 값만 본다).
# 이 PC 의 화면이 15초마다 probe 를 부르므로 그 값이 곧 「PC 가 읽은 값」이다. 아직 한 번도 안 읽었으면 없다(None).
_LAST_PROBE: dict = {}


def last_probe():
    """PC 가 마지막으로 읽어 둔 상태 (CLI 를 부르지 않는다). 아직 없으면 None."""
    return dict(_LAST_PROBE) if _LAST_PROBE else None


def probe() -> dict:
    """UI 상태표시용: 실행파일 유무 + status. 게임이 꺼져 있으면 5초쯤 걸리므로 자주 부르지 않는다."""
    exe = find_exe()
    out = {"exe": exe, "found": exe is not None, "pipe": None, "reason": None, "demo": DEMO, "disabled": NO_CLI,
           "override_invalid": bool(_override) and not os.path.exists(_override),
           # 권한만 읽는다 (CLI 를 실행하지 않는다). 데모의 가짜 경로는 보지 않는다
           "exe_warning": exe_warning(exe) if exe and not DEMO and os.path.isfile(exe) else None}
    if NO_CLI and not DEMO:   # status 도 CLI 실행이다 — 부르지 않고 '차단됨'으로 답한다
        out["pipe"] = "disabled"
        return _remember_probe(out)
    if exe:
        r = call("status", timeout=20)
        if isinstance(r.body, dict):
            out["pipe"] = r.body.get("pipe")
            out["reason"] = r.body.get("reason")
        out["status_error"] = r.error
    return _remember_probe(out)


def _remember_probe(out: dict) -> dict:
    out["at"] = time.time()   # 언제 읽은 값인지 — 폰이 「n초 전 값」임을 알 수 있게
    _LAST_PROBE.clear()
    _LAST_PROBE.update(out)
    return out
