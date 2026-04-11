---
Module: lunch
Version: Odoo 18
Type: Business
Tags: #odoo, #odoo18, #lunch, #catering, #employee-services, #workflow
---

# lunch — Employee Lunch Management

Employees order lunch from configured vendors (suppliers). The lunch manager approves and sends aggregated orders to vendors. Supports extras/toppings, wallet-based payment, vendor-specific delivery schedules, and chat/alert notifications.

> **Technical depth:** L4 (fully read from source)
> **Source:** `~/odoo/odoo18/odoo/addons/lunch/models/`

---

## Architecture Overview

```
lunch.supplier (vendors)
    1:N lunch.product (via supplier_id)
            N:N res.users (via favorite_user_ids)
    1:N lunch.topping (topping_ids_1/2/3)

lunch.product.category (e.g., Pizza, Sushi, Sandwiches)
    1:N lunch.product (via category_id)

lunch.order (employee orders)
    N:1 lunch.product (product_id)
    N:1 lunch.supplier (supplier_id, via product)
    N:1 lunch.location (lunch_location_id)
    N:N lunch.topping (via topping_ids_1/2/3)
    N:1 res.users (user_id)
    N:1 res.company (company_id)

lunch.cashmove (wallet debits/credits)
    N:1 res.users (user_id)

lunch.alert (notifications)
    N:N lunch.location (location_ids)

lunch.location (delivery sites)
    N:N lunch.supplier (available_location_ids)
    N:N lunch.alert (location_ids)
```

**Order state machine:**
```
new → ordered → sent → confirmed
                ↘ cancelled ↙
```

**Wallet model:** `lunch.cashmove` records act as a wallet. `get_wallet_balance()` sums all cashmoves + company `lunch_minimum_threshold` (free credit). Orders debit the wallet; managers/top-ups credit it.

---

## lunch.supplier

Vendor/restaurant that delivers lunch. Each supplier has a cron-scheduled email that sends the day's aggregated orders. Supports AM/PM ordering windows, per-day availability, and location restrictions.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `partner_id` | Many2one res.partner | Vendor company contact |
| `name` | Char (related) | Mirrors `partner_id.name` |
| `email` | Char (related) | Vendor email |
| `email_formatted` | Char (related) | Formatted email for mail composer |
| `phone` | Char (related) | Vendor phone |
| `street`, `street2`, `zip_code`, `city`, `state_id`, `country_id` | Address fields (related) | Vendor address |
| `responsible_id` | Many2one res.users | Person who sends orders and receives confirmations |
| `send_by` | Selection | `phone` or `mail` |
| `automatic_email_time` | Float | Hour to send email (0–12, validated) |
| `moment` | Selection | `am` or `pm` — used with `automatic_email_time` |
| `tz` | Selection | Timezone for scheduling (required, default: `UTC` or user tz) |
| `cron_id` | Many2one ir.cron | Auto-created daily cron for `_send_auto_email()` |
| `active` | Boolean | Archive/unarchive cascades to products |
| `mon`–`sun` | Boolean | Per-day availability (default: Mon–Fri True) |
| `recurrency_end_date` | Date | End date for recurring availability |
| `available_location_ids` | Many2many lunch.location | Locations this vendor delivers to |
| `available_today` | Boolean (computed) | Is vendor open today? |
| `order_deadline_passed` | Boolean (computed) | Has the ordering window closed today? |
| `delivery` | Selection | `delivery` or `no_delivery` |
| `topping_label_1/2/3` | Char | Labels for the three topping groups |
| `topping_ids_1/2/3` | One2many lunch.topping | Available extras per group |
| `topping_quantity_1/2/3` | Selection | `0_more` (optional), `1_more` (required ≥1), `1` (exactly one) |
| `show_order_button` | Boolean (computed) | Any `ordered` state orders today? |
| `show_confirm_button` | Boolean (computed) | Any `sent` state orders today? |
| `company_id` | Many2one res.company | Related to `partner_id.company_id` |

### SQL Constraints

