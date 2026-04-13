---
Module: membership
Version: Odoo 18
Type: Business
---

# Membership Management (`membership`)

Manages organization membership subscriptions with invoice-based billing. Tracks membership lines linked to `account.move.line` invoices. Differs from [Modules/loyalty](Modules/loyalty.md) in that membership is about recurring paid subscriptions (clubs, associations, NGOs), not point-based reward programs.

**Source path:** `~/odoo/odoo18/odoo/addons/membership/`
**Depends:** `base`, `product`, `account`

---

## Membership States

Defined as a module-level constant `STATE`:

| State | Label | Trigger |
|-------|-------|---------|
| `none` | Non Member | No active membership line; partner not free member |
| `free` | Free Member | `free_member=True` on partner and not currently `paid` |
| `waiting` | Waiting Member | Membership line exists but invoice still in `draft` |
| `invoiced` | Invoiced Member | Invoice posted but not yet paid (`payment_state` not paid/in_payment) |
| `paid` | Paid Member | Invoice posted with `payment_state='paid'` or `'in_payment'` |
| `old` | Old Member | Membership expired, invoice was paid |
| `canceled` | Cancelled Member | Invoice cancelled, or reversed after payment |

---

## Models

### `res.partner` — EXTENDED (membership module)

Extends `res.partner` with membership tracking fields.

```python
class Partner(models.Model):
    _inherit = 'res.partner'
```

| Field | Type | Notes |
|-------|------|-------|
| `associate_member` | M2O `res.partner` | Links to another partner whose membership state is mirrored |
| `member_lines` | O2M `membership.membership_line` | All membership subscription lines for this partner |
| `free_member` | Boolean | Marks partner as free member (bypasses invoice creation) |
| `membership_amount` | Float | Negotiated membership fee |
| `membership_state` | Selection (compute, store, recursive) | Current state across all member lines |
| `membership_start` | Date (compute, store) | Start of current active membership period |
| `membership_stop` | Date (compute, store) | End of current active membership period |
| `membership_cancel` | Date (compute, store) | Date of cancellation |

#### `_compute_membership_state()` Logic

The compute iterates over `member_lines` and applies this priority:

1. **Associate member**: Mirror `associate_member.membership_state` and `continue`
2. **Free member**: If `free_member=True` and state is not `paid` → `state = 'free'`, `continue`
3. **Active period** (today within `[date_from, date_to]`): Set state to `mline.state`
4. **Past period**: If invoice is paid/in_payment → `state = 'old'`; if invoice cancelled → `state = 'canceled'`
5. **Fallback**: No matching line → `state = 'none'`

Also populates:
- `membership_start`: `date_from` of earliest non-cancelled line
- `membership_stop`: `date_to` of latest non-cancelled line
- `membership_cancel`: `date_cancel` of most recent line

#### Key Methods

- `_check_recursion_associate_member()` — `api.constrains` prevents circular `associate_member` chains
- `_cron_update_membership()` — Scheduled action that recomputes `membership_state` for all partners currently in `invoiced` or `paid` state (handles payment receiving while cron runs)
- `create_membership_invoice(product, amount)` — Creates `out_invoice` for each partner with a `membership` product line. Raises `UserError` if partner is a free member or lacks invoice address. Applies product taxes filtered by current company.

---

### `membership.membership_line` — Subscription Line

Represents a membership subscription period. Created automatically when a membership product invoice line is posted.

```python
class MembershipLine(models.Model):
    _name = 'membership.membership_line'
    _rec_name = 'partner'
```

| Field | Type | Notes |
|-------|------|-------|
| `partner` | M2O `res.partner` | Member (required, index, cascade delete) |
| `membership_id` | M2O `product.product` | Membership product (required) |
| `date_from` | Date | Membership start (readonly) |
| `date_to` | Date | Membership end (readonly) |
| `date_cancel` | Date | Cancellation date |
| `date` | Date | Join date |
| `member_price` | Float | Membership fee charged (digits: Product Price) |
| `account_invoice_line` | M2O `account.move.line` | Source invoice line (readonly, cascade) |
| `account_invoice_id` | M2O `account.move` | Related invoice (readonly) |
| `company_id` | M2O | Related from invoice move (readonly, store) |
| `state` | Selection (compute, store) | Derived membership state |

#### `_compute_state()` Logic

Queries `account_move` to find reversal entries, then for each line:

```
invoice.state = 'draft'                     → state = 'waiting'
invoice.state = 'posted' + payment_state = 'paid'     → state = 'paid' (or 'canceled' if reversed)
invoice.state = 'posted' + payment_state = 'in_payment' → state = 'paid'
invoice.state = 'posted' + payment_state in ('not_paid', 'partial') → state = 'invoiced'
invoice.state = 'cancel'                    → state = 'canceled'
```

