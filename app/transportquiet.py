"""Process-wide CLI admission gate; never acknowledges or resets game limits."""
import threading
import time
from contextlib import contextmanager

_cv = threading.Condition()
_quiet = False
_active = 0
_seq = 0
_sink = lambda message: None


def configure(sink):
    global _sink
    _sink = sink


def record(event, **fields):
    # Metadata only: no bodies, raw responses, paths, or credentials.
    try:
        _sink('[connector-traffic] ' + event + ' ' + ' '.join(f'{k}={v}' for k, v in fields.items()))
    except Exception:
        pass


@contextmanager
def admission(command):
    global _active, _seq
    with _cv:
        allowed = not _quiet
        _seq += 1
        request_id = _seq
        if allowed:
            _active += 1
    record('admitted' if allowed else 'suppressed', id=request_id, command=command)
    try:
        yield allowed, request_id
    finally:
        if allowed:
            with _cv:
                _active -= 1
                _cv.notify_all()


def begin(stop):
    """Close admission, then drain existing calls. Never kill an active action."""
    global _quiet
    with _cv:
        _quiet = True
        record('draining', active=_active)
        while _active and not stop.is_set():
            _cv.wait(0.1)
        ready = not stop.is_set()
    record('quiet-ready' if ready else 'quiet-canceled')
    return ready


def end():
    global _quiet
    with _cv:
        _quiet = False
        _cv.notify_all()
    record('quiet-ended')
