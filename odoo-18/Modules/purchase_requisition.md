# purchase_requisition - Purchase Requisition

**Module:** `purchase_requisition`
**Depends:** `purchase`
**Category:** Purchases/Purchases

---

## Purpose

Centralized purchasing workflow that consolidates internal demand into vendor RFQs. Supports two procurement strategies: **blanket orders** (framework agreements with pre-agreed pricing) and **calls for bids** (competitive tendering across multiple vendors). Enables centralized approval, vendor comparison, and PO generation from requisition lines.

---

## Models

### purchase.requisition

**File:** `models/purchase_requisition.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Auto-generated sequence (default "/") |
| `origin` | `Char` | Source document reference |
| `vendor_id` | `Many2one` | Preferred/default vendor (res.partner) |
| `line_ids` | `One2many` | Requisition product lines (`purchase.requisition.line`) |
| `schedule_date` | `Date` | Requested delivery date for the whole requisition |
| `ordering_date` | `Date` | Order placement date to meet schedule |
| `date_end` | `Datetime` | Deadline for bid submission |
| `user_id` | `Many2one` | Responsible buyer |
| `description` | `Text` | Internal notes/Terms |
| `state` | `Selection` | `draft` / `in_progress` / `open` / `done` / `cancel` |
| `exclusive` | `Selection` | `exclusive` / `exclusive_view` (only one vendor can be selected) |
| `requisition_type` | `Selection` | `blanket_order` / `purchase_template` / `blanket` (legacy) |
| `type_id` | `Many2one` | `purchase.requisition.type` template |
| `currency_id` | `Many2one` | Currency for pricing |
| `company_id` | `Many2one` | Company |
| `purchase_ids` | `One2many` | Generated purchase orders (`purchase.order`) |
| `analytic_distribution` | `Json` | Analytic distribution for all lines |
| `dest_address_id` | `Many2one` | Delivery address |
| `ordering_date` | `Date` | When to order |
| `receipt_date` | `Date` | Expected delivery date |
| `group_id` | `Many2one` | Procurement group for PO linking |
| `product_id` | `Many2one` | Single-product mode (for blanket orders) |
| `quantity` | `Float` | Single-product qty |

**State Machine:**

```
draft ──(confirm)──> in_progress ──(open)──> open ──(done)──> done
                     │                  ▲
                     └──(cancel)────────┘
