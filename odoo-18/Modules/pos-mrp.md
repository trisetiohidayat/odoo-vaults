---
Module: pos_mrp
Version: Odoo 18
Type: Integration
Dependencies: point_of_sale, mrp
---

# Point of Sale - MRP Integration (`pos_mrp`)

## Overview

`pos_mrp` is a lightweight **hidden** auto-install module that links the Point of Sale to the Manufacturing module. Its purpose is narrowly scoped: it ensures that **phantom kit products** (BOMs of type `phantom` / "Kit" in Odoo MRP) are correctly handled when sold through POS.

**Key architectural role:**
- Extends `pos.order.line` with phantom BOM-aware stock move filtering
- Extends `pos.order` with Anglo-Saxon costing for kit products

Unlike `pos_loyalty` or `pos_sale`, `pos_mrp` does **not** add a large set of models. It contains only one Python file: `models/pos_order.py` which overrides two methods across two models.

> **No `pos.order` is directly created from MRP in Odoo 18.** The MRP integration in POS is solely about phantom kit accounting and stock move handling — made-to-order workflows that create `mrp.production` records are handled by the MRP module itself, not by `pos_mrp`.

---

## Module Structure

```
pos_mrp/
├── models/
│   └── pos_order.py       # pos.order.line + pos.order overrides
└── __manifest__.py        # depends: point_of_sale, mrp; auto_install: True; category: Hidden
```

---

## Phantom Kits at POS

### What is a Phantom BOM?

A **phantom (kit) bill of materials** (`bom_type = 'phantom'`) is a type of BoM where the finished product does not exist as a stocked item. Instead, when the product is sold (or consumed in manufacturing), the system "explodes" it into its component lines. Components are tracked individually; the kit product itself has no inventory.

In POS, when a customer orders a kit product:
- The `pos.order.line` records the kit product and quantity
- Stock moves should be generated for the **components**, not the kit itself
- The cost price for Anglo-Saxon accounting must account for component costs

`pos_mrp` handles both of these scenarios.

---

## `pos.order.line` — Extended

### Method Override

**`_get_stock_moves_to_consider(self, stock_moves, product) -> stock.move recordset`**

Filters stock moves to only those related to this POS order line's product, with special handling for phantom BOMs.

**Logic:**
```python
def _get_stock_moves_to_consider(self, stock_moves, product):
    bom = product.env['mrp.bom']._bom_find(
        product, company_id=stock_moves.company_id.id, bom_type='phantom'
    ).get(product)
    if not bom:
        return super()._get_stock_moves_to_consider(stock_moves, product)

    # Explode the kit into its components
    boms, components = bom.explode(product, self.qty)

    # Flat list of all bom_line_ids (including sub-BOM lines)
    bom_line_ids = [item for x in boms for item in x[0].bom_line_ids.ids]

    # Products from the kit
    ml_product_to_consider = (
        (product.bom_ids and [comp[0].product_id.id for comp in components])
        or [product.id]
    )

    # Filter stock_moves: component products + matching bom_line_id
    return stock_moves.filtered(
        lambda ml: ml.product_id.id in ml_product_to_consider
        and (ml.bom_line_id.id in bom_line_ids)
    )
```

**L4 — Why `bom_line_ids` is flattened:**
When a phantom BOM contains sub-assemblies that are themselves phantom kits, `bom.explode()` returns multiple BOMs in the `boms` list. Flattening `bom_line_ids` across all returned BOMs ensures that even deeply nested component moves are included.

**L4 — `ml_product_to_consider` fallback:**
If the product has no BOMs (`not product.bom_ids`), the fallback is the product itself — meaning non-kit products pass through to the parent's standard logic.

---

## `pos.order` — Extended

### Method Override

**`_get_pos_anglo_saxon_price_unit(self, product, partner_id, quantity) -> float`**

Computes the Anglo-Saxon (landed cost) price unit for a product, with special handling for phantom kit products.

**Logic:**
```python
def _get_pos_anglo_saxon_price_unit(self, product, partner_id, quantity):
    bom = product.env['mrp.bom']._bom_find(
        product,
        company_id=self.mapped('picking_ids.move_line_ids').company_id.id,
        bom_type='phantom'
    )[product]

    if not bom:
        return super()._get_pos_anglo_saxon_price_unit(...)

    _dummy, components = bom.explode(product, quantity)

    total_price_unit = 0
    for comp in components:
        # Get Anglo-Saxon price of the component
        price_unit = super()._get_pos_anglo_saxon_price_unit(
            comp[0].product_id, partner_id, comp[1]['qty']
        )
        # Convert from sale UoM to component's product UoM
        price_unit = comp[0].product_id.uom_id._compute_price(
            price_unit, comp[0].product_uom_id
        )
        # Pro-rate by quantity fraction in the kit
        qty_per_kit = (
            comp[1]['qty'] / bom.product_qty / (quantity or 1)
        )
        total_price_unit += price_unit * qty_per_kit

    return total_price_unit
```

