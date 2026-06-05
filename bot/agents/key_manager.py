import asyncio
import json
import os
import subprocess
from datetime import datetime
from typing import Optional

from bot.db.repository import save_api_key, get_active_api_keys, update_api_key_status, log_action
from bot.utils.config import settings
from bot.utils.crypto import encrypt


KEYHUNTER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "key-hunter")


FREE_PROVIDERS = {
    "openrouter": {
        "signup_url": "https://openrouter.ai/keys",
        "models": ["llama-3.3-70b", "qwen-3", "deepseek-v4-flash"],
        "rate_limits": "50 req/day",
        "requires_cc": False,
    },
    "groq": {
        "signup_url": "https://console.groq.com/keys",
        "models": ["llama-3.3-70b", "qwen-32b", "deepseek-r1"],
        "rate_limits": "1000 req/day",
        "requires_cc": False,
    },
    "google_gemini": {
        "signup_url": "https://aistudio.google.com/app/apikey",
        "models": ["gemini-2.5-flash", "gemma-3-27b"],
        "rate_limits": "20 req/day",
        "requires_cc": False,
    },
    "cloudflare_workers": {
        "signup_url": "https://dash.cloudflare.com/profile/api-tokens",
        "models": ["llama-3.3-70b", "qwen-3", "kimi-k2.6"],
        "rate_limits": "10000 neurons/day",
        "requires_cc": False,
    },
    "github_models": {
        "signup_url": "https://github.com/marketplace/models",
        "models": ["gpt-4.1", "claude", "llama", "deepseek"],
        "rate_limits": "limited free tier",
        "requires_cc": False,
    },
    "huggingface": {
        "signup_url": "https://huggingface.co/settings/tokens",
        "models": ["various open models <10GB"],
        "rate_limits": "$0.10/month credits",
        "requires_cc": False,
    },
    "nvidia_nim": {
        "signup_url": "https://build.nvidia.com/",
        "models": ["various open models"],
        "rate_limits": "40 RPM",
        "requires_cc": False,
        "requires_phone": True,
    },
    "cohere": {
        "signup_url": "https://dashboard.cohere.com/api-keys",
        "models": ["command-r+", "command-a"],
        "rate_limits": "1000 req/month",
        "requires_cc": False,
    },
    "mistral": {
        "signup_url": "https://console.mistral.ai/",
        "models": ["mistral-small", "mistral-medium"],
        "rate_limits": "1 req/s",
        "requires_cc": False,
        "requires_phone": True,
    },
    "cerebras": {
        "signup_url": "https://cloud.cerebras.ai/",
        "models": ["gpt-oss-120b", "llama-3.1-8b"],
        "rate_limits": "30 RPM",
        "requires_cc": False,
    },
}


