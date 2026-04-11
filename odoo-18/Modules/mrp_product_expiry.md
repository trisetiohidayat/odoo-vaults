# mrp_product_expiry — MRP Product Expiry

**Tags:** #odoo #odoo18 #mrp #product #expiry #quality
**Odoo Version:** 18.0
**Module Category:** MRP + Quality / Product Expiry
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`mrp_product_expiry` integrates the product expiry (lot retirement) checking with MRP production orders. When a production order is marked done, it checks whether any component lots have passed their expiry date and prompts the user for confirmation before completing.

**Technical Name:** `mrp_product_expiry`
**Python Path:** `~/odoo/odoo18/odoo/addons/mrp_product_expiry/`
**Depends:** `mrp`, `product_expiry`
**Inherits From:** `mrp.production`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/mrp_production.py` | `mrp.production` | Expiry check before production completion |

---

## Models Reference

### `mrp.production` (models/mrp_production.py)

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `pre_button_mark_done()` | — | Calls `_check_expired_lots()`, returns confirmation wizard if expired lots found |
| `_check_expired_lots()` | — | Returns action to open `expiry.picking.confirmation` wizard if component lots have `product_expiry_alert` set |

#### Critical Flow

```
User clicks "Mark as Done" (button_mark_done)
  → pre_button_mark_done()
    → _check_expired_lots()
      → If raw material lots have expired: returns confirmation wizard
      → If no expired lots: proceeds with super().pre_button_mark_done()
```

**Expired lot detection:**
```python
expired_lot_ids = self.move_raw_ids.move_line_ids.filtered(
    lambda ml: ml.lot_id.product_expiry_alert  # lot has passed its expiration date
).lot_id.ids
```

**Context for wizard:**
```python
context = {
    'default_lot_ids': [(6, 0, expired_lot_ids)],
    'default_production_ids': self.ids,
}
```

The wizard (`expiry.picking.confirmation`) allows the user to confirm or cancel. When confirmed with `skip_expired=True`, the production can proceed.

---

## Wizard Reference

The confirmation wizard is `confirm.expiry` (defined in `wizard/confirm_expiry.py`, which is a standard Odoo wizard from the `product_expiry` module reused here).

| Context Key | Purpose |
|-----------|---------|
| `skip_expired` | When True, `_check_expired_lots()` returns False (skips the check) |
| `default_lot_ids` | List of expired lot IDs for display |
| `default_production_ids` | Production orders being processed |

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Per-Production Check**: The expiry check runs per production order. Multiple production orders can be processed simultaneously, but the wizard handles each set independently.

2. **Component-Only Check**: Only `move_raw_ids` (component consumption moves) are checked. The finished product lot is not checked for expiry in this module.

3. **`product_expiry_alert` Flag**: This flag on `stock.lot` is set automatically by the `product_expiry` module when the lot's `expiration_date` has passed. The logic is handled in `product_expiry/models/stock_lot.py`.

4. **Skippable**: The user can proceed with using expired components after confirmation, so this is a warning/informed consent flow, not a hard block.

5. **Uses `pre_button_mark_done()`**: This method is the pre-validation hook called by the "Mark as Done" button on production orders (not the same as `action_mark_done()`). It returns an action dict (wizard) or `True` to proceed.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified. Module structure remains consistent.

---

## Notes

- This module is small (1 model file, ~40 lines of logic) but addresses a critical quality assurance use case
- The `skip_expired` context key is the mechanism for the wizard to bypass the check after user confirmation
- Reuses the `expiry.picking.confirmation` wizard from `product_expiry`, making the UX consistent across stock and manufacturing modules
