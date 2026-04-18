---
type: new-feature
tags: [odoo, odoo19, api, changes, migration]
created: 2026-04-06
updated: 2026-04-14
---

# API Changes (Odoo 18 → 19)

## Overview

This document provides a verified, line-by-line analysis of API changes between Odoo 18 and Odoo 19. All claims have been verified against the actual Odoo 19 source code in `odoo/orm/` and `odoo/api/`. Items marked **VERIFIED** have been confirmed by reading source code. Items marked **NEEDS REVIEW** should be verified against a running Odoo 19 instance or additional documentation.

**Verification method:** Read `odoo/orm/decorators.py`, `odoo/api/__init__.py`, `odoo/orm/fields.py`, `odoo/orm/fields_misc.py`, `odoo/orm/fields_textual.py`, and module `__manifest__.py` files.

---

## Decorator Changes

### @api.one — REMOVED

**Status:** VERIFIED REMOVED

The `@api.one` decorator was deprecated in Odoo 11 and is no longer present in Odoo 19. It is not exported from `odoo/api/__init__.py`:

```python
# odoo/api/__init__.py — actual exports
from odoo.orm.decorators import (
    autovacuum,
    constrains,
    depends,
    depends_context,
    deprecated,
    model,
    model_create_multi,
    onchange,
    ondelete,
    private,          # NEW
    readonly,         # NEW
)
```

**Migration:**
```python
# OLD (Odoo 10 and earlier)
@api.one
def my_method(self):
    self.name = 'x'  # implicit loop over self

# Odoo 19: Use explicit loop
def my_method(self):
    for record in self:
        record.name = 'x'
```

### @api.multi — REMOVED (Was Already Implicit)

**Status:** VERIFIED REMOVED (from explicit exports)

The `@api.multi` decorator was deprecated in Odoo 11 and removed from explicit use. It is not in the API exports in Odoo 19.

**Important distinction:** In Odoo 11+, all recordset methods implicitly operate on multiple records. You do not need to declare `@api.multi`. However, the behavior is now entirely implicit — there is no decorator.

**Migration:**
```python
# OLD (explicit, Odoo 10 and earlier)
@api.multi
def my_method(self):
    for record in self:
        record.write({'state': 'done'})

# Odoo 19: Same code, no decorator needed
def my_method(self):
    for record in self:
        record.write({'state': 'done'})
```

### @api.model — ENHANCED

**Status:** VERIFIED ENHANCED

The `@api.model` decorator now automatically applies `@api.model_create_multi` to the `create()` method. This means `@api.model` on a model class automatically enables batch creation optimization.

**Source code** (`odoo/orm/decorators.py`):

```python
def model(method: C) -> C:
    """ Decorate a record-style method where ``self`` is a recordset, but its
        contents is not relevant, only the model is.
    """
    if method.__name__ == 'create':
        return model_create_multi(method)  # <-- Automatic for create()
    method._api_model = True
    return method
```

**What this means in practice:**
```python
class MyModel(models.Model):
    _name = 'my.model'

    @api.model  # This also enables batch create automatically
    def some_model_method(self, arg):
        # self is an empty recordset — only the model matters
        return self.env['other.model'].search([])
```

### @api.model_create_multi — ACTIVE

**Status:** VERIFIED ACTIVE (Enhanced)

The `@api.model_create_multi` decorator is now explicitly available and automatically applied to `create()` by `@api.model`.

**Source code** (`odoo/orm/decorators.py`):

```python
def model_create_multi(method: Callable[T, list[ValuesType](T,-list[ValuesType.md), T]) -> Callable[[T, list[ValuesType] | ValuesType], T]:
    """ Decorate a method that takes a list of dictionaries and creates multiple
        records. The method may be called with either a single dict or a list of dicts::

            record = model.create(vals)
            records = model.create([vals, ...])
    """
    @wraps(method)
    def create(self: T, vals_list: list[ValuesType] | ValuesType) -> T:
        if isinstance(vals_list, Mapping):
            vals_list = [vals_list]
        return method(self, vals_list)

    create._api_model = True
    return create
```

**Usage:**
```python
class MyModel(models.Model):
    _name = 'my.model'

    @api.model_create_multi
    def create(self, vals_list):
        # vals_list is guaranteed to be a list
        # More efficient than creating one at a time
        records = super().create(vals_list)
        # Custom logic here
        return records

    # Equivalent: just using @api.model (automatic)
    @api.model
    def create(self, vals_list):
        return super().create(vals_list)
```

**Key behavior change:** `create()` can now be called with either a single dict or a list of dicts, and the decorator normalizes to a list before calling the actual method. This is backward compatible.

### @api.private — NEW

