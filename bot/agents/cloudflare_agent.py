import httpx
from typing import Optional
from bot.utils.config import settings


CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareAgent:
    def __init__(self):
        self.api_token = settings.cloudflare_api_token
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=CLOUDFLARE_API_BASE,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
        return self._client

    def is_configured(self) -> bool:
        return bool(self.api_token)

    async def list_zones(self) -> list[dict]:
        resp = await self.client.get("/zones", params={"per_page": 50})
        data = self._handle_response(resp)
        return data.get("result", [])

    async def get_zone(self, zone_id_or_name: str) -> Optional[dict]:
        resp = await self.client.get("/zones", params={"name": zone_id_or_name})
        data = self._handle_response(resp)
        results = data.get("result", [])
        return results[0] if results else None

    async def list_dns_records(self, zone_id: str, record_type: str = "") -> list[dict]:
        params = {"per_page": 100}
        if record_type:
            params["type"] = record_type
        resp = await self.client.get(f"/zones/{zone_id}/dns_records", params=params)
        data = self._handle_response(resp)
        return data.get("result", [])

    async def create_dns_record(self, zone_id: str, name: str, type_: str, content: str, ttl: int = 1, proxied: bool = False) -> dict:
        resp = await self.client.post(
            f"/zones/{zone_id}/dns_records",
            json={
                "type": type_,
                "name": name,
                "content": content,
                "ttl": ttl,
                "proxied": proxied,
            },
        )
        return self._handle_response(resp)

    async def delete_dns_record(self, zone_id: str, record_id: str):
        resp = await self.client.delete(f"/zones/{zone_id}/dns_records/{record_id}")
        self._handle_response(resp)

    async def update_dns_record(self, zone_id: str, record_id: str, name: str, type_: str, content: str, ttl: int = 1, proxied: bool = False) -> dict:
        resp = await self.client.put(
            f"/zones/{zone_id}/dns_records/{record_id}",
            json={
                "type": type_,
                "name": name,
                "content": content,
                "ttl": ttl,
                "proxied": proxied,
            },
        )
        return self._handle_response(resp)

    async def purge_cache(self, zone_id: str):
        resp = await self.client.post(f"/zones/{zone_id}/purge_cache", json={"purge_everything": True})
        self._handle_response(resp)

    async def get_dnssec(self, zone_id: str) -> dict:
        resp = await self.client.get(f"/zones/{zone_id}/dnssec")
        return self._handle_response(resp)

    async def list_accounts(self) -> list[dict]:
        resp = await self.client.get("/accounts")
        data = self._handle_response(resp)
        return data.get("result", [])

    @staticmethod
    def _handle_response(resp: httpx.Response) -> dict:
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"Cloudflare API: HTTP {resp.status_code} - {resp.text}")

        if not data.get("success", False):
            errors = data.get("errors", [])
            error_msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise RuntimeError(f"Cloudflare API error: {error_msg}")

        return data

    async def close(self):
        if self._client:
            await self._client.aclose()