#### Key Notes

- Line is created by `account.move.line.create()` / `write()` hooks when a product with `membership=True` is invoiced
- `date_from` / `date_to` come from the product's `membership_date_from` / `membership_date_to` fields; overridden to invoice date if the product's fixed dates don't bracket the invoice date

---

### `product.template` — EXTENDED (membership module)

| Field | Type | Notes |
|-------|------|-------|
| `membership` | Boolean | Mark product as membership-eligible |
| `membership_date_from` | Date | Default membership start date |
| `membership_date_to` | Date | Default membership end date |

#### Constraints

- `membership_date_to >= membership_date_from` (SQL CHECK constraint)

---

### `account.move` — EXTENDED (membership module)

| Method | Behavior |
|--------|---------|
| `button_draft()` | Clears `date_cancel` on related membership lines (uncancel) |
| `button_cancel()` | Sets `date_cancel = today` on related membership lines |
| `write()` | Syncs `partner_id` change to related membership lines |

On cancel: membership lines are not deleted — `date_cancel` is set, which causes `_compute_membership_state` on partner to exclude that line from active period checks.

---

### `account.move.line` — EXTENDED (membership module)

This is the core integration point. The `create()` and `write()` hooks on invoice lines auto-create `membership.membership_line` records.

#### `create()` / `write()` Logic

Triggered when a line's `move_id.move_type == 'out_invoice'` and `product_id.membership == True`:

1. Check if membership line already exists for this invoice line
2. If not, compute `date_from` / `date_to` from product:
   - If `membership_date_from < invoice_date < membership_date_to` → use `invoice_date` as effective start
3. Create `membership.membership_line` with `partner`, `membership_id`, `member_price`, `date`, `date_from`, `date_to`, `account_invoice_line`

---

## L4: Membership vs. Loyalty — Key Differences

| Aspect | Membership | Loyalty |
|--------|-----------|---------|
| **Purpose** | Club/association subscriptions | Point-based customer rewards |
| **Points** | No points system | Points accumulate and are redeemed |
| **Billing** | Invoice-based (creates `account.move`) | No invoices; points computed at order |
| **Card** | No physical/digital card | `loyalty.card` with code and balance |
| **Expiration** | Fixed date period (`date_from`/`date_to`) | Cards may have `expiration_date` |
| **Programs** | Single membership product per partner | Multiple programs with rules and rewards |
| **State transitions** | Driven by invoice payment state | Driven by order placement and coupon use |

---

## L4: Membership Renewal Flow

```
1. Partner selects membership product
2. create_membership_invoice() creates out_invoice
   └─ invoice in 'draft' state → membership_line.state = 'waiting'
3. Invoice posted → membership_line.state = 'invoiced' (payment pending)
4. Payment received → membership_line.state = 'paid'
   └─ Cron _cron_update_membership() picks up state change
5. Membership expires (date_to passed):
   └─ _compute_membership_state: no line with today in [from,to]
   └─ if last line had paid invoice → state = 'old'
6. Next renewal: steps 1-5 repeat, new membership_line created
```

**Cancellation flow:**
```
Invoice cancelled → button_cancel()
  └─ date_cancel = today
  └─ membership_line.state = 'canceled'
  └─ partner.membership_state = 'canceled'
```

**Credit/Refund reversal:**
```
Invoice reversed (reversed_entry_id) → payment_state check sees reversal
  └─ membership_line.state = 'canceled'
```

---

## L4: How `invoice_line` Creates `membership_line`

The integration is entirely in `account.move.line`:

```python
# account.move.line write/create hook
to_process = lines.filtered(
    lambda line: line.move_id.move_type == 'out_invoice'
                and line.product_id.membership
)
# Exclude already-linked lines
existing = self.env['membership.membership_line'].search([
    ('account_invoice_line', 'in', to_process.ids)])
to_process = to_process - existing_memberships.mapped('account_invoice_line')
# Create membership_line for remaining lines
memberships_vals.append({
    'partner': line.move_id.partner_id.id,
    'membership_id': line.product_id.id,
    'member_price': line.price_unit,
    'date': fields.Date.today(),
    'date_from': date_from,   # from product or invoice_date
    'date_to': date_to,       # from product
    'account_invoice_line': line.id,
})
```

The `membership_line.state` is then a **computed reflection** of the invoice state — no direct writes to `membership_line` are needed after creation.

---

## L4: `associate_member` — Shared Membership

A partner can set `associate_member` to point to another partner. The `_compute_membership_state()` method then mirrors the associated member's state, so a household or corporate membership can share a single paid membership line. The constraint `_check_recursion_associate_member` prevents circular references.

---

## Tags

#membership #odoo18 #business #subscription #invoice #association
