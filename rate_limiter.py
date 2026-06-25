#rate_limiter.py
import time
import asyncio


class RateLimiter:
    def __init__(self, calls_per_second=2, calls_per_minute=15):
        self.calls_per_second = calls_per_second
        self.calls_per_minute = calls_per_minute
        self._call_times: list[float] = []
        self._lock = asyncio.Lock()

    def _wartezeit(self):
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        wait = 0.0
        # Minuten-Limit: warten, bis der aelteste Aufruf aus dem Fenster faellt.
        if len(self._call_times) >= self.calls_per_minute:
            wait = max(wait, 60 - (now - self._call_times[0]))
        # Sekunden-Limit: warten, bis genug Zeit seit dem letzten Aufruf vergangen ist.
        if self._call_times:
            wait = max(wait, 1.0 / self.calls_per_second - (now - self._call_times[-1]))
        return wait

    def acquire(self):
        """Synchron – für generate()"""
        wait = self._wartezeit()
        if(wait > 0):
            print(f"  [RateLimiter] Warte {wait:.1f}s...")
            time.sleep(wait)
            self._call_times.append(time.time())

    async def a_acquire(self):
        """Asynchron – für generate_async()"""
        async with self._lock:
            wait = self._wartezeit()
            if wait>0:
                if wait > 1:
                    print(f"  [RateLimiter] Warte {wait:.1f}s...")
                await asyncio.sleep(wait)
            self._call_times.append(time.time())