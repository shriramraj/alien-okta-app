import time
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.openapi.docs import get_redoc_html

from app.models import (
    VerifyHumanRequest,
    VerifyHumanResponse,
    EligibilityRequest,
    EligibilityResponse,
    ClaimRequest,
    ClaimResponse,
)
from app.security import (
    VERIFICATION_TTL_SECONDS,
    mint_claim_token,
    verify_replay_store,
    verification_store,
)
from app.okta import okta_client
from app.rate_limit import rate_limiter
from app.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Alien Okta Mini App",
    description="API for human verification, eligibility check, and claim.",
    version="1.0.0",
    openapi_url="/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Paths that skip rate limiting
RATE_LIMIT_SKIP = {"/healthz", "/healthz/ready", "/favicon.ico", "/openapi.json"}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in RATE_LIMIT_SKIP:
        return await call_next(request)
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        return Response(
            content='{"reason":"rate_limited","message":"Too many requests"}',
            status_code=429,
            media_type="application/json",
        )
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    email = request.query_params.get("email", "")
    endpoint = request.url.path
    result = "ok" if response.status_code < 400 else "fail"
    logger.info("endpoint=%s email=%s result=%s status=%s elapsed_ms=%s",
                endpoint, email or "-", result, response.status_code, elapsed_ms)
    return response


@app.get("/redoc", include_in_schema=False)
async def redoc_html(request: Request):
    openapi_url = str(request.base_url).rstrip("/") + "/openapi.json"
    return get_redoc_html(openapi_url=openapi_url, title=app.title + " - ReDoc")


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Alien Okta Mini App</title></head>
    <body style="font-family: system-ui; max-width: 40rem; margin: 2rem auto; padding: 0 1rem;">
        <h1>Alien Okta Mini App</h1>
        <ul>
            <li><a href="/demo">Demo UI</a></li>
            <li><a href="/docs">API docs (Swagger)</a></li>
            <li><a href="/redoc">API docs (ReDoc)</a></li>
            <li><a href="/healthz">Health check</a></li>
        </ul>
        <h2>API</h2>
        <ul>
            <li><code>POST /api/verify-human</code> — verify human</li>
            <li><code>POST /api/eligibility</code> — check eligibility</li>
            <li><code>POST /api/claim</code> — claim</li>
        </ul>
    </body>
    </html>
    """


# ----- Demo UI (single HTML page) -----
DEMO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Alien Okta Demo</title>
  <style>
    body { font-family: system-ui; max-width: 42rem; margin: 2rem auto; padding: 0 1rem; }
    label { display: block; margin-top: 0.75rem; font-weight: 600; }
    input, textarea { width: 100%; padding: 0.5rem; box-sizing: border-box; }
    button { margin-top: 1rem; margin-right: 0.5rem; padding: 0.5rem 1rem; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    #output { margin-top: 1.5rem; padding: 1rem; background: #f5f5f5; border-radius: 6px; font-family: monospace; white-space: pre-wrap; word-break: break-all; min-height: 4rem; }
    .error { color: #c00; }
    .success { color: #080; }
    h2 { margin-top: 1.5rem; }
    .flow { background: #eee; padding: 0.5rem 0.75rem; border-radius: 6px; margin: 0.75rem 0; font-size: 0.95rem; }
    #verificationId { font-family: monospace; font-size: 0.9rem; margin-top: 0.25rem; }
  </style>
</head>
<body>
  <h1>Alien Okta Mini App – Demo</h1>
  <div class="flow"><strong>Flow:</strong> 1. Verify Human → 2. Check Eligibility → 3. Claim Reward</div>

  <label for="email">Email</label>
  <input id="email" type="email" placeholder="e.g. you@example.com">

  <label for="attestation">Attestation (min 10 chars for verify)</label>
  <input id="attestation" type="text" placeholder="e.g. I am a human proof string" value="I am a human proof string">

  <label for="nonce">Nonce (use a new value each time you run Verify)</label>
  <input id="nonce" type="text" placeholder="e.g. my-nonce-123" value="">

  <label for="amount">Amount (for claim)</label>
  <input id="amount" type="number" value="100" min="1" max="1000000">

  <p id="verificationId" style="display:none;"></p>

  <h2>Actions</h2>
  <button id="btnVerify">1. Verify Human</button>
  <button id="btnEligibility">2. Check Eligibility</button>
  <button id="btnClaim">3. Claim Reward</button>

  <h2>Response (JSON)</h2>
  <div id="output">—</div>

  <script>
    const base = window.location.origin;
    const output = document.getElementById('output');
    const verificationIdEl = document.getElementById('verificationId');
    const buttons = ['btnVerify', 'btnEligibility', 'btnClaim'];

    function setLoading(loading) {
      buttons.forEach(id => {
        const btn = document.getElementById(id);
        if (!btn) return;
        btn.disabled = loading;
        if (loading) btn.dataset.oldText = btn.textContent;
        btn.textContent = loading ? 'Loading…' : (btn.dataset.oldText || btn.textContent);
      });
    }

    function show(data, isError) {
      output.textContent = JSON.stringify(data, null, 2);
      output.className = isError ? 'error' : 'success';
    }

    function showVerificationId(vid) {
      if (vid) {
        verificationIdEl.style.display = 'block';
        verificationIdEl.textContent = 'Verification ID (valid 5 min): ' + vid;
      } else {
        verificationIdEl.style.display = 'none';
      }
    }

    async function api(path, body) {
      setLoading(true);
      try {
        const res = await fetch(base + path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          show({ status: res.status, ...data }, true);
          if (path === '/api/verify-human') showVerificationId(null);
        } else {
          show(data, false);
          if (path === '/api/verify-human' && data.verification_id) showVerificationId(data.verification_id);
        }
      } finally {
        setLoading(false);
      }
    }

    document.getElementById('btnVerify').onclick = () => {
      const email = document.getElementById('email').value;
      const attestation = document.getElementById('attestation').value;
      const nonce = document.getElementById('nonce').value || ('n-' + Date.now());
      document.getElementById('nonce').value = nonce;
      api('/api/verify-human', { email, attestation, nonce });
    };

    document.getElementById('btnEligibility').onclick = () => {
      const email = document.getElementById('email').value;
      const nonce = document.getElementById('nonce').value;
      api('/api/eligibility', { email, nonce: nonce || 'any' });
    };

    document.getElementById('btnClaim').onclick = () => {
      const email = document.getElementById('email').value;
      const nonce = document.getElementById('nonce').value;
      const amount = parseInt(document.getElementById('amount').value, 10);
      api('/api/claim', { email, nonce: nonce || 'any', amount });
    };

    if (!document.getElementById('nonce').value) document.getElementById('nonce').value = 'n-' + Date.now();
  </script>
</body>
</html>
"""


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
async def demo_page():
    return DEMO_HTML


