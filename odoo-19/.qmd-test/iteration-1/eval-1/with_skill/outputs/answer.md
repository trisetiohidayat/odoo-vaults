# `_inherit` vs `_inherits` in Odoo

## Summary

Odoo provides two fundamentally different inheritance mechanisms for extending models: **`_inherit`** (Classic / Extension Inheritance) and **`_inherits`** (Delegation Inheritance). `_inherit` is used to add fields and methods to an existing model without creating a new database table, while `_inherits` creates a separate child model that stores its own database table and transparently exposes fields from a parent model through SQL joins.

## Key Points

| Aspect | `_inherit` | `_inherits` |
|--------|-----------|-------------|
| **Mechanism** | Classic extension / monkey-patching | Delegation via `Many2one` with `delegate=True` |
| **Database** | No new table; fields added to parent's table | New child table; parent fields accessed via SQL JOIN |
| **Model Identity** | Same `_name` as parent | New `_name`, different from parent |
| **Parent Storage** | Single table | Two linked tables (parent + child) |
| **Use Case** | Adding fields/methods to an existing model | Creating specialized subtypes (e.g., `res.users` from `res.partner`) |
| **Records** | One record per entity | Two records per entity (one in each table) |

## Detail

### 1. Classic Inheritance — `_inherit`

`_inherit` is the most common pattern. It tells Odoo to extend an existing model. When you specify `_inherit = 'sale.order.line'` with the same `_name`, you are **adding** fields and methods to that existing model. The model continues to use a single database table.

You can also pass a **list** of models to `_inherit` to combine multiple behaviors (Prototype Inheritance), for example:
```python
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'mail.thread', 'portal.mixin']
```
This mixes in `mail.thread` (for messaging/Chatter) and `portal.mixin` (for portal access) alongside the base `sale.order`.

**Source:** [Patterns/Inheritance Patterns.md](Inheritance Patterns.md)

---

### 2. Delegation Inheritance — `_inherits`

`_inherits` creates a child model that **delegates** field access to a parent model via an implicit `Many2one` field. The child has its own `_name` and its own database table, but parent fields appear directly on the child model (accessed via SQL JOIN at read time).

```python
class MyOrderLine(models.Model):
    _name = 'my.order.line'
    _inherits = {'product.product': 'product_id'}

    product_id = fields.Many2one(
        'product.product',
        delegate=True,
        required=True,
        ondelete='cascade'
    )
```

In this example, `my.order.line` gets its own table, but fields from `product.product` (like `name`, `list_price`, etc.) are accessible directly on `my.order.line` records because they are delegated to the linked `product.product` via the `product_id` field.

A real-world example in Odoo is `hr.employee`, which uses `_inherits` on `hr.version`:
> `hr.employee` uses Odoo's delegation inheritance (`_inherits`) rather than classic extension. This means every `hr.employee` record has a corresponding `hr.version` record stored in a separate table (`hr_version`). Fields defined on `hr.version` appear directly on `hr.employee` via SQL join at read time.

**Source:** [Modules/HR.md](HR.md)

---

### Key Behavioral Differences

1. **Single vs. Multiple Tables**
   - `_inherit` with the same `_name`: one table, fields are added to it
   - `_inherits`: two tables (parent + child), joined at read time

2. **Field Access**
   - Fields added via `_inherit` live in the child's `_fields` dict and are stored in the parent table
   - Fields delegated via `_inherits` are **not included in the child model's `_fields` dict** — they live on the parent model's table and are accessed via `__get__` delegation

3. **Record Creation**
   - `_inherit` (same name): one `create()` call, one record
   - `_inherits`: one `create()` call creates **two records** — one in the parent table and one in the child table, linked by the delegate `Many2one`

4. **Odoo 19 Change: `mail.group.message`**
   In Odoo 19, `mail.group.message` was refactored away from `_inherits`:
   > Does **not** inherit from `mail.message` via `_inherits` (unlike Odoo 18 and earlier) — this was changed in Odoo 19 to avoid ORM cache penalties. Instead, fields are mirrored via `related='mail_message_id.field_name'` with `readonly=False`. This means the model has its own table (`mail_group_message`), separate from `mail_message`.

   **Source:** [Modules/mail-group.md](Modules/mail-group.md)

---

### When to Use Which

| Scenario | Use |
|----------|-----|
| Add custom fields to `sale.order.line` | `_inherit = 'sale.order.line'` (same name) |
| Add messaging/Chatter to a model | `_inherit = ['res.partner', 'mail.thread']` (mixin) |
| Create a `sale.report` that aggregates data (no table) | Abstract model with `_name` only |
| Create a specialized subtype (e.g., Employee as Person) | `_inherits` |
| Add methods to an existing model | `_inherit = 'model.name'` (same name) |

---

## Sources

- [Patterns/Inheritance Patterns.md](Inheritance Patterns.md) — Primary source for three inheritance patterns with code examples
- [Modules/HR.md](HR.md) — Real-world `_inherits` example with `hr.employee` / `hr.version`
- [Modules/mail-group.md](Modules/mail-group.md) — Odoo 19 change: `_inherits` removed in favor of `related` fields
- [Core/BaseModel.md](BaseModel.md) — `_inherit` as a key model attribute
