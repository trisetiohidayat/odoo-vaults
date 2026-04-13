---
type: guide
title: "Product Master Data Guide"
module: product
submodule: product-master-data
audience: business-consultant, developer, ai-reasoning
level: 2
prerequisites:
  - product_categories_configured
  - uom_units_defined
  - vendor_list_setup
estimated_time: "~15 minutes"
related_flows:
  - "[Flows/Product/product-creation-flow](flows/product/product-creation-flow.md)"
  - "[Flows/Product/pricelist-computation-flow](flows/product/pricelist-computation-flow.md)"
source_module: product
created: 2026-04-07
version: "1.0"
---

# Product Master Data Guide

> **Quick Summary:** A step-by-step guide for creating and configuring product master data in Odoo 19 — covering storable, service, and kit product types — with prerequisites, system trigger annotations, and common pitfalls for each scenario.

**Actor:** Product Manager, Sales Manager, IT Administrator
**Module:** Product (product)
**Use Case:** Creating and configuring product master data records across all product types
**Difficulty:** ⭐ Easy

---

## Prerequisites Checklist

Before creating products in Odoo 19, ensure the following foundation records are in place. Skipping these will cause errors or missing functionality.

- [ ] **Product categories configured** — Navigate to `Settings → Products → Product Categories`. Create at least one category. For storable products with valuation, the category must have a `Property Stock Valuation Account` set.
- [ ] **Units of Measure defined** — Navigate to `Settings → Products → Units of Measure`. Confirm `Unit(s)` exists and its category (e.g., "Unit"). If you need to purchase in different UoM, also define the purchase UoM and its conversion factor.
- [ ] **Vendor/supplier list setup** — Navigate to `Purchase → Products → Suppliers`. Ensure vendor partners (res.partner with supplier flag) exist before assigning vendors to products.
- [ ] **Chart of Accounts loaded** — For storable products with valuation, ensure the `Property Stock Valuation Account` and `Property Account In/Expense` accounts exist in your company's fiscal localization.
- [ ] **Pricelist created** — Navigate to `Sales → Products → Pricelists`. Create at least one pricelist with your default currency. Assign it to the appropriate customer.

> **⚠️ Critical:** If product categories do not have stock valuation accounts configured, storable products will fail to generate valuation journal entries on receipt. Always configure the category's accounts before creating storable products.

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Product/product-creation-flow](flows/product/product-creation-flow.md) | Full method chain and branching logic |
| 🔀 Technical Flow | [Flows/Product/pricelist-computation-flow](flows/product/pricelist-computation-flow.md) | Pricelist price computation for sales |
| 📖 Module Reference | [Modules/product](modules/product.md) | Complete field and method reference |
| 📋 Related Guide | [Flows/Stock/receipt-flow](flows/stock/receipt-flow.md) | Stock receipt flow using products |
| 🔧 Configuration | [Modules/Product](modules/product.md) | Accounting-related product settings |

---

## Use Cases Covered

