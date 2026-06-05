import httpx
import json
from typing import Optional
from bot.utils.config import settings
from bot.db.repository import get_active_api_keys


OPENAI_COMPATIBLE_HEADERS = {
    "Content-Type": "application/json",
}


class LLMRouter:
    def __init__(self):
        self.current_provider = settings.default_llm_provider or "auto"
        self._provider_cache = {}

    async def _discover_best_key(self) -> Optional[dict]:
        keys = await get_active_api_keys()
        priority = ["openrouter", "groq", "openai", "anthropic", "google", "mistral", "deepseek", "together"]
        for prov in priority:
            for k in keys:
                if k["provider"] == prov:
                    return k
        return keys[0] if keys else None

    async def get_provider_config(self) -> dict:
        if self.current_provider == "auto":
            key = await self._discover_best_key()
            if key:
                return {
                    "provider": key["provider"],
                    "api_key": key["api_key"],
                    "base_url": key.get("base_url") or self._default_base_url(key["provider"]),
                }
            return {"provider": "ollama", "api_key": "", "base_url": settings.ollama_base_url}

        if self.current_provider == "ollama":
            return {"provider": "ollama", "api_key": "", "base_url": settings.ollama_base_url}

        if self.current_provider == "openrouter":
            return {
                "provider": "openrouter",
                "api_key": settings.openrouter_api_key,
                "base_url": "https://openrouter.ai/api/v1",
            }

        if self.current_provider == "groq":
            return {
                "provider": "groq",
                "api_key": settings.groq_api_key,
                "base_url": "https://api.groq.com/openai/v1",
            }

        keys = await get_active_api_keys(self.current_provider)
        if keys:
            return {
                "provider": self.current_provider,
                "api_key": keys[0]["api_key"],
                "base_url": keys[0].get("base_url") or self._default_base_url(self.current_provider),
            }

        return {"provider": "ollama", "api_key": "", "base_url": settings.ollama_base_url}

    def _default_base_url(self, provider: str) -> str:
        urls = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "google": "https://generativelanguage.googleapis.com/v1beta",
            "deepseek": "https://api.deepseek.com/v1",
            "together": "https://api.together.xyz/v1",
            "mistral": "https://api.mistral.ai/v1",
            "cohere": "https://api.cohere.com/v2",
            "perplexity": "https://api.perplexity.ai",
            "huggingface": "https://api-inference.huggingface.co/v1",
            "cerebras": "https://api.cerebras.ai/v1",
        }
        return urls.get(provider, f"https://api.{provider}.com/v1")

    async def chat_completion(self, messages: list[dict], model: str = "", max_tokens: int = 1024) -> str:
        config = await self.get_provider_config()
        provider = config["provider"]
        api_key = config["api_key"]
        base_url = config["base_url"]

        if provider == "ollama":
            return await self._ollama_chat(messages, model or "llama3")

        if not api_key:
            return "No API key available for this provider."

        model = model or self._default_model(provider)
        headers = {**OPENAI_COMPATIBLE_HEADERS}

        if provider in ("openai", "groq", "openrouter", "deepseek", "together", "perplexity", "cerebras"):
            headers["Authorization"] = f"Bearer {api_key}"
        elif provider == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        elif provider == "google":
            base_url = f"{base_url}/models/{model}:generateContent"
        elif provider == "huggingface":
            headers["Authorization"] = f"Bearer {api_key}"

        if provider == "anthropic":
            return await self._anthropic_chat(base_url, headers, messages, model, max_tokens)

        if provider == "google":
            return await self._google_chat(base_url, headers, messages)

        url = f"{base_url}/chat/completions"
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                elif resp.status_code == 429:
                    return f"[Rate limited on {provider}]"
                else:
                    return f"[{provider} error: HTTP {resp.status_code}]"
            except Exception as e:
                return f"[{provider} connection error: {str(e)[:100]}]"

    async def _ollama_chat(self, messages: list[dict], model: str) -> str:
        url = f"{settings.ollama_base_url}/api/chat"
        body = {"model": model, "messages": messages, "stream": False}
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                resp = await client.post(url, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["message"]["content"]
                return f"[Ollama error: HTTP {resp.status_code}]"
            except Exception as e:
                return f"[Ollama unavailable: {str(e)[:100]}]"

    async def _anthropic_chat(self, base_url: str, headers: dict, messages: list[dict], model: str, max_tokens: int) -> str:
        system_msgs = [m for m in messages if m["role"] == "system"]
        chat_msgs = [m for m in messages if m["role"] != "system"]

        body = {
            "model": model or "claude-sonnet-4-20250514",
            "messages": chat_msgs,
            "max_tokens": max_tokens,
        }
        if system_msgs:
            body["system"] = system_msgs[0]["content"]

        url = f"{base_url}/messages"
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["content"][0]["text"]
                return f"[Anthropic error: HTTP {resp.status_code}]"
            except Exception as e:
                return f"[Anthropic error: {str(e)[:100]}]"

    async def _google_chat(self, base_url: str, headers: dict, messages: list[dict]) -> str:
        contents = []
        for m in messages:
            if m["role"] != "system":
                contents.append({"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]})

        body = {"contents": contents}
        api_key = headers.get("x-api-key") or headers.get("Authorization", "").replace("Bearer ", "")
        url = f"{base_url}?key={api_key}"

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(url, json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                return f"[Google error: HTTP {resp.status_code}]"
            except Exception as e:
                return f"[Google error: {str(e)[:100]}]"

    @staticmethod
    def _default_model(provider: str) -> str:
        models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "google": "gemini-2.5-flash",
            "deepseek": "deepseek-chat",
            "together": "meta-llama/llama-3.3-70b-instruct-turbo",
            "mistral": "mistral-small-latest",
            "cohere": "command-r-plus",
            "perplexity": "sonar-pro",
            "cerebras": "llama-3.1-8b",
            "replicate": "meta/meta-llama-3-70b-instruct",
        }
        return models.get(provider, "gpt-4o-mini")

    async def summarize_emails(self, emails: list[dict]) -> str:
        if not emails:
            return "No emails to summarize."

        email_text = "\n\n".join(
            f"From: {e['from']}\nSubject: {e['subject']}\n{e.get('body', e.get('snippet', ''))[:500]}"
            for e in emails[:10]
        )

        messages = [
            {"role": "system", "content": "You are an email assistant. Summarize the following emails concisely in French. Group by topic, highlight important messages."},
            {"role": "user", "content": f"Here are the latest emails:\n\n{email_text}"},
        ]

        return await self.chat_completion(messages, max_tokens=2048)