# ----- Favicon -----
FAVICON_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(content=FAVICON_BYTES, media_type="image/png")


@app.on_event("startup")
async def startup():
    logger.info("DEMO_MODE=%s", str(settings.demo_mode).lower())
    if not settings.demo_mode and not settings.okta_domain:
        logger.warning("DEMO_MODE is false but OKTA_DOMAIN is empty; Okta calls will fail.")


@app.on_event("shutdown")
async def shutdown():
    pass


@app.get("/healthz")
async def health_check():
    return {"status": "healthy"}


@app.get("/healthz/ready", include_in_schema=False)
async def health_ready():
    """When DEMO_MODE=false, pings Okta; 503 if unreachable."""
    if settings.demo_mode:
        return {"status": "ready", "demo_mode": True}
    ok = await okta_client.ping()
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "okta_unreachable", "message": "Okta API unreachable"},
        )
    return {"status": "ready", "demo_mode": False}


# Input limits (hackathon-friendly)
MAX_ATTESTATION_LEN = 10_000
MAX_CLAIM_AMOUNT = 1_000_000

# ----- API: verify-human -----
@app.post("/api/verify-human", response_model=VerifyHumanResponse)
async def verify_human(request: VerifyHumanRequest):
    verification_store.cleanup_expired()

    if verify_replay_store.is_replay(request.nonce):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "nonce_reused", "message": "Nonce already used"},
        )

    if len(request.attestation) < 10:
        return VerifyHumanResponse(
            human_verified=False,
            verification_id=None,
            reason="attestation_too_short",
        )
    if len(request.attestation) > MAX_ATTESTATION_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "attestation_too_long", "message": f"Attestation max {MAX_ATTESTATION_LEN} chars"},
        )

    verification_id = __import__("secrets").token_urlsafe(16)
    verify_replay_store.mark_used(request.nonce)
    verification_store.set(request.email, verification_id)

    return VerifyHumanResponse(
        human_verified=True,
        verification_id=verification_id,
        expires_in_seconds=VERIFICATION_TTL_SECONDS,
    )


# ----- API: eligibility -----
@app.post("/api/eligibility", response_model=EligibilityResponse)
async def check_eligibility(request: EligibilityRequest):
    try:
        eligible, okta_user_id, group_id = await okta_client.is_user_in_target_group(
            request.email
        )
        return EligibilityResponse(
            eligible=eligible,
            okta_user_id=okta_user_id,
            group_id=group_id,
            email=request.email,
        )
    except Exception as e:
        logger.exception("Eligibility error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"reason": "okta_error", "message": str(e)},
        )


# ----- API: claim -----
@app.post("/api/claim", response_model=ClaimResponse)
async def claim(request: ClaimRequest):
    verification_store.cleanup_expired()

    vid = verification_store.get_valid(request.email)
    if not vid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": "human_not_verified", "message": "Complete verify-human first"},
        )

    if request.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "invalid_amount", "message": "Amount must be positive"},
        )
    if request.amount > MAX_CLAIM_AMOUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "amount_too_high", "message": f"Amount max {MAX_CLAIM_AMOUNT}"},
        )

    try:
        eligible, okta_user_id, _ = await okta_client.is_user_in_target_group(
            request.email
        )
        if not eligible or not okta_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"reason": "not_eligible", "message": "User not in target group"},
            )

        claim_token, expires_in_seconds = mint_claim_token(
            okta_user_id, request.nonce, request.amount
        )
        verification_store.consume(request.email)  # one claim per verification
        return ClaimResponse(
            claim_token=claim_token,
            expires_in_seconds=expires_in_seconds,
            okta_user_id=okta_user_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Claim error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"reason": "claim_error", "message": str(e)},
        )