class KeyManager:
    def __init__(self):
        self.keyhunter_dir = KEYHUNTER_DIR

    @property
    def is_keyhunter_available(self) -> bool:
        main_py = os.path.join(self.keyhunter_dir, "main.py")
        return os.path.isfile(main_py)

    async def run_keyhunter_scan(self, provider: str = "", pages: int = 2, verify: bool = True) -> list[dict]:
        if not self.is_keyhunter_available:
            raise RuntimeError(
                "key-hunter not found. Clone it: git clone https://github.com/thelambdaone-commits/key-hunter"
            )

        env = os.environ.copy()
        if settings.github_token:
            env["GITHUB_TOKEN"] = settings.github_token
        if settings.github_account_token:
            env["GITHUB_ACCOUNT_TOKEN"] = settings.github_account_token

        cmd = [
            "python3", os.path.join(self.keyhunter_dir, "main.py"),
            "--once",
        ]
        if verify:
            cmd.append("--verify")
        if provider:
            cmd.extend(["--providers", provider])
        cmd.extend(["--pages", str(pages)])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=self.keyhunter_dir,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"KeyHunter scan failed: {stderr.decode()[:500]}")

        findings = []
        results_dir = os.path.join(self.keyhunter_dir, "results")
        if os.path.isdir(results_dir):
            for fname in os.listdir(results_dir):
                if fname.endswith(".json") and ("findings" in fname or "verified" in fname or "working" in fname):
                    fpath = os.path.join(results_dir, fname)
                    try:
                        with open(fpath) as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                findings.extend(data)
                            elif isinstance(data, dict) and "keys" in data:
                                findings.extend(data["keys"])
                    except (json.JSONDecodeError, IOError):
                        pass

            txt_path = os.path.join(results_dir, "working-keys.txt")
            if os.path.isfile(txt_path):
                with open(txt_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            findings.append({
                                "key": line,
                                "provider": provider or "unknown",
                                "source": "keyhunter_txt",
                            })

        for f in findings:
            key = f.get("key") or f.get("key_masked", "")
            prov = f.get("provider") or provider or "unknown"
            if key and key != "...":
                await save_api_key(
                    provider=prov,
                    api_key=key,
                    source="keyhunter",
                )

        return findings

    async def get_key_status(self) -> list[dict]:
        keys = await get_active_api_keys()
        return keys

    async def test_key(self, provider: str) -> dict:
        keys = await get_active_api_keys(provider)
        if not keys:
            return {"status": "no_keys", "provider": provider}

        import httpx

        for key_data in keys[:3]:
            api_key = key_data["api_key"]
            try:
                result = await self._test_single_key(provider, api_key)
                if result.get("valid"):
                    return {
                        "status": "valid",
                        "provider": provider,
                        "key_id": key_data["id"],
                        "details": result,
                    }
                else:
                    await update_api_key_status(key_data["id"], "expired")
            except Exception as e:
                await update_api_key_status(key_data["id"], "rate_limited")

        return {"status": "no_valid_keys", "provider": provider}

    async def _test_single_key(self, provider: str, api_key: str) -> dict:
        import httpx

        endpoints = {
            "openai": ("https://api.openai.com/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "anthropic": ("https://api.anthropic.com/v1/messages", {"x-api-key": api_key, "anthropic-version": "2023-06-01"}),
            "groq": ("https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "openrouter": ("https://openrouter.ai/api/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "google": ("https://generativelanguage.googleapis.com/v1beta/models", {}),
            "huggingface": ("https://huggingface.co/api/whoami-v2", {"Authorization": f"Bearer {api_key}"}),
            "cohere": ("https://api.cohere.com/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "mistral": ("https://api.mistral.ai/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "deepseek": ("https://api.deepseek.com/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "together": ("https://api.together.xyz/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "perplexity": ("https://api.perplexity.ai/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "fireworks": ("https://api.fireworks.ai/inference/v1/models", {"Authorization": f"Bearer {api_key}"}),
            "replicate": ("https://api.replicate.com/v1/account", {"Authorization": f"Bearer {api_key}"}),
        }

        if provider not in endpoints:
            return {"valid": False, "reason": f"No test endpoint for {provider}"}

        url, headers = endpoints[provider]
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return {"valid": True, "status_code": resp.status_code}
            elif resp.status_code == 429:
                return {"valid": False, "reason": "rate_limited"}
            else:
                return {"valid": False, "reason": f"HTTP {resp.status_code}"}

    async def auto_register_provider(self, provider: str) -> dict:
        if provider not in FREE_PROVIDERS:
            return {"status": "unsupported", "provider": provider}

        info = FREE_PROVIDERS[provider]
        from scrapling.fetchers import StealthyFetcher

        try:
            page = StealthyFetcher.fetch(
                info["signup_url"],
                headless=True,
                solve_cloudflare=True,
                network_idle=True,
            )

            return {
                "status": "page_loaded",
                "provider": provider,
                "signup_url": info["signup_url"],
                "message": f"Loaded signup page for {provider}. Manual interaction may be required for credentials.",
            }
        except Exception as e:
            return {"status": "error", "provider": provider, "error": str(e)}

    async def rotate_key(self, provider: str) -> Optional[dict]:
        keys = await get_active_api_keys(provider)
        if not keys:
            return None

        for key_data in keys:
            result = await self._test_single_key(provider, key_data["api_key"])
            if result.get("valid"):
                return {"provider": provider, "key_id": key_data["id"], "status": "active"}

        return None

    async def list_providers(self) -> list[dict]:
        keys = await get_active_api_keys()
        providers = {}
        for k in keys:
            if k["provider"] not in providers:
                providers[k["provider"]] = {"provider": k["provider"], "key_count": 0, "models": []}
            providers[k["provider"]]["key_count"] += 1

        return list(providers.values())
