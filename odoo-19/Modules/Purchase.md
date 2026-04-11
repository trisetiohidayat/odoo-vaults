---
title: Purchase Module
category: Supply Chain/Purchase
module_key: purchase
depends:
  - account
version: "1.2"
author: Odoo S.A.
license: LGPL-3
summary: Purchase orders, tenders and agreements
website: https://www.odoo.com/app/purchase
tags: [odoo, odoo19, modules, supply-chain, purchasing, invoicing]
---

# Purchase Module (`purchase`)

**Path:** `odoo/addons/purchase/`
**Manifest:** `purchase/__manifest__.py` (version 1.2)
**Depends:** `account` only — the purchase module is deliberately minimal at its core

The `purchase` module is Odoo's core purchasing management system. It manages the full procurement lifecycle from Request for Quotation (RFQ) through Purchase Order (PO) confirmation to vendor bill processing. It is the bridge between procurement and accounting.

---

## Module Inventory

### Models
| Model | File | Purpose |
|---|---|---|
| `purchase.order` | `models/purchase_order.py` | RFQ and PO header |
| `purchase.order.line` | `models/purchase_order_line.py` | Per-product/order line |
| `purchase.bill.line.match` | `models/purchase_bill_line_match.py` | Read-only union view: unmatched PO lines vs. unmatched vendor bill lines |
| `product.supplierinfo` | `models/product.py` | Vendor price lists (inherited from base product) |
| `product.template` | `models/product.py` | Purchase-specific fields on product templates |
| `product.product` | `models/product.py` | Purchase-specific fields on variants |
| `res.partner` | `models/res_partner.py` | Vendor-specific fields on partner |
| `account.move` | `models/account_invoice.py` | Vendor bill extension with PO linking and auto-matching |
| `account.move.line` | `models/account_invoice.py` | PO-to-bill line linking field |
| `account.tax` | `models/account_tax.py` | Tax usage tracking for PO lines |
| `res.company` | `models/res_company.py` | PO lock and approval workflow settings |
| `account.analytic.account` | `models/analytic_account.py` | Purchase order count on analytic accounts |
| `account.analytic.applicability` | `models/analytic_applicability.py` | Analytic applicability for purchase orders |
| `bill.to.po.wizard` | `wizard/bill_to_po_wizard.py` | Convert vendor bill lines to PO lines or downpayments |

### Security Groups
| Group | XML ID | Implied from | Key Rights |
|---|---|---|---|
| `group_purchase_user` | `purchase.group_purchase_user` | `base.group_user` | Read/create POs, vendor bills, purchase warnings |
| `group_purchase_manager` | `purchase.group_purchase_manager` | `group_purchase_user` | Unlock POs, full control |
| `group_warning_purchase` | `purchase.group_warning_purchase` | — | See purchase warnings on products/partners |
| `group_send_reminder` | `purchase.group_send_reminder` | `base.group_user` | Send receipt reminder emails |

### State Machine: `purchase.order`

```
draft (RFQ)
    └─→ sent (RFQ Sent)          [via print_quotation() or message_post with mark_rfq_as_sent]
           └─→ to approve (To Approve)  [double validation: amount >= threshold, not manager]
                  └─→ purchase (Purchase Order)  [via button_approve()]
                         └─→ cancel (Cancelled)  [locked POs must be unlocked first]
```

- **`draft`**: Initial state. RFQ being prepared.
- **`sent`**: RFQ sent to vendor; set automatically by `message_post` with `mark_rfq_as_sent` context.
- **`to approve`**: Reached when `po_double_validation == 'two_step'` and amount exceeds threshold.
- **`purchase`**: Confirmed PO. Sets `date_approve = now`. Locks automatically if `company_id.po_lock == 'lock'`.
- **`cancel`**: Cannot cancel if PO is locked or has any non-cancelled/non-draft vendor bills.

---

## `purchase.order`

**File:** `models/purchase_order.py`
**Inherits:** `portal.mixin`, `product.catalog.mixin`, `mail.thread`, `mail.activity.mixin`, `account.document.import.mixin`

### L1: All Field Signatures

```python
# Identification
name = fields.Char('Order Reference', required=True, index='trigram',
                   copy=False, default='New')
priority = fields.Selection([('0', 'Normal'), ('1', 'Urgent')],
                            'Priority', default='0', index=True)
origin = fields.Char('Source', copy=False)
    # Reference of the document that generated this PO (e.g., sale order name)
partner_ref = fields.Char('Vendor Reference', copy=False)
    # Vendor's own PO reference; used for matching incoming vendor bills

# Dates
date_order = fields.Datetime('Order Deadline', required=True, index=True, copy=False,
                             default=fields.Datetime.now)
date_approve = fields.Datetime('Confirmation Date', readonly=True, index=True, copy=False)

# Parties
partner_id = fields.Many2one('res.partner', string='Vendor', required=True,
                              change_default=True, check_company=True, index=True)
dest_address_id = fields.Many2one('res.partner', check_company=True, string='Dropship Address')
user_id = fields.Many2one('res.users', string='Buyer', index=True, tracking=True,
                          default=lambda self: self.env.user, check_company=True)

# Financial
currency_id = fields.Many2one('res.currency', required=True,
                              compute='_compute_currency_id', store=True,
                              readonly=False, precompute=True)
currency_rate = fields.Float(string="Currency Rate",
                             compute='_compute_currency_rate',
                             digits=0, store=True, precompute=True)
amount_untaxed = fields.Monetary(store=True, readonly=True,
                                 compute='_amount_all', tracking=True)
amount_tax = fields.Monetary(store=True, readonly=True, compute='_amount_all')
amount_total = fields.Monetary(store=True, readonly=True, compute='_amount_all')
amount_total_cc = fields.Monetary(string="Total in currency",
                                  store=True, readonly=True, compute="_amount_all",
                                  currency_field="company_currency_id")
tax_totals = fields.Binary(compute='_compute_tax_totals', exportable=False)

# Terms
fiscal_position_id = fields.Many2one('account.fiscal.position')
tax_country_id = fields.Many2one('res.country', compute='_compute_tax_country_id',
                                 compute_sudo=True)
tax_calculation_rounding_method = fields.Selection(
    related='company_id.tax_calculation_rounding_method', readonly=True)
payment_term_id = fields.Many2one('account.payment.term')
incoterm_id = fields.Many2one('account.incoterms')
note = fields.Html('Terms and Conditions')

# Lines
order_line = fields.One2many('purchase.order.line', 'order_id',
                              string='Order Lines', copy=True)

# Status
state = fields.Selection([
    ('draft', 'RFQ'), ('sent', 'RFQ Sent'),
    ('to approve', 'To Approve'), ('purchase', 'Purchase Order'),
    ('cancel', 'Cancelled')
], string='Status', readonly=True, index=True, copy=False,
   default='draft', tracking=True)
locked = fields.Boolean(help="Locked POs cannot be modified.",
                        default=False, copy=False, tracking=True)
lock_confirmed_po = fields.Selection(related="company_id.po_lock")
invoice_status = fields.Selection([
    ('no', 'Nothing to Bill'), ('to invoice', 'Waiting Bills'),
    ('invoiced', 'Fully Billed')
], string='Billing Status', compute='_get_invoiced', store=True,
   readonly=True, copy=False, default='no')
invoice_count = fields.Integer(compute="_compute_invoice", string='Bill Count',
                               copy=False, default=0, store=True)
invoice_ids = fields.Many2many('account.move', compute="_compute_invoice",
                               string='Bills', copy=False, store=True)

# Scheduling
date_planned = fields.Datetime(string='Expected Arrival', index=True, copy=False,
                                compute='_compute_date_planned', store=True, readonly=False)
date_calendar_start = fields.Datetime(compute='_compute_date_calendar_start',
                                       readonly=True, store=True)

# Vendor acknowledgment and reminders
acknowledged = fields.Boolean('Acknowledged', copy=False, tracking=True)
receipt_reminder_email = fields.Boolean(compute='_compute_receipt_reminder_email',
                                        store=True, readonly=False)
reminder_date_before_receipt = fields.Integer(compute='_compute_receipt_reminder_email',
                                               store=True, readonly=False)

# Company and currency
company_id = fields.Many2one('res.company', 'Company', required=True,
                             index=True, default=lambda self: self.env.company.id)
company_currency_id = fields.Many2one(related="company_id.currency_id")
country_code = fields.Char(related='company_id.account_fiscal_country_id.code')
company_price_include = fields.Selection(related='company_id.account_price_include')

# Duplicates and warnings
duplicated_order_ids = fields.Many2many(comodel_name='purchase.order',
                                        compute='_compute_duplicated_order_ids')
is_late = fields.Boolean('Is Late', search='_search_is_late')
show_comparison = fields.Boolean(compute='_compute_show_comparison')
purchase_warning_text = fields.Text(compute='_compute_purchase_warning_text')

# Related shortcuts
partner_bill_count = fields.Integer(related='partner_id.supplier_invoice_count')
product_id = fields.Many2one('product.product', related='order_line.product_id',
                              string='Product')
```

