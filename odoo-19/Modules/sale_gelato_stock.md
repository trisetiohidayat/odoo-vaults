---
type: module
module: sale_gelato_stock
tags: [oddoo, odoo19, sale, gelato, stock, procurement, mto, fulfillment]
created: 2026-04-14
uuid: a1c5e8f2-3d7b-4a9e-8f1c-2b6d4e6a8f3c
---

# Sale Gelato Stock (`sale_gelato_stock`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Sale Gelato Stock |
| **Technical** | `sale_gelato_stock` |
| **Category** | Sales / Sales |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 19.0 |
| **Depends** | `sale_gelato`, `sale_stock` |

The `sale_gelato_stock` module is a bridge module that prevents Odoo's standard stock procurement from creating delivery orders for Gelato print-on-demand products. Gelato is an external fulfillment service that handles printing and shipping directly to end customers. When a sales order contains Gelato products, the order is sent to Gelato's API for fulfillment — Odoo must not simultaneously attempt to create stock pickings for those items, as this would result in duplicate fulfillments.

This module overrides the stock procurement trigger on `sale.order.line` to filter out Gelato product lines before calling the parent method. It is the counterpart to `sale_gelato`, which sends the order to Gelato, and together the two modules ensure that Gelato products follow the external fulfillment flow while non-Gelato products follow the standard Odoo stock flow.

## Architecture

### Design Philosophy

This is a surgical, single-method override. The module does not create new models, new database fields, or new controllers. It simply intercepts the stock procurement call and removes Gelato lines from the processing set before delegating to the parent implementation. This minimal approach ensures maximum compatibility with other modules and the Odoo core.

### Why a Bridge Module?

Odoo's standard `sale_stock` module creates procurement orders (stock moves, pickings) automatically when a sales order is confirmed. This behavior is correct for physical inventory items but is incorrect for print-on-demand products managed by an external fulfillment service.

The options for handling this conflict were:

1. **Modify `sale_gelato` to delete pickings after creation**: Inefficient — creates pickings only to delete them.
2. **Modify the procurement rule to exclude Gelato products**: Complex — requires custom procurement rules per product.
3. **Override `_action_launch_stock_rule()` to filter lines**: Clean — prevents the creation at the source.

The bridge module approach (option 3) is the cleanest and most maintainable solution.

### Module Structure

```
sale_gelato_stock/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale_order_line.py    # Single override of _action_launch_stock_rule
└── security/
    └── ir.model.access.csv
```

### Dependency Chain

```
sale_gelato_stock
├── sale_gelato       (Gelato API integration, product gelato_product_uid field)
│   └── sale           (Sales order and order line models)
└── sale_stock         (Stock procurement from sales, _action_launch_stock_rule)
    ├── sale            (Sale order models)
    └── stock           (Stock moves and pickings)
```

The module depends on both `sale_gelato` and `sale_stock` — it must be installed after both are present, and it extends `sale.order.line` which is provided by `sale` (a transitive dependency of both).

## Models

### `sale.order.line` (Extended)

**File:** `sale_gelato_stock/models/sale_order_line.py`

The only code change in the module is a single method override on `sale.order.line`.

#### `_action_launch_stock_rule()` — Stock Procurement Override

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _action_launch_stock_rule(self, **kwargs):
        """ Override of sale_stock to prevent creating pickings for Gelato products. """
        gelato_lines = self.filtered(lambda l: l.product_id.gelato_product_uid)
        super(SaleOrderLine, self - gelato_lines)._action_launch_stock_rule(**kwargs)
```

**Line-by-line analysis:**

1. **`gelato_lines = self.filtered(...)`**: Filters the current recordset to identify lines where the product has a `gelato_product_uid` field set. The `gelato_product_uid` field is added by `sale_gelato` and stores the product's unique identifier in Gelato's system. If a product has this field populated, it is a Gelato-managed product.

2. **`super(SaleOrderLine, self - gelato_lines)._action_launch_stock_rule(...)`**: Calls the parent method from `sale_stock` with all lines **except** the Gelato lines. The `self - gelato_lines` syntax is a recordset subtraction operation that returns all non-Gelato lines.

3. **`**kwargs` passthrough**: Any keyword arguments passed to the method (e.g., from other modules that extend this method) are forwarded to the parent. This ensures compatibility with other modules that may add parameters to this method.

**What the parent method does (from `sale_stock`):**

The `sale_stock` module's `_action_launch_stock_rule()` iterates over the order lines and, for each line that has a stock route (like "Make to Order" or "Buy"), creates:
- A procurement group
- Stock moves linking the source location to the destination
- If applicable, a `stock.picking` (delivery order) record

By excluding Gelato lines, this method ensures no stock moves or pickings are created for Gelato products.

## How Gelato Fulfillment Works

### The Complete Gelato Flow

```
Customer places order on website (e-commerce or POS)
    ↓