```

- `draft` - Initial state; lines can be added/edited
- `in_progress` - Active sourcing; vendors are being contacted
- `open` - Bidding period open (for calls-for-bids type)
- `done` - Awarded; POs have been created
- `cancel` - Cancelled

**Key Methods:**

- `action_cancel()` - Cancels the requisition
- `action_in_progress()` - Moves to in_progress state
- `action_open()` - Opens the bidding period
- `action_draft()` - Resets to draft
- `_purchase_confirm` - Converts requisition lines to PO lines

---

### purchase.requisition.line

**File:** `models/purchase_requisition.py`

| Field | Type | Description |
|---|---|---|
| `requisition_id` | `Many2one` | Parent requisition |
| `product_id` | `Many2one` | Product to procure |
| `product_uom_id` | `Many2one` | UoM (defaults to product UoM) |
| `product_qty` | `Float` | Quantity to order |
| `product_description_vendor` | `Text` | Vendor-specific product description |
| `price_unit` | `Monetary` | Agreed unit price (for blanket orders) |
| `schedule_date` | `Date` | Line-level delivery date |
| `analytic_distribution` | `Json` | Analytic account distribution |
| `account_analytic_id` | `Many2one` | Single analytic account (deprecated, use analytic_distribution) |
| `supplier_info_ids` | `One2many` | Linked `product.supplierinfo` records |
| `qty_ordered` | `Float` | Total qty already ordered in POs |
| `price_average` | `Float` | Weighted average price from POs |
| `currency_id` | `Many2one` | Currency |
| `taxes_id` | `Many2many` | Taxes |

**Key Methods:**

- `_compute_price_average()` - Recomputes weighted average from PO lines
- `write()` - Updates `qty_ordered` from linked POs

**Compute Fields:**

- `qty_ordered` - `sum(purchase_line_id.product_qty)` from POs linked to this line
- `price_average` - Weighted average price from awarded PO lines

---

### purchase.requisition.type

**File:** `models/purchase_requisition.py`

| Field | Type | Description |
|---|---|---|
| `name` | `Char` | Type name |
| `exclusive` | `Selection` | `exclusive` / `exclusive_view` - restricts vendor selection |
| `deadline_bidding` | `Integer` | Days before deadline_bidding date to send reminders |
| `type` | `Selection` | `purchase_template` (blanket order) / `purchase_template_view` (call for bids) |

**`exclusive` Values:**
- `exclusive` - Once a PO is confirmed against this requisition, other vendors are excluded
- `exclusive_view` - Multiple POs can be created against one requisition

---

## purchase.order Extension

**File:** `models/purchase.py`

| Field | Type | Description |
|---|---|---|
| `requisition_id` | `Many2one` | Source requisition (`purchase.requisition`) |
| `requisition_line_id` | `Many2one` | Source line (when created from a single line) |
| `purchase_type` | `Selection` | Source type (not in Odoo 18 core) |

**Key Methods:**

- `_onchange_requisition_id()` - Onchange handler that fills PO with requisition data:
  - Sets vendor from `requisition_id.vendor_id`
  - Sets currency from `requisition_id.currency_id`
  - Copies notes from requisition description
  - Adds all requisition lines as PO lines
  - Sets `purchase_type = 'requisition'`

- `_compute_requisition_line_ids()` - Gets all requisition lines from all linked requisitions

**Overridden Methods:**

- `_compute_price_unit_and_date_planned_and_name()` - On `purchase.order.line`: if `requisition_line_id` is set, pulls `price_unit`, `date_planned`, and `product_description_vendor` from the requisition line

---

## Alternative Purchase Orders

**File:** `models/purchase.py`

| Field | Type | Description |
|---|---|---|
| `alternative_po_ids` | `One2many` | Related POs in the same group (`purchase.order.group`) |

**`purchase.order.line` Extension:**

| Field | Type | Description |
|---|---|---|
| `purchase_group_id` | `Many2one` | `purchase.order.group` linking POs from the same requisition |

**`purchase.order.group` Model:**

| Field | Type | Description |
|---|---|---|
| `order_ids` | `One2many` | Purchase orders in this group |

Used to track and compare alternative purchase orders created from the same requisition. Users can create multiple POs (alternative vendors) and compare them before awarding one.

---

## Blanket Orders

**Blanket Order Flow:**

1. Create a `purchase.requisition` with `requisition_type = 'blanket_order'`
2. Add lines with pre-agreed `price_unit` values
3. Set `vendor_id` to the preferred supplier
4. Confirm the requisition (moves to `in_progress`)
5. When products are needed, create POs that reference the blanket order:
   - The PO inherits `price_unit` and `product_description_vendor` from requisition lines
   - `qty_ordered` on requisition lines is tracked as POs are confirmed

**Key Method:** `_create_supplier_info()` on `purchase.requisition`

Creates or updates `product.supplierinfo` records when a blanket order is confirmed:
- Sets `partner_id` = `requisition_id.vendor_id`
- Sets `price` = requisition line `price_unit`
- Sets `currency_id` from requisition

This syncs the blanket order pricing into the product's vendor price list.

---

## Calls for Bids

**Call for Bids Flow:**

1. Create a `purchase.requisition` of type `purchase_template_view`
2. Add product lines with quantities
3. Confirm the requisition
4. Send RFQs to multiple vendors:
   - Each vendor receives an RFQ (PO in `draft` state)
   - Vendors submit their best prices
5. Compare bids using the requisition form:
   - Multiple POs are linked to the same requisition
   - `price_unit` on each PO line reflects the vendor's quote
6. Award to selected vendor(s):
   - Confirm the chosen PO(s)
   - Other alternative POs can be cancelled

**RFQ Generation:**

When a requisition is in `in_progress` state, the user can trigger:
- `action_create_purchase_orders()` - Creates POs for selected lines to the `vendor_id`
- Or individually create POs per vendor

---

## create_purchase_order() Method

**File:** `models/purchase_requisition.py`

```python
def create_purchase_order(self):
```

Creates one or more purchase orders from the requisition:

- If `vendor_id` is set: creates a single PO to that vendor with all lines
- If `vendor_id` is not set: creates separate POs for each vendor based on line suppliers
- Sets `requisition_id` on created POs
- Links PO lines to requisition lines via `requisition_line_id`

For blanket orders: the PO inherits pre-agreed pricing.
For calls for bids: the PO is created as a draft RFQ for vendor comparison.

---

## quantity_in_POs Computation

**File:** `models/purchase_requisition.py`

```python
@api.depends('line_ids.purchase_line_ids.product_qty')
def _compute_quantity_in_po(self):
    for requisition in self:
        for line in requisition.line_ids:
            line.qty_ordered = sum(line.purchase_line_ids.mapped('product_qty'))
```

Tracks how much of each requisition line has been ordered through purchase orders. This allows monitoring blanket order fulfillment against original quantities.

---

## Key Workflows

### Blanket Order Procurement

```
Requisition (blanket_order, vendor_id set)
  └─> Lines with pre-agreed price_unit
       └─> PO created referencing requisition
            └─> price_unit inherited from requisition line
                 └─> qty_ordered tracked on requisition line
```

### Call for Bids Procurement

```
Requisition (purchase_template_view, no single vendor)
  └─> Lines with quantities
       └─> Multiple RFQs sent to different vendors
            └─> Multiple POs (draft) created
                 └─> User compares prices
                      └─> One PO confirmed, others cancelled
```

---

## Integration Points

### With `purchase`
- `purchase.order` gets `requisition_id` linking it to a requisition
- `purchase.order.line` can pull pricing from `requisition_line_id`
- Alternative POs tracked via `purchase.order.group`

### With `product`
- Blanket orders create `product.supplierinfo` entries for vendor pricing
- `supplierinfo_id` on requisition lines tracks vendor product info

### With `stock`
- `schedule_date` and `dest_address_id` flow into PO and delivery

---

## Dependencies

```
purchase
  └── purchase_requisition
```

Auto-installed with `purchase` in standard installations.