### L2: Field Types, Defaults, Constraints

#### `name` — Sequence-based reference
- **Default:** `'New'` — triggers `ir.sequence.next_by_code('purchase.order')` on `create()`
- **Sequence date:** `date_order` timestamp; falls back to current time
- **Index:** Trigram (fast `ilike` search across all POs)
- Sequence code is `'purchase.order'` — customize via `ir.sequence` for company-specific numbering

#### `date_order` — Order Deadline / RFQ validity date
- Stored as UTC `Datetime`
- Dual purpose: (1) RFQ validity deadline displayed in email subtitle for drafts/sent, (2) the date used for `seller` price/validity lookup in PO lines
- In calendar view, `date_calendar_start` uses `date_approve` (if confirmed) else `date_order`

#### `currency_id` — Vendor's trading currency
- **Compute:** `_compute_currency_id` with cascade: `partner_id.property_purchase_currency_id` → `company_id.currency_id`
- **Precompute:** Set on create before other computations run — prevents currency-dependent cascades on new records
- **Onchange:** Changing `partner_id` via `onchange_partner_id()` triggers recompute
- `property_purchase_currency_id` on `res.partner` is company-dependent; allows different currencies per company for the same vendor

#### `locked` — Post-confirmation edit lock
- Set automatically by `button_approve()` when `lock_confirmed_po == 'lock'`
- Manually toggled via `button_lock()` / `button_unlock()`
- A locked PO cannot be cancelled without explicit unlock via `button_unlock()`
- Locked PO lines cannot be deleted

#### `date_planned` — Earliest expected delivery
- **Compute:** `_compute_date_planned` — `min()` of all non-display-type line `date_planned` values; recomputed and stored on any line change
- **Onchange:** Changing PO-level `date_planned` propagates to all lines via `onchange_date_planned()`
- **Loop prevention:** The `onchange()` override strips `date_planned` from line-value diffs when the PO-level field change triggered the onchange, preventing oscillation

#### `currency_rate` — Live conversion rate
- **Compute:** `_compute_currency_rate` calls `res.currency._get_conversion_rate()` from company currency to PO currency as of `date_order`
- **Precompute:** Set on create; stored
- **Purpose:** `amount_total_cc = amount_total / currency_rate` provides the company-currency equivalent

#### `invoice_status` — Three-state billing indicator
| State | Condition |
|---|---|
| `no` | `state != 'purchase'`, OR all lines have `qty_to_invoice == 0` and no `invoice_ids` |
| `to invoice` | `state == 'purchase'` AND any line has `qty_to_invoice != 0` |
| `invoiced` | All lines have `qty_to_invoice == 0` AND `invoice_ids` exists |

Uses `float_is_zero` with `'Product Unit'` precision. Stored; recomputed on `state` or `qty_to_invoice` change.

#### `amount_untaxed / amount_tax / amount_total` — Tax totals
- Excludes `display_type` lines (sections, notes)
- Uses `AccountTax._get_tax_totals_summary()` on base lines, which calls `_round_base_lines_tax_details()`
- `amount_total_cc` only differs from `amount_total` when PO currency ≠ company currency

### L3: Cross-Model Relationships and Computed Logic

#### Vendor price resolution on line creation
When a PO line is created with a `product_id`, the system resolves pricing via `_select_seller()`:
1. Matches `product_id.seller_ids` on `partner_id`, `product_id` (or no product for template-level sellers), date range
2. Selects by `min_qty` threshold — best seller is the one with lowest `min_qty` that is still ≤ `product_qty`
3. Price taken from `seller.price`, adjusted for tax inclusion via `_fix_tax_included_price_company()`
4. Converted from seller's currency to PO currency at `date_order` rate
5. Rounded to max(PO currency decimal places, 'Product Price' precision)
6. `technical_price_unit` set equal to `price_unit` — this sentinel prevents re-overwriting a manually-set price

#### `button_confirm()` — Confirmation gate
```python
def button_confirm(order):
    # 1. Validate: all non-downpayment lines have a product_id
    # 2. Validate analytic distribution on all lines
    # 3. Add vendor to product's supplierinfo if not already present (up to 10 sellers)
    # 4. Check approval:
    if _approval_allowed():
        button_approve()       # state → 'purchase', sets date_approve, locks if configured
    else:
        write({'state': 'to approve'})   # requires manager approval
```

#### `_approval_allowed()` — Double validation gate
```
one_step mode:              always True
two_step + amount < threshold: True (any buyer)
two_step + amount >= threshold: requires group_purchase_manager
```
Threshold (`po_double_validation_amount`) is converted from company currency to PO currency at `date_order` rate.

#### PO-to-vendor-bill linking
- `invoice_ids`: computed from `order_line.invoice_lines.move_id` (all invoices containing any PO line)
- Each `purchase.order.line` links to `account.move.line` via `purchase_line_id` Many2one on `account.move.line`
- `action_create_invoice()` batches invoice creation by `(company_id, partner_id, currency_id)` — multiple POs to the same vendor in the same currency produce a single invoice

#### Duplicate order detection (raw SQL)
`_fetch_duplicate_orders()` executes raw SQL to find draft POs sharing: same `company_id`, same `partner_id`, and matching `origin`/`partner_ref`. Runs at create/write time. Uses `array_agg` and a self-join — efficient for datasets where duplicate detection is needed.

#### Downpayment flow
Downpayment sections created with `is_downpayment=True`, `display_type='line_section'`. Child lines carry `is_downpayment=True`. They are excluded from the "missing product" validation. When generating invoice lines, their `display_type` is reset to `'product'` so they appear correctly on the bill.

#### Receipt reminder system
- `receipt_reminder_email` and `reminder_date_before_receipt` are computed from `partner_id` company-dependent fields
- A scheduled action (cron) calls `_send_reminder_mail()` which finds POs where `(date_planned - reminder_date_before_receipt).date() == today`
- `_get_orders_to_remind()` excludes purely-service product POs

#### Dashboard: `retrieve_dashboard()`
- Computes counts for: draft, sent, late (date_order < now), not acknowledged, late receipt
- `days_to_order` = average `(date_approve - create_date)` in days over the last 3 months of confirmed POs, computed globally and per-buyer
- Uses `_read_group` for efficient aggregation

### L4: Performance, Odoo 18→19 Changes, Security, Invoicing Control

#### L4-A: Performance Analysis

##### `_amount_all` — Tax computation per PO
```python
for order in self:                              # O(n) per PO in the write set
    order_lines = order.order_line.filtered(...)   # O(lines per PO)
    base_lines = [line._prepare_base_line_for_taxes_computation() ...]
    AccountTax._add_tax_details_in_base_lines(...)
    AccountTax._round_base_lines_tax_details(...)
    tax_totals = AccountTax._get_tax_totals_summary(...)
```
**Complexity:** O(total_lines) in Python — one loop per PO, no batch across the entire write set. Acceptable for typical PO sizes (10–100 lines). If hundreds of POs are written in a single transaction, this does not batch; each PO triggers its own tax computation loop. Tax computation itself is delegated to `AccountTax` which is largely SQL-based inside `_add_tax_details_in_base_lines`.

**Optimization opportunity:** If called via the dashboard (which calls `retrieve_dashboard` independently), the `_amount_all` computes for all visible POs on page load. No caching is used for `amount_untaxed/tax/total` across repeated reads.

##### `_compute_show_comparison` — O(n) on total confirmed PO volume
```python
line_groupby_product = self.env['purchase.order.line']._read_group(
    [('product_id', 'in', self.order_line.product_id.ids), ('state', '=', 'purchase')],
    ['product_id'],
    ['order_id:array_agg']
)
order_by_product = {p: set(o_ids) for p, o_ids in line_groupby_product}
for record in self:
    record.show_comparison = any(
        set(record.ids) != order_by_product[p]
        for p in record.order_line.product_id if p in order_by_product
    )
```
**Complexity:** One `_read_group` query across ALL confirmed PO lines whose `product_id` is in the current PO's lines. For deployments with tens of thousands of confirmed POs, this reads a large cross-section of the `purchase_order_line` table every time ANY PO form is opened. The `_read_group` is single-query but the domain can be wide.

