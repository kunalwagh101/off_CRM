# S-06.02.02 — API authorization and validation boundary

## Contract

The API is private by default.

`api/app.py` has one middleware boundary for every route under `/api/`.
A route is public only when its exact path or prefix appears in the closed
`PUBLIC_API_PATHS` / `PUBLIC_API_PREFIXES` declarations.

The public exceptions are bootstrap/callback surfaces that cannot require an
already-authenticated CRM session:

- auth session/login/logout;
- signed unsubscribe;
- signed SES/SNS delivery feedback.

Operational liveness/readiness probes live outside the customer API and expose
no customer data.

## Validation

FastAPI/Pydantic validation happens before business logic. A dedicated
`RequestValidationError` handler returns bounded field/type information and
does not echo the submitted body. This matters because malformed bodies can
contain passwords, API keys or imported customer data.

The contract test enumerates the routes FastAPI actually registered rather than
maintaining a hand-written endpoint list. A new private route is therefore
covered automatically.

## Verification

```bash
uv run pytest tests/test_api_boundary_contract.py tests/test_api_auth.py -q
```

The focused suite checks:

- every registered private API method returns 401 without credentials;
- every public exemption still maps to a real route;
- malformed JSON returns 4xx, not a traceback;
- object-body endpoints reject array bodies;
- validation errors do not echo a planted secret.

## Migration / rollback

No database migration. Rolling back restores the older API middleware/validation
behaviour; there is no persistent state to convert.