Sale Order created in Odoo
    ↓
Sale Order confirmed (action_confirm)
    ↓
For each order line:
    ├── Gelato product line → sale_gelato sends order to Gelato API
    │                              ↓
    │                         Gelato prints and ships directly
    │                         (no Odoo stock picking)
    │
    └── Non-Gelato product line → sale_gelato_stock blocks procurement
                                      ↓
                                 sale_stock creates picking
                                      ↓
                                 Warehouse ships to customer
```

### Gelato Product Identification

Products are marked as Gelato products by the `sale_gelato` module. This module adds a `gelato_product_uid` field to `product.product`:

```python
# In sale_gelato/models/product.py
gelato_product_uid = fields.Char(
    string='Gelato Product ID',
    help='The product ID in Gelato\'s system. '
         'If set, this product is fulfilled by Gelato.')
```

When a product is synced with Gelato (typically through an API integration), its `gelato_product_uid` is populated with Gelato's product identifier. Products without this field (or with an empty value) are treated as standard Odoo-managed products.

### What Happens Without `sale_gelato_stock`

If `sale_gelato_stock` is not installed but `sale_gelato` is:

1. A sales order with a Gelato product is confirmed.
2. `sale_stock`'s `_action_launch_stock_rule()` is called for all lines.
3. A stock picking is created for the Gelato product.
4. The warehouse receives the picking and attempts to ship a physical product.
5. Simultaneously, Gelato also ships a print-on-demand copy to the customer.
6. Result: **duplicate shipments** and **inventory discrepancies**.

This module prevents step 3 by intercepting the procurement trigger.

## Inventory Check Behavior

The `sale_gelato_stock` module does not prevent Odoo's **inventory availability check** from running. When a sales order line is saved in the backend or POS, Odoo checks whether the product is available in warehouse stock. For Gelato products:

- **Available stock**: The check shows "available" (since Gelato fulfillment is external and not tracked in Odoo stock).
- **Unavailable stock**: A warning is shown, but no procurement is created because the Gelato product is filtered out by this module.

This means Gelato products effectively bypass Odoo's inventory reservation system. Inventory management for Gelato products happens entirely within Gelato's platform.

If you need Gelato products to show "available" regardless of Odoo stock levels, configure the product with:
- **Route**: "Dropship" or "Dropship + MTO" pointing to Gelato's vendor.
- The `sale_gelato_stock` override still prevents the standard warehouse picking.

## Interaction with Other Sale Modules

### With `sale_stock`

`sale_stock` extends `sale.order.line` with the `_action_launch_stock_rule()` method. This module's override calls `super()` with filtered lines, ensuring the parent method only processes non-Gelato lines.

### With `sale_management`

`sale_management` adds order templates and optional order lines. Gelato products in order templates are handled identically to regular order lines — the override filters them out regardless of how they were added to the order.

### With `sale_loyalty`

`sale_loyalty` may add discount lines or free product lines to orders. These are not Gelato products and are processed normally through `sale_stock`. The override has no effect on loyalty program lines.

### With `sale_renting`

`sale_renting` manages rental products with specific return flows. Rental products are not Gelato products and follow the standard stock procurement route.

## Multi-Company Considerations

When `sale_gelato_stock` is used in a multi-company environment:

1. **Gelato product identification**: The `gelato_product_uid` is per-product and is visible across companies (unless restricted via `company_id`). Ensure the Gelato API integration handles company-specific product mapping correctly.

2. **Stock procurement**: The filtered-out Gelato lines do not create pickings in any company. This is correct behavior — Gelato fulfillment is independent of Odoo's company structure.

3. **Reporting**: Sales of Gelato products still appear in sales reports, but they do not appear in stock reports. This is intentional — Gelato fulfillment is external to Odoo's inventory.

## Testing Considerations

When testing `sale_gelato_stock` in a custom module or test suite:

1. Create a Gelato product (with `gelato_product_uid` set) and a non-Gelato product.
2. Create a sales order with both products.
3. Confirm the order.
4. Verify: Gelato product has no stock picking; non-Gelato product has a stock picking.
5. Verify: Both products appear in the sales order's `order_line` records.

## Business Impact

### Preventing Duplicate Shipments

The primary business impact is preventing the most disruptive operational error: sending the same product to the customer twice (once from the warehouse, once from Gelato). In a print-on-demand context, duplicate shipments represent direct financial loss and damage to customer relationships.

### Accurate Inventory Reporting

By preventing Gelato products from entering Odoo's stock system, the module ensures that inventory reports reflect only physically stocked items. Mixing Gelato-managed SKUs with physical inventory would distort stock levels and reorder points.

### Operational Separation

The module maintains a clean separation between two fulfillment models: external (Gelato) and internal (warehouse). Operations teams can manage these flows independently without interference.

## Related

- [Modules/sale_gelato](Modules/sale_gelato.md) — Gelato API integration: order submission, product sync
- [Modules/sale_stock](Modules/sale_stock.md) — Stock procurement from sales orders
- [Modules/sale](Modules/Sale.md) — Sales order and order line models
- [Modules/stock](Modules/Stock.md) — Stock moves, pickings, and warehouse management

## Real-World Scenarios

### Scenario 1: Mixed Order (Gelato + Physical Products)

A customer orders two items on the website:
- **Product A**: A printed marketing brochure (Gelato product, `gelato_product_uid='GL-12345'`)
- **Product B**: A branded USB drive from the warehouse (standard stock product)

The sales order is confirmed:
1. **Product A** (Gelato): `sale_gelato` sends the order to the Gelato API. `sale_gelato_stock` prevents any stock picking from being created. Gelato prints and ships the brochure.
2. **Product B** (Physical): `sale_stock` creates a delivery order from the warehouse. The warehouse team picks, packs, and ships the USB drive.

The customer receives two shipments: one from Gelato (direct), one from the warehouse. Both fulfillments are properly managed with zero confusion.

### Scenario 2: Gelato Product with Warehouse Stock Check

A product is available both as a physical printed item (in local warehouse) and as a print-on-demand item (Gelato). The company uses Gelato primarily for customizations and local warehouse for standard items:

1. The Gelato product has a specific `gelato_product_uid`.
2. For standard orders, a separate non-Gelato product variant is used.
3. The `gelato_product_uid` acts as a clear demarcation between the two fulfillment paths.

### Scenario 3: Gelato API Failure

If the `sale_gelato` module's API call to Gelato fails (e.g., network error, Gelato service unavailable):

1. The order may remain in a "pending Gelato" state.
2. No stock picking is created for Gelato products (this module prevents it).
3. The warehouse team does not attempt to ship a non-existent physical item.
4. Once the Gelato API recovers, `sale_gelato` retries the order submission.

The separation of concerns between `sale_gelato` (Gelato API) and `sale_gelato_stock` (stock blocking) ensures that Gelato failures do not cause warehouse confusion.

## Debugging and Troubleshooting

### Issue: Gelato Products Still Creating Pickings

**Symptoms**: Even with `sale_gelato_stock` installed, delivery orders are created for Gelato products.

**Possible causes**:
1. **Module not installed**: Verify `sale_gelato_stock` is in the installed modules list.
2. **`gelato_product_uid` not set**: The product must have the Gelato product ID populated in `sale_gelato`. Check the product form.
3. **Direct SQL manipulation**: If the procurement was created before the module was installed, existing procurements may still create pickings. Cancel those procurements manually.

### Issue: Gelato Order Not Sent

**Symptoms**: A Gelato product order is confirmed but no order appears in Gelato.

**Possible causes** (checked in `sale_gelato`, not this module):
1. Gelato API credentials are not configured.
2. The `gelato_product_uid` is invalid in Gelato's system.
3. The order failed Gelato's validation (e.g., missing required fields).

## Key Differences from Other Fulfillment Patterns

| Fulfillment Type | Route Used | Procurement Behavior | Odoo Stock Impact |
|-------------------|-----------|----------------------|-------------------|
| **Standard** | MTS (Make to Stock) | Creates procurement → picking | Full impact |
| **MTO** | MTO (Make to Order) | Creates procurement → PO or picking | Full impact |
| **Dropship** | Dropship | PO sent directly to vendor | Picking = 0 |
| **Gelato** | None (external) | `sale_gelato_stock` blocks procurement | Picking = 0 |

Gelato fulfillment is most similar to dropshipping in its Odoo stock impact, but the mechanism is entirely different: dropshipping uses vendor-managed shipping, while Gelato uses a print-on-demand fulfillment network.

## Related

- [Modules/sale_gelato](Modules/sale_gelato.md) — Gelato API integration: product sync, order submission, tracking
- [Modules/sale_stock](Modules/sale_stock.md) — Standard stock procurement from sales orders
- [Modules/sale_dropshipping](sale_dropshipping.md) — Dropship fulfillment route
- [Modules/sale](Modules/Sale.md) — Sales order and order line models
