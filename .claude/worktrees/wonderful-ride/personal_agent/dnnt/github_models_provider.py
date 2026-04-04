"""GitHub Models API provider — uses Copilot subscription for GPT-4o access."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Optional, Tuple


def _get_github_token() -> str:
    """Get GitHub token from env or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        token = result.stdout.strip()
        if token:
            return token
    except Exception:
        pass
    raise RuntimeError(
        "No GitHub token found. Set GITHUB_TOKEN env var or run 'gh auth login'."
    )


class GitHubModelsClient:
    """
    OpenAI-compatible client for GitHub Models API.

    Uses your Copilot subscription to access GPT-4o, GPT-4o-mini, o1, o3-mini
    at https://models.inference.ai.azure.com.
    """

    BASE_URL = "https://models.inference.ai.azure.com"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        token: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 30.0,
    ):
        from openai import OpenAI

        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._token = token or _get_github_token()
        self.client = OpenAI(base_url=self.BASE_URL, api_key=self._token)
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.errors = 0

    def chat(
        self,
        query: str,
        facts: list[str] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Tuple[str, str]:
        """
        Call the model and return (thinking, response).

        Structured to match the DNNT llm_callback signature:
            (query, facts) -> (thinking, response)

        For models that don't have native thinking (4o, 4o-mini), we ask
        for a structured response with <think> and <response> tags.
        """
        facts_str = "\n".join(f"- {f}" for f in facts) if facts else "(no facts available)"

        sys_msg = system_prompt or (
            "You are a helpful AI assistant. When answering, first think through "
            "the problem step by step inside <think>...</think> tags, then give "
            "your final answer inside <response>...</response> tags.\n\n"
            "Example format:\n"
            "<think>The user asked X. Based on the facts, Y is relevant...</think>\n"
            "<response>Here is my answer.</response>"
        )

        user_msg = f"Facts:\n{facts_str}\n\nQuestion: {query}"

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ]

        for attempt in range(self.max_retries):
            try:
                r = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self.total_calls += 1
                if r.usage:
                    self.total_input_tokens += r.usage.prompt_tokens or 0
                    self.total_output_tokens += r.usage.completion_tokens or 0

                text = r.choices[0].message.content or ""
                thinking, response = self._parse_structured(text)
                return thinking, response

            except Exception as e:
                self.errors += 1
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    wait = self.retry_delay * (attempt + 1)
                    print(f"[GitHubModels] Rate limited. Sleeping {wait:.0f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(wait)
                    continue
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(5)

        raise RuntimeError(f"[GitHubModels] Failed after {self.max_retries} retries")

    @staticmethod
    def _parse_structured(text: str) -> Tuple[str, str]:
        """Extract <think> and <response> from model output."""
        thinking = ""
        response = text  # fallback: entire output is the response

        if "<think>" in text:
            start = text.index("<think>") + len("<think>")
            end = text.index("</think>") if "</think>" in text else len(text)
            thinking = text[start:end].strip()

        if "<response>" in text:
            start = text.index("<response>") + len("<response>")
            end = text.index("</response>") if "</response>" in text else len(text)
            response = text[start:end].strip()

        return thinking, response

    def as_llm_callback(self):
        """Return a function matching the DNNT llm_callback signature."""
        def callback(query: str, facts: list[str]) -> Tuple[str, str]:
            return self.chat(query, facts)
        return callback

    def stats(self) -> dict:
        return {
            "model": self.model,
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "errors": self.errors,
        }