This guide covers the following use cases:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Create a storable product with costing and valuation | [#use-case-a-create-storable-product-with-costing](#use-case-a-create-storable-product-with-costing.md) | ⭐ |
| 2 | Create a service product | [#use-case-b-create-service-product](#use-case-b-create-service-product.md) | ⭐ |
| 3 | Create a kit/bom product | [#use-case-c-create-kitbom-product](#use-case-c-create-kitbom-product.md) | ⭐⭐ |

---

## Use Case A: Create Storable Product with Costing

### Scenario

A company needs to add a new physical product — a branded notebook — to its catalog. The product must be tracked in stock, valued at standard cost, and automatically generate accounting entries on receipt. The sales price will be managed via a pricelist.

### Steps

#### Step 1 — Navigate to Product Creation

Navigate to: `Settings → Products → Products`

Click **[Create]**.

> **⚡ System Behavior:** Odoo opens a blank product form. The default `type` is `consu`. You must change it to `product` (storable) to enable stock tracking and valuation.

#### Step 2 — Fill Basic Information

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Product Name** | "Branded Notebook A5" | ✅ Yes | — |
| **Product Type** | `Storable product` | ✅ Yes | `consu` (Consumable) by default — must change |
| **Category** | Select an existing category | No | — |
| **Can be sold** | ✅ Checked | No | `True` default |
| **Can be purchased** | ✅ Checked | No | `True` default |

> **⚡ System Trigger:** When you select `Storable product` (type = 'product'), Odoo enables the **Inventory** tab and the **Routes** section. The **Route** checkboxes (Make to Order, Drop Shipping, On Order) become available. Route assignment triggers `stock.location.route.rule` matching — see [Flows/Product/product-creation-flow#complete-method-chain](flows/product/product-creation-flow#complete-method-chain.md).

> **⚡ Side Effect:** Changing type to `Storable product` triggers `_onchange_type()` which resets `procurement_jit` to False and ensures no JIT-related defaults are applied.

#### Step 3 — Set Pricing

| Field | Value | Notes |
|-------|-------|-------|
| **Sales Price** | `12.50` | Per unit. This is `list_price` on `product.template`. |
| **Cost** | `6.00` | This is `standard_price` — used for margin calculation and valuation. |
| **Fiscal Position** | (optional) | If set, Odoo maps taxes via `_onchange_fiscal_position_id()` during sale order line creation. |

> **⚡ System Trigger:** Setting `Cost` (standard_price) triggers `_onchange_standard_price()` which validates that the cost is non-negative. If negative, a `UserError` is raised: "Cost must be positive."

> **⚡ System Trigger:** When `Category` is set, `_onchange_categ_id()` fires — `property_stock_valuation_account_id` and `property_account_income_id` are pulled from the category. This is critical for automatic valuation. If the category has no valuation account, receipt will fail.

#### Step 4 — Set Unit of Measure

| Field | Value | Notes |
|-------|-------|-------|
| **Unit of Measure** | `Unit(s)` | Default from `_get_default_uom_id()` |
| **Purchase UoM** | `Unit(s)` | Suggested by `_onchange_uom()` equal to `uom_id` |

> **⚡ System Trigger:** When `Unit of Measure` is set, `_onchange_uom()` fires. It suggests `uom_po_id = uom_id`. If the purchase UoM is in a different UoM category than the sales UoM, Odoo will raise a `UserError`: "Inconsistent UoM category". Always match UoM categories.

> **⚡ Side Effect:** The UoM determines stock quantity granularity. If you use `Units`, all stock quantities are integers. If you use `kg`, decimal quantities are allowed.

#### Step 5 — Configure Inventory Tab

Click the **Inventory** tab:

| Field | Value | Notes |
|-------|-------|-------|
| **Weight** | `0.15` | In kg. Used for shipping rate calculation. |
| **Volume** | `0.0002` | In cubic meters. Used for shipping estimation. |
| **Internal Reference** | `NBA5-001` | `default_code` field — used in barcode/SKU lookups. |
| **Barcode** | (optional) | `barcode` field — scanned in POS/WMS. |
| ** Routes** | `On Order` (if Make to Order) | Select applicable routes. |

> **⚡ System Trigger:** When `Routes` are selected, Odoo creates many-to-many records in `stock_location_route_product_rel`. Route matching is done against `stock.location.route.rule` records — see [Flows/Product/product-creation-flow#decision-tree](flows/product/product-creation-flow#decision-tree.md).

#### Step 6 — Assign Vendor (Purchase Tab)

Click the **Purchase** tab:

| Field | Value | Notes |
|-------|-------|-------|
| **Vendors** | Add vendor partner | Line: Vendor, Unit Price, Currency, Delivery Lead Time |
| **Min Order Qty** | `100` | Optional — controls PO quantity threshold |
| **Delivery Lead Time** | `7` days | Used by MRP and purchase planning |

> **⚡ System Trigger:** When vendor is assigned, `product.supplierinfo` record is created. `_select_seller()` in `product.product` uses the vendor's `price` and `delay` when creating purchase orders.

#### Step 7 — Save and Verify

Click **Save**.

**Expected Results Checklist:**
- [ ] Product appears in **Settings → Products → Products** list
- [ ] Product type shown as "Storable product" in list view
- [ ] Category correctly assigned
- [ ] Standard price = `6.00`, Sales price = `12.50`
- [ ] Vendor appears under Purchase tab
- [ ] On a test purchase receipt, `stock.valuation.account` entry is generated (if `stock_account` module installed)

---

## Use Case B: Create Service Product

### Scenario

A consulting company needs to add a "Strategic Advisory" consulting service to its Odoo catalog. Service products are not tracked in stock but are invoiced based on time or fixed price. They require no UoM or route configuration.

### Steps

#### Step 1 — Navigate to Product Creation

Navigate to: `Settings → Products → Products`

Click **[Create]**.

#### Step 2 — Set Product Type

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Product Name** | "Strategic Advisory" | ✅ Yes | — |
| **Product Type** | `Service` | ✅ Yes | Must change from default `consu` |
| **Can be sold** | ✅ Checked | No | `True` default |
| **Can be purchased** | ☐ Unchecked | No | Services may not be purchased |

> **⚡ System Trigger:** When type is set to `Service`, `_onchange_type()` fires and sets `procurement_jit = True` (via `_onchange_uom()` logic). This enables Just-In-Time procurement for service products — they are treated as instantly deliverable without stock moves.

#### Step 3 — Set Pricing

| Field | Value | Notes |
|-------|-------|-------|
| **Sales Price** | `250.00` | Per hour or fixed — depends on invoicing policy |
| **Cost** | `0.00` | Services have no cost of goods sold by default |
| **Invoicing Policy** | `Prepaid/Fixed` | Controlled in the Sale app per order type |

> **⚡ Side Effect:** Service products do NOT trigger stock valuation. There is no `stock.quant` created when a service is sold. All revenue goes directly to the income account.

#### Step 4 — Set Description for Sales

| Field | Value | Notes |
|-------|-------|-------|
| **Sales Description** | "Strategic advisory session, 4-hour block" | Used in SO, DO, Invoice printout |
| **Purchase Description** | "Strategic advisory service" | Used on purchase orders |

> **⚡ System Trigger:** When this product is added to a sale order, `sale.order.line._onchange_product_id()` populates `name` from `description_sale` via `get_product_multiline_description_sale()`.

#### Step 5 — Configure Invoicing (Optional)

Click the **General Information** tab:

| Field | Value | Notes |
|-------|-------|-------|
| **General Account** | `Service Revenue` (4-digit account) | Used for invoice line posting |
| **Customer Taxes** | Select applicable tax | Applied on sale invoice |
| **Invoice Policy** | `Manual` or `Ordered quantity` | Determines when invoice is generated |

> **⚡ Side Effect:** The `General Account` (property_account_income_id) is used when validating a sale invoice containing this product. Set via category defaults or directly on the product.

#### Step 6 — Save and Verify

Click **Save**.

**Expected Results Checklist:**
- [ ] Product appears in product list with "Service" type icon
- [ ] No stock routes pre-selected (service products skip route assignment)
- [ ] Vendor tab empty (services not typically purchased)
- [ ] On a test SO, adding this product does NOT create a delivery order
- [ ] On a test Invoice, adding this product posts to the correct revenue account

---

## Use Case C: Create Kit/BOM Product

### Scenario

A company sells a product bundle called "Desktop Setup Kit" that consists of: 1x Monitor, 1x Keyboard, 1x Mouse, 1x USB Hub. Each component is already a storable product in Odoo. When this kit is sold, it should be manufactured (or assembled) before delivery. This requires a Bill of Materials (BOM).

### Steps

#### Step 1 — Create Component Products First

Before creating the kit, ensure all components exist as storable products. Create them per [#use-case-a-create-storable-product-with-costing](#use-case-a-create-storable-product-with-costing.md):

- [ ] Monitor 24" — type: Storable, list_price: `180.00`, standard_price: `110.00`
- [ ] Mechanical Keyboard — type: Storable, list_price: `75.00`, standard_price: `45.00`
- [ ] Wireless Mouse — type: Storable, list_price: `35.00`, standard_price: `20.00`
- [ ] USB Hub 4-Port — type: Storable, list_price: `15.00`, standard_price: `8.00`

> **⚡ System Behavior:** Each component is a regular `product.product` record with type='product'. You will reference them in the BOM.

#### Step 2 — Create the Kit Product

Navigate to: `Settings → Products → Products` → **Create**

| Field | Value | Required |
|-------|-------|----------|
| **Product Name** | "Desktop Setup Kit" | ✅ Yes |
| **Product Type** | `Storable product` | ✅ Yes |
| **Sales Price** | `280.00` | Kit priced as bundle discount vs. sum of components |
| **Cost** | Leave blank (computed from BOM) | Will be computed via BOM |

> **⚡ System Trigger:** For kit products, `standard_price` may be left empty — it will be computed from the BOM's component costs. The `mrp.bom._compute_scrap()` method sums component `standard_price` values to determine the kit's effective cost for valuation.

> **⚡ Side Effect:** When `type = 'product'` (storable), the **Manufacturing** tab appears with BOM type options.

#### Step 3 — Navigate to Manufacturing Tab

Click the **Manufacturing** tab (visible only for Storable products):

| Field | Value | Notes |
|-------|-------|-------|
| **BoM Type** | `Kit` | Also known as "phantom" BOM — components are subtracted from stock on delivery, not via a production order |
| **Supply Method** | `Manufacture` or `Buy` | `Manufacture` creates a production order; `Kit` (phantom) subtracts components directly |

> **⚡ System Trigger:** Setting `BoM Type = Kit` and `Supply Method = Manufacture` triggers the creation of an `mrp.bom` record linked to this product. If a MO is confirmed, Odoo will explode the BOM and create `mrp.bom.line` entries for each component.

#### Step 4 — Define the Bill of Materials

Navigate to: `Manufacturing → Products → Bills of Materials` → **Create**

| Field | Value | Notes |
|-------|-------|-------|
| **Product** | "Desktop Setup Kit" | The finished kit product |
| **BoM Type** | `Kit` | Phantom — components consumed on sale |
| **Operations** | (optional) | Workcenters and routing steps |

In the **Components** tab, add:

| Component | Quantity | Notes |
|-----------|----------|-------|
| Monitor 24" | 1 | `product.product` record |
| Mechanical Keyboard | 1 | `product.product` record |
| Wireless Mouse | 1 | `product.product` record |
| USB Hub 4-Port | 1 | `product.product` record |

> **⚡ System Trigger:** When the BOM is saved, `mrp.bom._check_bom_lines()` validates that all components exist and have type='product'. It also checks for recursive BOM (A's BOM contains A) — which is forbidden.

> **⚡ Side Effect:** When a sale order with this kit product is confirmed:
> - If `supply_method = manufacture`: A production order (`mrp.production`) is created
> - If `BoM Type = Kit` (phantom): `mrp.bom.explode()` is called directly on sale order confirmation, subtracting component quantities from stock without a production order

#### Step 5 — Verify Kit Pricing

On the kit product form, navigate to **Sales** tab:

The kit's `list_price = 280.00`. The sum of component list prices = `180 + 75 + 35 + 15 = 305.00`. The kit is priced at a `25.00` discount vs. buying separately — this is the bundle selling point.

> **⚡ System Trigger:** When `sale.order.line._onchange_product_id()` fires for this kit product:
> - `get_product_price()` returns `280.00` (the kit's list_price)
> - If `mrp.bom._compute_scrap()` is used as base_price, the effective cost = `110 + 45 + 20 + 8 = 183.00`
> - Margin = `280.00 - 183.00 = 97.00` per kit

#### Step 6 — Save and Verify

Click **Save** on the BOM record.

**Expected Results Checklist:**
- [ ] Kit product appears in product list with "Storable" type
- [ ] BOM record exists under Manufacturing → Bills of Materials
- [ ] BOM shows 4 components with correct quantities
- [ ] On a test sale order, adding kit product creates:
  - [ ] SO line with kit at `280.00`
  - [ ] Delivery order with 4 component products (phantom exploded) — OR
  - [ ] Manufacturing order to produce the kit (if non-phantom BOM)
- [ ] Component stock levels decrease by the correct quantities on delivery validation

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Creating storable product without setting category | Receipt creates `stock.quant` but no accounting entry. Valuation report shows "No valuation account" | Always set `categ_id` with `property_stock_valuation_account_id` before saving |
| 2 | Mismatched UoM categories for purchase vs. sales | `UserError`: "Inconsistent UoM category" on product save | Ensure purchase UoM is in same category as sales UoM |
| 3 | Negative cost price | `UserError`: "Cost must be positive" on standard_price write | Always set non-negative `standard_price` |
| 4 | Forgetting to set `type` field | Product created as consumable, no stock tracking | Always explicitly set `type = 'product'` for storable items |
| 5 | Creating kit product without components | BOM validation error on save | Create all component products first |
| 6 | Setting kit price without BOM cost review | Bundle sold below component cost | Always verify: kit `list_price` > SUM(component `standard_price`) |
| 7 | Not assigning vendor before PO creation | Manual vendor entry required on PO line | Always assign at least one vendor in Purchase tab |
| 8 | Activating route without rule configuration | Route appears selected but no moves created | Configure `stock.location.route.rule` before assigning route to product |
| 9 | Re-using barcode from inactive product | `ValidationError`: "Barcode already assigned" | Use `action_archive()` on old product, never delete products used in transactions |
| 10 | Changing UoM on product with existing stock | Existing quantities not converted — new UoM applied to future only | Change UoM only on products with zero stock |

---

## Configuration Deep Dive

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| Product Categories | `Settings → Products → Product Categories` | Valuation accounts, parent hierarchy |
| Units of Measure | `Settings → Products → Units of Measure` | UoM categories and conversion factors |
| Pricelists | `Sales → Products → Pricelists` | Price rules per customer/category |
| Vendors | `Purchase → Products → Suppliers` | Vendor partner list for PO sourcing |
| Routes | `Inventory → Configuration → Routes` | Warehouse-level procurement routes |
| Product Labels | `Settings → Products → Product Labels` | Barcode label printing |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|-------------------|
| Multi-company product | `company_id` | False (shared) | When set, product only visible in that company |
| Variant tracking | `product_variant_ids` | Auto (empty) | Creates variant records when attributes added |
| Dynamic product creation | `is_dynamically_created` | False | Enables on-the-fly variant creation |
| Fiscal position mapping | `taxes_id` + `fiscal_position_id` | None | Auto-maps tax accounts based on customer fiscal position |
| Volume/Weight conversion | `volume_uom_name`, `weight_uom_name` | From ir.config.parameter | Controls shipping rate calculation unit system |

### BOM Configuration for Kit Products

| Option | Value | Effect |
|--------|-------|--------|
| `BoM Type = Kit` (phantom) | Components consumed at delivery | No MO created; component stock directly reduced |
| `BoM Type = Normal` | Manufacture to stock | MO created on SO confirmation |
| `BoM Type = Subcontract` | Outsourced manufacture | Subcontract PO created; BOM components shipped to subcontractor |
| `Kit + supply_method = buy` | Components bought on PO | PO created for kit, not for components |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|---------|
| Product not appearing in sale order product picker | `sale_ok = False` or `active = False` | Check `sale_ok` checkbox and `active` status on product form |
| No stock valuation entry on receipt | Category missing `property_stock_valuation_account_id` | Navigate to product category and set the valuation account |
| Kit product shows 0 stock when components have stock | `BoM Type = Normal` requires MO to be done | Either create and validate MO, or switch to `Kit` (phantom) type |
| Pricelist rule not applying | Rule `min_quantity > 1` not met | Verify quantity on sale order line meets rule's `min_quantity` |
| Price different from expected | Wrong `pricelist_id` on SO (partner has different default) | Check `partner_id.property_product_pricelist` on the customer form |
| Cannot delete product | Linked to open SO/PO/stock moves | Archive the product instead (`action_archive()`) |
| Product variant not found in picker | Attribute line not properly configured | Check `product.template.attribute.line` — values must have `price_extra` set |
| BOM not exploding on sale | `BoM Type = Normal` but MO not confirmed | Confirm the manufacturing order linked to the sale order line |
| UoM conversion warning on product save | Purchase UoM in different category than sales UoM | Reconfigure purchase UoM to match the sales UoM category |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Product/product-creation-flow](flows/product/product-creation-flow.md) | Full method chain for product create |
| 🔀 Technical Flow | [Flows/Product/pricelist-computation-flow](flows/product/pricelist-computation-flow.md) | Price computation on sale order lines |
| 📖 Module Reference | [Modules/product](modules/product.md) | Complete product model reference |
| 📋 Related Guide | [Flows/Stock/receipt-flow](flows/stock/receipt-flow.md) | Stock receipt workflow |
| 📋 Related Guide | [Flows/Purchase/purchase-order-creation-flow](flows/purchase/purchase-order-creation-flow.md) | Purchase order creation |
| 🔧 Patterns | [Patterns/Inheritance Patterns](patterns/inheritance-patterns.md) | Delegation inheritance for product.product |
| 🛠️ Snippets | [Snippets/Model Snippets](snippets/model-snippets.md) | Code snippets for product customization |