```python
('automatic_email_time_range',
 'CHECK(automatic_email_time >= 0 AND automatic_email_time <= 12)',
 'Automatic Email Sending Time should be between 0 and 12')
```

### Key Methods

#### `_sync_cron()`
Dynamically synchronizes the companion `ir.cron` record whenever supplier fields change (`CRON_DEPENDS = {name, active, send_by, automatic_email_time, moment, tz}`).

**Cron behavior:**
- `active = supplier.active AND supplier.send_by == 'mail'`
- `nextcall` computed from `automatic_email_time` + `moment` + `tz`, in the supplier's timezone, then converted to UTC
- `code`: `env['lunch.supplier'].browse([id])._send_auto_email()`
- If the computed send time has already passed today, schedules for tomorrow

#### `_available_on_date(date)`
```python
def _available_on_date(self, date):
    fieldname = WEEKDAY_TO_NAME[date.weekday()]
    return not (self.recurrency_end_date and date.date() >= self.recurrency_end_date) and self[fieldname]
```
Checks: today is not past `recurrency_end_date` AND today's boolean flag is True.

#### `_get_current_orders(state='ordered')`
Searches `lunch.order` for today (in supplier timezone) with the given state. Returns orders sorted by `user_id, product_id`.

#### `_send_auto_email()`
Called by cron. Sends the day's aggregated order to the vendor.
1. Checks `available_today` and `send_by == 'mail'`
2. Fetches orders via `_get_current_orders()`
3. Groups by delivery location
4. Renders `lunch.lunch_order_mail_supplier` QWeb email template with per-line details (product, toppings, username, location, price)
5. Sends via `send_mail()` with `email_from = responsible_id.email_formatted`
6. Calls `orders.action_send()` → sets state to `sent`

#### `action_send_orders()`
Manual trigger for sending orders. For `send_by='mail'` suppliers: calls `_send_auto_email()`. For `send_by='phone'`: just calls `action_send()` on orders (no email). Shows success notification.

#### `action_confirm_orders()`
Called when vendor confirms delivery. Fetches all `sent` orders for today and calls `action_confirm()` → state=`confirmed`.

#### `toggle_active()`
When archiving a supplier: sets all related `lunch.product` records to `active=False`. When unarchiving: sets them to `active=True`.

---

## lunch.product

Individual menu items available for ordering. Products are always linked to exactly one `lunch.supplier` and one `lunch.product.category`.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Product name (translate) |
| `category_id` | Many2one lunch.product.category |  |
| `description` | Html | Product description |
| `price` | Float | Unit price (digits: Account) |
| `supplier_id` | Many2one lunch.supplier |  |
| `active` | Boolean | |
| `company_id` | Many2one (related, readonly=False) | Via `supplier_id.company_id` |
| `currency_id` | Many2one (related) | Via `company_id.currency_id` |
| `new_until` | Date | Product is marked `is_new` until this date |
| `is_new` | Boolean (computed) | `new_until >= today` |
| `favorite_user_ids` | Many2many res.users | Users who favorited this product |
| `is_favorite` | Boolean (computed/inverse) | Current user is in `favorite_user_ids` |
| `last_order_date` | Date (computed) | When current user last ordered this product |
| `product_image` | Image (computed) | `image_128` or falls back to `category_id.image_128` |
| `is_available_at` | Many2one lunch.location (computed/search) | Search-only field for filtering products by location |

### Key Methods

#### `_search_is_available_at(operator, value)`
Enables searching products by delivery location:
- `operator in` → `supplier_id.available_location_ids` contains value (or has no restriction)
- `operator not in` → `supplier_id.available_location_ids` does not contain value (and has some restriction)

#### `toggle_active()`
Constrained `toggle_active`: prevents archiving a product whose `category_id` is active but whose `supplier_id` is inactive, and vice versa. Raises `UserError` listing invalid categories/suppliers.

#### `_sync_active_from_related()`
Called by `lunch.product.category.toggle_active()`. Archives/unarchives products when their parent category or supplier is toggled.

