"""Placeholder until remote Render acceptance is implemented (TDD RED)."""

class SmokeError(RuntimeError):
    pass

def _request(base_url, path, *, method="GET", data=None):
    raise NotImplementedError

def run_smoke(base_url):
    return []
