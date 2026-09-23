"""Faking a model call without faking the workspace binding.

The app never calls the shared ``EgressBroker`` directly: each request asks for
a copy bound to its own workspace's keys (``with_credential_resolver``), so two
workspaces cannot race for one key. A test that patched ``call`` on the shared
broker therefore patched an object no request uses any more.

``fake_model_calls`` keeps the real binding and replaces only ``call`` on each
bound copy, so a test still proves the request went through a workspace-bound
broker, and still controls what the model says.
"""

from __future__ import annotations

from typing import Any, Callable


def fake_model_calls(monkeypatch: Any, broker: Any, fake: Callable[..., Any]) -> list[Any]:
    """Every broker bound from ``broker`` answers with ``fake``.

    Returns the list of bound brokers, in the order requests asked for them.
    The shared broker's own ``call`` is patched too, for any path that still
    uses it unbound.
    """
    bound: list[Any] = []
    original = broker.with_credential_resolver

    def bind(resolver: Any) -> Any:
        copy = original(resolver)
        monkeypatch.setattr(copy, "call", fake)
        bound.append(copy)
        return copy

    monkeypatch.setattr(broker, "with_credential_resolver", bind)
    monkeypatch.setattr(broker, "call", fake)
    return bound
