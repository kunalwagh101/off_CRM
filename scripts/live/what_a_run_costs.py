"""The live check for `S-06.01.03` — the estimate, the bill, and the cap.

Real: a local HTTP server standing in for a provider API, spoken to over real
HTTP by the real adapter, through the real broker, with a real quota file on
disk. The only thing pretended is the provider's identity — and the response it
returns is the exact shape OpenAI, Anthropic and every Chat Completions clone
send back, `usage` block included.

It checks the three things this story is for:

    1. the adapter reads what the provider says the call used
    2. the ledger records *that* number, not a hardcoded zero (`D-35`)
    3. the owner's daily spend cap therefore refuses something

Run it with ``python scripts/live/what_a_run_costs.py``. Exit 0 means all three.
"""

from __future__ import annotations

import http.server
import json
import socket
import tempfile
import threading
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from offsetx_apollo_builder.agent.run import estimate_run  # noqa: E402
from offsetx_apollo_builder.ai.broker import measure  # noqa: E402
from offsetx_apollo_builder.ai.quota import QuotaLimits, QuotaTracker  # noqa: E402
from offsetx_apollo_builder.ai.registry import ModelEntry  # noqa: E402
from offsetx_apollo_builder.outreach.providers import (  # noqa: E402
    ProviderConfig,
    create_provider,
)

MODEL = ModelEntry(id="planner", cost_per_1m_input_usd=2.0, cost_per_1m_output_usd=8.0)
REPORTED_IN, REPORTED_OUT = 1_842, 97


def serve() -> str:
    """A stand-in provider that answers the way real ones do."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            # The Chat Completions shape, which is what `openai_compatible`
            # speaks — and which names the usage fields `prompt_tokens` and
            # `completion_tokens`, so this exercises the other half of the
            # translation too.
            body = json.dumps({
                "choices": [{"message": {
                    "role": "assistant",
                    "content": '{"state": "done", "reason": "ok", "result": "42"}',
                }}],
                "usage": {
                    "prompt_tokens": REPORTED_IN,
                    "completion_tokens": REPORTED_OUT,
                    "total_tokens": REPORTED_IN + REPORTED_OUT,
                },
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}"


def _check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  [{'ok' if passed else 'NO'}] {label}{(' — ' + detail) if detail else ''}")
    return passed


def main() -> int:
    base = serve()
    print(f"a stand-in provider is answering at {base}\n")
    ok = True

    print("0. before anything runs, what does the owner see?")
    estimate = estimate_run(MODEL, step_budget=50)
    print(f"      {estimate.describe()}")
    ok &= _check("an estimate exists before the first call",
                 estimate.projected_cost_usd > 0,
                 f"${estimate.projected_cost_usd:.4f} for 50 decisions")

    print("\n1. the adapter reads what the provider reported")
    provider = create_provider(
        ProviderConfig(provider_type="openai_compatible", model="planner",
                       api_key_env="K", base_url=base, timeout_seconds=10),
        environ={"K": "not-a-real-key"},
    )
    text = provider.generate(system_prompt="you drive a browser", user_prompt="{}")
    ok &= _check("the call came back", "result" in text, text[:60])
    ok &= _check("and its usage came with it",
                 provider.last_usage == {"tokens_in": REPORTED_IN,
                                         "tokens_out": REPORTED_OUT},
                 str(provider.last_usage))

    print("\n2. the ledger records that number, not a zero")
    tokens_in, tokens_out, cost, source = measure(
        MODEL, reported=provider.last_usage, sent="x" * 99_999, received=text)
    ok &= _check("priced from the receipt, not from a character count",
                 source == "provider" and (tokens_in, tokens_out) == (REPORTED_IN, REPORTED_OUT),
                 f"{tokens_in} in / {tokens_out} out · ${cost:.6f} · {source}")

    ledger = QuotaTracker(Path(tempfile.mkdtemp(prefix="cost-")) / "quota.json")
    limits = QuotaLimits(max_spend_usd_per_day=1.00)
    calls = 0
    while ledger.check("openai", limits)[0] and calls < 10_000:
        ledger.record("openai", spend_usd=cost)
        calls += 1
    spent = ledger.usage("openai", limits)["day_spend_usd"]
    ok &= _check("the ledger moved off zero", spent > 0, f"${spent:.4f} after {calls} calls")

    print("\n3. so the owner's cap refuses something")
    allowed, reason = ledger.check("openai", limits)
    ok &= _check("the $1.00 cap is enforced", not allowed, reason)
    ok &= _check("and it took a believable number of calls to get there",
                 0 < calls < 10_000, f"{calls} calls at ${cost:.6f} each")

    print("\n   for contrast, the behaviour this replaced:")
    dead = QuotaTracker(Path(tempfile.mkdtemp(prefix="cost-")) / "quota.json")
    for _ in range(10_000):
        dead.record("openai", spend_usd=0.0)
    still_allowed, _ = dead.check("openai", limits)
    ok &= _check("10,000 calls recorded at $0.00 refused nothing", still_allowed,
                 f"${dead.usage('openai', limits)['day_spend_usd']:.4f} counted")

    print(f"\n{'all three hold' if ok else 'SOMETHING DID NOT HOLD'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
