import os
import threading

import fastf1

from ..config import CACHE_DIR, MAX_CONCURRENT_LOADS

os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

_session_cache: dict = {}
_load_locks: dict[tuple, threading.Lock] = {}
_locks_lock = threading.Lock()
_semaphore = threading.Semaphore(MAX_CONCURRENT_LOADS)


def _get_lock(key: tuple) -> threading.Lock:
    with _locks_lock:
        if key not in _load_locks:
            _load_locks[key] = threading.Lock()
        return _load_locks[key]


def load_session(year: int, race: str, session_type: str):
    """Load and cache a FastF1 session (thread-safe with semaphore)."""
    key = (year, race, session_type)
    if key in _session_cache:
        return _session_cache[key]

    lock = _get_lock(key)
    with lock:
        # Double-check after acquiring lock
        if key in _session_cache:
            return _session_cache[key]

        _semaphore.acquire()
        try:
            session = fastf1.get_session(year, race, session_type)
            session.load()
            _session_cache[key] = session
        finally:
            _semaphore.release()

    return _session_cache[key]
