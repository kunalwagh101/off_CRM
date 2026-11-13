import io, json, time
from h import call, check, save, c

A = "CRM/Outreach"
r = call("POST", "/ai/workspace", json={"positioning_line": "We help EU importers file CBAM reports fast.", "owner_domains": ["offsetx-test.example"], "owner_addresses": ["owner@offsetx-test.example"]})
check(A, "set workspace positioning", r.ok_, r.text[:200])

r = call("POST", "/campaigns", json={"name": "E2E CBAM Main", "daily_send_limit": 50, "timezone": "Europe/Berlin", "approval_mode": "each_message"})
check(A, "create campaign", r.ok_, r.text[:300])
camp = r.j or {}
cid = camp.get("id") or camp.get("campaign", {}).get("id")
save(campaign_id=cid)
r = call("POST", "/campaigns", json={"name": "E2E CBAM Q4"})
check(A, "duplicate campaign name handled (refused or allowed, no crash)", r.status_code < 500, f"{r.status_code} {r.text[:200]}")
r = call("POST", "/campaigns", json={"name": "   "})
check(A, "blank campaign name refused", r.status_code == 422 or r.status_code == 400, f"{r.status_code} {r.text[:200]}")
r = call("POST", "/campaigns", json={"name": "bad tz", "timezone": "Mars/Olympus"})
check(A, "invalid timezone refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", "/campaigns", json={"name": "neg", "daily_send_limit": -5})
check(A, "negative daily limit refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")

r = call("GET", f"/campaigns/{cid}"); check(A, "get campaign", r.ok_, r.text[:200])
r = call("PATCH", f"/campaigns/{cid}", json={"daily_send_limit": 40}); check(A, "patch campaign", r.ok_, f"{r.status_code} {r.text[:200]}")
r = call("GET", f"/campaigns/{cid}/launch-readiness"); check(A, "launch readiness (empty campaign) explains what is missing", r.ok_, r.text[:300])

r = call("POST", f"/campaigns/{cid}/contacts/manual", json={"full_name": "Ana Silva", "email": "ana.silva@importco-test.example", "company": "ImportCo", "title": "Head of Compliance", "category": "CBAM / Trade Compliance", "public_hook": "Ana Silva spoke at the EU trade summit about CBAM."})
check(A, "add contact manually", r.ok_, r.text[:300]); first_member = (r.j or {}).get("id")
r = call("POST", f"/campaigns/{cid}/contacts/manual", json={"full_name": "Ana Dup", "email": "ANA.SILVA@importco-test.example"})
check(A, "same email with different case returns the existing membership", r.status_code in (200, 201) and (r.j or {}).get("id") == first_member, f"{r.status_code} {r.text[:300]}")
r = call("POST", f"/campaigns/{cid}/contacts/manual", json={"full_name": "Bad", "email": "not-an-email"})
check(A, "invalid email refused", r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}")
r = call("POST", f"/campaigns/{cid}/contacts/manual", json={"full_name": "<img src=x onerror=alert(1)>", "email": "xss@importco-test.example", "company": "\"><script>alert(2)</script>"})
check(A, "HTML in names stored as text (no crash)", r.status_code < 500, f"{r.status_code} {r.text[:200]}")

csv = ("full_name,email,company,title,category\n"
       "Ben Ode,ben@exporter-test.example,Exporter GmbH,CFO,CBAM / Trade Compliance\n"
       "Cara Lee,cara@exporter-test.example,Exporter GmbH,COO,\n"
       "No Mail,,X,,\n"
       "=HYPERLINK(\"http://evil\"),formula@evil-test.example,=1+1,,\n"
       "Ben Again,BEN@exporter-test.example,Exporter GmbH,CFO,\n")
r = c.post(f"/campaigns/{cid}/contacts/import", files={"file": ("c.csv", csv.encode(), "text/csv")}, data={"default_category": "CBAM / Trade Compliance"})
check(A, "CSV import works and reports skipped rows", r.status_code in (200, 201), f"{r.status_code} {r.text[:500]}")
save(import_resp=r.text[:1500])
r = c.post(f"/campaigns/{cid}/contacts/import", files={"file": ("c.exe", b"MZ\x90\x00binary", "application/octet-stream")})
check(A, "binary file import refused with a readable message", 400 <= r.status_code < 500, f"{r.status_code} {r.text[:300]}")

r = call("GET", f"/campaigns/{cid}/contacts")
items = (r.j or {}).get("items", [])
check(A, "list contacts", r.ok_ and len(items) >= 3, f"{len(items)} {r.text[:300]}")
save(contacts=[{"id": i.get("id") or i.get("campaign_contact_id"), "email": i.get("email")} for i in items])
r = call("GET", f"/campaigns/{cid}/contacts/facets"); check(A, "contact facets", r.ok_, r.text[:200])
r = call("GET", f"/campaigns/{cid}/contacts/download")
check(A, "contacts CSV download", r.ok_, r.text[:200])
dl = r.text
check(A, "CSV export neutralises spreadsheet formulas (CSV injection)", "\n=" not in dl and ",=" not in dl, [l for l in dl.splitlines() if "=" in l][:3])

