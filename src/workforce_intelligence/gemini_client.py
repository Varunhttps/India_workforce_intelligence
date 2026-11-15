"""Gemini adapter with bounded retries for transient API failures."""
from __future__ import annotations
import os
import time
from .extraction import build_extraction_prompt, parse_extraction_response

_TRANSIENT_MARKERS = ("429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL")

class GeminiExtractor:
    def __init__(self, api_key=None, model=None, client=None, max_attempts=4, retry_delay=2):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay = max(0, float(retry_delay))
        self._client = client
        if self._client is None:
            if not self.api_key:
                raise ValueError("Set GEMINI_API_KEY before using Gemini extraction.")
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("Install google-genai to use Gemini extraction.") from exc
            self._client = genai.Client(api_key=self.api_key)

    def extract(self, text, source_metadata):
        prompt = build_extraction_prompt(text, source_metadata)
        response = None
        for attempt in range(self.max_attempts):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0},
                )
                break
            except Exception as exc:
                message = str(exc).upper()
                transient = any(marker in message for marker in _TRANSIENT_MARKERS)
                if not transient or attempt == self.max_attempts - 1:
                    raise
                time.sleep(self.retry_delay * (2 ** attempt))
        return parse_extraction_response(response.text or "{}", source_metadata, source_text=text)
