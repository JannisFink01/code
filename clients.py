"""clients.py

Baut die drei DeepEval-LLM-Wrapper (Judge, Simulator, Tutor) sowie den
gemeinsamen RateLimiter zentral einmal auf und lädt den fachlichen Kontext
(KONTEXT_FILE), damit alle anderen Module
dieselben Instanzen wiederverwenden können, statt sie mehrfach zu erzeugen.
"""

from openai import OpenAI
from config import (
    REASONING_EFFORT,
    JUDGE_API_KEY,
    JUDGE_BASE_URL,
    JUDGE_VERIFY_SSL,
    SIMULATOR_BASE_URL,
    SIMULATOR_VERIFY_SSL,
    SIMULATOR_API_KEY,
    TUTOR_MODEL,
    SIMULATOR_MODEL,
    JUDGE_MODEL,
    KONTEXT_FILE,
    RATE_CALLS_PER_SECOND,
    RATE_CALLS_PER_MINUTE,
)
from rate_limiter import RateLimiter
from gwdg_model import GWDGModel
from rag_client import RAGPipelineClient

rate_limiter = RateLimiter(
    calls_per_second=RATE_CALLS_PER_SECOND, calls_per_minute=RATE_CALLS_PER_MINUTE
)
judge_llm = GWDGModel(
    JUDGE_MODEL,
    rate_limiter=rate_limiter,
    base_url=JUDGE_BASE_URL,
    api_key=JUDGE_API_KEY,
    verify_ssl=JUDGE_VERIFY_SSL,
    reasoning_effort=REASONING_EFFORT,
    extra_body=None,  # muse nutzt Reasoning-Prefix, kein enable_thinking
)
simulator_llm = GWDGModel(
    SIMULATOR_MODEL, 
    rate_limiter=rate_limiter, 
    base_url=SIMULATOR_BASE_URL, 
    api_key=SIMULATOR_API_KEY,
    verify_ssl=SIMULATOR_VERIFY_SSL,
    extra_body={"enable_thinking": False}
)
tutor_llm = GWDGModel(TUTOR_MODEL, rate_limiter=rate_limiter)
rag_llm = RAGPipelineClient(rate_limiter=rate_limiter)
with open(KONTEXT_FILE, encoding="utf-8") as f:
    CONTEXT = f.read()
