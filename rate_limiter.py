import time
import asyncio

class RateLimiter:
    def __init__(self, calls_per_second=2, calls_per_minute=15):
        self.calls_per_second = calls_per_second
        self.calls_per_minute = calls_per_minute
        self._call_times: list[float] = []
        self._lock = asyncio.Lock()

    def acquire(self):
        """Synchron – für generate()"""
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self.calls_per_minute:
            wait = 60 - (now - self._call_times[0])
            if wait > 0:
                print(f"  [RateLimiter] warte {wait:.1f}s...")
                time.sleep(wait)
        if self._call_times:
            elapsed = time.time() - self._call_times[-1]
            gap = 1.0 / self.calls_per_second
            if elapsed < gap:
                time.sleep(gap - elapsed)
        self._call_times.append(time.time())

    async def a_acquire(self):
        """Asynchron – für generate_async()"""
        async with self._lock:  # Lock bleibt bis acquire() fertig ist
            now = time.time()
            self._call_times = [t for t in self._call_times if now - t < 60]
            
            if len(self._call_times) >= self.calls_per_minute:
                wait = 60 - (now - self._call_times[0])
                if wait > 0:
                    print(f"  [RateLimiter] Minuten-Limit – warte {wait:.1f}s...")
                    await asyncio.sleep(wait)
            
            gap = 1.0 / self.calls_per_second
            if self._call_times:
                elapsed = time.time() - self._call_times[-1]
                if elapsed < gap:
                    await asyncio.sleep(gap - elapsed)
            
            self._call_times.append(time.time())
            # Lock wird erst hier freigegeben → nächster Task wartet