**Mitigation:** The comparison button only appears when there are confirmed POs for the same product across different vendors/orders. For large deployments, consider adding a `date_approve` filter to the domain (e.g., last 12 months).

##### `retrieve_dashboard()` — Six separate `_read_group` queries + iteration
```
rfq_draft_group     → _read_group by (priority, user_id)
rfq_sent_group      → _read_group by (priority, user_id)
rfq_late_group      → _read_group by (priority, user_id)  [state in ['draft','sent','to approve'], date_order < now]
rfq_not_ack_group   → _read_group by (priority, user_id)  [state in ['purchase','done'], acknowledged=False]
rfq_late_receipt    → _read_group by (priority, user_id)  [state in ['purchase','done'], is_late=True]
purchases search    → search + iteration for days_to_order (date_approve - create_date)
```
**Complexity:** Five `_read_group` calls + one `search_fetch` + Python iteration. Each `_read_group` is fast (indexed on `state`, `date_order`, `priority`, `user_id`), but the aggregation is done on the full table per call. The `days_to_order` search reads all POs from the last 3 months and iterates in Python to accumulate `total_seconds` — O(number of confirmed POs in 3 months) in memory.

**Note:** `_read_group` with `['priority', 'user_id']` and `['id:count_distinct']` is efficient (single indexed query per groupby). The overhead is the six separate database round-trips.

##### `duplicated_order_ids` — Raw SQL self-join
`_fetch_duplicate_orders()` runs a raw SQL query with a self-join on `purchase_order` table:
```sql
SELECT po.id, array_agg(duplicate_po.id)
FROM purchase_order po
JOIN purchase_order duplicate_po
    ON po.company_id = duplicate_po.company_id
    AND po.id != duplicate_po.id
    AND duplicate_po.state != 'cancel'
    AND po.partner_id = duplicate_po.partner_id
    AND (po.origin = duplicate_po.name OR po.partner_ref = duplicate_po.partner_ref)
WHERE po.id IN (...)
GROUP BY po.id
```
**Complexity:** Called at create/write time for draft POs. The `flush_model` call forces sync of the four columns (`company_id`, `partner_id`, `partner_ref`, `state`) before executing raw SQL. The query benefits from indexes on `(company_id, partner_id, state)`, `(partner_ref)`, and `(origin)`. With a large PO table, ensure these indexes exist. The `array_agg` collects duplicate IDs per PO — reasonable for up to ~100 duplicates per PO.

##### `_compute_qty_received` — `compute_sudo=True` for stock override
In the base purchase module, `qty_received` for non-storable products uses `qty_received_manual` (manual entry via `_inverse_qty_received`). The `compute_sudo=True` flag allows stock users to write this field without purchase ACL. When the `stock` module is installed, it overrides `_compute_qty_received` and `_prepare_qty_received` with stock picking logic (see Cross-Module Integration).

##### `_prepare_qty_invoiced()` — Per-line invoice traversal
```python
for pol in self:
    for inv_line in pol.invoice_lines:           # O(n invoice lines per PO line)
        if inv_line.move_id.state == 'cancel':  # skip cancelled (unless legacy)
        qty = inv_line.product_uom_id._compute_quantity(inv_line.quantity, ...)
        if inv_line.move_id.move_type == 'in_refund':
            invoiced_qties[pol] -= qty           # negate for refunds
        else:
            invoiced_qties[pol] += qty
```
**Complexity:** For PO lines with many small invoice entries (e.g., partial billing per delivery), this loops over all invoice lines. No caching is used. If a line has 50 invoice lines, each read triggers a fresh traversal.

##### `selected_seller_id` — Per-line seller lookup
```python
seller = product_id._select_seller(
    partner_id=self.order_id.partner_id,
    quantity=self.product_uom_qty,
    uom_id=self.product_uom_id,
    date=self.order_id.date_order and self.order_id.date_order.date(),
)
```
**Complexity:** Called per PO line. `_select_seller()` searches `product_supplierinfo` filtered by partner, product, date, and UoM. Without an index on `(partner_id, product_id, date_start, date_end)`, this degrades on products with many seller entries.

##### `_add_supplier_to_product()` at confirm time
```python
for line in self.order_line:
    already_seller = (partner | self.partner_id) & line.product_id.seller_ids.mapped('partner_id')
    if ... and len(line.product_id.seller_ids) <= 10:
        line.product_id.product_tmpl_id.sudo().write(vals)  # write per line
```
**Performance note:** This writes to `product_product` or `product_template` per PO line at confirm time. For POs with 50+ lines, this generates 50 separate `sudo().write()` calls. Each triggers a recompute on `product.template` fields (e.g., `seller_ids`, `purchase_method`). Consider batching if many supplierinfo records need creation.

#### L4-B: Odoo 18 → 19 Changes

The following changes represent the most significant additions and modifications to the purchase module moving from Odoo 18 to Odoo 19. Each is verified against the source code.

| Change | What changed | Why it matters |
|---|---|---|
| **`product.catalog.mixin`** | `purchase.order` now inherits `product.catalog.mixin` (added to `_inherit`) | Enables the in-form product catalog sidebar picker. Users search and add products via the catalog view rather than the classic search widget. `_get_product_catalog_domain()` filters to `purchase_ok=True`. `_get_product_catalog_order_data()` fetches seller prices. `_update_order_line_info()` creates/updates lines from catalog. |
| **`account.document.import.mixin`** | `purchase.order` now inherits `account.document.import.mixin` (added to `_inherit`) | Enables OCR-based vendor bill import with automatic PO matching via `_find_and_set_purchase_orders()`. The mixin provides `create_document_from_attachment()` which creates POs from EDI XML/CSV imports. |
| **`is_downpayment`** | New `fields.Boolean` on `purchase.order.line` | Downpayment lines are now explicitly tracked with a dedicated flag. Previously, downpayments were indicated by `display_type='line_section'` with `product_qty=0`. The explicit flag enables cleaner logic for billing (`qty_to_invoice`) and invoice matching. |
| **`amount_total_cc`** | New computed + stored `Monetary` field with `currency_field="company_currency_id"` | Stores `amount_total / currency_rate` — the PO total expressed in company currency. Enables reporting and dashboards to show both the vendor-currency total and the company-currency equivalent for multi-currency POs. |
| **`currency_rate`** | New computed + stored + precomputed `Float` field | Stores the live conversion rate from company currency to PO currency as of `date_order`. Previously, rate was implicitly used in amount computation. Now it is explicitly stored for use in reporting (via `amount_total_cc`) and audit. |
| **`product_uom_qty`** | New computed `Float` field (previously the normalized qty was stored directly in `product_qty`) | Normalizes the ordered quantity to the product's UoM. `product_qty` stays in the line's own UoM; `product_uom_qty` provides the UoM-normalized value used in `_read_group` aggregations, `_amount_all`, and comparisons with `qty_received`. |
| **`price_unit_product_uom`** | New computed `Float` field | Expresses `price_unit` in the product's base UoM rather than the line's UoM. Enables comparison between lines with different UoMs. Previously this required manual computation. |
| **`amount_to_invoice_at_date`** | New computed `Float` on `purchase.order.line` | Supports pre-date/accrual reporting scenarios. When the `accrual_entry_date` context is set, `*_at_date` computes return historical values rather than current-state values. Used by the accrued expense entry wizard. |
| **`qty_invoiced_at_date`**, **`qty_received_at_date`** | New computed `Float` fields on `purchase.order.line` | Similar to `amount_to_invoice_at_date`: return historical billing/receipt quantities for accrual reporting. `_date_in_the_past()` checks the `accrual_entry_date` context. |
| **`selected_seller_id`** | New `Many2one` to `product.supplierinfo` | Explicitly tracks which vendor pricelist was used to generate a PO line's price. Previously, the selected seller was implicit in `price_unit` computation. Now the system records the `supplierinfo` record, enabling downstream audit, repricing logic, and the `_prepare_supplier_info()` method to copy `product_name`/`product_code`/`product_uom_id` from the actual seller record at confirm time. |
| **PDF EDI embedding** | `ir_actions_report.py` override of `_render_qweb_pdf_prepare_streams()` | When printing a PO (single-record), the system calls `purchase_order._get_edi_builders()` (returns `[]` in CE; overridden in `sale` module for sale orders). For each EDI builder, it exports XML and attaches it as `text/xml` to the PDF using PyPDF2. Enables electronic document interchange where the PDF and its machine-readable EDI counterpart are bundled in a single file. |
| **`analytic.applicability`** | `account.analytic.applicability` now includes `'purchase_order'` as a `business_domain` | Administrators can define default analytic account distributions that auto-apply to PO lines, similar to how applicability rules work on account move lines or project tasks. |
| **`portal.mixin` URL** | `_compute_access_url()` sets `access_url = '/my/purchase/%s' % order.id` | Vendors accessing via the customer portal see their PO at `/my/purchase/<id>`. The acknowledgment URL is `/my/purchase/<id>?acknowledge=True`. |
| **`_get_gross_price_unit()`** | New method on `purchase.order.line` | Computes the gross (pre-discount) unit price including taxes, normalized to the product's UoM. Used for comparative pricing in the catalog. |
| **`action_merge()`** | New RFQ merge action | Allows merging multiple draft/sent RFQs from the same vendor into the oldest one. Lines with matching product/UoM/analytic/date (±24h) are merged (qty summed). Source documents and vendor references are concatenated. Unmergeable RFQs are cancelled. |