---

## lunch.product.category

Product category (e.g., Pizza, Sushi, Sandwiches, Salad). Each category has an icon image shown in the lunch dashboard.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Category name (translate) |
| `company_id` | Many2one res.company |  |
| `currency_id` | Many2one (related) |  |
| `product_count` | Integer (computed) | Count of products in this category |
| `active` | Boolean | |
| `image_1920` | Image | Category icon (default: `lunch/static/img/lunch.png`) |

### `toggle_active()`
Syncs active state to all products via `_sync_active_from_related()`.

---

## lunch.order

Individual employee lunch line items. One record per product per order. Supports toppings/extras, quantity adjustments, and automatic merging of identical lines.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `product_id` | Many2one lunch.product |  |
| `category_id` | Many2one (related, stored) | Mirrors `product_id.category_id` |
| `supplier_id` | Many2one (related, stored) | Mirrors `product_id.supplier_id` |
| `date` | Date | Order date (default: today) |
| `user_id` | Many2one res.users | Ordering employee (default: current user) |
| `lunch_location_id` | Many2one lunch.location | Delivery location (default: `user.last_lunch_location_id`) |
| `note` | Text | Special instructions for this line |
| `quantity` | Float | Unit count (default: 1) |
| `price` | Monetary (computed, stored) | `quantity * (product.price + sum(topping prices))` |
| `state` | Selection | `new`, `ordered`, `sent`, `confirmed`, `cancelled` |
| `topping_ids_1/2/3` | Many2many lunch.topping | Extras (via `lunch_order_topping` relation table) |
| `available_today` | Boolean (related) | `supplier_id.available_today` |
| `available_on_date` | Boolean (computed) | `supplier_id._available_on_date(date)` |
| `order_deadline_passed` | Boolean (computed) | `supplier_id.order_deadline_passed` |
| `display_toppings` | Text (computed, stored) | Concatenated topping names |
| `display_add_button` | Boolean (computed) | Can current user add another order? (wallet balance check) |
| `display_reorder_button` | Boolean (computed) | Show reorder button? (state=confirmed, supplier available today) |
| `available_toppings_1/2/3` | Boolean (computed) | Does this product's supplier have toppings in each group? |
| `active` | Boolean | Allows soft-delete |
| `notified` | Boolean | Has `action_notify()` been called? |
| `company_id` | Many2one res.company |  |
| `currency_id` | Many2one (related) |  |
| `new_until` | Date (related) |  |
| `image_1920` / `image_128` | Image (computed) | Product or category image |
| `product_description` | Html (related) |  |
| `topping_label_1/2/3` | Char (related) |  |
| `topping_quantity_1/2/3` | Selection (related) |  |

### State Machine

```
new ──────→ ordered ────→ sent ────→ confirmed
  │                           │
  └───────── cancelled ◀──────┘
```

| State | Meaning | Transition |
|-------|---------|-----------|
| `new` | In cart, not yet submitted | `action_order()` |
| `ordered` | Submitted, waiting to be sent to vendor | `action_send()` |
| `sent` | Emailed/called to vendor | `action_confirm()` |
| `confirmed` | Received/delivered | — |
| `cancelled` | Cancelled by user or auto (vendor unavailable) | — |

### Key Methods

#### `_find_matching_lines(values)`
Searches for an existing `new` state order with identical: `user_id`, `product_id`, `date`, `note`, `lunch_location_id`, AND toppings. Used by `create()` and `write()` to merge duplicate orders.

#### `create(vals_list)`
Smart creation: if an identical `new` order exists for the same user/product/date/toppings, increments quantity of that order instead of creating a new record. Avoids duplicate lines when employee clicks "Add" twice.

#### `write(values)`
Smart merge on topping/quantity changes: if editing an order and the new toppings match an existing `new` order, deactivates the current one and increments the existing one.

#### `update_quantity(increment)`
Adjusts quantity. If resulting quantity ≤ 0: soft-deletes (`active=False`). Then calls `_check_wallet()` to verify balance not negative.

