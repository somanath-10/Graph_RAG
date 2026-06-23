import json
import re
from typing import Any

from openai import OpenAI

from backend.app.config import get_settings


class OpenAIClient:
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        if not self.settings.use_mock_openai:
            if not self.settings.openai_api_key:
                raise RuntimeError('OPENAI_API_KEY is missing. Set it in .env or enable USE_MOCK_OPENAI=true for local UI testing.')
            self.client = OpenAI(api_key=self.settings.openai_api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.settings.use_mock_openai:
            return [self._mock_embedding(t) for t in texts]
        response = self.client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def text(self, user_prompt: str, system_prompt: str = 'You are a helpful assistant.', max_output_tokens: int | None = None) -> str:
        max_output_tokens = max_output_tokens or self.settings.default_text_max_output_tokens
        if self.settings.use_mock_openai:
            return self._mock_text(user_prompt)
        response = self.client.responses.create(
            model=self.settings.openai_small_model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=max_output_tokens,
        )
        return response.output_text

    def json(self, user_prompt: str, system_prompt: str, max_output_tokens: int | None = None) -> Any:
        max_output_tokens = max_output_tokens or self.settings.default_json_max_output_tokens
        raw = self.text(user_prompt, system_prompt, max_output_tokens=max_output_tokens)
        return parse_json(raw, preview_chars=self.settings.parse_json_preview_chars)

    def _mock_embedding(self, text: str) -> list[float]:
        # Deterministic small mock vector padded to configured dimension.
        import hashlib
        h = hashlib.sha256(text.encode('utf-8')).digest()
        vals = [((b / 255.0) - 0.5) for b in h]
        dim = self.settings.embedding_dimensions
        out = []
        while len(out) < dim:
            out.extend(vals)
        return out[:dim]

    def _mock_text(self, prompt: str) -> str:
        if 'Return JSON' in prompt or 'return JSON' in prompt or 'JSON' in prompt:
            return json.dumps({
                'entities': [],
                'relationships': [],
                'contexts': []
            })
        return self.settings.mock_answer_text


def parse_json(raw: str, preview_chars: int = 500) -> Any:
    text = raw.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise ValueError(f'LLM did not return valid JSON: {raw[:preview_chars]}')
