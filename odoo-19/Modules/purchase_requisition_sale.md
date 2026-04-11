---
date: 2026-04-11
tags:
  - odoo
  - odoo19
  - modules
  - purchase
  - sale
  - procurement
  - subcontracting
---

# purchase_requisition_sale

# Module Overview

| Attribute | Value |
|-----------|-------|
| Technical Name | `purchase_requisition_sale` |
| Category | Supply Chain / Purchase |
| Version | 1.0 |
| Depends | `purchase_requisition`, `sale_purchase` |
| Auto-install | Yes |
| License | LGPL-3 |
| Author | Odoo S.A. |
| Files | `__manifest__.py`, `wizard/purchase_requisition_create_alternative.py`, `tests/test_purchase_requisition_sale.py` |

`purchase_requisition_sale` is a minimal bridge module with exactly one purpose: preserve the `sale_line_id` forward-reference on purchase order lines when the purchase requisition wizard creates alternative RFQs for subcontracted services.

**Module path:** `~/odoo/odoo19/odoo/addons/purchase_requisition_sale/`

---

## L1 — purchase.requisition Extensions: How Sale Orders Feed into Purchase Requisitions

### The Problem This Module Solves

The Odoo procurement-for-subcontracting flow involves three modules working together:

1. **`sale_purchase`** (dependency): When a `sale.order` is confirmed, any line where `product_id.service_to_purchase = True` automatically triggers `_purchase_service_generation()`, which creates a draft `purchase.order` (RFQ) linked back to the `sale.order.line` via `sale_line_id`.

2. **`purchase_requisition`** (dependency): Provides the **Create Alternative** action on any RFQ. This opens the `purchase.requisition.create.alternative` wizard, which generates competing RFQs from different vendors so buyers can compare prices side-by-side.

3. **`purchase_requisition_sale`** (this module): The wizard in step 2 does not know about `sale_line_id`. Without this bridge, the alternative PO's lines lose the link back to the originating `sale.order.line`.

### The Failure Mode (Without the Bridge)

When a buyer confirms a sale order containing a subcontracted service:

```
sale.order confirmed
  └─ sale.order.line (service_to_purchase=True)
        └─ _purchase_service_generation()
              └─ purchase.order created, purchase.order.line.sale_line_id = SOL.id
                    └─ action_create_alternative() → wizard creates alt PO
                          └─ WITHOUT bridge: alt PO line has sale_line_id = False
                                ├─ sale.order.purchase_order_count undercounts (misses alt PO)
                                ├─ purchase.order._get_sale_orders() returns empty for alt PO
                                └─ SO's procurement reporting is incomplete
```

### How Sale Orders Feed into Purchase Requisitions

The bridge preserves the cross-document linkage at the point where the alternative PO is created. The `sale.order` does not directly "feed into" a `purchase.requisition` — rather, the `purchase.order` generated from the SO becomes the **origin PO** for the alternative PO flow. The bridge ensures the alternative PO's lines retain the `sale_line_id` that the origin PO already had.

### Dependency Chain

```
sale
  └─ purchase
        ├─ sale_purchase           (sale.order ←→ purchase.order linkage, auto-PO creation)
        └─ purchase_requisition   (blanket orders, alternative PO wizard)
              └─ purchase_requisition_sale  ← this bridge
```

The module has no models of its own, no data files, no security files, and no views. It contains only one override of one wizard method.

---

## L2 — Field Types, Defaults, Constraints

Since this module introduces no new models or fields, L2 covers the one method override's data flow.

### `purchase.requisition.create.alternative` Wizard — Method Override

File: `wizard/purchase_requisition_create_alternative.py`

```python
class PurchaseRequisitionCreateAlternative(models.TransientModel):
    _inherit = 'purchase.requisition.create.alternative'

    @api.model
    def _get_alternative_line_value(self, order_line, product_tmpl_ids_with_description):
        res_line = super()._get_alternative_line_value(
            order_line, product_tmpl_ids_with_description
        )
        if order_line.sale_line_id:
            res_line['sale_line_id'] = order_line.sale_line_id.id
        return res_line
```

#### Method Signature

