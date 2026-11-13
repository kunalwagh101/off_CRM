"""Route-wide robustness sweep.

Every route is hit with: no auth, auth + empty JSON, auth + junk JSON types,
auth + non-JSON body. Any 5xx, any non-JSON 5xx body without a reference, and
any 2xx on an unauthenticated call is recorded as a finding.
"""
import json, sys, re, httpx

B = sys.argv[1]
TOKEN = sys.argv[2]
spec = json.load(open(sys.argv[3]))
out = sys.argv[4]
H = {"X-OffsetX-Token": TOKEN}
PUBLIC = {"/health/live", "/health/ready", "/api/v1/meta", "/docs/oauth2-redirect",
          "/api/v1/auth/login", "/api/v1/auth/session", "/api/v1/auth/logout",
          "/api/v1/privacy/deletion-confirmation"}
SKIP = {"/api/v1/backups/restore"}  # exercised separately with a real archive

c = httpx.Client(base_url=B, timeout=60)
rows = []

def fill(path, val):
    return re.sub(r"\{[^}]+\}", val, path)

JUNK = [{}, {"a": None}, [], "x", 12, {"name": "A" * 20000}]
for path, ops in spec["paths"].items():
    if path in SKIP:
        continue
    for method in ops:
        if method not in ("get", "post", "put", "patch", "delete"):
            continue
        for pv in ("does-not-exist", "999999", "..%2f..%2fetc"):
            p = fill(path, pv)
            # unauthenticated
            r = c.request(method, p, json={} if method != "get" else None)
            if path not in PUBLIC and r.status_code < 400:
                rows.append({"kind": "UNAUTH_OK", "m": method, "p": p, "s": r.status_code, "b": r.text[:200]})
            bodies = [None] if method in ("get", "delete") else JUNK + ["RAW"]
            for body in bodies:
                if body == "RAW":
                    r = c.request(method, p, content=b"\x00\xffnot json", headers={**H, "content-type": "application/json"})
                else:
                    r = c.request(method, p, json=body, headers=H) if body is not None else c.request(method, p, headers=H)
                if r.status_code >= 500:
                    rows.append({"kind": "5XX", "m": method, "p": p, "body": str(body)[:60], "s": r.status_code, "b": r.text[:300]})
                elif r.status_code >= 400:
                    try:
                        d = r.json()
                    except Exception:
                        rows.append({"kind": "NONJSON_4XX", "m": method, "p": p, "s": r.status_code, "b": r.text[:200]})
            if "{" not in path:
                break
json.dump(rows, open(out, "w"), indent=1)
from collections import Counter
print(Counter(r["kind"] for r in rows))
seen = set()
for r in rows:
    k = (r["kind"], r["m"], re.sub(r"(does-not-exist|999999|\.\.%2f\.\.%2fetc)", "{id}", r["p"]))
    if k in seen:
        continue
    seen.add(k)
    print(r["kind"], r["m"].upper(), k[2], r["s"], r.get("body", ""), r["b"][:160].replace("\n", " "))
