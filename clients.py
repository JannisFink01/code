# clients.py
from openai import OpenAI
from config import (
    TUTOR_MODEL,
    SIMULATOR_MODEL,
    JUDGE_MODEL,
    KONTEXT_FILE,
    RATE_CALLS_PER_SECOND,
    RATE_CALLS_PER_MINUTE,
    THRESHOLD,
)
from rate_limiter import RateLimiter
from gwdg_model import GWDGModel

rate_limiter = RateLimiter(
    calls_per_second=RATE_CALLS_PER_SECOND, calls_per_minute=RATE_CALLS_PER_MINUTE
)
judge_llm = GWDGModel(JUDGE_MODEL, rate_limiter=rate_limiter)
simulator_llm = GWDGModel(SIMULATOR_MODEL, rate_limiter=rate_limiter)
tutor_llm = GWDGModel(TUTOR_MODEL, rate_limiter=rate_limiter)

with open(KONTEXT_FILE, encoding="utf-8") as f:
    CONTEXT = f.read()
