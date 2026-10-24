"""Observed CLI action durations, NOT the game's timer or reset mechanism."""
import copy
import math
import threading
import time

COMMANDS = frozenset(('execute_gathering', 'execute_crafting', 'execute_altering',
                      'complete_altering_work'))


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


class UsageObserver:
    def __init__(self, clock=time.monotonic, wall=time.time):
        self.clock, self.wall = clock, wall
        self.lock = threading.RLock()
        self.persist = None
        self.active = {}
        self.serial = 0
        self.data = self._empty()
        self.process_base = 0.0

    def _empty(self):
        return dict(version=1, observedSince=self.wall(), completedSeconds=0.0,
                    calls=0, byCommand={}, confirmedAt=None, confirmedBase=0.0,
                    awaitingConfirmation=False, lastLimitAt=None,
                    incomplete=False, overlapObserved=False, openCalls=0)

    def configure(self, saved=None, persist=None):
        with self.lock:
            if self.active:
                raise RuntimeError('Cannot reconfigure an active observation')
            data = self._empty()
            if isinstance(saved, dict) and saved.get('version') == 1:
                for key in ('observedSince', 'completedSeconds', 'calls', 'confirmedBase'):
                    data[key] = number(saved.get(key))
                for key in ('confirmedAt', 'lastLimitAt'):
                    data[key] = number(saved[key]) if saved.get(key) is not None else None
                for key in ('awaitingConfirmation', 'incomplete', 'overlapObserved'):
                    data[key] = saved.get(key) is True
                data['incomplete'] |= bool(number(saved.get('openCalls')))
                data['confirmedBase'] = min(data['completedSeconds'], data['confirmedBase'])
                commands = saved.get('byCommand') or {}
                if isinstance(commands, dict):
                    data['byCommand'] = {k: number(v) for k, v in commands.items() if k in COMMANDS}
            self.data, self.persist = data, persist
            self.process_base = data['completedSeconds']
            self._save()

    def _save(self):
        self.data['openCalls'] = len(self.active)
        if self.persist:
            try:
                self.persist(copy.deepcopy(self.data))
            except Exception:
                # Failure to record must never repeat, cancel or fail a paid command.
                self.data['incomplete'] = True

    def begin(self, command):
        if command not in COMMANDS:
            return None
        with self.lock:
            self.serial += 1
            self.data['overlapObserved'] |= bool(self.active)
            self.active[self.serial] = (command, self.clock())
            self._save()
            return self.serial

    def finish(self, ticket, result=None):
        if ticket is None:
            return
        with self.lock:
            pending = self.active.pop(ticket, None)
            if pending is None:
                return
            command, began = pending
            elapsed = getattr(result, 'elapsed', None)
            try:
                valid_elapsed = elapsed is not None and math.isfinite(float(elapsed)) and float(elapsed) >= 0
            except (ValueError, TypeError, OverflowError):
                valid_elapsed = False
            if not valid_elapsed:
                elapsed = max(0.0, self.clock() - began)
                self.data['incomplete'] = True
            elapsed = number(elapsed)
            self.data['completedSeconds'] += elapsed
            self.data['calls'] += 1
            self.data['byCommand'][command] = self.data['byCommand'].get(command, 0.0) + elapsed
            body = getattr(result, 'body', None)
            if getattr(result, 'error', None) == 'blocked' and isinstance(body, dict) and body.get('kind') == 'continuous_run_limit':
                self.data['awaitingConfirmation'] = True
                self.data['lastLimitAt'] = self.wall()
            self._save()

    def acknowledge(self):
        """Record a human acknowledgement, never send a game command or reset total."""
        with self.lock:
            if self.active:
                return False
            self.data['confirmedAt'] = self.wall()
            self.data['confirmedBase'] = self.data['completedSeconds']
            self.data['awaitingConfirmation'] = False
            self._save()
            return True

    def snapshot(self):
        with self.lock:
            total = self.data['completedSeconds']
            return dict(completedSeconds=round(total, 1), calls=int(self.data['calls']),
                        processSeconds=round(max(0, total-self.process_base), 1),
                        observedSince=self.data['observedSince'],
                        confirmedAt=self.data['confirmedAt'],
                        sinceConfirmationSeconds=(round(max(0, total-self.data['confirmedBase']), 1)
                                                  if self.data['confirmedAt'] is not None else None),
                        awaitingConfirmation=self.data['awaitingConfirmation'],
                        lastLimitAt=self.data['lastLimitAt'],
                        inFlightCount=len(self.active),
                        inFlightSeconds=round(sum(max(0, self.clock()-began) for _, began in self.active.values()), 1),
                        byCommand={k: round(v, 3) for k, v in self.data['byCommand'].items()},
                        incomplete=self.data['incomplete'], overlapObserved=self.data['overlapObserved'],
                        gameTimerVerified=False, scope='observed_cli_action_duration')


observer = UsageObserver()
