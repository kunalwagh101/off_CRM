import json, io, struct, wave, math
from h import call, check, state, save, c

s = state(); cid = s["campaign_id"]

# ---------------- Sales pipeline
A = "Sales"
r = call("GET", "/sales/meta"); check(A, "sales meta", r.ok_, r.text[:200])
r = call("POST", "/sales/leads", json={"lead_name": "Ella Brown", "company": "Brown Ltd", "email": "ella@brown-test.example", "total_deal_value": 12000, "deposit_amount": 2000, "commission_percent": 10})
check(A, "create lead", r.ok_, r.text[:300]); lid = (r.j or {}).get("id")
rev = (r.j or {}).get("revision")
r = call("POST", "/sales/leads", json={"lead_name": "Neg", "total_deal_value": -500})
check(A, "negative deal value refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", "/sales/leads", json={"lead_name": "Bad pct", "commission_percent": 250})
check(A, "commission over 100% refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", "/sales/leads", json={"lead_name": "Cash > deal", "total_deal_value": 100, "cash_collected": 5000})
check(A, "cash collected above deal value refused or flagged", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", f"/sales/leads/{lid}/move", json={"lead_status": "proposal", "expected_revision": rev})
check(A, "move lead with correct revision", r.ok_, r.text[:300])
r = call("POST", f"/sales/leads/{lid}/move", json={"lead_status": "deposit", "expected_revision": rev})
check(A, "move with STALE revision refused (no lost update)", r.status_code == 409, f"{r.status_code} {r.text[:200]}")
r = call("GET", f"/sales/leads/{lid}/events"); check(A, "lead history recorded", r.ok_ and "proposal" in r.text, r.text[:300])
r = call("GET", "/sales/board"); check(A, "board shows lead in Proposal", r.ok_ and "Ella" in r.text, r.text[:200])
r = call("POST", "/sales/activity", json={"activity_date": "2026-11-13", "setter_name": "Major", "dials_dms_sent": 40, "conversations": 8, "declines": 3})
check(A, "log daily activity", r.ok_, r.text[:200])
r = call("POST", "/sales/activity", json={"activity_date": "2026-13-45", "setter_name": "Major"})
check(A, "impossible date refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", "/sales/activity", json={"activity_date": "2026-11-14", "setter_name": "Major", "dials_dms_sent": 5, "conversations": 50})
check(A, "more conversations than dials refused or flagged", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("PATCH", "/sales/goals/2026-11", json={"revenue_goal": 50000, "cash_goal": 30000, "currency": "EUR"}); check(A, "set monthly goal", r.ok_, r.text[:200])
r = call("PATCH", "/sales/goals/2026-99", json={"revenue_goal": 1}); check(A, "invalid month refused", r.status_code in (400, 404, 422), f"{r.status_code} {r.text[:200]}")
r = call("GET", "/sales/dashboard"); check(A, "sales dashboard", r.ok_, r.text[:300])
r = call("POST", "/sales/projection", json={"forecast_month": "2026-12"}); check(A, "projection", r.ok_, f"{r.status_code} {r.text[:300]}")

# ---------------- Memory & context
A = "Memory/Context"
r = call("POST", "/memory", json={"content": "Our product files CBAM quarterly reports in 2 days.", "kind": "fact", "tags": ["cbam"]})
check(A, "add memory", r.ok_, r.text[:200]); mid = (r.j or {}).get("id")
r = call("PATCH", f"/memory/{mid}", json={"approved": True}); check(A, "approve memory", r.ok_, r.text[:200])
r = call("POST", "/memory", json={"content": "my api_key=sk-abcdefghijklmnopqrstuvwxyz123456"})
check(A, "secret pasted into memory is refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("GET", "/memory"); check(A, "list memory", r.ok_ and "CBAM" in r.text, r.text[:200])
r = call("GET", "/memory/stats"); check(A, "memory stats", r.ok_, r.text[:200])
r = call("GET", "/ai/context"); check(A, "context store view", r.ok_, r.text[:200])
r = call("POST", "/ai/context/templates", json={"template_id": "e2e-t", "variant_id": "A", "label": "E2E", "template_text": "Hi {first_name}, quick question about CBAM."})
check(A, "store a template variant", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
r = call("POST", "/ai/context/templates/e2e-t/rewrite", json={"variant_id": "A"})
check(A, "AI rewrite of a template via NVIDIA", r.status_code < 400, f"{r.status_code} {r.elapsed_s}s {r.text[:400]}")
r = call("POST", "/ai/context/tasks", json={"kind": "research", "title": "E2E task", "steps": ["a", "b"]})
check(A, "create context task", r.status_code < 400, f"{r.status_code} {r.text[:200]}"); tid = (r.j or {}).get("id") or (r.j or {}).get("task", {}).get("id")
if tid:
    r = call("POST", f"/ai/context/tasks/{tid}/step", json={"step_index": 0, "note": "done", "status": "done"}); check(A, "advance task step", r.status_code < 400, f"{r.status_code} {r.text[:200]}")

# ---------------- Recall
A = "Recall"
r = call("GET", "/ai/recall"); check(A, "recall status", r.ok_, r.text[:300])
r = call("POST", "/ai/recall/rebuild", json={}); check(A, "recall rebuild gives readable answer", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
r = call("POST", "/ai/recall/search", json={"query": "CBAM", "limit": 5}); check(A, "recall search", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
r = call("POST", "/ai/recall/preview", json={"query": "CBAM"}); check(A, "recall preview (what a model would see)", r.status_code < 500, f"{r.status_code} {r.text[:300]}")

# ---------------- Companions & skills & agents
A = "Companions/Agents"
r = call("GET", "/companion-tools"); check(A, "companion tool catalogue", r.ok_, r.text[:200])
r = call("POST", "/companion-skills", json={"name": "Short emails", "content": "Keep every email under 90 words."}); check(A, "create skill", r.ok_, r.text[:200]); sk = (r.j or {}).get("id")
r = call("POST", "/companions", json={"name": "E2E Scout", "instructions": "Find CBAM news.", "granted_tool_ids": []}); check(A, "create companion", r.ok_, r.text[:200]); comp = (r.j or {}).get("id")
r = call("POST", "/companions", json={"name": "Hacker", "instructions": "x", "granted_tool_ids": ["shell.exec", "../../etc"]}); check(A, "companion with unknown tool ids refused", r.status_code in (400, 404, 422), f"{r.status_code} {r.text[:200]}")
if comp:
    r = call("POST", f"/companions/{comp}/memory", json={"content": "Prefers German sources.", "approved": True}); check(A, "companion memory", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
    r = call("POST", f"/companions/{comp}/context", json={"skill_ids": [sk] if sk else []}); check(A, "companion context build", r.status_code < 400, f"{r.status_code} {r.text[:300]}")
    r = call("POST", "/ai/chats", json={"title": "companion chat"}); ch = (r.j or {}).get("id")
    r = call("POST", f"/ai/chats/{ch}/messages", json={"content": "In one sentence, who are you?", "companion_id": comp, "skill_ids": [sk] if sk else [], "data_class": "campaign"})
    check(A, "chat with a companion through NVIDIA", r.ok_, f"{r.status_code} {r.elapsed_s}s {r.text[:400]}")
    r = call("POST", f"/companions/{comp}/delegate", json={"assignments": [{"companion_id": comp, "task": "x"}]}); check(A, "delegate gives readable answer", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
    r = call("DELETE", f"/companions/{comp}"); check(A, "delete companion", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
r = call("GET", "/agent-permissions"); check(A, "agent permissions", r.ok_, r.text[:200])
r = call("PUT", "/agent-permissions", json={"global_mode": "ask"}); check(A, "set agent permissions", r.ok_, r.text[:200])
r = call("POST", "/agent-routines", json={"name": "Watch", "goal": "check", "target_url": "http://169.254.169.254/latest/meta-data", "trigger_type": "interval", "interval_seconds": 3600})
check(A, "routine targeting cloud metadata IP refused (SSRF)", r.status_code in (400, 422), f"{r.status_code} {r.text[:300]}")
r = call("POST", "/agent-routines", json={"name": "Watch2", "goal": "check", "target_url": "file:///etc/passwd", "trigger_type": "interval", "interval_seconds": 3600})
check(A, "routine with file:// URL refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:300]}")
r = call("POST", "/agent-routines", json={"name": "Watch3", "goal": "check", "target_url": "https://example.com/", "trigger_type": "interval", "interval_seconds": 3600, "enabled": False})
check(A, "create a valid routine", r.ok_, f"{r.status_code} {r.text[:300]}")
for p in ["/agent-routines", "/agent-routine-runs", "/agent-routine-status", "/agent-routine-notifications"]:
    r = call("GET", p); check(A, "GET " + p, r.ok_, r.text[:200])
r = call("POST", "/agent-team/provision", json={}); check(A, "agent team provision", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
r = call("POST", "/agent-team/execute", json={"role": "Analyst", "campaign_id": cid}); check(A, "agent team execute (Analyst)", r.status_code < 500, f"{r.status_code} {r.elapsed_s}s {r.text[:300]}")

# ---------------- Meetings
A = "Meetings"
r = call("GET", "/meetings/capabilities"); check(A, "meeting capabilities", r.ok_, r.text[:300])
r = call("POST", "/meetings", json={"title": "E2E call", "provider_id": "nvidia", "model_id": "nvidia/nemotron-3-ultra-550b-a55b"})
check(A, "start a meeting with a non-transcription model is refused or explained", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
r = call("GET", "/meetings"); check(A, "list meetings", r.ok_, r.text[:200])

# ---------------- Privacy (GDPR)
A = "Privacy"
r = call("POST", "/privacy/subject-access", json={"subject": {"emails": ["dora.klein@steelimport-test.example"]}})
check(A, "subject access export finds the person", r.ok_ and "dora" in r.text.lower(), f"{r.status_code} {r.text[:300]}")
r = call("POST", "/privacy/deletion-preview", json={"subject": {"emails": ["ben@exporter-test.example"]}})
check(A, "deletion preview", r.ok_, f"{r.status_code} {r.text[:400]}"); save(del_preview=r.text[:2000])
rid = (r.j or {}).get("request_id") or (r.j or {}).get("id")
conf = "DELETE SUBJECT DATA"
if rid:
    r = call("POST", f"/privacy/deletions/{rid}", json={"subject": {"emails": ["ben@exporter-test.example"]}, "confirmation": "wrong"})
    check(A, "deletion with wrong confirmation refused", r.status_code in (400, 403, 409, 422), f"{r.status_code} {r.text[:200]}")
    r = call("POST", f"/privacy/deletions/{rid}", json={"subject": {"emails": ["ben@exporter-test.example"]}, "confirmation": conf})
    check(A, "deletion executes with the right confirmation", r.ok_, f"{r.status_code} {r.text[:300]}")
    r = call("GET", "/crm/search", params={"query": "ben@exporter-test.example"})
    check(A, "deleted person is gone from CRM search", r.ok_ and not (r.j or {}).get("items"), r.text[:300])
    r = call("POST", f"/campaigns/{cid}/contacts/manual", json={"full_name": "Ben Back", "email": "ben@exporter-test.example"})
    check(A, "deleted person cannot be silently re-added (suppression)", r.status_code >= 400 or "suppress" in r.text.lower(), f"{r.status_code} {r.text[:300]}")

# ---------------- Video / images / content
A = "Video/Images/Content"
for p in ["/video/presets", "/video/effects", "/video/recipes", "/trends", "/trends/topics", "/trends/channels", "/distribution/platforms", "/distribution/accounts", "/content-automation", "/automation", "/notion/settings", "/research/graph", "/apollo/rejections", "/apollo/exclusions"]:
    r = call("GET", p); check(A, "GET " + p, r.ok_, f"{r.status_code} {r.text[:200]}")
r = call("POST", "/campaigns", json={"name": "E2E content", "kind": "image"})
ccamp = (r.j or {}).get("id"); check(A, "create content campaign", r.ok_, r.text[:300])
kc = ccamp or cid
r = call("POST", f"/campaigns/{kc}/video-projects", json={"name": "Teaser", "preset": "reel"}); check(A, "create video project", r.status_code < 400, f"{r.status_code} {r.text[:300]}")
vp = (r.j or {}).get("id") or (r.j or {}).get("project", {}).get("id")
if vp:
    r = call("POST", f"/video-projects/{vp}/edit", json={"op": "add_track", "params": {"kind": "text"}}); check(A, "edit video (add text)", r.status_code < 400, f"{r.status_code} {r.text[:300]}")
    r = call("POST", f"/video-projects/{vp}/undo", json={}); check(A, "undo", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
    r = call("POST", f"/video-projects/{vp}/redo", json={}); check(A, "redo", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
    r = call("GET", f"/video-projects/{vp}/manifest"); check(A, "video manifest", r.ok_, r.text[:200])
    r = call("GET", f"/video-projects/{vp}/frame", params={"t": 0}); check(A, "render a preview frame", r.ok_, f"{r.status_code} {r.text[:200]}")
# upload a tiny WAV as media
buf = io.BytesIO(); w = wave.open(buf, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 5))) for i in range(8000))); w.close()
r = c.post(f"/campaigns/{kc}/video-media", files={"file": ("tone.wav", buf.getvalue(), "audio/wav")}, data={"name": "tone"})
check(A, "upload audio media", r.status_code < 400, f"{r.status_code} {r.text[:300]}")
r = c.post(f"/campaigns/{kc}/video-media", files={"file": ("evil.html", b"<script>alert(1)</script>", "text/html")})
check(A, "HTML disguised upload refused", r.status_code in (400, 415, 422), f"{r.status_code} {r.text[:300]}")
r = c.post(f"/campaigns/{kc}/video-media", files={"file": ("fake.mp4", b"<script>alert(1)</script>", "video/mp4")})
check(A, "fake mp4 (wrong magic bytes) refused", r.status_code in (400, 415, 422), f"{r.status_code} {r.text[:300]}")
r = call("POST", f"/campaigns/{kc}/image-briefs", json={"brief": "Steel coils at a port, editorial photo", "wanted": 1})
check(A, "create image brief", r.status_code < 400, f"{r.status_code} {r.text[:300]}")
bid = (r.j or {}).get("id") or (r.j or {}).get("brief", {}).get("id")
if bid:
    r = call("POST", f"/image-briefs/{bid}/generate", json={"count": 1, "provider_id": "nvidia"})
    check(A, "generate image with NVIDIA FLUX", r.ok_, f"{r.status_code} {r.elapsed_s}s {r.text[:400]}")
r = call("POST", "/ai/image", json={"prompt": "a blue square", "data_class": "public", "provider_id": "nvidia"})
check(A, "ai/image with NVIDIA", r.ok_, f"{r.status_code} {r.elapsed_s}s {r.text[:400]}")
r = call("POST", "/distribution/accounts", json={"platform": "local_outbox", "handle": "e2e-test", "label": "E2E", "daily_cap": 2}); check(A, "add distribution account", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
r = call("POST", "/trends/channels", json={"handle": "javascript:alert(1)"}); check(A, "bad trend channel handle refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", "/notion/settings", json={"token": "secret_abc", "workspace_name": "x"}); check(A, "notion settings save gives readable result", r.status_code < 500, f"{r.status_code} {r.text[:200]}")
r = call("GET", "/notion/settings"); check(A, "notion token never echoed", "secret_abc" not in r.text, r.text[:200])
r = call("POST", "/notion/disconnect", json={})

# ---------------- Discovery (SSRF guard)
A = "Discovery"
for u in ["http://127.0.0.1:8777/api/v1/dashboard", "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://localtest.me/", "file:///etc/passwd", "http://0x7f000001/"]:
    r = call("POST", f"/campaigns/{cid}/discovery/runs", json={"seed_urls": [u], "target_count": 1, "max_pages": 1})
    ok = r.status_code in (400, 422) or ("refus" in r.text.lower() or "block" in r.text.lower() or "not allowed" in r.text.lower() or "private" in r.text.lower())
    check(A, f"discovery refuses internal URL {u}", ok, f"{r.status_code} {r.text[:300]}")
r = call("GET", f"/campaigns/{cid}/discovery/runs"); check(A, "list discovery runs", r.ok_, r.text[:300]); save(disc=r.text[:3000])
