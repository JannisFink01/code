# gwdg_model.py
# OpenAI-kompatibler Wrapper – bedient jetzt ZWEI Backends:
#   - GWDG (Simulator, gpt-oss)  -> Default base_url/api_key
#   - lokales muse-Modell (Judge, self-signed) -> base_url/api_key/verify_ssl je Instanz
# Mit Rate Limiter, Retry, optionalem Reasoning-Effort-Prefix (muse) und verify_ssl.

import json
import time
import asyncio
import httpx
from openai import OpenAI
from pydantic import BaseModel as PydanticBaseModel
from deepeval.models import DeepEvalBaseLLM
from rate_limiter import RateLimiter
from config import GWDG_API_KEY, GWDG_BASE_URL
MAX_RETRIES = 10
RETRY_WAIT = 60


class GWDGModel(DeepEvalBaseLLM):
    """OpenAI-kompatibler DeepEval-Wrapper.

    Neu gegenueber der GWDG-only-Version:
    - base_url / api_key pro Instanz (verschiedene Endpunkte moeglich),
    - verify_ssl=False fuer self-signed Endpunkte (lokales muse-Modell),
    - reasoning_effort: wird als "Reasoning_effort: <wert>" dem Prompt vorangestellt
      (muse-glimmer steuert Reasoning ueber den Prompt, nicht ueber einen API-Parameter),
    - extra_body: optionaler Zusatz-Payload (z. B. {"enable_thinking": False} fuer GWDG).
    """

    def __init__(
        self,
        model_name: str,
        rate_limiter: RateLimiter = None,
        base_url: str = None,
        api_key: str = None,
        verify_ssl: bool = True,
        reasoning_effort: str = None,
        extra_body: dict = None,
    ):
        self.model_name = model_name
        self.rate_limiter = rate_limiter
        self.reasoning_effort = reasoning_effort
        self.extra_body = extra_body
        # self-signed Endpunkt (muse) -> Zertifikatspruefung abschalten
        http_client = None if verify_ssl else httpx.Client(verify=False)
        self._client = OpenAI(
            api_key=api_key or GWDG_API_KEY,
            base_url=base_url or GWDG_BASE_URL,
            http_client=http_client,
        )

    def load_model(self):
        return self._client

    def get_model_name(self) -> str:
        return self.model_name

    def _prefix(self, text: str) -> str:
        """Stellt bei gesetztem reasoning_effort das Reasoning-Prefix voran (muse)."""
        if self.reasoning_effort:
            return f"Reasoning_effort: {self.reasoning_effort}\n\n{text}"
        return text

    def _extra(self) -> dict:
        """Gibt {'extra_body': ...} nur zurueck, wenn extra_body gesetzt ist."""
        return {"extra_body": self.extra_body} if self.extra_body else {}

    # ─────────────────────────────────────────────
    # INTERNER API-CALL (sync)
    # ─────────────────────────────────────────────
    def _call_api(self, prompt: str, schema: PydanticBaseModel = None):
        if schema:
            resp = self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Respond with valid JSON only. No markdown, no explanation."},
                    {"role": "user", "content": self._prefix(prompt)},
                ],
                temperature=0.0,
                max_tokens=16000,
                **self._extra(),
            )
            raw = resp.choices[0].message.content.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return schema(**json.loads(raw))

        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": self._prefix(prompt)}],
            temperature=0.0,
            max_tokens=16000,
            **self._extra(),
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
                    print(f"  [{type(e).__name__}] Retry {attempt}/{MAX_RETRIES} – warte {RETRY_WAIT}s...")
                    time.sleep(RETRY_WAIT)
                else:
                    raise
        raise RuntimeError(f"[GWDGModel] Rate limit nach {MAX_RETRIES} Versuchen nicht ueberwunden.")

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
                if ("429" in str(e) or "500" in str(e) or "rate limit" in str(e).lower()
                        or "internal server" in str(e).lower()):
                    wait = min(45 * attempt, 180)
                    print(f"  [{type(e).__name__}] Retry {attempt}/{MAX_RETRIES} – warte {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"[GWDGModel] Rate limit nach {MAX_RETRIES} Versuchen nicht ueberwunden.")