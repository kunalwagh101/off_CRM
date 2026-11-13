"""Tiny live E2E harness: every check is one JSON line in results.jsonl.

Configured only from the environment, so no token or path is committed:
  OFFCRM_E2E_BASE   default http://127.0.0.1:8777/api/v1
  OFFCRM_E2E_TOKEN  the server's OFFSETX_LOCAL_API_TOKEN (required)
  OFFCRM_E2E_OUT    folder for results.jsonl and state.json (default: cwd)
"""
import json, os, time, httpx

B = os.environ.get("OFFCRM_E2E_BASE", "http://127.0.0.1:8777/api/v1")
TOKEN = os.environ["OFFCRM_E2E_TOKEN"]
H = {"X-OffsetX-Token": TOKEN}
c = httpx.Client(base_url=B, headers=H, timeout=300)
OUT = os.environ.get("OFFCRM_E2E_OUT", os.getcwd())
RES = os.path.join(OUT, "results.jsonl")
STATE = os.path.join(OUT, "state.json")


def state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save(**kw):
    s = state(); s.update(kw); json.dump(s, open(STATE, "w"), indent=1)


def check(area, name, ok, detail=""):
    row = {"area": area, "check": name, "result": "PASS" if ok else "FAIL",
           "detail": str(detail)[:700], "t": time.strftime("%H:%M:%S")}
    open(RES, "a").write(json.dumps(row) + "\n")
    print(("PASS " if ok else "FAIL ") + area + " :: " + name + ("" if ok else "  ->  " + str(detail)[:400]))
    return ok


def call(method, path, expect=(200, 201), **kw):
    t = time.time()
    try:
        r = c.request(method, path, **kw)
    except Exception as e:  # a network error or timeout is a finding too
        class R:  # noqa
            status_code = 0; text = repr(e)
            def json(self): return {}
        r = R()
    r.elapsed_s = round(time.time() - t, 1)
    r.ok_ = r.status_code in (expect if isinstance(expect, tuple) else (expect,))
    try:
        r.j = r.json()
    except Exception:
        r.j = None
    return r