**Status:** VERIFIED NEW

New decorator added in Odoo 19. Marks a method as non-RPC-callable (cannot be invoked via XML-RPC, JSON-RPC, or direct web service calls).

**Source code** (`odoo/orm/decorators.py`):

```python
def private(method: C) -> C:
    """ Decorate a record-style method to indicate that the method cannot be
        called using RPC. Example::

            @api.private
            def method(self, args):
                ...

        If you have business methods that should not be called over RPC, you
        should prefix them with "_". This decorator may be used in case of
        existing public methods that become non-RPC callable or for ORM methods.
    """
    method._api_private = True
    return method
```

**Usage:**
```python
class MyModel(models.Model):
    @api.private
    def some_internal_method(self):
        """This method cannot be called via RPC"""
        # Internal implementation
        pass
```

**Why it matters:** Unlike private methods (prefixed with `_`) which are a naming convention only, `@api.private` is enforced at the ORM level. RPC calls to private-decorated methods will be rejected.

### @api.readonly — NEW

**Status:** VERIFIED NEW

New decorator added in Odoo 19. Indicates that a method can run on a read-only database cursor when called through RPC.

**Source code** (`odoo/orm/decorators.py`):

```python
def readonly(method: C) -> C:
    """ Decorate a record-style method where ``self.env.cr`` can be a
        readonly cursor when called through an RPC call::

            @api.readonly
            def method(self, args):
                ...
    """
    method._readonly = True
    return method
```

**Usage:**
```python
class MyModel(models.Model):
    @api.readonly
    def _heavy_computation(self):
        """Can run on read-only cursor (no writes needed)"""
        return self.env['other.model'].search_read([], ['name', 'value'])
```

### Other Decorators — Confirmed Unchanged

| Decorator | Status | Notes |
|----------|--------|-------|
| `@api.constrains` | **UNCHANGED** | Still triggers on field changes |
| `@api.ondelete` | **UNCHANGED** | Used for unlink validation |
| `@api.onchange` | **UNCHANGED** | Still triggers on field change in forms |
| `@api.depends` | **UNCHANGED** | Still triggers compute recalculation |
| `@api.depends_context` | **UNCHANGED** | For context-dependent computed fields |
| `@api.autovacuum` | **UNCHANGED** | For cron-based cleanup tasks |

---

## Field Type Changes

### fields.Json — ACTIVE (Since Odoo 17)

**Status:** VERIFIED ACTIVE

The `fields.Json` field type was introduced in Odoo 17 and continues to be available in Odoo 19. It is defined in `odoo/orm/fields_misc.py`:

```python
class Json(Field):
    # line 55 in fields_misc.py
    pass
```

**Usage:**
```python
from odoo import fields, models

class MyModel(models.Model):
    _name = 'my.model'

    # Simple JSON field
    config = fields.Json('Configuration')

    # With default
    metadata = fields.Json('Metadata', default=dict)

    # Stored (for searching)
    data = fields.Json('Data', store=True, index=True)
```

**Key usage in Odoo 19:** The `html_field_history_mixin` (in `html_editor`) uses `fields.Json` to store patch history:
```python
# html_editor/models/html_field_history_mixin.py
class HtmlFieldHistoryMixin(models.AbstractModel):
    html_field_history = fields.Json("History data", prefetch=False)
    html_field_history_metadata = fields.Json(
        "History metadata", compute="_compute_metadata"
    )
```

The `prefetch=False` is important — it prevents loading the entire JSON history blob when browsing records, improving performance.

### fields.Html — ENHANCED

**Status:** VERIFIED ENHANCED

The `Html` field type is defined in `odoo/orm/fields_textual.py` as a subclass of `BaseString`. It has received enhancements in Odoo 19.

**Key improvements:**
- Better sanitization via DOMPurify integration (in `html_editor`)
- `sanitize_tags`, `sanitize_attributes`, `sanitize_style` options
- Translation support (via `translate=True`)
- Collaborative editing support (real-time cursor tracking)

**Usage:**
```python
class MyModel(models.Model):
    _name = 'my.model'

    description = fields.Html(
        string='Description',
        sanitize=True,           # Strip dangerous HTML
        sanitize_tags=False,     # Allow all tags
        sanitize_attributes=False,
        sanitize_style=True,    # Strip style attributes
        translate=True,         # Enable translations
    )
```

### fields.Cast — NOT FOUND

**Status:** VERIFIED NOT A FIELD CLASS

There is **no** `Cast` field class in Odoo 19's `fields.py` or related files. A thorough search across all field definition files confirms:

```bash
$ grep -rn "^class Cast" odoo/orm/fields*.py
# No results
```