**L4 — Anglo-Saxon Costing for Kits:**

In Anglo-Saxon ( perpetual) accounting, cost of goods sold is recorded at the same time as the sale. For a kit sold at POS:
- The kit product's cost is the **sum of its component costs**
- `super()._get_pos_anglo_saxon_price_unit()` fetches the component's cost using the standard product costing mechanism (FIFO/AVCO from stock valuation)
- `uom_id._compute_price()` converts from the sale unit (e.g., "Units" of the kit) to the component's unit of measure (e.g., "kg" of flour in the kit)
- `qty_per_kit` calculates the fraction: if the kit contains 2kg of flour per kit unit, and the order is for 3 kits, then `qty_per_kit = 2 / 1 / 3` = proportion of flour cost attributable to each kit unit

**L4 — Why `bom.explode()` instead of `bom.bom_line_ids`:**
`explode()` recursively processes multi-level BOMs (phantom sub-assemblies) and handles the `product_qty` multiplier correctly. Direct `bom_line_ids` access would miss nested components.

---

## POS → MRP Flow (Made-to-Order)

`pos_mrp` does **not** implement made-to-order (MTO) manufacturing triggers. In Odoo 18, MTO flows at POS are handled by the core MRP module's rules engine, triggered when:

1. A `pos.order` is validated and `stock.picking` records are created
2. If the product's `route_id` includes "Manufacture" (MTO), the MRP module's stock rule fires
3. `mrp.production` is created by the stock rule (via `stock.rule` action)
4. The POS picking's moves are linked to the production order's moves

`pos_mrp`'s role is solely in the **costing and inventory** layers — ensuring component moves are properly accounted for when the POS order is confirmed.

---

## L4: Kitchen Display / Manufacturing Orders Triggered from POS

Kitchen display (KDU) functionality is in the core **POS** module (`point_of_sale`), not in `pos_mrp`. When a POS order with a kitchen-orderable product is paid:

1. The `pos.order` creates a `pos.order.line` for the product
2. If the product has `pos_categ_id` with kitchen screen enabled, it appears on the kitchen display
3. The chef marks items as prepared
4. The POS order continues to delivery/invoicing

`pos_mrp` is unrelated to kitchen display — it only handles phantom BOM accounting.

---

## Constraints and Limitations

| Aspect | Behavior |
|---|---|
| Non-phantom BOMs (`normal`, `kit`) | Ignored by `pos_mrp`; handled by base `pos.order.line` |
| Multi-level phantom BOMs | Supported via `bom.explode()` flattening |
| MTO (manufacture to order) | Handled by MRP stock rules, not `pos_mrp` |
| Work orders | Not created by `pos_mrp`; MTO MO work orders created by MRP module |
| Manufacturing lead times | Not affected by `pos_mrp` |

---

## L4: POS Order → Stock Picking → MRP Production Sequence

```
pos.order (kit product qty=3)
  └─ _create_picking()
       └─ Stock move for kit product created
            └─ MRP stock rule (if route= Manufacture)
                 └─ mrp.production created (qty=3)
                      └─ work orders scheduled
                      └─ components reserved from stock

pos.order.line: _get_stock_moves_to_consider()
  └─ Filters stock_moves to kit components
  └─ Only components considered for availability/picking

pos.order: _get_pos_anglo_saxon_price_unit()
  └─ Called during order-line cost computation
  └─ Explodes kit → sums component costs
  └─ Used for real-time margin display at POS

pos.order: _create_invoice()
  └─ Anglo-Saxon price_unit used for COGS journal entry
  └─ Cost = sum(component costs) × qty
```

---

## Related Documentation

- [Modules/Point of Sale](Modules/Point-of-Sale.md) — POS core
- [Modules/MRP](odoo-18/Modules/mrp.md) — Manufacturing module
- [Modules/Stock](odoo-18/Modules/stock.md) — Inventory and stock moves
- [Core/API](odoo-18/Core/API.md) — ORM method overrides, `_compute`, `@api.depends`

#odoo #odoo18 #pos_mrp #mrp #phantom-bom #anglo-saxon #point_of_sale
