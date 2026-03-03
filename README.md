# Alien Okta Mini App

FastAPI backend for hackathon MVP with Okta integration and a **demo UI**.

## Local Development

### Setup

1. Clone and enter directory:
   ```bash
   cd alien-okta-app
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env: set DEMO_MODE=true for local demo (no Okta needed)
   # Optional: set DEMO_ALLOWLIST=a@b.com,c@d.com (comma-separated)
   ```

5. Run locally:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

6. Run tests (optional):
   ```bash
   pytest tests/ -v
   ```
   Uses `DEMO_MODE=true` and allowlisted test emails; no Okta needed.

---

## How to Demo (5 steps)

1. **Set demo mode** – In `.env` set `DEMO_MODE=true` and `DEMO_ALLOWLIST=a@b.com,c@d.com` (or your test emails).

2. **Open the demo UI** – Visit `http://localhost:8080/demo`. Use the form: enter email (e.g. `a@b.com`), an attestation string (≥10 chars), a nonce (e.g. `demo-001`), and amount (e.g. `100`).

3. **Run the flow** – Click **Verify Human** → then **Check Eligibility (Okta)** → then **Claim Reward**. Responses appear in the JSON viewer. In demo mode, allowlisted emails are treated as eligible.

4. **Try failures** – Use attestation &lt; 10 chars → `human_verified: false`. Use a non-allowlisted email in demo mode → eligibility `false`. Skip Verify and go straight to Claim → `403` with `reason: "human_not_verified"`.

5. **Use curl** – See sample curl commands below to hit the API from the terminal.

---

## Sample curl commands

Base URL (adjust port if needed): `http://localhost:8080`

**1. Verify Human** (attestation ≥10 chars; nonce must be unique per request or 409):

```bash
curl -s -X POST http://localhost:8080/api/verify-human \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","attestation":"I am a human proof string","nonce":"unique-nonce-1"}' | jq
```

**2. Check Eligibility** (in demo mode, allowlisted emails return `eligible: true`):

```bash
curl -s -X POST http://localhost:8080/api/eligibility \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","nonce":"any"}' | jq
```

**3. Claim Reward** (must have called verify-human first for that email; then eligibility; then claim):

```bash
curl -s -X POST http://localhost:8080/api/claim \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","nonce":"any","amount":100}' | jq
```

**4. Replay nonce (expect 409)**:

```bash
curl -s -X POST http://localhost:8080/api/verify-human \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","attestation":"long enough attestation","nonce":"same-nonce-twice"}' | jq
curl -s -X POST http://localhost:8080/api/verify-human \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","attestation":"long enough attestation","nonce":"same-nonce-twice"}' | jq
```

---

## API summary

| Endpoint | Purpose |
|----------|--------|
| `GET /` | Landing with links to demo and docs |
| `GET /demo` | **Demo UI** – single page with Verify / Eligibility / Claim buttons and JSON viewer |
| `GET /docs` | Swagger UI |
| `GET /redoc` | ReDoc |
| `GET /healthz` | Health check |
| `GET /healthz/ready` | Readiness (pings Okta when DEMO_MODE=false) |
| `POST /api/verify-human` | Verify human (attestation + nonce); returns `verification_id`; nonce replay → 409 |
| `POST /api/eligibility` | Check Okta (or demo allowlist) eligibility |
| `POST /api/claim` | Mint claim token (requires prior verify + eligible); returns `claim_token`, `expires_in_seconds`, `okta_user_id` |

### Response conventions

- **Verify:** `human_verified`, `verification_id` (or `reason` on failure).
- **Eligibility:** `eligible`, `okta_user_id`, `group_id`, `email`.
- **Claim:** `claim_token`, `expires_in_seconds`, `okta_user_id`.
- Errors include a stable `reason` field (e.g. `human_not_verified`, `not_eligible`, `nonce_reused`).

### Demo mode

- **DEMO_MODE=true** – No real Okta calls; emails in **DEMO_ALLOWLIST** (comma-separated) are treated as eligible.
- **DEMO_MODE=false** – Real Okta (requires `OKTA_DOMAIN`, `OKTA_API_TOKEN`, `OKTA_TARGET_GROUP_ID`).

---

## Deploy to Cloud Run

```bash
export PROJECT_ID=your-gcp-project-id
export SERVICE_NAME=alien-okta-app
export REGION=us-central1

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars OKTA_DOMAIN=dev-123456.okta.com,OKTA_API_TOKEN=xxx,OKTA_TARGET_GROUP_ID=xxx,JWT_SECRET=xxx,DEMO_MODE=false
```

---

## Notes

- Verification sessions (by email) expire after **5 minutes**.
- Claim tokens (JWT HS256) expire after **5 minutes**.
- Nonces in **verify-human** are replay-protected (409 if reused).
- Request logging: one line per request with endpoint, result, status, and `elapsed_ms`.

---

## Implemented extras

- **Rate limiting** – 60 requests per minute per IP (in-memory). Skipped for `/healthz`, `/healthz/ready`, `/favicon.ico`, `/openapi.json`. 429 with `reason: "rate_limited"` when exceeded.
- **Tests** – `pytest` + FastAPI `TestClient` in `tests/`. Run: `pytest tests/ -v`.
- **Readiness** – `GET /healthz/ready`: when `DEMO_MODE=true` returns 200; when `DEMO_MODE=false` pings Okta and returns 503 if unreachable.
- **One claim per verification** – After a successful claim, the verification for that email is consumed; a second claim without a new verify returns 403 `human_not_verified`.
- **CORS** – Configurable via `CORS_ORIGINS` (comma-separated or `*`). Default `*` for demo; set to your frontend origin(s) in production.
- **OpenAPI examples** – Request bodies in Swagger/ReDoc show example values (email, attestation, nonce, amount).