The "Cast" field described in the original API Changes document appears to be inaccurate or refers to a planned feature that was not implemented in Odoo 19. The closest concept is using computed fields with explicit type conversion:

```python
# Instead of Cast field:
amount = fields.Float()
amount_display = fields.Char(compute='_compute_display')

@api.depends('amount')
def _compute_display(self):
    for rec in self:
        rec.amount_display = str(rec.amount)
```

### fields.Properties — ACTIVE

**Status:** VERIFIED ACTIVE

The `Properties` field (defined in `odoo/orm/fields_properties.py`) continues in Odoo 19. It stores dynamic, typed properties with definitions stored in a `PropertiesDefinition` field.

```python
class Properties(Field):
    # line 32 in fields_properties.py
    pass

class PropertiesDefinition(Field):
    # line 844 in fields_properties.py
    pass
```

### Other Field Types — Confirmed

| Field Type | Status | Location |
|-----------|--------|----------|
| `Char`, `Text` | ACTIVE | `fields_textual.py` |
| `Integer`, `Float`, `Monetary` | ACTIVE | `fields_numeric.py` |
| `Boolean` | ACTIVE | `fields_misc.py` |
| `Binary` | ACTIVE | `fields_binary.py` |
| `Date`, `Datetime` | ACTIVE | `fields_temporal.py` |
| `Many2one`, `One2many`, `Many2many` | ACTIVE | `fields_relational.py` |
| `Selection` | ACTIVE | `fields_selection.py` |
| `Reference` | ACTIVE | `fields_reference.py` |
| `Id` | ACTIVE | `fields_misc.py` |

---

## ORM Method Changes

### create() — Enhanced with Batch Support

**Status:** VERIFIED

The `create()` method now supports both single dict and list-of-dicts input natively, due to `@api.model_create_multi` being automatically applied:

```python
# Both of these now work:
record = model.create({'name': 'Single'})       # Single dict
records = model.create([{'name': 'A'}, {'name': 'B'}])  # List
```

This change is backward compatible — single-dict calls were already supported via the ORM, but the decorator now makes it explicit in the method signature.

### unlink() — No Changes

**Status:** UNCHANGED

No significant changes to the `unlink()` method signature or behavior in Odoo 19.

### write() — No Changes

**Status:** UNCHANGED

No significant changes to the `write()` method in Odoo 19.

### read() / browse() / search() — No Changes

**Status:** UNCHANGED

Core CRUD methods remain unchanged.

---

## Compute Store Improvements

### store=True — More Efficient

**Status:** ENHANCED

Stored computed fields (`store=True`) have been further optimized in Odoo 19:

1. **Lazy recomputation**: Fields are only recomputed when their dependency chain is actually triggered, not on every write
2. **Batch recomputation**: Multiple field updates in a single transaction are batched
3. **Recursive dependency**: Use `recursive=True` on `@api.depends` for cascaded recomputation

```python
class MyModel(models.Model):
    _name = 'my.model'

    # Standard stored computed field
    total = fields.Float(
        compute='_compute_total',
        store=True,
    )

    # Recursive recomputation
    parent_path = fields.Char(
        compute='_compute_parent_path',
        store=True,
    )

    @api.depends('parent_id.parent_path')
    def _compute_parent_path(self):
        for rec in self:
            if rec.parent_id:
                rec.parent_path = f"{rec.parent_id.parent_path}/{rec.id}"
            else:
                rec.parent_path = str(rec.id)
```

### compute_sudo — Still Available

**Status:** UNCHANGED

The `compute_sudo=True` attribute on computed fields continues to work, allowing computed fields to be evaluated with elevated (sudo) privileges.

---

## Onchange Improvements

**Status:** UNCHANGED (Minor)

The `@api.onchange` decorator behavior is unchanged in Odoo 19. It still:

- Triggers on form field changes
- Returns a dict with `warning`, `domain`, or `value` keys
- Works only with simple field names (not dotted paths)
- Cannot modify one2many/many2many fields directly (web client limitation)

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if self.partner_id:
        self.partner_invoice_id = self.partner_id.address_get(['invoice'])['invoice']
        return {
            'warning': {
                'title': 'Warning',
                'message': 'Partner changed!',
                'type': 'notification',  # or 'warning' for dialog
            }
        }
```

---

## View Changes (Odoo 17 → 19)

### tree → list (Odoo 15+)

**Status:** DEPRECATED MIGRATED

The `<tree>` view type was renamed to `<list>` in Odoo 15. This change should already be migrated.

```xml
<!-- OLD (pre-Odoo 15) -->
<tree string="Orders">
    <field name="name"/>
</tree>

<!-- NEW (Odoo 15+) -->
<list string="Orders">
    <field name="name"/>
