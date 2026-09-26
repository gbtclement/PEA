import threading
import time
from collections.abc import Callable, Hashable
from typing import Any


class TTLCache:
    """Cache mémoire minimal : chaque valeur expire `ttl_seconds` après son calcul."""

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._values: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        now = self._clock()
        with self._lock:
            cached = self._values.get(key)
            if cached and now - cached[0] < self._ttl:
                return cached[1]
        value = factory()
        with self._lock:
            self._values[key] = (now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
