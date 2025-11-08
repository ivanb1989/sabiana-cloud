from __future__ import annotations
from typing import Any, Dict, List
from aiohttp import ClientSession, ClientTimeout

class SabianaApiError(Exception):
    pass

class SabianaApiClient:
    def __init__(self, session: ClientSession, base_url: str, api_key: str, *, timeout: int = 15) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._headers = {"accept": "application/json", "auth": api_key}
        self._timeout = ClientTimeout(total=timeout)

    async def _get_json(self, path: str) -> Any:
        url = f"{self._base}{path}"
        async with self._session.get(url, headers=self._headers, timeout=self._timeout) as resp:
            if resp.status == 403:
                raise SabianaApiError("Forbidden (API key o rate limit)")
            if resp.status == 404:
                raise SabianaApiError("Endpoint non trovato")
            resp.raise_for_status()
            return await resp.json()

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Any:
        url = f"{self._base}{path}"
        async with self._session.post(url, headers={**self._headers, "Content-Type": "application/json"},
                                      json=payload, timeout=self._timeout) as resp:
            if resp.status == 403:
                raise SabianaApiError("Forbidden (API key o rate limit)")
            if resp.status == 404:
                raise SabianaApiError("Endpoint non trovato")
            resp.raise_for_status()
            if resp.content_length and resp.content_type == "application/json":
                return await resp.json()
            return None

    async def list_vent(self) -> List[Dict[str, Any]]:
        return await self._get_json("/api/v1/vent")

    async def get_unit(self, address: str) -> Dict[str, Any]:
        return await self._get_json(f"/api/v1/unit/{address}")

    async def cmd_vent(self, address: str, payload: Dict[str, Any]) -> None:
        await self._post_json(f"/api/v1/cmd/vent/{address}", payload)
