"""Experimental action-boundary rest. Does not reset or acknowledge game limits."""
import time


class BoundaryBreak:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = None
        self.anchor = None
        self.count = 0
        self.paused = False
        self.last_rest = None
        self.last_outcome = None
        self.rest_until = None

    def due(self, enabled, interval):
        now = self.clock()
        if not enabled:
            self.anchor = None
            return False
        if self.anchor is None:
            self.anchor = now
            if self.started is None:
                self.started = now
            return False
        return now - self.anchor >= interval

    def begin(self, seconds=None):
        self.paused = True
        now = self.clock()
        self.rest_until = now + seconds if seconds is not None else None
        return now

    def finish(self, began, interrupted=False):
        self.paused = False
        self.rest_until = None
        self.last_rest = round(max(0, self.clock() - began), 1)
        if not interrupted:
            self.count += 1
            self.anchor = self.clock()

    def snapshot(self):
        return {'paused': self.paused, 'breaks': self.count, 'lastRestSeconds': self.last_rest,
                'remainingRestSeconds': max(0, round(self.rest_until-self.clock())) if self.paused and self.rest_until is not None else None,
                'observedSeconds': round(max(0, self.clock() - self.started), 1) if self.started is not None else 0,
                'lastOutcome': self.last_outcome,
                'verifiedReset': False}

    def rearm_after_confirmation(self):
        """Only reset OUR rest schedule after explicit human acknowledgement."""
        self.anchor = self.clock()
