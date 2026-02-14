import httpx
from typing import Optional

from app.settings import settings


class OktaClient:
    def __init__(self):
        self.base_url = f"https://{settings.okta_domain}" if settings.okta_domain else ""
        self.headers = {
            "Authorization": f"SSWS {settings.okta_api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        if not self.base_url:
            return None
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/users",
                headers=self.headers,
                params={"filter": f'profile.email eq "{email}"'},
            )
            response.raise_for_status()
            users = response.json()
            return users[0] if users else None

    async def get_user_groups(self, user_id: str) -> list[dict]:
        if not self.base_url:
            return []
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/users/{user_id}/groups",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def is_user_in_target_group(
        self, email: str
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Returns (eligible, okta_user_id, group_id)."""
        if settings.demo_mode:
            allowlist = settings.demo_allowlist_set
            if email.lower() in allowlist:
                return True, "demo-" + email.lower().replace("@", "-"), "demo-group"
            return False, None, None

        user = await self.get_user_by_email(email)
        if not user:
            return False, None, None

        user_id = user["id"]
        groups = await self.get_user_groups(user_id)

        for group in groups:
            if group["id"] == settings.okta_target_group_id:
                return True, user_id, settings.okta_target_group_id

        return False, user_id, None

    async def ping(self) -> bool:
        """Light call to Okta to check connectivity. Returns True if OK."""
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient() as client:
                # Minimal read: list users with limit 1
                r = await client.get(
                    f"{self.base_url}/api/v1/users",
                    headers=self.headers,
                    params={"limit": "1"},
                    timeout=5.0,
                )
                return r.status_code == 200
        except Exception:
            return False


okta_client = OktaClient()
