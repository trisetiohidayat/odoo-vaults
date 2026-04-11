# sale_mrp_margin — Sale MRP Margin

**Tags:** #odoo #odoo18 #sale #mrp #margin #bom #phantom-kit
**Odoo Version:** 18.0
**Module Category:** Sale + MRP + Margin Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_mrp_margin` bridges the gap between MRP kit (phantom BoM) products and sale margin computation. When a kit product is sold, the margin should reflect the component costs tracked through manufacturing — not a zero or static purchase price. This module ensures `sale_stock_margin`'s `_compute_purchase_price()` correctly traces kit component costs via the MRP production chain.

**Technical Name:** `sale_mrp_margin`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_mrp_margin/`
**Depends:** `sale_mrp`, `sale_stock_margin`
**Inherits From:** (data-only module — no Python models)

---

## Module Structure

`sale_mrp_margin` is a **data/metadata-only module** — it has no `models/` directory. All behavior is driven by dependency ordering:

```
addons/sale_mrp_margin/
├── __init__.py
├── __manifest__.py
```

The module exists purely to sequence `sale_mrp` (kit logic) before `sale_stock_margin` (margin computation) in the load order, ensuring that when `_compute_purchase_price()` runs on a kit SOL, the MRP component cost chain is already in place.

---

## `__manifest__.py`

```python
{
    'name': "Sale Mrp Margin",
    'category': 'Sales/Sales',
    'version': '0.1',
    'description': 'Handle BoM prices to compute sale margin.',
    'depends': ['sale_mrp', 'sale_stock_margin'],
    'license': 'LGPL-3',
}
```

**Key points:**
- `depends` ordering is intentional: `sale_mrp` must load before `sale_stock_margin`
- No data files, no models, no controllers
- Version `0.1` indicates this is a thin integration module

---

## How It Works

### Dependency Chain for Kit Margin

The full margin computation chain for a kit product sold via `sale_mrp`:

```
sale.order.line (kit product)
  → _compute_purchase_price()
      → sale_stock_margin: uses valued moves + avg price
          → sale_mrp_margin: ensures MRP component costs are resolved first
              → sale_mrp: _get_bom_component_qty(), phantom kit handling
                  → mrp.production: component consumption tracked via stock.moves
                      → purchase_stock: component purchase price from PO
```

### Phantom BoM Behavior

`sale_mrp` changes how kit products flow through the stock:
- A kit (phantom BoM) SOL does not create a `mrp.production` directly
- Instead, the kit's component moves are generated at `_action_launch_stock_rule()` time
- `sale_mrp_margin` ensures the component-level purchase price flows back to the kit's SOL

### Cost Share (mrp_bom_line)

The `cost_share` field on `mrp.bom.line` (from `purchase_mrp`) allows proportional cost attribution:
- A kit with 2 components at 60%/40% cost share uses those ratios when computing the kit's implied purchase price
- `sale_mrp_margin` does not directly use `cost_share` — that is handled by `purchase_mrp`'s `_get_price_unit()` override

---

## Security File

No security file.

---

## Data Files

None — this module has no data files.

---

## Critical Behaviors

1. **No Code, Only Ordering**: The module contributes nothing in terms of Python code. Its sole purpose is ensuring the right dependency order so that `sale_mrp`'s kit-handling logic is active when `sale_stock_margin` computes purchase prices.

2. **Phantom Kit Margin**: Without this module, a kit SOL's `purchase_price` might fall back to the product's standard price (often zero or outdated). With it, the component-level Anglo-Saxon (real-time) or average cost flows through.

3. **Dependency is Load Order**: Odoo loads modules in dependency order. By depending on both, the module ensures `sale_mrp` is fully initialized before `sale_stock_margin` runs its `_compute_purchase_price()` on kit lines.

---

## v17→v18 Changes

- No significant structural changes from v17 to v18
- Module continues to rely on `sale_mrp` phantom kit handling and `sale_stock_margin` purchase price computation

---

## Notes

- This module is always installed alongside `sale_mrp` and `sale_stock_margin` in manufacturing-aware sales deployments
- For a fully featured margin picture on kit sales, also consider `purchase_mrp` which adds `cost_share` to `mrp.bom.line` for proportional component pricing
- The combined stack is: `sale` + `sale_mrp` + `sale_stock` + `sale_stock_margin` + `sale_mrp_margin` + `purchase_stock` + `purchase_mrp`
