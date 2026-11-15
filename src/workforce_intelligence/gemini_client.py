"""Gemini adapter for structured workforce-problem extraction."""
from __future__ import annotations
import os
from .extraction import build_extraction_prompt,parse_extraction_response

class GeminiExtractor:
    def __init__(self,api_key=None,model=None,client=None):
        self.api_key=api_key or os.getenv("GEMINI_API_KEY")
        self.model=model or os.getenv("GEMINI_MODEL","gemini-3.8-flash")
        self._client=client
        if self._client is None:
            if not self.api_key: raise ValueError("Set GEMINI_API_KEY before using Gemini extraction.")
            try: from google import genai
            except ImportError as exc: raise RuntimeError("Install google-genai to use Gemini extraction.") from exc
            self._client=genai.Client(api_key=self.api_key)
    def extract(self,text,source_metadata):
        prompt=build_extraction_prompt(text,source_metadata)
        response=self._client.models.generate_content(model=self.model,contents=prompt,config={"response_mime_type":"application/json","temperature":0})
        return parse_extraction_response(response.text or "{}",source_metadata)