#### L4-C: Security and Access Rights

##### Record rules and ir.rule
| Rule name | XML ID | What it restricts |
|---|---|---|
| `purchase_order_comp_rule` | `purchase.purchase_order_comp_rule` | PO access: `company_id in company_ids` (user's accessible companies). All states. |
| `purchase_order_user_rule` | `purchase.purchase_order_user_rule` | PO read: any state if user is in `group_purchase_user`. Write: only `user_id = current_user` or `group_purchase_manager`. Unlink: same as write. |
| `portal_purchase_order_user_rule` | `purchase.portal_purchase_order_user_rule` | Portal users can read/write POs where `partner_id` is in their commercial partner hierarchy. |
| `purchase_order_line_comp_rule` | `purchase.purchase_order_line_comp_rule` | PO line access follows the parent PO's company rule. |

##### `group_purchase_user` vs `group_purchase_manager` — Full rights matrix
| Operation | `group_purchase_user` | `group_purchase_manager` |
|---|---|---|
| Create RFQ | Yes | Yes |
| Edit draft/sent RFQ (own PO) | Yes | Yes |
| Edit draft/sent RFQ (any PO) | No | Yes |
| Confirm PO (amount < threshold) | Yes | Yes |
| Confirm PO (amount >= threshold, two_step) | **No** | Yes |
| Unlock locked PO | **No** | Yes |
| Cancel confirmed PO (no locked/billed) | Yes | Yes |
| Cancel locked PO | **No** (must unlock first) | Yes |
| Delete cancelled PO | **No** (only manager via `_unlink_if_cancelled`) | Yes |
| Send receipt reminder email | Yes (requires `group_send_reminder`) | Yes |
| View purchase warnings | Yes (requires `group_warning_purchase`) | Yes |
| View dashboard KPIs | Yes (requires `group_purchase_user`) | Yes |
| Access to `retrieve_dashboard` | Yes (internal users only via `_is_internal()`) | Yes |
| Access to `purchase.bill.line.match` | Yes (group `group_purchase_user`) | Yes |

##### Multi-company constraints
- `check_company=True` on: `partner_id`, `dest_address_id`, `user_id`, `order_line`
- Line-level constraint: when writing a line, the product's company must be compatible with the line's company. Mismatched company raises `ValidationError`.
- `ir.rule` ensures POs are scoped to `company_id in user.company_ids`
- `company_id` is required on PO creation; `default=lambda self: self.env.company.id`

##### Portal vendor access details
Portal users (with `base.group_portal`) get read/write access via `portal_purchase_order_user_rule`. The access is scoped to POs where `partner_id` is in the user's commercial partner hierarchy. This allows a vendor company with multiple contacts (users) to see all POs sent to any of their partner entities. Portal users cannot create POs — creation requires `group_purchase_user`. The portal URL pattern is `/my/purchase/<id>`. Acknowledgment is handled via `action_acknowledge()` which sets `acknowledged=True`.

##### `_compute_purchase_warning_text` group check
```python
if not self.env.user.has_group('purchase.group_warning_purchase'):
    self.purchase_warning_text = ''
    return
```
This field is shown on the PO form and vendor bills. The group check ensures users without the warning group see an empty warning text — the field exists but is scrubbed for unauthorized users.

#### L4-D: Invoicing Control — `qty_invoiced` vs `product_uom_qty` vs `qty_received`

This is the most critical billing control in the purchase module. Three quantities interact:

| Field | Meaning | Source |
|---|---|---|
| `product_uom_qty` | Ordered quantity in product's base UoM | `product_qty` converted via line UoM → product UoM |
| `qty_received` | Quantity physically received (manual or stock picking) | Manual entry or `stock` module override |
| `qty_invoiced` | Quantity already billed | Sum of `account.move.line.quantity` linked via `purchase_line_id` |
| `qty_to_invoice` | Quantity eligible for billing | `product_uom_qty - qty_invoiced` (purchase) or `qty_received - qty_invoiced` (receive) |

##### Two `purchase_method` policies on `product.template`

| `purchase_method` | Label | Billing trigger | `qty_to_invoice` formula | Typical use |
|---|---|---|---|---|
| `'purchase'` | On ordered quantities | PO confirmation | `product_uom_qty - qty_invoiced` | Services, consumables billed at order |
| `'receive'` | On received quantities | Receipt validation | `qty_received - qty_invoiced` | Storable goods billed on delivery |

**Services always default to `'purchase'`** (set in `_compute_purchase_method`). Consumables and storable products default to `'receive'` (from the company default, settable in product category).

##### `qty_to_invoice` state machine per line
```
Line state: purchase + purchase_method=purchase
  product_uom_qty = 100, qty_invoiced = 0  → qty_to_invoice = 100  [bill all]
  product_uom_qty = 100, qty_invoiced = 40  → qty_to_invoice = 60   [bill remaining]
  product_uom_qty = 100, qty_invoiced = 100 → qty_to_invoice = 0    [fully billed]
  product_uom_qty = 100, qty_invoiced = 120 → qty_to_invoice = 0    [OVER-billed, 0, no negative]

Line state: purchase + purchase_method=receive
  qty_received = 0,   qty_invoiced = 0   → qty_to_invoice = 0   [nothing to bill yet]
  qty_received = 75,  qty_invoiced = 0   → qty_to_invoice = 75  [bill partial receipt]
  qty_received = 75,  qty_invoiced = 40  → qty_to_invoice = 35  [bill remaining of receipt]
  qty_received = 100, qty_invoiced = 100 → qty_to_invoice = 0    [fully billed]
```

**Invoice status rolls up to the PO header:**
- `no`: `state != 'purchase'` OR all lines have `qty_to_invoice == 0` and no `invoice_ids`
- `to invoice`: `state == 'purchase'` AND any line has `qty_to_invoice != 0`
- `invoiced`: All lines have `qty_to_invoice == 0` AND `invoice_ids` exists

##### Over-billing scenario
If `qty_invoiced > product_uom_qty` (for `'purchase'` method), `qty_to_invoice` is floored at 0. The vendor has been billed for more than was ordered. No further billing is possible. The overbilling is visible in the PO line's billed qty and in the invoice. Reversal requires a credit note (refund).

##### Invoice line generation — currency conversion at billing time
```python
'price_unit': self.currency_id._convert(
    self.price_unit,          # stored in PO currency
    aml_currency,             # invoice's currency
    self.company_id,
    date,                     # move.date (today), NOT date_order!
    round=False               # allow non-rounded for natural exchange diff
)
```
**Important:** `price_unit` on invoice lines is converted at the current date's exchange rate, NOT at `date_order`'s rate. This allows natural exchange rate gains/losses to appear on the vendor bill — a difference between the PO booking rate and the billing date rate flows through the exchange gain/loss account.

##### Partial billing flow
1. Vendor delivers 80 of 100 ordered units
2. Stock user validates receipt → `qty_received = 80` (if `purchase_stock` installed) OR manually set `qty_received_manual = 80`
3. PO `invoice_status` becomes `to invoice`
4. Buyer creates vendor bill → `action_create_invoice()` or manual bill → PO line quantity = `qty_to_invoice` (either 80 if `purchase_method=receive`, or 100 if `purchase_method=purchase`)
5. After bill posted: `qty_invoiced = 80` (or 100), `qty_to_invoice = 0` (or 20)

#### L4-E: Failure Modes

##### FM-1: Vendor delivers less than ordered
- **Trigger:** Receipt (or manual `qty_received`) < `product_qty`
- **Mechanism:** `qty_to_invoice` computes based on `purchase_method`. With `'receive'`, the under-delivery creates a permanent positive `qty_to_invoice`. With `'purchase'`, the buyer can still bill the full ordered qty regardless of receipt.
- **Consequence:** PO shows `invoice_status='to invoice'` even after billing, because `qty_to_invoice > 0`. Or conversely, if the buyer bills the full ordered qty but only receives partial, the `qty_to_invoice` shows 0 but the vendor may not have received full payment claim.
- **Resolution:** Require `purchase_method='receive'` for storable products; set `qty_received` correctly before billing.

##### FM-2: Vendor delivers more than ordered
- **Trigger:** Receipt (or manual `qty_received`) > `product_qty`
- **Mechanism:** No hard constraint prevents `qty_received > product_qty`. For `'receive'` method, `qty_to_invoice = qty_received - qty_invoiced`. If `qty_invoiced` is 0, the full over-delivery qty is billable. For `'purchase'` method, the over-delivery does not increase `qty_to_invoice` (it is based on `product_uom_qty`).
- **Consequence:** With `'receive'` method, the vendor can invoice for over-delivered quantities that were never validated against a purchase agreement.
- **Resolution:** Use `purchase_method='purchase'` for goods where over-delivery should not be billed without a PO amendment.

##### FM-3: PO cancelled after partial receipt
- **Trigger:** Buyer cancels PO after some lines are partially received
- **Mechanism:** `button_cancel()` checks: (1) not locked, (2) no non-cancelled/non-draft invoices. Partial receipt is allowed — there is no check on `qty_received`.
- **Consequence:** The PO is cancelled but the partial receipt remains in stock. Vendor bills for the partial delivery. The PO shows `state='cancel'`, `invoice_status='invoiced'` if billed. Stock valuation is unaffected.
- **Important:** A cancelled PO with received goods cannot be reopened. A new PO must be created for additional orders.

##### FM-4: PO cancelled with partial invoice (billed + cancelled)
- **Trigger:** Buyer cancels PO where some lines are partially invoiced
- **Mechanism:** `button_cancel()` blocks cancellation if `any(i.state not in ('cancel', 'draft') for i in po.invoice_ids)`. A posted vendor bill blocks cancellation.
- **Consequence:** The user must cancel the vendor bill first (via Account), then cancel the PO. If the bill is partially paid, the payment must also be reversed.
- **Resolution:** A strict cancellation workflow is enforced: all vendor bills (posted or draft) must be cancelled before the PO can be cancelled.

##### FM-5: Price mismatch on vendor bill import
- **Trigger:** Vendor sends a bill with a different `price_unit` than the PO
- **Mechanism:** `_find_matching_po_and_inv_lines()` matches by `price_unit >= inv_line.price_unit` and `remaining_qty >= inv_line.quantity`. It does NOT reject price mismatches; it links the line and uses the PO's price for the `purchase_line_id` relationship. However, the invoice line's `price_unit` is preserved.
- **Consequence:** The vendor bill shows the vendor's price but the PO line reference links it to the PO. A discrepancy between `price_unit` on the bill and `price_unit` on the PO indicates a pricing dispute.
- **Tolerance:** No monetary tolerance is applied in line-level matching (only in `subset_match` amount comparison). A 1-cent difference per line is enough to prevent automatic line-level linking.

##### FM-6: Refund after full receipt creates negative billing
- **Trigger:** Vendor bill is reversed via credit note after full delivery
- **Mechanism:** `_prepare_qty_invoiced()` handles refunds: `invoiced_qties[pol] -= converted_qty` for `in_refund` lines. After a full refund, `qty_invoiced` returns to 0, restoring `qty_to_invoice`.
- **Consequence:** `invoice_status` reverts to `to invoice`. The PO can be re-billed.

##### FM-7: Currency mismatch on PO vs. vendor bill
- **Trigger:** PO created in EUR, vendor sends a bill in USD (unusual — normally PO currency drives the bill currency)
- **Mechanism:** `_onchange_partner_id()` on `account.move` suggests a journal with `currency_id` matching `partner_id.property_purchase_currency_id`. If the user forces a different currency, the PO lines' `price_unit` (stored in PO currency) are converted at `move.date` rate.
- **Consequence:** The `account.move.line.price_unit` may differ significantly from `purchase.order.line.price_unit` due to exchange rate movement. An unrealized exchange gain/loss appears on the vendor bill.

##### FM-8: `_find_matching_subset_po_lines` timeout
- **Trigger:** Large PO with many lines (>50), complex subset-sum where the recursive algorithm exhausts its 10-second timeout
- **Mechanism:** The recursive divide-and-conquer algorithm (O(2^n) worst case) is called with `timeout=10` seconds. If `time.time() - start_time > timeout`, it raises `TimeoutError` and returns `[]`.
- **Consequence:** `subset_total_match` fails, falls back to `po_match` (imports all PO lines regardless of billing status). The vendor bill is over-imported with zero-quantity lines.
- **Resolution:** Keep PO line counts manageable; timeout is configurable via the `timeout` parameter in `_find_and_set_purchase_orders`.

---

## `purchase.order.line`

**File:** `models/purchase_order_line.py`
**Inherits:** `analytic.mixin`

### L1: All Field Signatures

```python
# Description and ordering
name = fields.Text(string='Description', required=True,
                    compute='_compute_price_unit_and_date_planned_and_name',
                    store=True, readonly=False)
sequence = fields.Integer(string='Sequence', default=10)
display_type = fields.Selection([
    ('line_section', "Section"),
    ('line_subsection', "Subsection"),
    ('line_note', "Note")], default=False)

# Product and quantity
product_id = fields.Many2one('product.product', string='Product',
                             domain=[('purchase_ok', '=', True)],
                             change_default=True, index='btree_not_null',
                             ondelete='restrict')
product_type = fields.Selection(related='product_id.type', readonly=True)
product_qty = fields.Float(string='Quantity', digits='Product Unit', required=True)
product_uom_qty = fields.Float(string='Total Quantity',
                                compute='_compute_product_uom_qty', store=True)
product_uom_id = fields.Many2one('uom.uom', string='Unit',
                                  domain="[('id', 'in', allowed_uom_ids)]",
                                  ondelete='restrict')
allowed_uom_ids = fields.Many2many('uom.uom', compute='_compute_allowed_uom_ids')

# Pricing
price_unit = fields.Float(string='Unit Price', required=True,
                           min_display_digits='Product Price', aggregator='avg',
                           compute="_compute_price_unit_and_date_planned_and_name",
                           readonly=False, store=True)
technical_price_unit = fields.Float(
    help="Technical sentinel: if != price_unit, price was manually edited; prevents recompute")
price_unit_product_uom = fields.Float(string='Unit Price Product UoM',
                                       min_display_digits='Product Price',
                                       compute="_compute_price_unit_product_uom")
price_unit_discounted = fields.Float('Unit Price (Discounted)',
                                      compute='_compute_price_unit_discounted')
discount = fields.Float(string="Discount (%)",
                        compute='_compute_price_unit_and_date_planned_and_name',
                        digits='Discount', store=True, readonly=False)

# Amounts (computed)
price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)

# Taxes
tax_ids = fields.Many2many('account.tax',
                           context={'active_test': False, 'hide_original_tax_ids': True})

# Dates
date_planned = fields.Datetime(string='Expected Arrival', index=True,
                                compute="_compute_price_unit_and_date_planned_and_name",
                                readonly=False, store=True)

# Billing quantities
invoice_lines = fields.One2many('account.move.line', 'purchase_line_id',
                               string="Bill Lines", readonly=True, copy=False)
qty_invoiced = fields.Float(compute='_compute_qty_invoiced', string="Billed Qty",
                           digits='Product Unit', store=True)
qty_to_invoice = fields.Float(compute='_compute_qty_invoiced',
                              string='To Invoice Quantity', store=True,
                              readonly=True, digits='Product Unit')
qty_invoiced_at_date = fields.Float(string="Billed",
                                    compute='_compute_qty_invoiced_at_date',
                                    digits='Product Unit')

# Receiving quantities
qty_received_method = fields.Selection([('manual', 'Manual')],
                                       compute='_compute_qty_received_method', store=True)
qty_received = fields.Float("Received Qty",
                            compute='_compute_qty_received',
                            inverse='_inverse_qty_received',
                            compute_sudo=True, store=True, digits='Product Unit')
qty_received_manual = fields.Float("Manual Received Qty",
                                   digits='Product Unit', copy=False)
qty_received_at_date = fields.Float(string="Received",
                                   compute='_compute_qty_received_at_date',
                                   digits='Product Unit')
amount_to_invoice_at_date = fields.Float(string='Amount',
                                        compute='_compute_amount_to_invoice_at_date')

# PO link and related
order_id = fields.Many2one('purchase.order', string='Order Reference',
                           index=True, required=True, ondelete='cascade')
company_id = fields.Many2one('res.company', related='order_id.company_id',
                              string='Company', store=True, readonly=True)
state = fields.Selection(related='order_id.state')
partner_id = fields.Many2one('res.partner', related='order_id.partner_id',
                             string='Partner', readonly=True, store=True,
                             index='btree_not_null')
currency_id = fields.Many2one(related='order_id.currency_id', string='Currency')
date_order = fields.Datetime(related='order_id.date_order', string='Order Date', readonly=True)
date_approve = fields.Datetime(related="order_id.date_approve", string='Confirmation Date',
                                readonly=True)
tax_calculation_rounding_method = fields.Selection(
    related='company_id.tax_calculation_rounding_method', readonly=True)

# Downpayment and hierarchy
is_downpayment = fields.Boolean()
parent_id = fields.Many2one('purchase.order.line', string="Parent Section Line",
                            compute='_compute_parent_id')

# Vendor selection tracking
selected_seller_id = fields.Many2one('product.supplierinfo',
                                      compute='_compute_selected_seller_id',
                                      help='Technical: which vendor pricelist was used to generate this line')

# Attributes
product_template_attribute_value_ids = fields.Many2many(
    related='product_id.product_template_attribute_value_ids', readonly=True)
product_no_variant_attribute_value_ids = fields.Many2many(
    'product.template.attribute.value', ondelete='restrict')
purchase_line_warn_msg = fields.Text(compute='_compute_purchase_line_warn_msg')
```

### L2: Field Details and Constraints

#### `price_unit` — Triple-computed field
`_compute_price_unit_and_date_planned_and_name` is the master compute, triggered by changes to `product_id`, `product_qty`, `product_uom_id`, `company_id`, `partner_id`, or `order_id.date_order`.

**Skip conditions** (no recompute):
1. No `product_id` set
2. `invoice_lines` exist (already partially billed — price should not change)
3. `skip_uom_conversion` context flag is set
4. `technical_price_unit != price_unit` — manually edited price, preserve it

**Price resolution cascade**:
```
If selected_seller_id exists:
    price = seller.price
    Apply tax inclusion fix: _fix_tax_included_price_company()
    Convert from seller.currency_id → PO.currency_id at date_order rate
    Convert from seller.product_uom_id → line.product_uom_id
    discount = seller.discount

Else (no seller for this vendor):
    price = product.standard_price (cost price)
    Convert from product.cost_currency_id → PO.currency_id at date_order rate
    discount = 0
```
The computed `price_unit` is then copied to `technical_price_unit` to mark it as non-manual.

#### `product_uom_qty` — UoM-normalized quantity
```python
if product.uom_id != product_uom_id:
    product_uom_qty = product_uom_id._compute_quantity(product_qty, product.uom_id)
else:
    product_uom_qty = product_qty
```
Keeps `product_qty` in the line's own UoM while normalizing for analytics and comparisons. Used in `_read_group` aggregations on the dashboard.

#### `qty_to_invoice` — Billing quantity based on control policy
```python
if order.state == 'purchase':
    if product.purchase_method == 'purchase':   qty_to_invoice = product_qty - qty_invoiced
    else:                                       qty_to_invoice = qty_received - qty_invoiced
else:
    qty_to_invoice = 0
```
| Product `purchase_method` | Label | Billing trigger |
|---|---|---|
| `'purchase'` | On ordered quantities | `product_qty` ordered |
| `'receive'` | On received quantities | `qty_received` from picking |

#### `qty_received_method` — Manual vs. stock-driven
| Product type | Method |
|---|---|
| `consu`, `service` | `'manual'` |
| `product` (storable) | `False` — `stock` module overrides with picking-based logic |

The `compute_sudo=True` on `qty_received` allows stock users to write the field without purchase ACL.

#### `date_planned` — Delivery scheduling
- Computed by `_get_date_planned(seller, po)` when no `selected_seller_id` or no `date_planned` exists
- Formula: `date_order + relativedelta(days=seller.delay if seller else 0)`
- `_convert_to_middle_of_day()`: converts to noon UTC using the order user's timezone (or company timezone as fallback)

#### Model Constraints (SQL-level)
```sql
CHECK(display_type IS NOT NULL OR is_downpayment
  OR (product_id IS NOT NULL AND product_uom_id IS NOT NULL AND date_planned IS NOT NULL))
-- 'Missing required fields on accountable purchase order line.'

CHECK(display_type IS NULL
  OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0
      AND product_uom_id IS NULL AND date_planned IS NULL))
-- 'Forbidden values on non-accountable purchase order line.'
```

### L3: Cross-Model Logic

#### Invoice line generation (`_prepare_account_move_line`)
Key behaviors:
- `quantity = -qty_to_invoice` for refunds (`move.move_type == 'in_refund'`), positive for invoices
- `price_unit` is converted to the invoice's currency at current date rate (not `date_order` rate) — allows exchange gains/losses to appear naturally
- `is_downpayment` copied to the invoice line
- Does NOT include `account_id` — `account.move.line` resolves it via `_get_computed_accounts()`

#### Tax computation flow
```
product_id.supplier_taxes_id
  → filter by company (company_id on the line)
  → map through fiscal_position_id.map_tax()
  → stored in tax_ids
  → used in _compute_amount
```
Fiscal position resolution: `order_id.fiscal_position_id or _get_fiscal_position(order_id.partner_id)`.

#### Analytic distribution
`_compute_analytic_distribution()` applies `account.analytic.distribution.model._get_distribution()` using product, partner, company as hints. Falls back to existing distribution on the line. Validated on `button_confirm()` via `_validate_analytic_distribution(business_domain='purchase_order')`.

#### `_suggest_quantity()` — Min order qty
Finds the seller matching the PO's vendor and product, filtered by date range, sorted by `min_qty` ascending. Sets `product_qty` to the lowest `min_qty` threshold found, or defaults to `1.0`.

### L4: Performance, Odoo 18→19 Changes, Edge Cases

#### L4-A: Performance
- `_compute_price_unit_and_date_planned_and_name` is a multi-field compute triggered on every relevant field change. The `skip_uom_conversion` context flag is the main bypass used by `action_create_invoice()` to prevent price recomputation during billing.
- `selected_seller_id` calls `product_id._select_seller()` per line. `_select_seller()` searches `product_supplierinfo` filtered by partner, product, date, UoM — O(m) per line where m = number of seller entries for that product. Ensure index on `(partner_id, product_id, date_start, date_end)` for this table.
- `_prepare_qty_invoiced()` traverses `invoice_lines` per line — for partially-billed lines with many small invoice entries, this can degrade. No result caching.
- `_compute_parent_id()` sorts all lines by sequence per order and walks forward — O(n log n) per `order_id` when called for multiple lines in batch.
- `price_unit_product_uom` compute converts from line UoM to product base UoM — called on demand (not stored). If rendered in a list view, it triggers N queries per page.

#### L4-B: Odoo 18→19 Changes
- `product_uom_qty` compute is new in Odoo 19 — previously the normalized quantity was stored directly as `product_qty`. The separation means `product_qty` preserves the buyer's entered UoM quantity, while `product_uom_qty` is the canonical normalized value.
- `price_unit_product_uom` (price expressed in the product's UoM vs. the line's UoM) is new. Used by `_get_gross_price_unit()` and the catalog display.
- `amount_to_invoice_at_date`, `qty_invoiced_at_date`, `qty_received_at_date` support pre-date/accrual reporting scenarios. `_date_in_the_past()` checks `accrual_entry_date` in context.
- `selected_seller_id` was added as a dedicated field to track which vendor pricelist was used, enabling downstream audit, `button_confirm()` to copy `product_name`/`product_code`/`product_uom_id` from the actual seller to the new supplierinfo record, and the repricing logic in `_update_order_line_info()`.
- `_merge_po_line()` is new — used by `action_merge()` on PO to absorb another RFQ's lines by summing quantities and keeping the minimum price.
- `_get_gross_price_unit()` is new — computes gross unit price including taxes, normalized to product UoM, used by the product catalog.

#### L4-C: Edge Cases
- **Manually edited price:** Setting `price_unit` directly sets `technical_price_unit = price_unit`. Future recomputes check `technical_price_unit != price_unit` and skip, preserving the manual price. Reset by clearing `technical_price_unit` (e.g., after changing the product).
- **Invoice line UoM mismatch:** `_prepare_qty_invoiced()` converts `inv_line.quantity` from `inv_line.product_uom_id` to `line.product_uom_id` via `_compute_quantity` — UoM rounding differences can cause small discrepancies in `qty_invoiced` (e.g., invoice in units, PO in dozens).
- **Cancelled invoice:** Excluded from `_prepare_qty_invoiced()` UNLESS `payment_state == 'invoicing_legacy'` (backward compat for migrated data where cancelled invoices were not properly cleaned up).
- **Refunds:** `in_refund` lines negate quantity: `invoiced_qties[line] -= converted_qty`. After a full refund, `qty_invoiced` returns to its pre-billing level.
- **Section/note display_type:** All product fields forced to False/NULL via SQL constraint. Changing `display_type` mid-life raises `UserError`. The constraint also permits `is_downpayment=True` lines to have NULL product_id.
- **Storable products without `stock` module:** `qty_received_method` is `False` (not `'manual'`). Without the `stock` module's override, `qty_received` stays 0 regardless of actual deliveries. Users must set `qty_received_manual` manually.
- **`_date_in_the_past()`:** The accrual context (`accrual_entry_date`) causes all `*_at_date` computes to query historical data rather than current state, enabling past-date accrual reporting without altering the current PO state.
- **Zero UoM conversion:** If `product_uom_id == product.uom_id`, `product_uom_qty` is set equal to `product_qty` with no conversion.
- **Supplierinfo with no price:** If the matched seller has `price = 0`, the computed `price_unit` is 0. No fallback to `standard_price` if a seller exists (even with zero price).
- **`_track_qty_received()`:** Posts a mail message only when `state == 'purchase'` and `qty_received` actually changes (not from accrual context). Uses `message_post_with_source()` with template `purchase.track_po_line_qty_received_template`.

---

## `product.supplierinfo` (Purchase Extension)

**File:** `models/product.py`
**Inherits:** `product.supplierinfo`

### `_onchange_partner_id`
When setting a vendor on a supplierinfo record, currency auto-fills from `partner_id.property_purchase_currency_id`, falling back to the current company currency. Ensures vendor price lists default to the correct currency.

### `_get_filtered_supplier`
Extends base to accept `order_id` in the `params` dict. When present, the company context is taken from `params['order_id'].company_id` rather than the current environment — critical for correct multi-company supplierinfo lookups from within a PO.

---

## `product.template` / `product.product` (Purchase Extensions)

**File:** `models/product.py`

### `purchase_method` — Invoice control policy
| Value | Label | `qty_to_invoice` formula |
|---|---|---|
| `'purchase'` | On ordered quantities | `product_qty - qty_invoiced` |
| `'receive'` | On received quantities | `qty_received - qty_invoiced` |

Computed from `type`: services always default to `'purchase'`. Consumables and storable products follow the company default via `default_get`.

### `purchased_product_qty` — Rolling 12-month volume
- Scope: `state = 'purchase'` AND `date_approve >= today - 1 year`
- Aggregated via `_read_group` across all variants
- Shows total units purchased in the last 12 months (in product's UoM)

### `is_in_purchase_order` — Context-sensitive product availability
- `compute_sudo=True` — visible without purchase ACL
- Used in the product catalog to indicate whether a product is already on the active PO being edited
- Driven by `order_id` in context: searches PO lines for the given `order_id`

---

## `res.partner` (Purchase Extension)

**File:** `models/res_partner.py`

### `property_purchase_currency_id`
Company-dependent Many2one to `res.currency`. Sets the default purchase trading currency for a vendor. Used by:
- `purchase.order._compute_currency_id()` — defaults PO currency
- `product.supplierinfo._onchange_partner_id()` — defaults supplierinfo currency

### `receipt_reminder_email` + `reminder_date_before_receipt`
Company-dependent Boolean + Integer. Controls the vendor receipt reminder workflow. `receipt_reminder_email` is computed onto the PO; `reminder_date_before_receipt` specifies how many days before `date_planned` the reminder fires.

### `buyer_id`
Many2one to `res.users`. When set on a vendor, `onchange_partner_id()` on PO auto-fills `user_id` with this buyer.

### `purchase_order_count`
Count of POs where the partner (or any of its children in the hierarchy) is the vendor. Uses `_read_group` with recursive parent traversal: for each partner in the count group, the count bubbles up through `parent_id` chain.

---

## `account.move` (Purchase Extension)

**File:** `models/account_invoice.py`

### PO-to-bill matching algorithm (`_match_purchase_orders`)
The matching system has five tiers, applied in order:

| Method | Trigger | Bill behavior |
|---|---|---|
| `total_match` | PO name/partner_ref + total amount within ±0.02 tolerance | All PO lines imported, existing lines replaced |
| `po_match` | PO reference only, OCR scan, no amount | All PO lines imported |
| `subset_total_match` | Subset of PO lines sums to bill total within tolerance (OCR) | Partial import; unmatched lines added with qty=0 |
| `subset_match` | Unit price + qty match at line level (EDI) | Invoice lines adjusted to PO quantities/taxes; unmatched deleted |
| `no_match` | Nothing found | Bill stays as-is; `invoice_origin` cleared |

**Subset-sum algorithm** (`_find_matching_subset_po_lines`): Recursive divide-and-conquer sorted by `amount_to_invoice` descending. Tolerates ±0.02 per line. Times out after `timeout` seconds (default 10). Returns empty list on timeout or multiple solutions.

**Line-level matching** (`_find_matching_po_and_inv_lines`):
1. Sort invoice lines by `(price_unit, quantity)` descending
2. Sort PO lines by `(price_unit, remaining_qty)` descending
3. Match when `po_line.price_unit >= inv_line.price_unit` and `remaining_qty >= inv_line.quantity`
4. Use `difflib.SequenceMatcher` on product names for disambiguation when multiple candidates qualify
5. Skips lines once matched (no double-use)

### `_set_purchase_orders()`
Links matched PO lines to the bill:
- `total_match` / `po_match`: `force_write=True` — clears existing invoice lines before importing PO lines
- `subset_total_match`: `force_write=False` — keeps invoice lines, sets matched PO lines to correct qty, others to qty=0
- `subset_match`: `force_write=False` — adjusts matched PO line quantities to match invoice, deletes original matched invoice lines

### `is_purchase_matched` — Bill completeness flag
True only if ALL product-type invoice lines have a `purchase_line_id`. Any unlinked product line sets this to False. Displayed on the vendor bill form as a matching status indicator.

---

## `purchase.bill.line.match`

**File:** `models/purchase_bill_line_match.py`
**Type:** Read-only SQL union view (auto-generated, `_auto = False`)

Presents a unified list of:
- Unmatched PO lines (positive `pol_id`, null `aml_id`)
- Unmatched vendor bill lines (null `pol_id`, positive `aml_id`)

```sql
-- PO lines side (pol_id positive; aml_id is NULL)
SELECT pol.id AS pol_id, ..., NULL AS aml_id, po.state
FROM purchase_order_line pol
LEFT JOIN purchase_order po ON pol.order_id = po.id
WHERE po.state = 'purchase'
  AND (pol.product_qty > pol.qty_invoiced OR pol.qty_to_invoice != 0)
     OR (display_type IS NULL AND is_downpayment AND qty_invoiced > 0)

UNION ALL

-- Bill lines side (aml_id negative; pol_id is NULL)
SELECT NULL AS pol_id, ..., aml.id AS aml_id, am.state
FROM account_move_line aml
LEFT JOIN account_move am ON aml.move_id = am.id
WHERE aml.display_type = 'product'
  AND am.move_type IN ('in_invoice', 'in_refund')
  AND aml.parent_state IN ('draft', 'posted')
  AND aml.purchase_line_id IS NULL
```

**SQL negation convention:** `aml.id` is negated (negative) in the PO side to distinguish PO lines from bill lines in the same ID column. The wizard's `action_add_to_po()` uses `abs(record_id)` to recover the original `aml.id`.

`action_match_lines()`: Links unmatched bill lines to PO lines by product (first match wins), then creates a draft bill for any remaining unmatched PO lines. `action_add_to_po()` opens the `bill.to.po.wizard` to redirect bill lines to a selected PO.

`action_open_line()`: Smart navigation — opens the PO form if `pol_id` is set, or the bill form if `aml_id` is set.

---

## `res.company` (Purchase Extension)

**File:** `models/res_company.py`

### `po_lock`
| Value | Label | Effect |
|---|---|---|
| `'edit'` | Allow to edit purchase orders | No automatic locking |
| `'lock'` | Confirmed POs are not editable | `button_approve()` sets `po.locked = True` |

### `po_double_validation`
| Value | Label | Effect |
|---|---|---|
| `'one_step'` | Confirm in one step | Any user can confirm |
| `'two_step'` | Get 2 levels of approvals | Amount >= threshold requires `group_purchase_manager` |

### `po_double_validation_amount`
Default: 5000 in company currency. Converted to PO currency at `date_order` rate for threshold comparison.

---

## `account.analytic.applicability` (Purchase Extension)

**File:** `models/analytic_applicability.py`

Adds `'purchase_order'` as a new `business_domain` for analytic applicability rules. Allows administrators to define default analytic account distributions that auto-apply to PO lines, similar to how they work on account move lines or project tasks.

---

## Wizard: `bill.to.po.wizard`

**File:** `wizard/bill_to_po_wizard.py`

### `action_add_to_po()`
1. Extracts negative AML IDs from `active_ids` (negative = from the bill line match view)
2. Filters to lines with `product_id`; raises `UserError` if none (prevents downpayment lines from being added as regular lines)
3. Either appends to a selected existing PO or creates a new PO
4. Calls `button_confirm()` on the target PO
5. Links each AML to its corresponding PO line by product match
6. Returns form view of the confirmed PO

### `action_add_downpayment()`
1. Creates (or uses selected) PO with downpayment section
2. Converts bill lines to PO lines with `is_downpayment=True`, `product_qty=0`, and currency-converted `price_unit`
3. Links AMLs to the new downpayment PO lines

---

## Tax Usage Tracking

**File:** `models/account_tax.py**

`_hook_compute_is_used()` extends the tax usage check to include taxes referenced in `purchase_order_line.tax_ids`. The SQL query directly joins `account_tax` with the `account_tax_purchase_order_line_rel` M2M table. This ensures taxes used only on draft or cancelled POs are excluded from "used" status for tax report purposes.

---

## Key Workflow Triggers

| Event | Action |
|---|---|
| `button_confirm()` | Validates lines have products, validates analytic distribution, adds vendor to product supplierinfo (up to 10 sellers), checks double-validation threshold |
| `button_approve()` | Sets `state='purchase'`, `date_approve=now`, locks if `po_lock=='lock'` |
| `button_cancel()` | Checks not locked, checks no billed invoices, sets `state='cancel'` |
| `button_lock()` / `button_unlock()` | Manually toggles `locked` flag |
| `action_create_invoice()` | Groups by (company, partner, currency), creates batched invoices, handles negative-total refunds |
| `message_post()` with `mark_rfq_as_sent` | Sets `state='sent'` on draft POs |
| `print_quotation()` | Sets `state='sent'` on draft POs, generates PDF |
| `_send_reminder_mail()` (cron) | Sends reminder email N days before `date_planned` for unacknowledged confirmed POs with non-service products |
| `action_acknowledge()` | Sets `acknowledged=True`; accessible from vendor portal |
| `onchange_partner_id()` | Sets fiscal position, payment terms, buyer_id; triggers currency recompute |
| `onchange_product_id()` (on line) | Resets price/qty/name, applies tax from fiscal position, suggests qty from seller min_qty |
| `_add_supplier_to_product()` | Called at confirm: adds vendor to product's supplierinfo if not present (max 10 entries), creates entry with PO price/UoM |

---

## Cross-Module Integration

### Module: `purchase_stock` — Receipt-driven `qty_received`

The `purchase_stock` module (part of the stock addons suite) overrides `purchase.order.line` to connect `qty_received` to stock picking operations.

**Override points:**
- `_compute_qty_received_method`: Changes from `'manual'` to `False` for storable products. The `False` sentinel signals that stock picking logic should be used.
- `_compute_qty_received`: Returns the sum of `move_ids` quantities for moves linked to this PO line (via `purchase_line_id` on `stock.move`). Reads from `stock.move.product_uom_qty` for done moves.
- `_prepare_qty_received()`: Returns a `defaultdict(float)` with quantities sourced from `stock.move` records.
- `stock_move` relation: `stock.picking` lines are created when the PO is confirmed (if `picking_type_id` is set on the PO or its warehouse). When the receipt is validated, `stock.move.quantity_done` is set, and `stock.move._action_done()` propagates the received qty back to `purchase.order.line.qty_received`.

**Key behavior:** When `stock` module is installed, `qty_received` is read-only (no inverse). It can only change through stock picking operations. Attempting to write to `qty_received` on a storable product line when `stock` is installed raises a `UserError` or the write is silently ignored (depending on the version).

### Module: `sale_purchase` — Service SO generates PO

The `sale_purchase` module enables dropshipping services: a service product on a Sale Order auto-generates a Purchase Order to the vendor when the SO is confirmed.

**Extension points on `purchase.order` (in `sale_purchase/models/purchase_order.py`):**
- `sale_order_count`: Computed from `order_line.sale_order_id` — count of source sale orders
- `has_sale_order`: Boolean flag for whether this PO originated from an SO
- `sale_order_id`: Related shortcut on `purchase.order.line` → `sale.order.line` via `sale_line_id`

**Extension on `purchase.order.line`:**
- `sale_line_id`: Many2one to `sale.order.line`. Set when the PO line is created from an SO line via `_purchase_service_create()`.
- `button_cancel()` override: Schedules a mail activity on the source SO when the PO is cancelled (via `_activity_cancel_on_sale()`).

**Service PO generation flow (`sale_purchase/models/sale_order_line.py`):**
1. SO confirmation calls `_purchase_service_generation()` for service lines with `product_id.service_to_purchase = True`
2. `_purchase_service_create()`: Creates PO and PO line, links via `sale_line_id`
3. `_purchase_service_prepare_line_values()`: Prepares PO line vals including `sale_line_id = self.id`
4. The PO is created in `'purchase'` state directly (skips RFQ stage via `_state_from_so`)

### Module: `stock_account` — Valuation entries on receipt

When `stock_account` is installed, receiving goods creates journal entries that debit the stock valuation account and credit the vendor variance account. The PO `price_unit` is used as the unit cost. Exchange rate differences between PO booking and receipt date flow through the valuation.

### Module: `account_3way_match` — Optional 3-way matching

When installed, a third level of matching is added: PO qty ordered → Receipt qty → Billed qty. This blocks vendor bill posting until the receipt is validated, enforcing receipt-before-payment for high-value purchases.

### Module: `purchase_product_matrix` — Grid product entry

Adds a matrix (grid) view on the PO form for configurable products (e.g., products with matrix variants). Allows bulk entry of variant combinations with their quantities and prices.

---

## Failure Modes (Cross-Module)

| Scenario | Trigger | Mechanism | Resolution |
|---|---|---|---|
| Stock installed but receipt not done | PO confirmed, buyer creates bill | `qty_received = 0`, `purchase_method='receive'`, `qty_to_invoice = 0` | Must validate receipt first, or switch product to `purchase_method='purchase'` |
| Sale→Purchase chain broken | SO cancelled after PO confirmed | No automatic PO cancellation. PO must be cancelled manually. | Cancel PO manually; `sale_purchase` only creates, does not manage lifecycle |
| PO confirmed, vendor changed on partner | Later bill arrives with new vendor | Bill is matched to PO by `partner_id` hierarchy. If `commercial_partner_id` differs, `subset_match`/`total_match` may fail. | Bill falls to `no_match`; manually link via `purchase.bill.line.match` |
| EDI PDF embedded but builder missing | Printing PO in CE | `_get_edi_builders()` returns `[]` in CE. PDF prints normally with no attachments. | Install the relevant EDI module (`sale_edi`, `account_edi_ubl_cii`, etc.) |
| PO currency ≠ company currency, vendor bill in different third currency | Multi-currency mismatch | Price conversion is from PO currency → bill currency at current rate, going through company currency as intermediate. Double conversion can introduce rounding discrepancies. | Use the same currency on PO and bill where possible |

---

## Security Reference

### ir.rule records (verified from source)
| Rule | Model | Domain |
|---|---|---|
| `purchase_order_comp_rule` | `purchase.order` | `[('company_id', 'in', company_ids)]` |
| `purchase_order_user_rule` | `purchase.order` | Read: always (if user). Write: `user_id = uid` or `group_purchase_manager`. Unlink: same as write. |
| `portal_purchase_order_user_rule` | `purchase.order` | Portal: `partner_id.commercial_partner_id` in user's commercial partners |
| `purchase_order_line_comp_rule` | `purchase.order.line` | `[('order_id.company_id', 'in', company_ids)]` |

### Field-level group restrictions
| Field | Group required |
|---|---|
| `res.partner.purchase_order_count` | `purchase.group_purchase_user` |
| `purchase_order_line.purchase_line_warn_msg` | `purchase.group_warning_purchase` |
| `account.move.purchase_warning_text` | `purchase.group_warning_purchase` |
| `account.move.line.purchase_line_warn_msg` | `purchase.group_warning_purchase` |