#### `_check_wallet()`
After every state change, verifies `get_wallet_balance(user) >= 0`. Raises `ValidationError` if wallet is negative.

#### `action_order()`
Validates vendor availability on date and product is active. Sets state to `ordered`. Calls `_check_wallet()`.

#### `action_reorder()`
Creates a copy of a `confirmed` order with today's date and `state='ordered'`. Only allowed if `supplier_id.available_today`.

#### `action_cancel()`
Sets state to `cancelled`.

#### `action_reset()`
Resets `cancelled` orders back to `ordered`.

#### `action_send()`
Sets state to `sent`. Called by `_send_auto_email()` cron or `action_send_orders()`.

#### `action_confirm()`
Sets state to `confirmed`. Called by `action_confirm_orders()` when vendor confirms delivery.

#### `action_notify()`
Sends a mail.notification to each user who has an order in the set. Uses `partner_id.message_notify()` with the company's `lunch_notify_message` as body. Translates per-user language. Skips already-notified orders.

### Constraints

```python
@api.constrains('topping_ids_1', 'topping_ids_2', 'topping_ids_3')
def _check_topping_quantity(self):
    # If topping_quantity_X is '1': must have exactly one topping
    # If topping_quantity_X is '1_more': must have at least one topping
    # If topping_quantity_X is '0_more': optional
```

---

## lunch.topping

Extra items/add-ons for products (e.g., Extras, Beverages). Three independent topping groups per supplier.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Topping name |
| `company_id` | Many2one res.company |  |
| `currency_id` | Many2one (related) |  |
| `price` | Monetary | Price of this extra |
| `supplier_id` | Many2one lunch.supplier | Parent vendor |
| `topping_category` | Integer | 1, 2, or 3 (determines which topping_ids_X field it belongs to) |

### Display Name

Computed as `"{name} {formatted_price}"` using the company's currency.

---

## lunch.cashmove

Wallet transactions: positive = credit (top-up), negative = debit (order). Used to track employee lunch balance.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `currency_id` | Many2one res.currency |  |
| `user_id` | Many2one res.users |  |
| `date` | Date |  |
| `amount` | Float | Positive (credit) or negative (debit) |
| `description` | Text | Reason for the transaction |

### Key Methods

#### `get_wallet_balance(user, include_config=True)`
Sums all `lunch.cashmove.report` amounts for the user. Adds `user.company_id.lunch_minimum_threshold` as free credit if `include_config=True`.

The actual report is a separate model (`lunch.cashmove.report`) — this is a read-through for reporting.

---

## lunch.location

Delivery/pickup locations where employees eat lunch.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Location name (e.g., "Building A — Floor 3") |
| `address` | Text | Delivery address |
| `company_id` | Many2one res.company |  |

Used by:
- `lunch.supplier.available_location_ids` — restricts which vendors deliver where
- `lunch.alert.location_ids` — restricts alerts to specific locations
- `lunch.order.lunch_location_id` — where to deliver an order
- `res.users.last_lunch_location_id` — user's default location

---

## lunch.alert

In-app or chat notifications shown to employees during the lunch ordering window.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Alert title |
| `message` | Html | Notification body |
| `mode` | Selection | `alert` (in-app banner) or `chat` (mail.thread notification) |
| `recipients` | Selection | `everyone`, `last_week`, `last_month`, `last_year` (based on who ordered) |
| `notification_time` | Float | Hour to send chat notification (0–12) |
| `notification_moment` | Selection | `am` or `pm` |
| `tz` | Selection | Timezone for notification scheduling |
| `cron_id` | Many2one ir.cron | Auto-created cron for `_notify_chat()` |
| `until` | Date | Alert expires after this date |
| `mon`–`sun` | Boolean | Days the alert is active |
| `available_today` | Boolean (computed) | Is alert active today? |
| `active` | Boolean | |
| `location_ids` | Many2many lunch.location | Restrict alert to specific locations |

