# API Decorators

Dokumentasi Odoo 15 untuk API decorators. Source: `odoo/odoo/api.py`

## Available Decorators

| Decorator | Purpose | Changes signature |
|---|---|---|
| `@api.model` | Method doesn't need record context | Yes (no `self`) |
| `@api.model_create_multi` | Create multiple records | No |
| `@api.depends(*fields)` | Triggers recompute on field change | No |
| `@api.onchange(*fields)` | Client-side onchange trigger | No |
| `@api.constrains(*fields)` | Raise ValidationError on constraint violation | No |
| `@api.returns(model, func=None)` | Specify return model for inheritance | No |
| `@api.one` | **Deprecated** (wraps `self` to single record per iteration) | No |
| `@api.multi` | Default decorator (no automatic wrapping) | No |

## @api.model

Method tanpa record context. Biasa untuk default_get, name_search, classmethod-like operations.

```python
@api.model
def _get_company_id_list(self):
    return self.env.company.ids

@api.model
def default_get(self, fields_list):
    defaults = super().default_get(fields_list)
    # self.env available but self is empty recordset
    return defaults

# Note: No automatic self iteration
```

**Key behavior:**
- `self` is an empty recordset
- Used for class-level logic, default values, name_search
- Cannot access `self` records (it's empty/missing)
- Available `self.env`, `self._name`, etc.

## @api.model_create_multi

Batched creation, returns list of created records.

```python
@api.model_create_multi
def create(self, vals_list):
    # vals_list: list of dicts to create
    # Returns: recordset of created records
    return super().create(vals_list)

# Usage:
records = self.env['my.model'].create([
    {'name': 'Record 1'},
    {'name': 'Record 2'},
])
```

**Override pattern:**

```python
@api.model_create_multi
def create(self, vals_list):
    # Pre-process
    for vals in vals_list:
        vals['name'] = self._process_name(vals.get('name', ''))
    return super().create(vals_list)
```

## @api.depends

Triggers recompute ketika field yang dibaca berubah.

```python
@api.depends('price', 'quantity')
def _compute_amount(self):
    for record in self:
        record.amount = record.price * record.quantity

# Nested relation access
@api.depends('line_ids.price', 'line_ids.quantity')
def _compute_total(self):
    ...

# Recursive
@api.depends('partner_id.country_id.code')
def _compute_region(self):
    ...

# With method as callable
@api.depends(method_name)
def _compute_something(self):
    ...
```

### store=True vs False

| Option | Stored in DB? | Recomputed |
|---|---|---|
| `store=False` (default) | No | On-demand when read |
| `store=True` | Yes | When any depends field changes |

Computed fields `store=True` hanya di-recompute saat dependensi berubah, bukan setiap read.

### Caching

Odoo 15 ORM melakukan prefetch dan caching otomatis. `invalidate_cache()` dipanggil saat flush.

## @api.onchange

Trigger method di client-side saat user mengubah field di form.

```python
@api.onchange('partner_id')
def _onchange_partner(self):
    if self.partner_id:
        self.address = self.partner_id.address
        self.phone = self.partner_id.phone
        # Return warning or domain via special dict
        return {
            'warning': {
                'title': 'Warning',
                'message': 'Please check',
                'type': 'notification',
            },
            'domain': {
                'user_id': [('partner_id', '=', self.partner_id.id)],
            }
        }

# Multiple fields
@api.onchange('date_from', 'date_to')
def _onchange_dates(self):
    if self.date_from and self.date_to:
        self.days = (self.date_to - self.date_from).days
```

**Warning types:** `dialog`, `notification`

**Limitation:** Onchange berjalan di client, tidak ada akses ke database write. Only for UI suggestions.

## @api.constrains

Validasi constraint. Dipanggil saat save/write, raise `ValidationError` jika violate.

```python
@api.constrains('start_date', 'end_date')
def _check_dates(self):
    for record in self:
        if record.start_date > record.end_date:
            raise ValidationError(
                _('Start Date must be before End Date')
            )

# Multiple fields
@api.constrains('quantity', 'price')
def _check_price(self):
    if any(r.quantity < 0 for r in self):
        raise ValidationError(_('Quantity cannot be negative'))
```

**Behavior:**
- Called **before** write is committed
- Can write to other fields (but not recommended)
- Raises `odoo.exceptions.ValidationError`
- All constraints run before any database write

**Note:** `@api.constrains` fields harus dibaca/diakses di method atau akan error saat compile check.

## @api.returns

Specify return model untuk method inheritance chain.

```python
@api.returns('account.move', func=lambda self: self.move_id)
def _create_account_moves(self):
    pass
```

Common in action methods returning browse records:

```python
@api.returns('self', lambda rec: rec.id)
def copy(self, default=None):
    ...
```

## Combined Decorators

```python
# Model method that also depends on fields
@api.model
@api.depends('company_id')
def _get_journal(self):
    ...

# Correct approach: depends tidak bisa digabung dengan @api.model
# Gunakan @api.multi dan akses self[0] untuk model context
```

## Environment

```python
self.env          # Environment
self.env.cr       # Cursor
self.env.uid      # User ID
self.env.user     # User record
self.env.company  # Current company
self.env.companies # All allowed companies

# Context-aware env
self.with_context(tz='America/New_York')
self.with_user(user_id)
self.sudo()
self.sudo(user_id)
```

## Meta Behavior (api.py:66)

`Meta` metaclass (`api.Meta`) secara otomatis men-decorate traditional-style methods
(methods yang tidak memiliki decorator `@api.*`).

Detection based on method signature:
- Parameters named `cr, uid, ids, context` → treated as old API
- Auto-decorated with appropriate wrapper

## See Also
- [Core/BaseModel](Core/BaseModel.md) — Model definition
- [Core/Fields](Core/Fields.md) — Field types
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine, action methods