| Parameter | Type | Description |
|-----------|------|-------------|
| `order_line` | `purchase.order.line` record | The line from the origin PO being copied |
| `product_tmpl_ids_with_description` | `set` of `int` | Product template IDs that have supplier descriptions (used to decide whether to copy the `name` field) |

#### Return Value

| Type | Description |
|------|-------------|
| `dict` | Field values to pass to `Command.create()` for the new PO line |

#### What the Parent Builds (for context)

The parent method (in `purchase_requisition`) returns:

```python
{
    'product_id': order_line.product_id.id,
    'product_qty': order_line.product_qty,
    'product_uom_id': order_line.product_uom_id.id,
    'display_type': order_line.display_type,
    'analytic_distribution': order_line.analytic_distribution,
    # 'name' conditionally added for notes/sections or when no supplier description
}
```

This bridge appends:

```python
{
    # ... from parent ...
    'sale_line_id': order_line.sale_line_id.id,   # ← bridge addition
}
```

#### Field Being Set

| Field | Target Model | Type | Index | Notes |
|-------|-------------|------|-------|-------|
| `sale_line_id` | `purchase.order.line` | `Many2one(sale.order.line)` | `btree_not_null` (on target) | Set only when `order_line.sale_line_id` is truthy; absent otherwise |

#### Guard Condition

```python
if order_line.sale_line_id:   # Many2one field: truthy when set, falsy when False/empty
```

The `if` guard prevents writing `sale_line_id: False` onto lines that have no SO link (e.g., regular purchase-only products). Writing `False` to a `Many2one` field is generally safe (ORM treats it as unsetting), but the guard avoids an unnecessary ORM write call.

---

## L3 — Cross-Model Integration: Sale ↔ Purchase Requisition

### Cross-Model Relationship Chain

```
sale.order
  └─ sale.order.line  (service_to_purchase=True)
        └─ purchase.order.line  (sale_line_id = SOL.id)   ← created by sale_purchase
              └─ purchase.order  (origin = SO.name)
                    └─ action_create_alternative()
                          └─ purchase.requisition.create.alternative
                                └─ _get_alternative_line_value()
                                      └─ purchase.order.line  (NEW alternative PO)
                                            sale_line_id = SOL.id  ← bridge preserves
```

### `sale_line_id` — The Cross-Module Key Field

The `sale_line_id` field is defined in `sale_purchase/models/purchase_order.py`:

```python
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    sale_line_id = fields.Many2one(
        'sale.order.line',
        string="Origin Sale Item",
        index='btree_not_null',
        copy=False
    )
    sale_order_id = fields.Many2one(
        related='sale_line_id.order_id',
        string="Sale Order"
    )
```

This field is the anchor that ties every PO line back to its originating SOL. It is set by `sale_purchase`'s `_purchase_service_prepare_line_values()`:

```python
purchase_line_vals = {
    # ...
    'sale_line_id': self.id,   # ← sale_purchase sets this
}
```

### Override Pattern

**Pattern used:** Classic `_inherit` override of a single method on a wizard.

```
Class:  PurchaseRequisitionCreateAlternative
_inherit: 'purchase.requisition.create.alternative'
File:   wizard/purchase_requisition_create_alternative.py
Method: _get_alternative_line_value()
```

The override is **additive only** — it never removes or replaces parent keys. The bridge is purely additive.

### Workflow Trigger — From Sale Order to Requisition Alternative

```
Step 1:  Sale order confirmed
           sale.order._action_confirm()
             └─ sale_order_line._purchase_service_generation()
                   └─ purchase.order created with sale_line_id set

Step 2:  Buyer opens the PO, clicks "Create Alternative"
           purchase.order.action_create_alternative()
             └─ Opens wizard with context {'default_origin_po_id': self.id}

Step 3:  Buyer selects alternate vendor(s), sets copy_products=True
           wizard.action_create_alternative()
             └─ _get_alternative_values()
                   └─ For each partner, loops over origin_po_id.order_line
                         └─ _get_alternative_line_value()
                               ├─ Parent builds: {product_id, product_qty, ...}
                               └─ Bridge adds:  {sale_line_id: SOL.id}

Step 4:  Alternative PO created with context['origin_po_id']
           purchase.order.create() with context
             └─ purchase_requisition.models.purchase.PurchaseOrder.create()
                   └─ purchase.order.group created linking origin + alternatives

Step 5:  Alternative confirmed
           ├─ sale.order.purchase_order_count = 2  ← bridge makes this correct
           └─ purchase.order._get_sale_orders() = [sale.order]  ← bridge makes this work
```

