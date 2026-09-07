"""FastAPI control plane for off_CRM."""

# Import the original application first, then install the cross-cutting
# production reliability boundary on the module itself. Python executes this
# package before ``offsetx_apollo_builder.api.app`` is handed to callers, so
# direct imports of that submodule and package-level imports both receive the
# same create_app implementation.
from . import app as _app
from .production_runtime import harden_create_app

create_app = harden_create_app(_app.create_app)
_app.create_app = create_app

__all__ = ["create_app"]
