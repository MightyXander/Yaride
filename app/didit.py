from __future__ import annotations

from dataclasses import dataclass

import aiohttp


@dataclass(slots=True)
class DiditSession:
    session_id: str
    session_token: str
    session_number: str
    url: str


class DiditClient:
    def __init__(
        self,
        api_key: str,
        workflow_id: str,
        base_url: str = "https://verification.didit.me/v3",
        callback_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.workflow_id = workflow_id
        self.base_url = base_url.rstrip("/")
        self.callback_url = callback_url

    async def create_session(self, vendor_data: str) -> DiditSession:
        payload: dict[str, object] = {
            "workflow_id": self.workflow_id,
            "vendor_data": vendor_data,
        }
        if self.callback_url:
            payload["callback"] = self.callback_url

        headers = {"x-api-key": self.api_key, "content-type": "application/json"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.post(f"{self.base_url}/sessions/", json=payload, headers=headers) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"Didit create session failed: {response.status} {body}")
        return DiditSession(
            session_id=str(body["session_id"]),
            session_token=str(body.get("session_token", "")),
            session_number=str(body.get("session_number", "")),
            url=str(body["url"]),
        )

    async def get_session_status(self, session_id: str) -> str:
        headers = {"x-api-key": self.api_key}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(f"{self.base_url}/sessions/{session_id}/", headers=headers) as response:
                body = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(f"Didit get session failed: {response.status} {body}")
        return str(body.get("status", "pending"))
