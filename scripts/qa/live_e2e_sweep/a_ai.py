import os, json
from h import call, check, save

A = "AI/NVIDIA"
key = os.environ["NVIDIA_API_KEY"]

r = call("POST", "/ai/providers/nvidia/connect", json={"api_key": "nvapi-bogus-000000000000000000000000000000000000000000"})
check(A, "connect with a bad key is refused or flagged, not marked healthy", r.status_code >= 400 or "invalid" in r.text.lower() or "401" in r.text, f"{r.status_code} {r.text[:300]}")

r = call("POST", "/ai/providers/nvidia/connect", json={"api_key": key, "enabled": True})
check(A, "connect with DEFAULT model then a call works (fresh-user path)", call("POST", "/ai/run", json={"mode": "simple", "data_class": "public", "instructions": "Reply PONG", "public_text": ""}).status_code == 200, "default model meta/llama-3.1-70b-instruct is retired by NVIDIA (410)")
r = call("POST", "/ai/providers/nvidia/connect", json={"api_key": key, "enabled": True, "model_id": "nvidia/nemotron-3-ultra-550b-a55b", "model_ids": ["nvidia/nemotron-3-ultra-550b-a55b"]})
check(A, "connect NVIDIA with real key through the app", r.ok_, f"{r.status_code} {r.text[:300]}")
check(A, "key never echoed back in connect response", key not in r.text, "key echoed")

r = call("GET", "/ai/providers")
nv = [p for p in (r.j or {}).get("providers", []) if p["id"] == "nvidia"]
check(A, "provider list shows nvidia connected", bool(nv) and nv[0].get("connected"), nv[:1])
check(A, "provider list never contains the key", key not in r.text)
models = [m["id"] for m in nv[0]["models"]] if nv else []

r = call("POST", "/ai/providers/nvidia/balance")
check(A, "balance check answers with a readable result", r.status_code < 500, f"{r.status_code} {r.text[:300]}")

r = call("POST", "/ai/providers/nvidia/discover-models", expect=(200,))
check(A, "discover models from NVIDIA live", r.ok_ and len(r.text) > 50, f"{r.status_code} {r.elapsed_s}s {r.text[:300]}")

r = call("GET", "/ai/modes")
check(A, "modes listed", r.ok_, r.text[:200])

r = call("POST", "/ai/plan", json={"data_class": "public", "task_type": "writing"})
check(A, "router plan for public writing picks a connected model", r.ok_ and "nvidia" in r.text, f"{r.status_code} {r.text[:400]}")

r = call("POST", "/ai/run", json={"mode": "simple", "data_class": "public", "instructions": "Reply with exactly the single word PONG.", "public_text": "ping"})
check(A, "ai/run simple mode returns real model text", r.ok_ and "PONG" in r.text.upper(), f"{r.status_code} {r.elapsed_s}s {r.text[:500]}")
save(run_simple=r.text[:2000])

r = call("POST", "/ai/run", json={"mode": "verified", "data_class": "public", "instructions": "Write one short sentence about bread.", "public_text": ""})
check(A, "ai/run verified mode", r.status_code < 500, f"{r.status_code} {r.elapsed_s}s {r.text[:500]}")

r = call("POST", "/ai/run", json={"mode": "simple", "data_class": "mailbox", "instructions": "Summarise", "public_text": "secret inbox mail"})
check(A, "mailbox data class is refused (rule 5)", r.status_code in (400, 403, 409, 422) or "not permitted" in r.text.lower(), f"{r.status_code} {r.text[:300]}")

r = call("POST", "/ai/chats", json={"title": "E2E chat"})
check(A, "create chat", r.ok_, r.text[:200])
cid = (r.j or {}).get("id") or (r.j or {}).get("chat", {}).get("id")
save(chat_id=cid)
r = call("POST", f"/ai/chats/{cid}/messages", json={"content": "Reply with exactly the word PONG.", "data_class": "public"})
check(A, "chat message gets a real NVIDIA reply", r.ok_ and "PONG" in r.text.upper(), f"{r.status_code} {r.elapsed_s}s {r.text[:600]}")
r = call("GET", f"/ai/chats/{cid}/messages")
check(A, "chat history persisted (user + assistant)", r.ok_ and r.text.upper().count("PONG") >= 2, r.text[:400])
r = call("POST", f"/ai/chats/{cid}/rename", json={"title": "Renamed <script>alert(1)</script>"})
check(A, "rename chat", r.status_code < 500, f"{r.status_code} {r.text[:200]}")

# privacy: an email address in a chat must not leave in clear text unless policy allows
r = call("POST", f"/ai/chats/{cid}/messages", json={"content": "My client is jane.secret@acme-private.com, phone +1 415 555 0199. Reply OK.", "data_class": "public"})
check(A, "chat with PII answered or refused cleanly", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
r = call("GET", "/ai/egress-log", params={"limit": 50})
log = r.text
check(A, "egress log records the calls", r.ok_ and (r.j or {}).get("total", 0) >= 2, r.text[:300])
check(A, "egress log never stores the API key", key not in log)
items = (r.j or {}).get("items", [])
leak = False
for it in items:
    lid = it.get("id")
    d = call("GET", f"/ai/egress-log/{lid}")
    if "jane.secret@acme-private.com" in d.text:
        leak = True
save(egress_items=len(items))
check(A, "client email address did NOT leave to NVIDIA in a public chat", not leak, "email found in an outbound payload")
r = call("GET", "/ai/egress-log/stats"); check(A, "egress stats", r.ok_, r.text[:200])
r = call("GET", "/provider-calls"); check(A, "provider-calls ledger", r.ok_, r.text[:200])
r = call("GET", "/ai/cache/stats"); check(A, "cache stats", r.ok_, r.text[:200])
r = call("GET", "/ai/failure-kinds"); check(A, "failure kinds", r.ok_, r.text[:200])

r = call("POST", "/ai/providers/nvidia/override", json={"data_policy": "full", "allow_above_ceiling": True, "reason": " "})
check(A, "above-ceiling full-data override without a written reason is refused", r.status_code >= 400, f"{r.status_code} {r.text[:300]}")
r = call("POST", "/ai/workspace/mailbox-unlock", json={"phrase": "wrong"})
check(A, "mailbox unlock with wrong phrase refused", r.status_code >= 400, f"{r.status_code} {r.text[:200]}")
