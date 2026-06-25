# gwdg_model.py
# GWDGModel – OpenAI-kompatibler Client für den GWDG KI-Server
# Mit Rate Limiter und automatischem Retry bei 429-Fehlern

import json
import time
import asyncio
from openai import OpenAI
from pydantic import BaseModel as PydanticBaseModel
from deepeval.models import DeepEvalBaseLLM
from rate_limiter import RateLimiter
from config import GWDG_API_KEY, GWDG_BASE_URL
MAX_RETRIES = 5
RETRY_WAIT = 45


class GWDGModel(DeepEvalBaseLLM):
    """
    DeepEval-kompatibler Wrapper für den GWDG KI-Server.
    Unterstützt:
    - Synchrone und asynchrone Aufrufe
    - Rate Limiting (calls_per_second, calls_per_minute)
    - Automatisches Retry bei 429-Fehlern
    - Schema-basierte JSON-Ausgabe für DeepEval-Metriken
    """

    def __init__(
        self,
        model_name: str,
        rate_limiter: RateLimiter = None,
    ):
        self.model_name = model_name
        self.rate_limiter = rate_limiter
        self._client = OpenAI(
            api_key=GWDG_API_KEY, base_url=GWDG_BASE_URL
        )

    def load_model(self):
        return self._client

    def get_model_name(self) -> str:
        return self.model_name

    # ─────────────────────────────────────────────
    # INTERNER API-CALL (sync)
    # ─────────────────────────────────────────────

    def _call_api(self, prompt: str, schema: PydanticBaseModel = None):
        """Führt den eigentlichen API-Call durch – ohne Rate Limiter."""
        if schema:
            resp = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "Respond with valid JSON only. No markdown, no explanation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=4000,
                extra_body={"enable_thinking": False},
            )
            raw = resp.choices[0].message.content.strip()
            print(f"\n[DEBUG RAW]: {repr(raw[:200])}")
            raw = (
                raw.removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return schema(**json.loads(raw))

        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=4000,
            extra_body={"enable_thinking": False},
        )
        return resp.choices[0].message.content

    # ─────────────────────────────────────────────
    # SYNCHRON
    # ─────────────────────────────────────────────

    def generate(self, prompt: str, schema: PydanticBaseModel = None):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self.rate_limiter:
                    self.rate_limiter.acquire()
                return self._call_api(prompt, schema)
            except Exception as e:
                if "429" in str(e) or "500" in str(e) or "rate limit" in str(e).lower():
                    print(
                        f"  [{type(e).__name__}] Rate limit – warte {RETRY_WAIT}s (Versuch {attempt}/{MAX_RETRIES})..."
                    )
                    time.sleep(RETRY_WAIT)
                else:
                    raise
        raise RuntimeError(
            f"[GWDGModel] Rate limit nach {MAX_RETRIES} Versuchen nicht überwunden."
        )

    # ─────────────────────────────────────────────
    # ASYNCHRON (für Simulator)
    # ─────────────────────────────────────────────

    async def a_generate(self, prompt: str, schema: PydanticBaseModel = None):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self.rate_limiter:
                    await self.rate_limiter.a_acquire()
                return self._call_api(prompt, schema)
            except Exception as e:
                if (
                    "429" in str(e)
                    or "500" in str(e)
                    or "rate limit" in str(e).lower()
                    or "internal server" in str(e).lower()
                    or isinstance(e, json.JSONDecodeError)
                ):
                    wait = min(45 * attempt, 180)
                    print(
                        f"  [{type(e).__name__}] Rate limit – warte {wait}s (Versuch {attempt}/{MAX_RETRIES})..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        raise RuntimeError(
            f"[GWDGModel] Rate limit nach {MAX_RETRIES} Versuchen nicht überwunden."
        )
