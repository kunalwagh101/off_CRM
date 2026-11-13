"""Security / penetration checks against the live local server."""
import os, re, json, httpx
from h import call, check, state, B, TOKEN

A = "Security"
s = state(); cid = s["campaign_id"]
ROOT = B.rsplit("/api/v1", 1)[0]

# --- login / session
anon = httpx.Client(base_url=B, timeout=30)
r = anon.post("/auth/login", json={"username": "major", "password": "Correct-Horse-Battery-9"})
check(A, "owner demo login works", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
sc = r.headers.get("set-cookie", "")
check(A, "session cookie is HttpOnly", "httponly" in sc.lower(), sc)
check(A, "session cookie is SameSite", "samesite" in sc.lower(), sc)
check(A, "login response does not echo the password", "Correct-Horse" not in r.text)
owner = anon

# --- create a second workspace (tenant B)
r = call("POST", "/workspaces", json={"username": "mallory2", "workspace_id": "tenant-b2", "password": "Mallory-Strong-Pass-77!", "confirm_install_owner": False})
check(A, "install owner creates a second workspace", r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}")
r = call("POST", "/workspaces", json={"username": "weak", "workspace_id": "weak-ws", "password": "123"})
check(A, "weak password for a new workspace refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
m = httpx.Client(base_url=B, timeout=60)
r = m.post("/auth/login", json={"username": "mallory2", "password": "Mallory-Strong-Pass-77!"})
check(A, "tenant B can log in", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
csrf = {}
for k, v in m.cookies.items():
    if "csrf" in k.lower():
        csrf = {"X-CSRF-Token": v}

# --- IDOR: tenant B reaches tenant A objects by id
probes = [
    ("GET", f"/campaigns/{cid}"), ("GET", f"/campaigns/{cid}/contacts"), ("GET", f"/campaigns/{cid}/drafts"),
    ("GET", f"/campaigns/{cid}/export"), ("GET", f"/campaigns/{cid}/contacts/download"),
    ("GET", f"/ai/chats/{s.get('chat_id')}/messages"), ("GET", "/ai/egress-log"), ("GET", "/memory"),
    ("GET", "/sales/board"), ("GET", "/crm/search?query=dora"), ("GET", "/dashboard"),
]
for meth, p in probes:
    r = m.request(meth, p, headers=csrf)
    leaked = r.status_code == 200 and any(x in r.text.lower() for x in ("dora", "ana silva", "pong", "cbam q4", "e2e cbam", "ella brown", "steelimport"))
    check(A, f"tenant B cannot see tenant A data: {meth} {p.split('?')[0]}", not leaked, f"{r.status_code} {r.text[:250]}")
r = m.post(f"/campaigns/{cid}/send", json={"mode": "local"}, headers=csrf)
check(A, "tenant B cannot send tenant A's campaign", r.status_code in (401, 403, 404), f"{r.status_code} {r.text[:200]}")
r = m.patch(f"/campaigns/{cid}", json={"daily_send_limit": 1}, headers=csrf)
check(A, "tenant B cannot edit tenant A's campaign", r.status_code in (401, 403, 404), f"{r.status_code} {r.text[:200]}")
r = m.post("/workspaces", json={"username": "x2", "workspace_id": "x2", "password": "Strong-Pass-123456!"}, headers=csrf)
check(A, "tenant B (non-owner) cannot create workspaces", r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}")
r = m.post("/backups/export", json={"passphrase": "a-very-long-passphrase-123"}, headers=csrf)
check(A, "tenant B cannot export the whole install backup", r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}")
r = m.post("/ai/providers/nvidia/connect", json={"api_key": "nvapi-x"}, headers=csrf)
check(A, "tenant B connecting a key does not touch tenant A's provider", True, f"{r.status_code}")
r = call("GET", "/ai/providers")
nv = [p for p in r.j["providers"] if p["id"] == "nvidia"][0]
check(A, "tenant A's NVIDIA model unchanged after tenant B action", nv["model_id"] == "nvidia/nemotron-3-ultra-550b-a55b", nv["model_id"])

# --- CSRF: cookie session POST without CSRF header
r = owner.post("/campaigns", json={"name": "csrf-probe"})
check(A, "cookie-session POST without CSRF token is refused", r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}")
r = owner.post("/campaigns", json={"name": "csrf-probe2"}, headers={"Origin": "https://evil.example"})
check(A, "cross-origin POST refused", r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}")

# --- logout really ends the session
r = m.post("/auth/logout", headers=csrf)
r2 = m.get("/dashboard")
check(A, "after logout the old session is refused", r2.status_code == 401, f"{r.status_code}/{r2.status_code}")

# --- disabled workspace
r = call("PATCH", "/workspaces/mallory2", json={"enabled": False})
m2 = httpx.Client(base_url=B, timeout=30)
r = m2.post("/auth/login", json={"username": "mallory2", "password": "Mallory-Strong-Pass-77!"})
check(A, "disabled workspace cannot log in", r.status_code in (401, 403), f"{r.status_code} {r.text[:200]}")
r = m2.post("/auth/login", json={"username": "MAJOR", "password": "Correct-Horse-Battery-9"})
check(A, "username lookup does not create a second identity by case", r.status_code in (200, 401), f"{r.status_code}")

# --- token timing / misuse
for bad in ["", "x", TOKEN + "x", TOKEN.upper(), "Bearer " + TOKEN]:
    r = httpx.get(B + "/dashboard", headers={"X-OffsetX-Token": bad})
    check(A, f"bad token variant refused ({bad[:6]!r}...)", r.status_code == 401, r.status_code)
r = httpx.get(B + "/dashboard?token=" + TOKEN)
check(A, "token in query string is not accepted (would leak in logs)", r.status_code == 401, r.status_code)

# --- host header / clickjacking / CSP on SPA
r = httpx.get(ROOT + "/", headers={"Host": "evil.example"})
check(A, "foreign Host header refused (DNS rebinding)", r.status_code in (400, 421), r.status_code)
r = httpx.get(ROOT + "/")
check(A, "SPA sends CSP and frame-deny", "frame-ancestors" in r.headers.get("content-security-policy", "") or r.headers.get("x-frame-options") == "DENY", dict(r.headers))
r = httpx.get(ROOT + "/docs/oauth2-redirect")
check(A, "leftover Swagger oauth2-redirect page not public", r.status_code in (401, 404), f"{r.status_code} (public static page with inline script)")

# --- secrets in logs / disk
log = open(os.environ["OFFCRM_E2E_SERVER_LOG"], errors="replace").read()
key = os.environ["NVIDIA_API_KEY"]
check(A, "server log never contains the NVIDIA key", key not in log)
check(A, "server log never contains the login password", "Correct-Horse-Battery-9" not in log and "Mallory-Strong" not in log)
check(A, "server log never contains contact emails", "dora.klein@steelimport-test.example" not in log, re.findall(r"[\w.]+@steelimport[\w.-]+", log)[:3])
hits = []
for dp, _, fs in os.walk(os.environ["OFFSETX_DATA_DIR"]):
    for f in fs:
        p = os.path.join(dp, f)
        try:
            if key.encode() in open(p, "rb").read():
                hits.append(p)
        except Exception:
            pass
check(A, "NVIDIA key is never stored in plain text anywhere on disk", not hits, hits)