### SQL Constraints

```python
('notification_time_range',
 'CHECK(notification_time >= 0 and notification_time <= 12)',
 'Notification time must be between 0 and 12')
```

### Key Methods

#### `_notify_chat()`
Called by cron for `mode='chat'` alerts. Logic:
1. If `not available_today`: log warning; if `until` passed, delete cron and unset `cron_id`
2. Builds `order_domain`: state != 'cancelled'
3. If `location_ids` set: filter by `user_id.last_lunch_location_id in location_ids`
4. If recipients != 'everyone': filter to users who ordered in last 1/4/52 weeks
5. `message_notify()` to all matched users via `mail.thread`

---

## L4: Order Aggregation and Vendor Delivery

### Daily Order Flow

```
Employee creates lunch.order (state=new)
    → _find_matching_lines() checks for duplicates
    → create(): if duplicate exists, update_quantity(1) instead of new record
    → _check_wallet(): wallet balance must stay >= 0

Employee calls action_order() (state=new → ordered)
    → Validates: available_on_date, product.active
    → _check_wallet(): re-validate

Lunch Manager calls action_send_orders() OR cron fires _send_auto_email()
    → _get_current_orders(state='ordered')
    → Groups orders by supplier
    → For each mail supplier: renders email template, sends
    → For each phone supplier: marks orders sent
    → action_send(): state = 'sent'

Vendor confirms → Lunch Manager calls action_confirm_orders()
    → action_confirm(): state = 'confirmed'
    → Employees see confirmed orders in dashboard
```

### Email Aggregation per Supplier

The email sent via `lunch_order_mail_supplier` template contains:

```python
order = {
    'company_name': orders[0].company_id.name,
    'currency_id': orders[0].currency_id.id,
    'supplier_id': self.partner_id.id,
    'supplier_name': self.name,
    'email_from': self.responsible_id.email_formatted,
    'amount_total': sum(order.price for order in orders),
}

# Grouped by delivery location
sites = orders.mapped('user_id.last_lunch_location_id').sorted()
email_orders = [{
    'product': order.product_id.name,
    'note': order.note,
    'quantity': order.quantity,
    'price': order.price,
    'toppings': order.display_toppings,  # " + " joined topping names
    'username': order.user_id.name,
    'site': order.user_id.last_lunch_location_id.name,
} for order in orders]
```

### Wallet Balance Check

```
get_wallet_balance(user) = sum(cashmove.amount) + company.lunch_minimum_threshold

Before action_order():
  price = quantity * (product.price + sum(toppings))
  wallet - price >= 0  ← raises ValidationError if not
```

### Topping Validation

Each supplier defines 3 topping groups. Each group has:
- A label (e.g., "Extras", "Beverages", "Sauces")
- A quantity rule: `'0_more'` (optional), `'1_more'` (at least one), `'1'` (exactly one)
- A set of `lunch.topping` records

When an order is placed, `_check_topping_quantity()` validates all three groups against the rule.

---

## Relationships Summary

```
lunch.supplier
    1:N lunch.product (supplier_id)
    1:N lunch.topping (topping_ids_1/2/3 via supplier_id)
    N:N lunch.location (available_location_ids)
    1:N lunch.order (supplier_id via product)
    1:1 ir.cron (cron_id)

lunch.product
    N:1 lunch.supplier
    N:1 lunch.product.category
    N:N res.users (favorite_user_ids)

lunch.product.category
    1:N lunch.product

lunch.order
    N:1 lunch.product
    N:1 lunch.supplier
    N:1 lunch.product.category
    N:1 lunch.location (lunch_location_id)
    N:1 res.users (user_id)
    N:1 res.company
    N:N lunch.topping (topping_ids_1/2/3)

lunch.topping
    N:1 lunch.supplier

lunch.cashmove
    N:1 res.users

lunch.alert
    N:N lunch.location (location_ids)
    1:1 ir.cron

lunch.location
    1:N lunch.order
    N:N lunch.supplier
    N:N lunch.alert
```
