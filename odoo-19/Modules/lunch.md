---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #lunch
description: L4 documentation for the Lunch ordering and management module — wallet system, supplier scheduling, cron-driven emails, cart merging, and topping constraints.
---

# lunch

**Module:** `lunch`
**Location:** `~/odoo/odoo19/odoo/addons/lunch/`
**Depends:** `mail`
**Category:** Human Resources/Lunch
**License:** LGPL-3
**Application:** Yes

Employee lunch ordering and vendor management module. Enables employees to order food from configured suppliers, add toppings/extras, place orders, and pay from a virtual wallet. Administrators manage suppliers with delivery schedules, automatic email ordering via cron, and cash reconciliation.

---

## Models Overview

| Model | `_name` | Summary |
|---|---|---|
| [Modules/lunch#lunch-product](modules/lunch#lunch-product.md) | `lunch.product` | Menu items linked to a vendor |
| [Modules/lunch#lunch-product-category](modules/lunch#lunch-product-category.md) | `lunch.product.category` | Product groupings (pizza, sandwich, burger, etc.) |
| [Modules/lunch#lunch-order](modules/lunch#lunch-order.md) | `lunch.order` | Per-user/order-date line item |
| [Modules/lunch#lunch-topping](modules/lunch#lunch-topping.md) | `lunch.topping` | Extras grouped by topping_category (1/2/3) |
| [Modules/lunch#lunch-supplier](modules/lunch#lunch-supplier.md) | `lunch.supplier` | Vendor with schedule, contacts, cron |
| [Modules/lunch#lunch-location](modules/lunch#lunch-location.md) | `lunch.location` | Delivery/pickup site |
| [Modules/lunch#lunch-cashmove](modules/lunch#lunch-cashmove.md) | `lunch.cashmove` | Wallet credit/debit ledger |
| [Modules/lunch#lunch-alert](modules/lunch#lunch-alert.md) | `lunch.alert` | In-app banners or chat notifications |

Extension models:
- `res.company`: adds `lunch_minimum_threshold`, `lunch_notify_message`
- `res.users`: adds `last_lunch_location_id`, `favorite_lunch_product_ids`

---

## `lunch.product`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_product.py`

```
class LunchProduct(models.Model):
    _name = 'lunch.product'
    _inherit = ['image.mixin']
    _order = 'name'
    _check_company_auto = True
```

### Fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | `Char` | Yes | — | Translatable |
| `category_id` | `Many2one(lunch.product.category)` | Yes | — | `check_company=True` |
| `description` | `Html` | No | — | Translatable |
| `price` | `Float` | Yes | — | Digits `'Account'` |
| `supplier_id` | `Many2one(lunch.supplier)` | Yes | — | `check_company=True` |
| `active` | `Boolean` | No | `True` | |
| `company_id` | `Many2one(res.company)` | No | — | Related from `supplier_id.company_id`, stored, `readonly=False` |
| `currency_id` | `Many2one(res.currency)` | No | — | Related from `company_id.currency_id` |
| `new_until` | `Date` | No | — | "NEW" badge until this date |
| `is_new` | `Boolean` | — | — | Computed: `today <= new_until` |
| `favorite_user_ids` | `Many2many(res.users)` | No | — | Link table: `lunch_product_favorite_user_rel` |
| `is_favorite` | `Boolean` | — | — | Computed + invertible: current user in `favorite_user_ids` |
| `last_order_date` | `Date` | — | — | Computed: most recent `lunch.order` date for current user + product |
| `product_image` | `Image` | — | — | Computed: `image_128` else `category_id.image_128` |
| `is_available_at` | `Many2one(lunch.location)` | — | — | Search-only; filters products by supplier delivery zone |
| `image_1920` / `image_128` | `Image` | — | — | From `image.mixin` |

### Computed Logic

**`_compute_is_new`**: Compares `new_until` against `context_today`. Returns `False` for null `new_until`. No dependency on product fields — only date context.

**`_compute_is_favorite`**: Uses `@api.depends_context('uid')` — result is per-session user and recomputed when the current user changes. Uses plain Python `in` on the recordset.

**`_compute_last_order_date`**: Searches all `lunch.order` for `(user_id, product_id)`, groups by product using `defaultdict(lambda: self.env['lunch.order'])`, then takes `max()` of mapped dates. Returns `False` if no orders exist. O(n) full table scan per product in the set.

**`_search_is_available_at`**: Custom search operator `'in'` only. Builds a compound domain with OR between supplier having the location in `available_location_ids` OR supplier having no location restriction (`available_location_ids = False`). This allows products from unconstrained suppliers to appear in any location-filtered search.

**`_compute_product_image`**: Priority: product's own `image_128` → category's `image_128` → falsy.

### Constraints

```python
@api.constrains('active', 'category_id')
def _check_active_categories(self):
    # Active product with archived category -> UserError

@api.constrains('active', 'supplier_id')
def _check_active_suppliers(self):
    # Active product with archived supplier -> UserError
```

### Cascade Archiving

**`_sync_active_from_related`**: Called by `lunch.product.category` and `lunch.supplier` when they archive/unarchive. Archives products whose category OR supplier is archived; unarchives products whose both category and supplier are active.

### Performance Notes

- `_compute_last_order_date` executes `search()` across all order history for the current user — cost grows with order history.
- `_compute_product_count` on categories uses `_read_group`, which is more efficient than looping with `search_count`.
- `is_favorite` invert function (`_inverse_is_favorite`) triggers a `write()` on `res.users` with `(4, id)` (link) or `(3, id)` (unlink) commands — one extra write per toggle.

---

## `lunch.product.category`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_product_category.py`

```
class LunchProductCategory(models.Model):
    _name = 'lunch.product.category'
    _inherit = ['image.mixin']
    _description = 'Lunch Product Category'
```

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `Char` | Yes | Translatable |
| `company_id` | `Many2one(res.company)` | No | |
| `currency_id` | `Many2one(res.currency)` | No | Related from `company_id.currency_id` |
| `product_count` | `Integer` | — | Computed via `_read_group` on `lunch.product` |
| `active` | `Boolean` | No | Default `True` |
| `image_1920` | `Image` | No | Falls back to `lunch/static/img/lunch.png` via `_default_image` |
| `image_128` | `Image` | No | From `image.mixin` |

### Cascade Behavior

**`_sync_active_products`**: Called on both `action_archive()` and `action_unarchive()`. Uses `Product.with_context(active_test=False)` to bypass active filtering during archive, finds all products in this category, then calls `product._sync_active_from_related()`. This ensures the product's active state always mirrors the category's.

---

## `lunch.order`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_order.py`

```
class LunchOrder(models.Model):
    _name = 'lunch.order'
    _order = 'id desc'
    _display_name = 'product_id'
    _user_product_date = models.Index("(user_id, product_id, date)")
```

Each record is one line item (product + toppings + quantity) for one user on one date. Shares the `lunch_order_topping` link table with all three topping groups.

### Fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | `Char` | — | — | Related from `product_id.name`, readonly |
| `product_id` | `Many2one(lunch.product)` | Yes | — | |
| `category_id` | `Many2one(lunch.product.category)` | — | — | Related + stored from `product_id.category_id` |
| `date` | `Date` | Yes | `context_today` | |
| `supplier_id` | `Many2one(lunch.supplier)` | — | — | Related + stored + indexed from `product_id.supplier_id` |
| `available_today` | `Boolean` | — | — | Related from `supplier_id.available_today` |
| `available_on_date` | `Boolean` | — | — | Computed: supplier available on `date` |
| `order_deadline_passed` | `Boolean` | — | — | Computed: past deadline or past date |
| `user_id` | `Many2one(res.users)` | Yes | `env.uid` | |
| `lunch_location_id` | `Many2one(lunch.location)` | No | `env.user.last_lunch_location_id` | |
| `note` | `Text` | No | — | Free-text instructions to supplier |
| `price` | `Monetary` | — | — | Computed + stored: `qty * (product.price + sum(toppings))` |
| `active` | `Boolean` | No | `True` | Deactivated orders are soft-deleted |
| `state` | `Selection` | Yes | `'new'` | |
| `notified` | `Boolean` | No | `False` | Set `True` after `action_notify()` |
| `company_id` | `Many2one(res.company)` | No | `env.company.id` | |
| `currency_id` | `Many2one(res.currency)` | No | — | Related + stored from `company_id.currency_id` |
| `quantity` | `Float` | Yes | `1` | |
| `display_toppings` | `Text` | — | — | Computed + stored: `' + '.join(names)` |
| `product_description` | `Html` | — | — | Related from `product_id.description` |
| `topping_label_1/2/3` | `Char` | — | — | Related from `product_id.supplier_id.topping_label_*` |
| `topping_quantity_1/2/3` | `Selection` | — | — | Related from supplier; controls min/max topping constraints |
| `image_1920` / `image_128` | `Image` | — | — | Computed from product or category |
| `available_toppings_1/2/3` | `Boolean` | — | — | Computed: topping exists for supplier in that category |
| `display_reorder_button` | `Boolean` | — | — | Computed: context `show_reorder_button` + state=`confirmed` + supplier available |
| `display_add_button` | `Boolean` | — | — | Computed: wallet - cart_total >= product price |
| `topping_ids_1` | `Many2many(lunch.topping)` | No | — | Domain `topping_category=1`; link table `lunch_order_topping` |
| `topping_ids_2` | `Many2many(lunch.topping)` | No | — | Domain `topping_category=2`; same link table |
| `topping_ids_3` | `Many2many(lunch.topping)` | No | — | Domain `topping_category=3`; same link table |

### State Machine

```
new ──action_order()──> ordered ──action_send()──> sent ──action_confirm()──> confirmed
  │                          │                        │
  +──action_cancel()────────->+──action_cancel()──────>+
                             │
                             +──action_reset()────────>+
                                                          │
                                                        cancelled
```

| State | Label | Editable | Deletable | Notes |
|---|---|---|---|---|
| `new` | To Order | Yes | Yes | Cart state |
| `ordered` | Ordered | No (rule) | No (rule) | User locked; wallet checked |
| `sent` | Sent | No | No | Sent to supplier |
| `confirmed` | Received | No | No | Delivered |
| `cancelled` | Cancelled | No | Yes | Soft-deleted |

### Workflow Actions

| Method | Transition | Validation | Side Effects |
|---|---|---|---|
| `action_order()` | `new` → `ordered` | Product active; supplier available on date; wallet balance | Calls `_check_wallet()` |
| `action_reorder()` | copy → `ordered` | Supplier available today | Copies to today |
| `action_confirm()` | `sent` → `confirmed` | None | None |
| `action_cancel()` | any → `cancelled` | None | None |
| `action_reset()` | `cancelled` → `ordered` | None | None |
| `action_send()` | `ordered` → `sent` | None | Called by `_send_auto_email()` |
| `action_notify()` | any → notified | None | Sends `message_notify` to each unique user; sets `notified=True` |
| `update_quantity(increment)` | in-place | Cannot edit `sent`/`confirmed` lines | Deactivates if `qty <= -increment`; calls `_check_wallet()` |

### Computed Logic

**`_compute_total_price`**: `quantity * (product_id.price + sum(all topping prices))`. Stored on write via `@api.depends`.

**`_compute_display_toppings`**: Concatenates `topping_ids_1 | topping_ids_2 | topping_ids_3` names with `' + '`. Stored.

**`_compute_available_toppings`**: Three separate `search_count()` calls per order line — one per topping category against the supplier. Called at render time. Potential N+1 in list views.

**`_compute_display_add_button`**: `_read_group` on `lunch.order` groups all `new` orders for current user on the same date, sums prices, then calls `get_wallet_balance() - cart_total >= product.price`. One `read_group` per visible order line.

**`_compute_available_on_date`**: Delegates to `supplier_id._available_on_date(date)` — checks weekday flag and `recurrency_end_date`.

**`_compute_order_deadline_passed`**: `date < today` → `True`; `date == today` → delegates to supplier; `date > today` → `False`.

### Cart Merge Pattern (Create)

```python
def create(self, vals_list):
    for vals in vals_list:
        lines = self._find_matching_lines({
            **vals, 'toppings': self._extract_toppings(vals), 'state': 'new'
        })
        if lines:
            lines.update_quantity(1)   # increment existing cart line
            orders |= lines[:1]
        else:
            orders |= super().create(vals)
    return orders
```

If an identical `new` order exists for the same user/product/date/location/note/toppings, the existing line's quantity is incremented instead of creating a new record. Prevents duplicate cart entries when the same item is added twice.

### Cart Merge Pattern (Write)

```python
def write(self, vals):
    if merge_needed:
        for line in self:
            toppings = self._extract_toppings(values)
            matching_lines = self._find_matching_lines({...})
            if matching_lines:
                lines_to_deactivate |= line
                matching_lines.update_quantity(line.quantity)
        lines_to_deactivate.write({'active': False})
        return super(LunchOrder, self - lines_to_deactivate).write(values)
    return super().write(values)
```

When `note`, toppings, or `state` changes, any matching `new` order absorbs this line's quantity and this line is deactivated.

### `_extract_toppings`

Pops `topping_ids_1/2/3` from `values` using `_fields[field].convert_to_cache()`. For existing records with no topping values in `vals`, falls back to `self[:1][topping_field].ids`. Returns a flat list of topping IDs.

Known bug (TODO in source): the topping comparison for existing records does not account for all individual order toppings in batch operations — only checks the first record.

### Topping Quantity Constraints

```python
@api.constrains('topping_ids_1', 'topping_ids_2', 'topping_ids_3')
def _check_topping_quantity(self):
    for line in self:
        for index in range(1, 4):
            quantity = line[f'topping_quantity_{index}']
            toppings = line[f'topping_ids_{index}'].filtered(...)
            label = line[f'topping_label_{index}']
            if availability and quantity != '0_more':
                check = bool(len(toppings) == 1 if quantity == '1' else toppings)
                if not check:
                    raise ValidationError(...)
```

| Supplier Setting | Rule |
|---|---|
| `'0_more'` | Zero toppings allowed |
| `'1_more'` | At least one topping required |
| `'1'` | Exactly one topping required |

### Wallet Validation

```python
def _check_wallet(self):
    self.env.flush_all()
    for line in self:
        if self.env['lunch.cashmove'].get_wallet_balance(line.user_id) < 0:
            raise ValidationError(_('Not enough money in your wallet...'))
```

`flush_all()` ensures all pending writes are persisted before the balance query. Allows balances down to `-lunch_minimum_threshold` (overdraft).

### Performance Notes

- `_user_product_date` composite index speeds `_find_matching_lines` lookups.
- `_compute_display_add_button` runs a `_read_group` per visible line — can be expensive in kanban view.
- `update_quantity` flushes per record, then calls `_check_wallet` with one query per order line.
- `invalidate_model(['topping_ids_2', 'topping_ids_3'])` in `write()` is necessary because ORM cache may be stale after writing via `topping_ids_1` alone.

---

## `lunch.topping`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_topping.py`

```
class LunchTopping(models.Model):
    _name = 'lunch.topping'
    _description = 'Lunch Extras'
```

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `Char` | Yes | |
| `company_id` | `Many2one(res.company)` | No | Default `env.company` |
| `currency_id` | `Many2one(res.currency)` | No | Related from `company_id.currency_id` |
| `price` | `Monetary` | Yes | |
| `supplier_id` | `Many2one(lunch.supplier)` | No | `ondelete='cascade'`, `index='btree_not_null'` |
| `topping_category` | `Integer` | Yes | Default `1`; determines `topping_ids_*` group |
| `display_name` | `Char` | — | Computed: `"name $price"` formatted with `formatLang` |

### Index

`btree_not_null` on `supplier_id` — PostgreSQL can use this for `WHERE supplier_id IS NOT NULL`, which is the typical query pattern.

---

## `lunch.supplier`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_supplier.py`

```
class LunchSupplier(models.Model):
    _name = 'lunch.supplier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

Vendor/partner record. Tracks delivery schedule, ordering method, and manages a linked cron for automatic email.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `partner_id` | `Many2one(res.partner)` | Yes | Vendor contact |
| `name` | `Char` | — | Related from `partner_id.name`, `readonly=False` |
| `email` / `phone` / address fields | Various | — | Related from `partner_id` |
| `company_id` | `Many2one(res.company)` | — | Related + stored from `partner_id.company_id` |
| `responsible_id` | `Many2one(res.users)` | No | Lunch manager; must be in `group_lunch_manager`; used as email "from" |
| `send_by` | `Selection` | No | `'phone'` or `'mail'`, default `'phone'` |
| `automatic_email_time` | `Float` | Yes | Order cutoff time; `0.0`–`12.0`, default `12.0` |
| `moment` | `Selection` | Yes | `'am'` or `'pm'`, default `'am'` |
| `tz` | `Selection` | Yes | Timezone; default `env.user.tz` or `'UTC'` |
| `cron_id` | `Many2one(ir.cron)` | Yes | Auto-created on supplier create; `ondelete='cascade'` |
| `mon`–`sun` | `Boolean` | No | Mon–Fri default `True`; Sat–Sun default `False` |
| `recurrency_end_date` | `Date` | No | Stop showing supplier after this date |
| `available_location_ids` | `Many2many(lunch.location)` | No | Delivery zone restriction |
| `available_today` | `Boolean` | — | Computed: open today given weekday + recurrency |
| `order_deadline_passed` | `Boolean` | — | Computed: cutoff time passed or supplier unavailable |
| `active` | `Boolean` | No | Default `True` |
| `delivery` | `Selection` | No | `'delivery'` or `'no_delivery'`, default `'no_delivery'` |
| `topping_label_1/2/3` | `Char` | Yes | Labels for extra categories; defaults: Extras, Beverages, Extra Label 3 |
| `topping_ids_1/2/3` | `One2many(lunch.topping)` | No | Domain-filtered by `topping_category = 1/2/3` |
| `topping_quantity_1/2/3` | `Selection` | Yes | `'0_more'`, `'1_more'`, `'1'`; default `'0_more'` |
| `show_order_button` | `Boolean` | — | Computed via raw SQL: any `ordered` orders for today |
| `show_confirm_button` | `Boolean` | — | Computed via raw SQL: any `sent` orders for today |

### Constraint

```sql
CHECK(automatic_email_time >= 0 AND automatic_email_time <= 12)
```
Enforced via `flush_model` before `_sync_cron()` on write.

### Float-to-Time Helpers

```python
def float_to_time(hours, moment='am'):
    if hours == 12.0 and moment == 'pm':
        return time.max                          # 23:59:59.999999
    fractional, integral = math.modf(hours)
    if moment == 'pm':
        integral += 12
    return time(int(integral), int(float_round(60 * fractional, precision_digits=0)), 0)

def time_to_float(t):
    return float_round(t.hour + t.minute/60 + t.second/3600, precision_digits=2)
```

Used for `automatic_email_time` + `moment` → Python `time` object for cron scheduling.

### Computed Logic

**`_compute_available_today`**: Converts `fields.Datetime.now()` to UTC then to supplier timezone via `pytz`. Calls `_available_on_date(supplier_date)`.

**`_available_on_date(date)`**: Selects the weekday boolean field by name (`WEEKDAY_TO_NAME[date.weekday()]`), checks `date < recurrency_end_date` (if set), and returns the boolean field value.

**`_search_available_today`**: Supports `'in'` / `'not in'` only. Builds compound domain: recurrency not ended AND correct weekday flag. Uses `Domain` helper for cleaner OR construction.

**`_compute_order_deadline_passed`**: For `send_by='mail'`: compares current time in supplier TZ to `automatic_email_time + moment`. For `send_by='phone'`: returns `not available_today`.

**`_compute_buttons`**: Raw SQL avoids ORM overhead for frequently-called kanban computes.

```python
def _compute_buttons(self):
    self.env.cr.execute("""
        SELECT supplier_id, state, COUNT(*)
          FROM lunch_order
         WHERE supplier_id IN %s
           AND state IN ('ordered', 'sent')
           AND date = %s
           AND active
      GROUP BY supplier_id, state
    """, (tuple(self.ids), fields.Date.context_today(self)))
```

### Cron Lifecycle

**`_sync_cron()`**: Computes next run time in supplier TZ, converts to UTC. Handles past-due by adding 1 day. Sets `cron.active = active AND send_by == 'mail'`. Only suppliers with `send_by='mail'` get active crons.

**`create()`**: Auto-creates an `ir.cron` (sudo), creates `ir.model.data` records with `noupdate=True` for the server action, assigns `cron_id` to each supplier, then calls `_sync_cron()`.

**`write()`**:
- Auto-assigns `topping_category=2/3` to toppings in `topping_ids_2/3` during create/write.
- Cascades `company_id` change to all related `lunch.order` records.
- Cascades `active` change to all related `lunch.product` records.
- Calls `_sync_cron()` when `CRON_DEPENDS` fields change.
- Calls `_cancel_future_days()` when a weekday is set to `False` — cancels pending `new`/`ordered` orders for that day.

**`unlink()`**: Deletes `ir.cron` and its `ir.actions.server` before unlinking the supplier.

### `_cancel_future_days`

Searches for orders where `date >= today`, `state IN ('new', 'ordered')`, filtered to the removed weekdays, then sets `state='cancelled'`. This prevents orders from being placed for days the supplier no longer operates.

### Automatic Email

**`_send_auto_email()`**: Called daily by cron. Only runs if `available_today=True` and `send_by='mail'`. Builds order lines for `state='ordered'` orders today. Renders `lunch.lunch_order_mail_supplier` template with company, supplier, responsible contact, currency, and per-line details (product, note, qty, price, toppings, username, site). Calls `orders.action_send()` to transition all to `sent`.

### Action Methods

**`action_send_orders()`**: For mail suppliers → `_send_auto_email()`. For phone suppliers → `_get_current_orders().action_send()`. Displays success notification.

**`action_confirm_orders()`**: Fetches `state='sent'` orders for today → `action_confirm()`.

---

## `lunch.location`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_location.py`

```
class LunchLocation(models.Model):
    _name = 'lunch.location'
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `Char` | Yes | |
| `address` | `Text` | No | |
| `company_id` | `Many2one(res.company)` | No | Default `env.company` |

---

## `lunch.cashmove`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_cashmove.py`

```
class LunchCashmove(models.Model):
    _name = 'lunch.cashmove'
    _order = 'date desc'
```

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `currency_id` | `Many2one(res.currency)` | Yes | Default `env.company.currency_id` |
| `user_id` | `Many2one(res.users)` | No | Default `env.uid` |
| `date` | `Date` | Yes | Default `context_today` |
| `amount` | `Float` | Yes | Positive = credit (deposit), negative = deduction |
| `description` | `Text` | No | |

### Wallet Balance

```python
def get_wallet_balance(self, user, include_config=True):
    result = float_round(sum(move['amount'] for move in
        self.env['lunch.cashmove.report'].search_read(
            [('user_id', '=', user.id)], ['amount'])), precision_digits=2)
    if include_config:
        result += user.company_id.lunch_minimum_threshold
    return result
```

The balance is the sum of all cashmoves for the user, plus the company overdraft allowance (`lunch_minimum_threshold`). The threshold allows employees to order slightly beyond their deposits up to a configured limit.

---

## `lunch.alert`

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/lunch_alert.py`

```
class LunchAlert(models.Model):
    _name = 'lunch.alert'
    _order = 'write_date desc, id'
```

### Fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | `Char` | Yes | — | Translatable |
| `message` | `Html` | Yes | — | Translatable |
| `mode` | `Selection` | No | `'alert'` | `'alert'` = in-app; `'chat'` = mail notification |
| `recipients` | `Selection` | No | `'everyone'` | Controls which users see the alert |
| `notification_time` | `Float` | No | `10.0` | 0–12 range |
| `notification_moment` | `Selection` | No | `'am'` | |
| `tz` | `Selection` | Yes | `env.user.tz` or `'UTC'` | |
| `cron_id` | `Many2one(ir.cron)` | Yes | — | Auto-created on create; readonly |
| `until` | `Date` | No | — | Hide after this date |
| `mon`–`sun` | `Boolean` | No | Mon–Fri `True` | Day flags |
| `available_today` | `Boolean` | — | — | Computed: today is a flag day AND (`until > today` or null) |
| `active` | `Boolean` | No | `True` | |
| `location_ids` | `Many2many(lunch.location)` | No | — | Restrict to orders at these locations |

### Constraint

```sql
CHECK(notification_time >= 0 AND notification_time <= 12)
```

### Cron Behavior

Crons are activated only for `mode='chat'` alerts. On `unlink()`, both cron and its server action are deleted.

**`_notify_chat()`**: Called daily by cron. Checks `available_today` first; if `until` is past, self-destructs the cron and sets `cron_id=False`. Builds an order domain with `state != 'cancelled'`, optionally filtered by `location_ids` (via `user_id.last_lunch_location_id`) and recipient recency. Sends a single `message_notify` to all matching partner IDs in one call.

| `recipients` | Time window |
|---|---|
| `everyone` | All non-cancelled orders |
| `last_week` | Orders in last 7 days |
| `last_month` | Orders in last 28 days |
| `last_year` | Orders in last 52 weeks |

---

## `res.company` Extensions

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/res_company.py`

| Field | Type | Notes |
|---|---|---|
| `lunch_minimum_threshold` | `Float` | Overdraft buffer; added to wallet balance in `get_wallet_balance()` |
| `lunch_notify_message` | `Html` | Delivery confirmation body; default: `"Your lunch has been delivered. Enjoy your meal!"` |

---

## `res.users` Extensions

**File:** `~/odoo/odoo19/odoo/addons/lunch/models/res_users.py`

| Field | Type | Groups | Notes |
|---|---|---|---|
| `last_lunch_location_id` | `Many2one(lunch.location)` | `lunch.group_lunch_user` | Most recent delivery location; used as default on new orders |
| `favorite_lunch_product_ids` | `Many2many(lunch.product)` | `lunch.group_lunch_user` | Starred products; inverse via `lunch.product.write()` with `is_favorite` toggle |

---

## Security Model

### Groups

| Group | Name | Implied | Notes |
|---|---|---|---|
| `lunch.group_lunch_user` | User: Order your meal | — | Base employee access |
| `lunch.group_lunch_manager` | Administrator | `group_lunch_user` | Inherits all user permissions |

### Access Control (`ir.model.access.csv`)

| Model | User | Manager | Notes |
|---|---|---|---|
| `lunch.cashmove` | Read | Full | Users read-only their own wallet |
| `lunch.order` | Full CRUD | Full CRUD | |
| `lunch.product` | Read | Full | |
| `lunch.product.category` | Read | Full | |
| `lunch.topping` | Read | Full | |
| `lunch.supplier` | Read | Full | |
| `lunch.location` | Read+Create | Full | |
| `lunch.alert` | Read (`base.group_user`) | Full | All authenticated users can read |
| `lunch.cashmove.report` | Read (`base.group_user`) | — | |

### Record Rules

| Rule | Model | Group | Force |
|---|---|---|---|
| Own cash moves only | `lunch.cashmove` | `group_lunch_user` | `[('user_id', '=', user.id)]` |
| All cash moves | `lunch.cashmove` | `group_lunch_manager` | `[(1, '=', 1)]` |
| Delete only `new`/`cancelled` orders | `lunch.order` | `group_lunch_user` | `state in ('new', 'cancelled')` with `perm_unlink=1` |
| Don't edit confirmed orders | `lunch.order` | `base.group_user` | `state != 'confirmed', user_id = user.id` |
| Manager unrestricted | `lunch.order` | `group_lunch_manager` | `[(1, '=', 1)]` |
| Multi-company all models | `lunch.*` | All | `[('company_id', 'in', company_ids + [False])]` |

### Key Security Implications

- Users cannot delete orders in `ordered`, `sent`, or `confirmed` states — enforces immutability after kitchen confirmation.
- Users cannot edit orders in `ordered`, `sent`, `confirmed`, or `cancelled` states (record rule + `state` field `readonly=True`).
- Wallet isolation: each user sees only their own `lunch.cashmove` records via record rule.
- Multi-company rules include `[False]` to allow records with no company assignment (demo data pattern).

---

## Cash Reconciliation Flow

```
Employee deposits money  ->  lunch.cashmove (amount > 0, credit)
                                |
                                v
Employee places order      ->  lunch.order (state: new -> ordered)
                                |
                                v
Order confirmed           ->  lunch.cashmove (amount < 0, debit) [optional manual entry]
                                |
                                v
Wallet balance = sum(cashmoves) + company.lunch_minimum_threshold
```

Orders are priced at creation time; wallet deduction is implicit via balance query. No automatic debit cashmove is created at order confirmation — the manager may manually enter deductions.

---

## Cron-Based Automatic Ordering

Each `lunch.supplier` with `send_by='mail'` and `active=True` has a linked `ir.cron` that triggers `_send_auto_email()` at `automatic_email_time` in the supplier's timezone. The cron is created on supplier creation and deleted on supplier unlink.

**CRON_DEPENDS** (`{'name', 'active', 'send_by', 'automatic_email_time', 'moment', 'tz'}`): Any change to these fields triggers `_sync_cron()` to update the cron nextcall and active state.

Similarly, each `lunch.alert` with `mode='chat'` and `active=True` has a cron for `_notify_chat()`.

---

## Odoo 18 → 19 Changes

- `image.mixin` is now directly inherited by `lunch.product` and `lunch.product.category`.
- `lunch.product.is_available_at` and `_search_is_available_at` restructured for location-filtered product searches.
- `lunch.supplier` and `lunch.alert` cron management uses `Domain` helper objects for cleaner domain construction in `_search_available_today` methods.
- `lunch.supplier._compute_buttons` switched to raw SQL `GROUP BY` — faster than repeated ORM calls per supplier in kanban.
- `lunch.order` gained `display_add_button` field and `_compute_display_add_button` logic for wallet-aware cart validation in kanban views.
- `_user_product_date` composite index added on `lunch.order` for faster `_find_matching_lines` queries.
- `lunch.alert` chat notifications use `mail.thread.message_notify` (via `user.partner_id.message_notify()`).
- `lunch.supplier` and `lunch.alert` `unlink()` methods delete associated `ir.actions.server` records alongside `ir.cron`.

---

## See Also

- [Modules/account](modules/account.md) — Monetary fields, currency
- [Core/API](core/api.md) — `@api.depends`, computed fields
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine design
- [Modules/Stock](modules/stock.md) — Inventory valuation concepts
