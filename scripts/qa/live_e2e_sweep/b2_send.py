import json, glob, os
from h import call, check, state, save
A="CRM/Outreach"; s=state(); cid=s["campaign_id"]
r=call("POST",f"/campaigns/{cid}/contacts/manual",json={"full_name":"Dora Klein","email":"dora.klein@steelimport-test.example","company":"SteelImport AG","title":"Head of Customs","category":"CBAM / Trade Compliance","public_hook":"SteelImport AG announced its first CBAM quarterly report in October.","hook_source":"https://steelimport-test.example/news/cbam"})
check(A,"add contact with a sourced public hook",r.ok_,r.text[:200]); ccid=r.j["id"]
r=call("POST",f"/campaigns/{cid}/drafts/generate",json={"stages":["initial"],"campaign_contact_ids":[ccid],"use_connectors":True})
check(A,"AI draft via Connectors (use_connectors) really calls NVIDIA",r.ok_,f"{r.status_code} {r.elapsed_s}s {r.text[:700]}")
r=call("GET",f"/campaigns/{cid}/drafts"); d=[x for x in r.j["items"] if x["campaign_contact_id"]==ccid]
check(A,"AI draft exists for the contact",bool(d),r.text[:200])
if d:
    x=d[-1]; meta=json.loads(x["generation_meta_json"]); save(ai_draft=x)
    check(A,"draft generation mode is AI, not template_only",meta.get("mode")!="template_only",meta)
    body=x["subject"]+"\n"+x["body"]
    check(A,"AI draft has no leftover privacy tokens",not any(t in body for t in ("PERSON_1","COMPANY_1","RECIPIENT_1","SENDER")),body[:500])
    check(A,"AI draft has no reasoning/thinking text",("<think" not in body.lower()) and ("the user wants" not in body.lower()),body[:300])
    check(A,"AI draft is sendable after quality audit",x["sendable"],x["audit_json"][:300])
    r=call("POST",f"/campaigns/{cid}/drafts/approve",json={"draft_ids":[x["id"]]}); check(A,"approve the AI draft",r.ok_ and r.j.get("approved")==1,r.text[:300])
    r=call("POST",f"/campaigns/{cid}/send",json={"mode":"local"}); check(A,"send to local outbox delivers exactly 1",r.ok_ and r.j.get("sent_count")==1,r.text[:500]); save(send2=r.text[:1500])
    r=call("POST",f"/campaigns/{cid}/send",json={"mode":"local"}); check(A,"second send does not double-send",r.ok_ and r.j.get("sent_count")==0,r.text[:300])
    out=[p for p in glob.glob(os.environ["OFFSETX_DATA_DIR"]+"/**/*",recursive=True) if os.path.isfile(p) and ("outbox" in p.lower()) ]
    save(outbox_files=out[:20]); check(A,"sent email exists as a file in the local outbox",bool(out),out[:5])
    if out:
        txt=open(sorted(out,key=os.path.getmtime)[-1],errors="replace").read()
        check(A,"outbox email is addressed to the real recipient (tokens re-attached)","dora.klein@steelimport-test.example" in txt,txt[:400])
        # 1:1 Gmail/local outreach only warns without a public unsubscribe URL; marketing/SES sends are blocked (preflight). Not asserted here.
