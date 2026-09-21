# S-06.02.05 — Keyboard and screen-reader accessibility

## Contract

Accessibility is a product invariant, not a per-page afterthought.

The shared shell provides:

- a skip-to-main-content link;
- current-page state through `aria-current`;
- a real main landmark and programmatically focusable main content;
- visible `:focus-visible` styling;
- polite/assertive live regions for status/error feedback;
- reduced-motion handling.

The shared modal provides dialog semantics, Escape close, focus trapping and
return-focus behaviour.

Product-specific pointer interactions keep keyboard alternatives:

- Sales lead drag/move also has explicit Edit and Move controls;
- video effect strength/order/removal uses ordinary form/buttons;
- AI drawer has an explicit Close control + Escape and returns focus.

## Repository guardrail

`tests/test_frontend_accessibility_contract.py` recursively scans every TSX
screen. It rejects:

- generic click targets with no keyboard path;
- positive tab indexes;
- fake `role="button"` controls without keyboard handlers;
- images without alt text.

This is deliberately static evidence. The owner/manual verification pass still
needs a real keyboard and screen-reader run before the story can be DONE.

## Verification

```bash
uv run pytest tests/test_frontend_accessibility_contract.py -q
npm test --prefix frontend
npm run build --prefix frontend
```

## Migration / rollback

No persistent-state migration. Rollback is frontend-only, but doing so reopens
the accessibility defects and should not be treated as behaviour-neutral.
