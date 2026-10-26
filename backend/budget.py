"""Token budget guard. Counters only: no text, no health data. Held in memory and never written to disk."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from contextvars import ContextVar

SESSION_TTL = 2 * 60 * 60
MAX_TRACKED = 2000


class BudgetExceeded(Exception):
    def __init__(self, scope: str, used: int, needed: int, cap: int):
        super().__init__(scope)
        self.scope, self.used, self.needed, self.cap = scope, used, needed, cap


def estimate_tokens(text: str) -> int:
    """A deliberately high estimate (about 3 characters per token) so the guard stops early, not late."""
    return len(text) // 3 + 1


class TokenBudget:
    """Input tokens used per key, within a time window. Old keys are dropped so memory cannot grow without limit."""

    def __init__(self, cap: int, window: int = SESSION_TTL):
        self.cap, self.window = cap, window
        self._used: OrderedDict[str, list] = OrderedDict()  # key -> [window_start, tokens]
        self._lock = threading.Lock()

    def _entry(self, key: str) -> list:
        now = time.monotonic()
        entry = self._used.get(key)
        if entry is None or now - entry[0] > self.window:
            entry = self._used[key] = [now, 0]
        self._used.move_to_end(key)
        while len(self._used) > MAX_TRACKED:
            self._used.popitem(last=False)
        return entry

    def used(self, key: str) -> int:
        with self._lock:
            return self._entry(key)[1]

    def check(self, key: str, estimate: int) -> None:
        with self._lock:
            used = self._entry(key)[1]
            if used + estimate > self.cap:
                raise BudgetExceeded(key, used, estimate, self.cap)

    def add(self, key: str, tokens: int) -> None:
        with self._lock:
            self._entry(key)[1] += tokens


class Guard:
    """The session budget plus a larger per-address budget, so a new session id is not a way around the cap."""

    def __init__(self, session_cap: int, address_cap: int):
        self.sessions = TokenBudget(session_cap)
        self.addresses = TokenBudget(address_cap, window=60 * 60)

    def before_call(self, who: "Who", estimate: int) -> None:
        self.sessions.check(who.session, estimate)
        self.addresses.check(who.address, estimate)

    def after_call(self, who: "Who", actual: int) -> None:
        self.sessions.add(who.session, actual)
        self.addresses.add(who.address, actual)


class Who:
    def __init__(self, session: str, address: str):
        self.session, self.address = session, address


current: ContextVar[Who | None] = ContextVar("current_budget_owner", default=None)


def make_guard() -> Guard:
    import config

    return Guard(config.SESSION_TOKEN_CAP, config.ADDRESS_TOKEN_CAP)


GUARD = make_guard()