### Failure Mode — What Breaks Without the Bridge

| Failure Point | Mechanism |
|--------------|-----------|
| `sale.order.purchase_order_count` undercounts | `_compute_purchase_order_count` uses `order._get_purchase_orders()` which traverses `order_line.purchase_line_ids.order_id`. Alt PO lines have no `sale_line_id`, so they are not in `purchase_line_ids` of the SOL. |
| `purchase.order._get_sale_orders()` returns empty for alt PO | The method returns `self.order_line.sale_line_id.order_id`. Without `sale_line_id` on alt PO lines, nothing is returned. |
| Activity notification from SO cancellation misses alt PO | `_activity_cancel_on_purchase()` searches `purchase.order.line` with `sale_line_id in SOL.ids`. Alt PO lines not found. |
| SO quantity-increase creates new line on wrong PO | `_purchase_increase_ordered_qty()` matches by `sale_line_id`. Without it, the new line goes to the origin PO only, not to the alt PO if it was chosen. |

---

## L4 — Version Change Odoo 18 → 19, Security, and Complete Test Coverage

### Odoo 18 → 19 Changes

The `purchase_requisition_sale` module is **structurally identical** between Odoo 18 and Odoo 19. No API changes, no new fields, no method signature changes.

The underlying `purchase_requisition` module (parent wizard's host) saw the `price_total_cc` field added for cross-currency comparison in tender comparisons — this is handled entirely within `purchase_requisition` and has no effect on this bridge.

```diff
# No changes to purchase_requisition_sale between Odoo 18 and 19
- __manifest__.py: version '1.0', unchanged
- wizard: single method, unchanged signature
- tests: same scenarios covered
```

### Security Analysis

| Aspect | Detail | Rating |
|--------|--------|--------|
| New models introduced | None | — |
| ACL introduced | None | — |
| Elevated privileges | None (`sudo()` not used) | — |
| SQL operations | None | — |
| Wizard context | Uses caller's environment; no new access granted | Low risk |
| Field written | `sale_line_id` (Many2one forward reference) | Read-only relationship; does not grant access |

**Security assessment:** The bridge module is a pure additive patch. It does not introduce any new access control concerns. The `sale_line_id` is a forward reference — setting it on a PO line does not grant the PO's user any additional read access to the `sale.order` or `sale.order.line` records.

The `purchase_group_id` mechanism (handled entirely in `purchase_requisition`) ensures all alternative POs are linked in a group, so a buyer with PO access can see all alternatives regardless of SO permissions.

### Complete Test Coverage

File: `tests/test_purchase_requisition_sale.py`

Class: `TestPurchaseRequisitionSale`

```python
@classmethod
def setUpClass(cls):
    super().setUpClass()
    cls.client = cls.env['res.partner'].create({'name': 'Client'})
    cls.vendor_1 = cls.env['res.partner'].create({'name': 'Vendor 1'})
    cls.vendor_2 = cls.env['res.partner'].create({'name': 'Vendor 2'})

    cls.sub_service = cls.env['product.product'].create({
        'name': 'Subcontracted service',
        'type': 'service',
        'seller_ids': [Command.create({
            'partner_id': cls.vendor_1.id,
            'price': 10.0,
            'delay': 0,
        })],
        'service_to_purchase': True,   # key flag
    })
```

**`test_01_purchase_requisition_services`** — Complete scenario:

```
1. Creates sale.order with sub_service line, confirms it
   └─ sale_purchase auto-creates RFQ (vendor_1) linked to SOL

2. Asserts sale_order.purchase_order_count == 1
   └─ PASS means auto-creation worked

3. Calls purchase_order.action_create_alternative(), selects vendor_2
   └─ Sets copy_products=True, saves wizard

4. Asserts purchase_order.alternative_po_ids has 2 POs
   └─ PASS means purchase.order.group created correctly

5. Gets the alternative PO, calls _get_sale_orders()
   └─ Asserts len == 1 and equals the original sale_order
        ↑ THIS is the key assertion the bridge enables

6. Asserts sale_order.purchase_order_count == 2
   └─ PASS means bridge correctly propagates SO link to alt PO
```

**Assertions in order:**

| # | Assertion | What it proves |
|---|-----------|----------------|
| 1 | `sale_order.purchase_order_count == 1` | `sale_purchase` auto-PO creation works |
| 2 | `len(purchase_order) == 1` | Only one PO linked to SO initially |
| 3 | `len(alternative_po_ids) == 2` | `purchase.order.group` created, origin + alt linked |
| 4 | `len(alt_po._get_sale_orders()) == 1` | Bridge preserves `sale_line_id` on alt PO |
| 5 | `alt_po._get_sale_orders().id == sale_order.id` | Alt PO returns correct SO |
| 6 | `sale_order.purchase_order_count == 2` | `purchase_order_count` correctly counts all POs |

---

## Module Structure

```
purchase_requisition_sale/
├── __init__.py
├── __manifest__.py      # depends: purchase_requisition, sale_purchase; auto_install: True
├── wizard/
│   ├── __init__.py
│   └── purchase_requisition_create_alternative.py   # single method override
└── tests/
    ├── __init__.py
    └── test_purchase_requisition_sale.py            # 1 integration test
```

---

## Edge Cases

| Scenario | Behavior |
|---------|----------|
| Alternative PO for a non-service product (no `sale_line_id`) | `if order_line.sale_line_id:` guard skips; no `sale_line_id` key added — correct behavior |
| Multiple alternative POs from same origin | Each alt PO line gets the same `sale_line_id`; all correctly linked to the same SO |
| Buyer cancels origin PO after alt PO created | `sale_purchase._activity_cancel_on_sale()` schedules activity on alt PO; bridge does not affect this |
| SO line quantity increased after alt PO confirmed | `sale_purchase._purchase_increase_ordered_qty()` uses `sale_line_id` to find the right PO; works correctly with bridge |
| PO created directly from blanket order (no SO involved) | No `sale_line_id` on lines; wizard override is a no-op — correct |
| `copy_products=False` in wizard | No lines are created, so `sale_line_id` is never needed — wizard works correctly |

---

## File Paths

| File | Absolute Path |
|------|-------------|
| Manifest | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_sale/__manifest__.py` |
| Wizard override | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_sale/wizard/purchase_requisition_create_alternative.py` |
| Tests | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition_sale/tests/test_purchase_requisition_sale.py` |
| Parent wizard (`purchase_requisition`) | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition/wizard/purchase_requisition_create_alternative.py` |
| `purchase.order` extensions (`purchase_requisition`) | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition/models/purchase.py` |
| `purchase.requisition` model | `/Users/tri-mac/odoo/odoo19/odoo/addons/purchase_requisition/models/purchase_requisition.py` |
| `sale.order.line` service generation (`sale_purchase`) | `/Users/tri-mac/odoo/odoo19/odoo/addons/sale_purchase/models/sale_order_line.py` |
| `purchase.order.line` SO link (`sale_purchase`) | `/Users/tri-mac/odoo/odoo19/odoo/addons/sale_purchase/models/purchase_order.py` |
| `sale.order` SO linkage (`sale_purchase`) | `/Users/tri-mac/odoo/odoo19/odoo/addons/sale_purchase/models/sale_order.py` |

---

## Related Modules

- `[[Modules/Sale]]` — `sale.order`, `sale.order.line`
- `[[Modules/Purchase]]` — `purchase.order`, `purchase.order.line`
- `[[Modules/purchase_requisition]]` — blanket orders, tender comparison, alternative PO wizard, `purchase.order.group`
- `purchase_requisition` — host module: `purchase.requisition.create.alternative` wizard, `purchase.order.group`
- `sale_purchase` — creates PO from `service_to_purchase` SOL on SO confirmation; defines `sale_line_id`
