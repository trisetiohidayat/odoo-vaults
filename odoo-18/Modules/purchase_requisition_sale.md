# purchase_requisition_sale — Purchase Requisition Sale

**Tags:** #odoo #odoo18 #purchase #requisition #sale #outsourcing #service
**Odoo Version:** 18.0
**Module Category:** Purchase + Sale + Requisition Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`purchase_requisition_sale` bridges purchase requisitions with the sale-purchase outsourcing chain (from `sale_purchase`). When a purchase requisition is created to source services subcontracted from a sale order, this module ensures the `sale_line_id` link is propagated from the requisition line to the alternative PO lines, maintaining the full SO→PO↔requisition traceability chain.

**Technical Name:** `purchase_requisition_sale`
**Python Path:** `~/odoo/odoo18/odoo/addons/purchase_requisition_sale/`
**Depends:** `purchase_requisition`, `sale_purchase`
**Auto-install:** True

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `wizard/purchase_requisition_create_alternative.py` | `purchase.requisition.create.alternative` (wizard) | Passes `sale_line_id` through to alternative PO lines |

**No core model files** — the module only overrides the wizard.

---

## Wizard

### `purchase.requisition.create.alternative`

**File:** `wizard/purchase_requisition_create_alternative.py` (lines 10–20)

Inherits the standard alternative PO creation wizard from `purchase_requisition`.

**Key Methods:**

- `_get_alternative_line_value(order_line)` (line 13) — Override. Copies `sale_line_id` from the requisition line to the alternative PO line, preserving the SO↔PO link across the full procurement chain.

---

## Design Notes

#### Why This Module Exists

`sale_purchase` creates a PO from a SOL when `service_to_purchase = True`. The PO is linked to the SOL via `sale_line_id`.

When a **purchase requisition** is used instead of a direct PO, the alternative PO wizard (`purchase.requisition.create.alternative`) generates a new PO from the requisition. Without this module, the `sale_line_id` would be **lost** in that process — the wizard's default `_get_alternative_line_value()` doesn't pass through the SO link.

`purchase_requisition_sale` fixes this by overriding `_get_alternative_line_value()` to preserve `sale_line_id`:

```python
def _get_alternative_line_value(self, order_line):
    res = super()._get_alternative_line_value(order_line)
    if order_line.sale_line_id:
        res['sale_line_id'] = order_line.sale_line_id.id
    return res
```

---

## Security File

No security file.

---

## Data Files

None.

---

## Critical Behaviors

1. **`sale_line_id` Propagation**: The key behavior is that when a PO is created from a requisition (via the "Create Alternative" wizard), any SOL link from the requisition line is copied to the new PO line. This maintains the full traceability chain: SO → SOL → PO Line ↔ Requisition Line.

2. **Auto-install**: With `auto_install: True`, this module is automatically activated when `purchase_requisition` and `sale_purchase` are both installed — no manual installation needed.

3. **Service Outsourcing Chain**: The full chain this module completes is:
   ```
   sale.order (SO with service product)
     → sale.order.line (service_to_purchase=True)
       → purchase.requisition (for sourcing the service)
         → purchase.requisition.create.alternative wizard
           → purchase.order.line (with sale_line_id preserved ← THIS MODULE)
   ```

4. **Conditional**: Only copies `sale_line_id` if it exists on the order line — the override is safe and backward-compatible.

---

## v17→v18 Changes

- No significant changes from v17 to v18
- Module structure remains consistent

---

## Notes

- This is a minimal but critical module for B2B service outsourcing scenarios where purchase requisitions are used alongside the standard sale_purchase flow
- The `sale_line_id` on `purchase.order.line` enables margin computation, project billing, and analytical tracking back to the original SO
- `auto_install` ensures this is always active in combined sale+purchase+requisition deployments
