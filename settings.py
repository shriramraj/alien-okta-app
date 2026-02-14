from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    okta_domain: str = ""
    okta_api_token: str = ""
    okta_target_group_id: str = ""
    jwt_secret: str = "change-me-in-production-min-32-chars"
    port: int = 8080

    # Demo mode: skip real Okta, treat DEMO_ALLOWLIST emails as eligible
    demo_mode: bool = False
    demo_allowlist: str = "a@b.com,c@d.com"  # comma-separated

    # CORS: comma-separated origins, or "*" for allow all (e.g. "https://app.example.com")
    cors_origins: str = "*"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def demo_allowlist_set(self) -> set[str]:
        return {e.strip().lower() for e in self.demo_allowlist.split(",") if e.strip()}

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
