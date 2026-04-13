---
tags: [odoo, odoo17, api, changes]
---

# API Changes — Odoo 16 to 17

## Decorator Changes

No major breaking changes in `@api` decorators. Odoo 17 continues to use:
- `@api.model`
- `@api.depends`
- `@api.onchange`
- `@api.constrains`
- `@api.depends_context` (added in earlier version)

## Field Changes

- `fields.Json` now has better indexing support
- `fields.Html` sanitization improved

## Model Changes

### res.users
- `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` continue to work
- `@check_identity` decorator introduced in v15, still present

### mail.thread
- `_message_auto_subscribe` still available
- Tracking via precommit hooks

## Deprecations

Check `~/odoo/odoo17/odoo/odoo/modules/deprecation.py` for deprecation warnings.

## See Also
- [New Features/What's New](new-features/what's-new.md) — Overview
- [Core/API](core/api.md) — Decorator reference