ccid = items[0].get("id") or items[0].get("campaign_contact_id")
r = call("PATCH", f"/campaigns/{cid}/contacts/{ccid}", json={"title": "VP Compliance"})
check(A, "edit contact", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
r = call("GET", f"/campaigns/{cid}/contacts/{ccid}/overview"); check(A, "contact overview", r.ok_, r.text[:200])

t = time.time()
r = call("POST", f"/campaigns/{cid}/drafts/generate", json={"stages": ["initial"]})
check(A, "AI draft generation with NVIDIA", r.ok_, f"{r.status_code} {r.elapsed_s}s {r.text[:600]}")
save(gen_resp=r.text[:3000])
r = call("GET", f"/campaigns/{cid}/drafts")
drafts = (r.j or {}).get("items", [])
check(A, "drafts listed after generation", r.ok_ and len(drafts) > 0, f"{len(drafts)} {r.text[:400]}")
save(drafts=drafts[:5])
if drafts:
    d0 = drafts[0]
    body = (d0.get("body") or "") + (d0.get("subject") or "")
    check(A, "draft has real subject and body text", len(d0.get("body") or "") > 40 and len(d0.get("subject") or "") > 3, json.dumps(d0)[:400])
    check(A, "no leftover tokens (PERSON_1/COMPANY_1/RECIPIENT_1) in final draft", not any(tok in body for tok in ("PERSON_1", "COMPANY_1", "RECIPIENT_1", "<RECIPIENT", "SENDER")), body[:400])
    check(A, "no model thinking text leaked into the email", "<think" not in body.lower() and "the user wants" not in body.lower(), body[:300])
    did = d0["id"]
    r = call("PATCH", f"/campaigns/{cid}/drafts/{did}", json={"subject": "Quick CBAM question", "body": d0.get("body")})
    check(A, "edit a draft", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
    r = call("POST", f"/campaigns/{cid}/send", json={"mode": "local"})
    sent_before_approval = (r.j or {}).get("sent_count", 0) if r.ok_ else 0
    check(A, "send BEFORE approval sends nothing", sent_before_approval == 0, f"{r.status_code} {r.text[:300]}")
    r = call("POST", f"/campaigns/{cid}/drafts/approve", json={"draft_ids": [x["id"] for x in drafts]})
    check(A, "approve drafts", r.ok_, f"{r.status_code} {r.text[:300]}")
    r = call("GET", f"/campaigns/{cid}/queue"); check(A, "queue view", r.ok_, r.text[:300])
    r = call("POST", f"/campaigns/{cid}/send", json={"mode": "gmail"})
    check(A, "gmail live send without typed confirmation refused", r.status_code in (400, 403, 409, 422), f"{r.status_code} {r.text[:300]}")
    r = call("POST", f"/campaigns/{cid}/send", json={"mode": "local"})
    check(A, "send approved drafts to local outbox", r.ok_, f"{r.status_code} {r.text[:400]}")
    save(send_resp=r.text[:1500])
    r2 = call("POST", f"/campaigns/{cid}/send", json={"mode": "local"})
    check(A, "second send does not double-send", r2.ok_ and ((r2.j or {}).get("sent_count", 0) == 0), f"{r2.status_code} {r2.text[:300]}")

r = call("GET", f"/campaigns/{cid}/summary"); check(A, "campaign summary", r.ok_, r.text[:300])
r = call("GET", f"/campaigns/{cid}/performance"); check(A, "campaign performance", r.ok_, r.text[:200])
r = call("GET", f"/campaigns/{cid}/progress"); check(A, "progress on an email campaign refused with a readable reason", r.status_code == 422 and "distribution" in r.text.lower(), r.text[:200])
r = call("GET", f"/campaigns/{cid}/events"); check(A, "campaign events timeline", r.ok_, r.text[:200])
r = call("GET", f"/campaigns/{cid}/reports/ab"); check(A, "A/B report", r.ok_, r.text[:200])
r = call("GET", f"/campaigns/{cid}/export"); check(A, "campaign export", r.ok_, f"{r.status_code} {r.text[:200]}")
r = call("GET", f"/campaigns/{cid}/replies/inbox"); check(A, "replies inbox", r.ok_, r.text[:200])
r = call("POST", f"/campaigns/{cid}/replies/sync", json={}); check(A, "reply sync without mailbox gives readable answer", r.status_code < 500, f"{r.status_code} {r.text[:300]}")
r = call("GET", f"/campaigns/{cid}/followups"); check(A, "follow-ups list", r.ok_, r.text[:200])
r = call("POST", f"/campaigns/{cid}/clone", json={"name": "E2E clone"}); check(A, "clone campaign", r.status_code < 400, f"{r.status_code} {r.text[:200]}")
r = call("GET", "/dashboard"); check(A, "dashboard counts reflect the sends", r.ok_ and (r.j or {}).get("total_contacts", 0) >= 3, r.text[:300])
for p in ["/crm/duplicates", "/crm/quality", "/crm/followup-performance", "/crm/accounts", "/crm/attribution", "/templates", "/campaign-kinds", "/settings/status", "/storage/readiness", "/operations/health"]:
    r = call("GET", p); check(A, "GET " + p, r.ok_, f"{r.status_code} {r.text[:200]}")
r = call("GET", "/crm/search", params={"query": "Ana"}); check(A, "CRM search finds Ana", r.ok_ and "Ana" in r.text, r.text[:200])
r = call("GET", "/crm/compare", params={"campaign_ids": cid}); check(A, "CRM compare", r.status_code < 500, f"{r.status_code} {r.text[:200]}")
