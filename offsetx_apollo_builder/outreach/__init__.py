"""Local-first outreach CRM and email automation domain."""

# The store module is loaded and hardened before the engine imports its
# OutreachStore symbol.  This keeps one transaction-ownership rule for API,
# sales, delivery, automation and direct store users.
from . import store as _store
from .sqlite_ownership import harden_outreach_store

harden_outreach_store(_store.OutreachStore)
OutreachStore = _store.OutreachStore

from .engine import OutreachEngine

__all__ = ["OutreachEngine", "OutreachStore"]
