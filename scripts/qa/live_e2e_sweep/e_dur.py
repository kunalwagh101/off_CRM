import os
from h import call, check, c, save
A="Backup/Durability"
r=call("POST","/backups/export",json={"passphrase":"short"}); check(A,"weak backup passphrase refused",r.status_code in (400,422),f"{r.status_code} {r.text[:200]}")
r=c.post("/backups/export",json={"passphrase":"e2e-backup-passphrase-long-enough-42"})
check(A,"encrypted backup export",r.status_code==200 and len(r.content)>1000,f"{r.status_code} {len(r.content)} {r.text[:200] if r.status_code!=200 else ''}")
blob=r.content; open("backup.bin","wb").write(blob)
check(A,"backup is encrypted (no plaintext contact emails inside)",b"dora.klein@steelimport-test.example" not in blob and b"PK\x03\x04" not in blob[:4],blob[:16])
check(A,"backup never contains the NVIDIA key in clear",os.environ["NVIDIA_API_KEY"].encode() not in blob)
r=c.post("/backups/restore",files={"file":("b.bin",blob,"application/octet-stream")},data={"passphrase":"wrong-passphrase-xxxxxxxxxx"})
check(A,"restore with wrong passphrase refused, data untouched",r.status_code in (400,401,403,422) and call("GET","/crm/search",params={"query":"Dora"}).text.count("Dora")>0,f"{r.status_code} {r.text[:200]}")
r=c.post("/backups/restore",files={"file":("b.bin",b"garbage"*100,"application/octet-stream")},data={"passphrase":"e2e-backup-passphrase-long-enough-42"})
check(A,"restore of a corrupt file refused cleanly",400<=r.status_code<500,f"{r.status_code} {r.text[:200]}")
r=call("POST","/campaigns",json={"name":"created-after-backup"})
r=c.post("/backups/restore",files={"file":("b.bin",blob,"application/octet-stream")},data={"passphrase":"e2e-backup-passphrase-long-enough-42"})
check(A,"restore of a good backup works",r.status_code==200,f"{r.status_code} {r.text[:300]}")
r=call("GET","/campaigns"); names=[x["name"] for x in r.j["items"]]
check(A,"after restore: data from backup present",any("E2E CBAM Main"==n for n in names),names)
check(A,"after restore: data created after backup is gone (true point-in-time)", "created-after-backup" not in names,names)
r=call("POST","/ai/run",json={"mode":"simple","data_class":"public","instructions":"Reply with exactly PONG.","public_text":""})
check(A,"after restore: NVIDIA key still works (encrypted keys restored)",r.ok_ and "PONG" in r.text.upper(),f"{r.status_code} {r.text[:300]}")