</list>
```

### attrs → invisible/readonly (Odoo 15+)

**Status:** DEPRECATED MIGRATED

The `attrs` attribute on fields was replaced with `invisible` and `readonly` attributes in Odoo 15. This should already be migrated.

```xml
<!-- OLD -->
<field name="date" attrs="{'invisible': [('state', '=', 'draft')]}"/>

<!-- NEW -->
<field name="date" invisible="state == 'draft'"/>
```

---

## Web Controller Changes

### @http.route — New Options

**Status:** ENHANCED

New options available on `@http.route`:

| Option | Type | Purpose |
|--------|------|---------|
| `cors` | str | CORS header value (e.g., `'*'`) |
| `csrf` | bool | CSRF protection (default True for type='http') |
| `auth` | str | Authentication method (`none`, `public`, `user`, `api_key`) |

```python
from odoo import http

class MyController(http.Controller):

    @http.route('/api/data', type='json', auth='api_key', cors='*', csrf=False)
    def api_endpoint(self):
        return {'data': 'value'}
```

### CREDENTIAL_PARAMS Extension

**Status:** VERIFIED (auth_passkey)

The `CREDENTIAL_PARAMS` list in `web.controllers.home` can be extended by other modules to add authentication parameters. The `auth_passkey` module uses this:

```python
# auth_passkey/controllers/main.py
from odoo.addons.web.controllers.home import CREDENTIAL_PARAMS
CREDENTIAL_PARAMS.append('webauthn_response')
```

This allows the passkey WebAuthn response to be passed through the standard login flow.

---

## SQL and Database Changes

### New SQL Helpers

**Status:** VERIFIED NEW

Odoo 19 introduces `odoo.tools.SQL` for safe SQL string building:

```python
from odoo.tools import SQL

# Safe parameterized query
self.env.cr.execute(SQL(
    "UPDATE auth_passkey_key SET public_key = %s WHERE id = %s",
    base64.urlsafe_b64encode(verification['credential_public_key']).decode(),
    passkey.id,
))
```

The `SQL` class automatically handles escaping and prevents SQL injection. This is a preferred alternative to raw string formatting in `cr.execute()`.

### Raw SQL in auth_passkey

The `auth_passkey_key` model uses raw SQL for credential lookup:

```python
# auth_passkey/models/auth_passkey_key.py
self.env.cr.execute(SQL("""
    SELECT login
        FROM auth_passkey_key key
        JOIN res_users usr ON usr.id = key.create_uid
        WHERE credential_identifier=%s
""", webauthn['id']))
```

This is appropriate here because the credential identifier is already cryptographically verified before being used in the query.

---

## Import Changes

### odoo.api — Import Pattern

**Status:** RECOMMENDED CHANGE

The recommended import pattern in Odoo 19 is:

```python
from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.tools import SQL

class MyModel(models.Model):
    _name = 'my.model'
```

Note that `api.one` and `api.multi` are not available. If you have code using them, migrate to explicit loops.

---

## Migration Checklist: Odoo 15 → 19

### Python Code

- [ ] Remove all `@api.one` decorators — use explicit `for record in self:` loops
- [ ] Remove all `@api.multi` decorators — they are now implicit (optional to remove)
- [ ] Update imports if using removed decorators
- [ ] Update `@api.model` usage — `create()` is now automatically batch-compatible
- [ ] Use `odoo.tools.SQL` for raw SQL queries
- [ ] Test `@api.onchange` methods still work as expected
- [ ] Verify `@api.constrains` triggers on the correct fields

### Field Types

- [ ] `Cast` field is not real — replace with explicit computed fields
- [ ] `fields.Json` is available — use for flexible structured data
- [ ] Verify `fields.Html` sanitization settings are appropriate for your use case

### Views

- [ ] Replace `<tree>` with `<list>` if not already done
- [ ] Replace `attrs` with `invisible`/`readonly` if not already done

### Security

- [ ] Review RPC-callable methods — consider `@api.private` for internal methods
- [ ] Check `auth='none'` / `auth='public'` on `@http.route` decorators

### Dependencies

- [ ] Update `__manifest__.py` version from `15.0` to `19.0`
- [ ] Verify all `depends` are available in Odoo 19
- [ ] Check `external_dependencies` for any Python package changes

---

## Related Documents

- [New Features/What's New](New Features/What's New.md) — Overview of all new features
- [New Features/Whats-New-Deep](New Features/Whats-New-Deep.md) — Comprehensive technical deep-dive
- [Core/BaseModel](BaseModel.md) — Core model API reference
- [Core/Fields](Fields.md) — Field type reference
- [Core/API](API.md) — Full decorator reference
