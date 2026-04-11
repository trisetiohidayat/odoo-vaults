---
tags: [odoo, odoo19, modules, sale, product_matrix, variant_matrix, grid_entry, sale-product-matrix]
description: Complete L4 documentation for sale_product_matrix - Grid/matrix entry for adding multiple product variants to Sales Orders in Odoo 19.
l4_version_changes: true
l4_security: true
l4_performance: true
l4_cross_module: true
---

# sale_product_matrix

> **Module:** `sale_product_matrix`
> **Path:** `odoo/addons/sale_product_matrix/`
> **Version:** Odoo 19 (CE)
> **Depends:** `sale`, `product_matrix`
> **License:** LGPL-3
> **Category:** Sales/Sales

## Overview

The `sale_product_matrix` module extends Odoo's standard Sale module with a **grid-based (matrix) entry interface** for adding configurable products with multiple variants to a Sales Order in bulk. Instead of adding variants one-by-one through the product configurator, salespersons fill a spreadsheet-like grid showing all possible attribute value combinations (variants), enter quantities directly in each cell, and apply all changes at once.

This module sits atop two layers of infrastructure:

1. **`product_matrix`** (base layer) — defines `_get_template_matrix()` on `product.template`, renders the grid dialog in OWL, and provides QWeb report templates. This layer is UI-agnostic; it only computes the matrix data structure and renders it.
2. **`sale_product_matrix`** (sale layer) — wires the grid dialog into `sale.order` lines, handles the full round-trip of grid-to-order-line synchronization, and manages the `product_add_mode` Selection on `product.template`.

---

## Module Dependency Chain

```
sale
 └── sale_product_matrix   ← this module
      └── product_matrix   ← grid computation + OWL dialog + QWeb report templates

product (implicit)
 └── product_matrix        ← product.template._get_template_matrix()
```

### Model Extensions Summary

| Extended Model | File | Key Addition |
|---|---|---|
| `product.template` | `models/product_template.py` | `product_add_mode` Selection field |
| `sale.order` | `models/sale_order.py` | `report_grids`, three transient fields + `_get_matrix()`, `_apply_grid()`, `get_report_matrixes()` |
| `sale.order.line` | `models/sale_order_line.py` | `product_add_mode` related field |

---

## Models Detail

### 1. `product.template` — Extended

**File:** `models/product_template.py`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_add_mode = fields.Selection(
        selection=[
            ('configurator', "Product Configurator"),
            ('matrix', "Order Grid Entry"),
        ],
        string="Add product mode",
        default='configurator',
        help="Configurator: choose attribute values to add the matching product variant to the order."
             "\nGrid: add several variants at once from the grid of attribute values")
```

#### `product_add_mode` Field

| Attribute | Value |
|---|---|
| Type | `Selection` |
| Default | `'configurator'` |
| Options | `'configurator'` — opens standard configurator; `'matrix'` — opens grid entry |
| Visibility | Controlled by `has_configurable_attributes` in product form |
| Persisted | Yes, stored in `product_template` table |

When set to `'matrix'`, selecting the product template on a sale order line triggers the grid dialog instead of the single-variant configurator.

#### `get_single_product_variant()` Method

```python
def get_single_product_variant(self):
    res = super().get_single_product_variant()
    if self.has_configurable_attributes:
        res['mode'] = self.product_add_mode
    else:
        res['mode'] = 'configurator'
    return res
```

**Purpose:** Called via `orm.call()` RPC from the client-side `SaleOrderLineProductField` component. The returned `mode` key controls which dialog opens:

- `'configurator'` — `ProductConfiguratorDialog` opens
- `'matrix'` — `ProductMatrixDialog` opens via `_openGridConfigurator()` stub

Non-configurable templates (no attribute lines, `has_configurable_attributes=False`) always return `'configurator'` regardless of the field value, since the grid has no purpose without attribute combinations.

---

### 2. `sale.order` — Extended

**File:** `models/sale_order.py`

#### Non-Stored Technical Fields

Three non-stored (`store=False`) fields as a communication channel between the OWL client-side dialog and Python server-side onchange handlers:

```python
grid_product_tmpl_id = fields.Many2one('product.template', store=False)
grid_update = fields.Boolean(default=False, store=False)
grid = fields.Char("Matrix local storage", store=False,
    help="Technical local storage of grid. "
         "\nIf grid_update, will be loaded on the SO."
         "\nIf not, represents the matrix to open.")
```

| Field | Type | Purpose |
|---|---|---|
| `grid_product_tmpl_id` | `Many2one` | Triggers `_set_grid_up()` onchange to load matrix for that template |
| `grid_update` | `Boolean` | Flag: `True` = the `grid` field contains changes to apply; `False` = full matrix for display |
| `grid` | `Char` | JSON string — either the full matrix (display mode) or a diff of changed cells (apply mode) |

These fields appear in the form view as `invisible="1"` fields. They are transient by design — the matrix data is too large and ephemeral to store permanently.

#### `report_grids` Field

```python
report_grids = fields.Boolean(string="Print Variant Grids", default=True)
```

| Attribute | Value |
|---|---|
| Type | `Boolean` |
| Default | `True` |
| Group-restricted | `groups="base.group_no_one"` — only visible to users with technical/debug access |

Controls whether the PDF/HTML sales order report renders variant matrices for grid-configured products.

---

### 3. `sale.order.line` — Extended

**File:** `models/sale_order_line.py`

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_add_mode = fields.Selection(
        related='product_template_id.product_add_mode',
        depends=['product_template_id'])
```

This related field exposes the template's `product_add_mode` onto the line record, allowing the client-side field widget to read the mode without an extra RPC call. The `depends` ensures it is re-evaluated when the template changes.

---

## Core Methods

### `sale.order._set_grid_up()`

```python
@api.onchange('grid_product_tmpl_id')
def _set_grid_up(self):
    """Save locally the matrix of the given product.template, to be used by the matrix configurator."""
    if self.grid_product_tmpl_id:
        self.grid_update = False
        self.grid = json.dumps(self._get_matrix(self.grid_product_tmpl_id))
```

**Trigger:** On change of `grid_product_tmpl_id` — set when the client-side `SaleOrderLineProductField` component calls `rootRecord.update({ grid_product_tmpl_id: record.data.product_template_id })` to open the matrix.

**Flow:**
1. Sets `grid_update = False` — this is a display load, not an apply operation
2. Calls `self._get_matrix()` to compute the full matrix with current order line quantities overlaid
3. Serializes the result to JSON via `json.dumps()` and stores in `self.grid`
4. The client reads `grid` from the record and opens `ProductMatrixDialog`

The method uses `@api.onchange` (not a regular method) because onchange handlers fire on the server and allow ORM operations without a full form save cycle.

---

### `sale.order._apply_grid()`

```python
@api.onchange('grid')
def _apply_grid(self):
    """Apply the given list of changed matrix cells to the current SO."""
    if self.grid and self.grid_update:
        grid = json.loads(self.grid)
        product_template = self.env['product.template'].browse(grid['product_template_id'])
        dirty_cells = grid['changes']
        ...
```

**Trigger:** When the user confirms the matrix dialog, the client writes back:
```javascript
rootRecord.update({
    grid: JSON.stringify({
        changes: matrixChanges,  // [{ qty, ptav_ids }, ...]
        product_template_id: template_id
    }),
    grid_update: true
});
```

#### Cell Processing Loop

For each cell in `dirty_cells`:

```python
combination = Attrib.browse(cell['ptav_ids'])
no_variant_attribute_values = combination - combination._without_no_variant_attributes()

# 1. Create or find product variant from combination
product = product_template._create_product_variant(combination)

# 2. Find existing SOL for this variant + no_variant attrs + no combo
order_lines = self.order_line.filtered(
    lambda line: line.product_id.id == product.id
    and line.product_no_variant_attribute_value_ids.ids == no_variant_attribute_values.ids
    and not line.combo_item_id
)

# 3. Compute quantity difference
old_qty = sum(order_lines.mapped('product_uom_qty'))
qty = cell['qty']
diff = qty - old_qty
```

**Variant Matching Logic:** The `filtered()` lambda matches on three simultaneous conditions:
- Same `product_id` (the specific variant)
- Same `product_no_variant_attribute_value_ids` — `no_variant` attributes do NOT create new variants
- Not a combo line (`not line.combo_item_id`)

#### Multi-Line Guard

```python
if len(order_lines) > 1:
    raise ValidationError(_("You cannot change the quantity of a product present in multiple sale lines."))
```

If the same variant+no_variant combination exists on multiple lines, the server raises a `ValidationError`. This is a deliberate tradeoff: updating the first line and removing others was rejected because it could bypass business logic attached to those lines.

#### State-Aware Line Removal

```python
if qty == 0:
    if self.state in ['draft', 'sent']:
        self.order_line -= order_lines  # Remove line entirely
    else:
        order_lines.update({'product_uom_qty': 0.0})  # Keep line with zero qty
```

When the matrix cell is set to zero:
- For editable SOs (draft or sent): the line is deleted entirely
- For locked/confirmed SOs: the line is kept but `product_uom_qty` is set to `0.0`

#### Variant Combination Handling

```python
no_variant_attribute_values = combination - combination._without_no_variant_attributes()
```

The raw cell combination contains all ptav IDs. The no-variant subset is separated via set subtraction of `_without_no_variant_attributes()`. This subset is:
1. Stored on new SOLs as `product_no_variant_attribute_value_ids`
2. Used as part of the match criteria when finding existing lines to update

---

### `sale.order._get_matrix(product_template)`

```python
def _get_matrix(self, product_template):
    def has_ptavs(line, sorted_attr_ids):
        ptav = line.product_template_attribute_value_ids.ids
        pnav = line.product_no_variant_attribute_value_ids.ids
        pav = pnav + ptav
        pav.sort()
        return pav == sorted_attr_ids
    matrix = product_template._get_template_matrix(
        company_id=self.company_id,
        currency_id=self.currency_id,
        display_extra_price=True)
    if self.order_line:
        lines = matrix['matrix']
        order_lines = self.order_line.filtered(lambda line: line.product_template_id == product_template)
        for line in lines:
            for cell in line:
                if not cell.get('name', False):
                    matching = order_lines.filtered(lambda ol: has_ptavs(ol, cell['ptav_ids']))
                    if matching and not matching.combo_item_id:
                        cell.update({'qty': sum(matching.mapped('product_uom_qty'))})
    return matrix
```

**Purpose:** Loads the base matrix from the template, then overlays current order line quantities onto it for display.

**Algorithm:**
1. Calls `product_template._get_template_matrix()` which returns `{ header: [...], matrix: `...` }` — the Cartesian product of all valid attribute line values
2. Filters `order_line` to those belonging to this template
3. For each matrix cell (skipping header cells), checks if any order line matches the cell's `ptav_ids` using `has_ptavs()`
4. If a match is found and the line is not a combo line, the cell's `qty` is updated to the sum of all matching lines' quantities

**Matrix structure returned:**

```python
{
    'header': [
        {'name': 'Product T-Shirt'},
        {'name': 'Color: Red', 'price': 5.0, 'currency_id': 1},
        {'name': 'Color: Blue', 'price': 0.0, 'currency_id': 1},
    ],
    'matrix': [
        [{'name': 'Size: S', 'price': 0.0}, {'ptav_ids': [1,3], 'qty': 0, ...}, ...],
        [{'name': 'Size: M', 'price': 10.0}, {'ptav_ids': [1,4], 'qty': 5, ...}, ...],
    ]
}
```

Cells where `is_possible_combination=False` are disabled/grayed out in the grid. They are excluded from the report if they have qty=0.

---

### `sale.order.get_report_matrixes()`

```python
def get_report_matrixes(self):
    matrixes = []
    if self.report_grids:
        grid_configured_templates = (
            self.order_line.filtered('is_configurable_product').product_template_id
                          .filtered(lambda ptmpl: ptmpl.product_add_mode == 'matrix'))
        for template in grid_configured_templates:
            if len(self.order_line.filtered(
                    lambda line: line.product_template_id == template)) > 1:
                matrix = self._get_matrix(template)
                matrix_data = []
                for row in matrix['matrix']:
                    if any(column['qty'] != 0 for column in row[1:]):
                        matrix_data.append(row)
                matrix['matrix'] = matrix_data
                matrixes.append(matrix)
    return matrixes
```

**Filters applied:**
1. Only templates where `product_add_mode == 'matrix'`
2. Only templates with more than 1 order line
3. Only rows where at least one non-header cell has `qty != 0` (prunes entirely empty rows)

**Called from:** QWeb template `product_matrix.matrix` in the sale report templates.

---

## Views

### Product Template Form View (`product_template_views.xml`)

Inserts a radio-button group inside the `variants` page, visible only when the template has configurable attributes:

```xml
<xpath expr="//page[@name='variants']" position="inside">
    <group name="product_mode" invisible="not has_configurable_attributes">
        <group string="Sales Variant Selection">
            <field name="has_configurable_attributes" invisible="1"/>
            <field name="product_add_mode" widget="radio" nolabel="1" colspan="2"/>
        </group>
    </group>
</xpath>
```

**Second patch:** In `sale.product_template_view_form`, hides `optional_product_ids` when the template is in matrix mode:

```xml
<field name="optional_product_ids" position="attributes">
    <attribute name="invisible">product_add_mode == 'grid'</attribute>
</field>
```

Optional/add-on products cannot be meaningfully represented within a variant quantity grid.

### Sale Order Form View (`sale_order_views.xml`)

Inserts three invisible technical fields after `partner_id`:
```xml
<field name="grid" invisible="1"/>
<field name="grid_product_tmpl_id" invisible="1"/>
<field name="grid_update" invisible="1"/>
```

Inserts the `report_grids` boolean in the "Sales Person" group:
```xml
<field name="report_grids" groups="base.group_no_one"/>
```

---

## Report Templates

**File:** `report/sale_report_templates.xml`

Extends `sale.report_saleorderdocument` by inserting the matrix table before the main order lines table:

```xml
<template id="grid_report_saleorder_inherit" inherit_id="sale.report_saleorder_document">
    <xpath expr="//table[hasclass('o_main_table')]" position="before">
        <t t-call="product_matrix.matrix">
            <t t-set="order" t-value="doc"/>
        </t>
    </xpath>
</template>
```

The `product_matrix.matrix` QWeb template iterates `order.get_report_matrixes()` and renders each grid as an HTML table.

---

## JavaScript Frontend

### File: `static/src/js/sale_product_field.js`

Patches `SaleOrderLineProductField` (defined in the `sale` module) to add matrix-specific behavior:

```javascript
patch(SaleOrderLineProductField.prototype, {
    setup() {
        super.setup(...arguments);
        this.matrixConfigurator = useMatrixConfigurator();
    },
    ...
});
```

Uses the `useMatrixConfigurator()` hook (exported from `@product_matrix/js/matrix_configurator_hook`) to get the `open` function.

#### `_openGridConfigurator(edit=false)`

```javascript
async _openGridConfigurator(edit=false) {
    return this.matrixConfigurator.open(this.props.record, edit);
}
```

Called when `get_single_product_variant` returns `mode: 'matrix'`. Also called from `_openProductConfigurator` when editing an existing line whose template is in matrix mode.

#### `_openProductConfigurator` Override

```javascript
async _openProductConfigurator(edit=false, selectedComboItems=[]) {
    if (edit && this.props.record.data.product_add_mode == 'matrix') {
        this._openGridConfigurator(true);  // Force grid for editing existing line
    } else {
        return super._openProductConfigurator(...arguments);
    }
}
```

When the user clicks "Edit Configuration" on an existing SOL whose template uses matrix mode, the standard configurator is bypassed entirely in favor of the grid.

#### Field Dependencies Extension

```javascript
Object.assign(saleOrderLineProductField, {
    fieldDependencies: [
        ...saleOrderLineProductField.fieldDependencies,
        { name: "product_add_mode", type: "selection"},
    ],
});
```

Adds `product_add_mode` to the list of fields fetched from the server, so the widget can read it without an extra RPC call.

---

## Client-Side Data Flow

```
User clicks "Add Product" on SO line
  → SaleOrderLineProductField._onProductTemplateUpdate()
    → orm.call('product.template', 'get_single_product_variant', [pt_id])
      ← { product_id, mode: 'matrix', ... }
        → _openGridConfigurator()
          → useMatrixConfigurator().open(this.props.record, edit=false)
            → rootRecord.update({ grid_product_tmpl_id: pt_id })
              → triggers _set_grid_up() server-side onchange
                → grid = json.dumps(_get_matrix(pt))
            → openDialog(rootRecord, rootRecord.data.grid, pt_id, [])
              → ProductMatrixDialog opens (OWL component)
                → User fills quantities in cells
                → User presses Enter OR clicks Confirm
                  → _onConfirm() builds matrixChanges[] array
                  → rootRecord.update({
                       grid: JSON.stringify({ changes: matrixChanges, product_template_id: pt_id }),
                       grid_update: True
                     })
                    → triggers _apply_grid() server-side onchange
                      → parse dirty cells → create/update/delete sale.order.line records
```

---

## The `product_matrix` Base Layer

### `product.template._get_template_matrix()`

Returns `{ header, matrix }`:
- `header`: Column header cells from `_grid_header_cell()`
- `matrix`: 2D array of rows (row header + data cells)

The matrix is the **Cartesian product** of all valid attribute lines. It uses `itertools.zip_longest` to interleave attribute value ID pools into rows.

### `product.template.attribute.value._grid_header_cell()`

Computes extra price for a header cell. The `display_extra_price=True` flag (passed from `sale_product_matrix._get_matrix()`) shows `price_extra` from attribute value records. Note from the template: this is the **catalog price**, not the post-pricelist price, because the pricelist rule might depend on the selected variant.

---

## L3 Escalation: Grid Line Fields and Matrix Behavior

### Relevant `sale.order.line` Fields

| Field | Type | Role in Matrix |
|---|---|---|
| `product_template_attribute_value_ids` | `Many2many` | Links to variant-defining attribute values; drives variant creation |
| `product_no_variant_attribute_value_ids` | `Many2many` | Links to ptav records where attribute has `create_variant = 'no_variant'`; stored for pricing, matched separately |
| `product_id` | `Many2one` | The specific `product.product` variant |
| `is_configurable_product` | `Boolean` (computed) | Indicates whether the line's template has configurable attributes |
| `combo_item_id` | `Many2one` | If set, the line is part of a combo and must be excluded from matrix matching |

### Price Computation

Prices are NOT set by `_apply_grid()`. The grid stores only `product_id` and `product_uom_qty`. Price computation is handled by the standard `sale.order.line` price computation logic triggered when `update()` is called. The `display_extra_price=True` flag in `_get_matrix()` shows attribute value price extras as informational catalog prices in grid headers.

---

## L4 Escalation: Performance, Historical Changes, Security

### Odoo 18 to 19 Architectural Changes

#### 1. Dialog Trigger: Direct → Phantom Line

| Odoo 18 | Odoo 19 |
|---|---|
| Clicking "Add to Order" on a matrix-mode product directly creates one `sale.order.line` placeholder record per possible variant combination, then opens an inline grid editor on those placeholder lines. | Clicking "Add to Order" creates a **single phantom SOL record** (with `product_template_id` set but no `product_id`), then triggers the matrix dialog. The phantom line is deleted by the JS client after the dialog is opened. |

**Rationale:** The Odoo 18 pattern left partial state on the order (potentially hundreds of placeholder lines with qty=0) if the user cancelled the dialog. The phantom-line approach ensures the order is clean on cancel — the server never creates placeholder lines; all SOLs are only created when the user confirms the dialog.

#### 2. JS Architecture

The JS in `sale_product_matrix/static/src/js/sale_product_field.js` uses the **patch pattern** to extend `SaleOrderLineProductField` without modifying it. The dialog component (`ProductMatrixDialog` in `product_matrix`) uses standard OWL class-based component patterns — `setup()`, `onMounted()`, `useRef()`, `useHotkey()` — stable across Odoo 18 and 19.

#### 3. `product_add_mode` Field

Present in both Odoo 18 and 19. Behavior is consistent across versions.

---

### Performance Analysis

#### Why Server-Side Matrix Computation?

The code comment states the rationale explicitly:

> "The matrix functionality was done in python, server side, to avoid js restriction. Indeed, the js framework only loads the x first lines displayed in the client, which means in case of big matrices and lots of so_lines, the js doesn't have access to the 41nth and following lines."

This means:
- **All matrix data is always available** regardless of how many SOLs are on the order
- **No lazy-loading cutoff** exists — the full Cartesian product is computed
- The cost is a full round-trip (client → server → JSON → client) on every matrix open

#### `_apply_grid()` Performance Characteristics

| Operation | Cost | Notes |
|---|---|---|
| `json.loads(self.grid)` | O(n) | Single parse; lightweight |
| `product_template._create_product_variant(combination)` per new cell | O(1) per distinct new variant | ORM `create()` |
| `self.order_line.filtered(...)` per cell | O(m) per cell, m = SOL count | Recordset `filtered()` with Python lambda; no DB query since SOLs are preloaded |
| `default_get(OrderLine._fields.keys())` | O(1), called **once** outside the dirty-cells loop | Critical optimization |
| `update(dict(order_line=new_lines))` | O(k) creates | Single `write()` call batching all new lines |

#### `_get_matrix()` Performance Characteristics

| Operation | Cost | Notes |
|---|---|---|
| `product_template._get_template_matrix(...)` | O(t) where t = all combinations | Each cell triggers `_is_combination_possible()` |
| `_is_combination_possible(combination)` per cell | O(1) to O(n) | Checks variant constraints |
| Nested `filtered()` for qty overlay | O(c × m) | c = data cells, m = SOLs for this template |

**Bottleneck scenario:** A product template with 4 attribute lines of 6 values each produces 1,296 cells. Each cell runs `_is_combination_possible()`, which involves attribute value compatibility checks. The matrix open will be noticeably slow (several seconds) in this case.

---

### Security Deep Dive

#### `report_grids` Group Restriction

```xml
<field name="report_grids" groups="base.group_no_one"/>
```

`base.group_no_one` is Odoo's "technical features" group. The restriction means:
- Standard sales users (even admin) do not see the "Print Variant Grids" checkbox
- Only users with debug/developer mode enabled can toggle it

#### Transient Field Onchange on Locked SOs

`_apply_grid()` fires as an `@api.onchange` on `grid`. Because the method is gated by `grid_update == True`, it cannot be triggered accidentally without UI interaction.

#### Phantom Line Security

When the user opens the matrix without confirming, the phantom SOL line is cleaned up by the JS client:
```javascript
if (!edit) {
    rootRecord.data.order_line.delete(record);
}
```

If the phantom line was somehow persisted, it would appear on the SO with no `product_id`. This is prevented by the JS cleanup.

#### No SQL Injection Surface

All data access uses the ORM. The `dirty_cells` loop uses `Attrib.browse(cell['ptav_ids'])` and `product_template._create_product_variant(combination)` — both are ORM-safe. The `json.loads()` input from `self.grid` is not used in any raw SQL call.

---

### Critical Edge Cases

#### 1. Same Variant on Multiple SOLs from Different Sources

If a variant appears on two SOLs, `_apply_grid` raises a `ValidationError`. This is deliberate — a "smart" strategy (update first, delete others) was rejected because it could bypass business logic attached to the other lines.

#### 2. Matrix Edit on Locked/Confirmed SOs

When `qty == 0` on a locked SO, the line is kept with zero quantity:
```python
order_lines.update({'product_uom_qty': 0.0})
```
This prevents accidental data loss on confirmed orders but may appear confusingly in reports.

#### 3. Dynamic Variants (`create_variant = 'dynamic'`)

When an attribute line has `create_variant = 'dynamic'`, `_apply_grid()` calls `product_template._create_product_variant(combination)` which creates the variant record on-the-fly before creating the SOL.

#### 4. Pricelist Price vs. Catalog Price in Grid Headers

`display_extra_price=True` causes `_grid_header_cell()` to display `price_extra` — the **catalog price** of the attribute value, not the post-pricelist price. The actual line price is computed by `sale.order.line` logic when `update()` is called.

#### 5. Zero-Quantity Rows in PDF Report

The row-pruning logic skips rows only when **all** non-header cells have `qty == 0`. Rows with at least one non-zero cell are always included.

---

## Demo Data

**File:** `data/product_matrix_demo.xml`

```xml
<record id="product_matrix.matrix_product_template_shirt" model="product.template">
    <field name="product_add_mode">matrix</field>
</record>
```

The demo product "My Company T-Shirt" is configured to use matrix mode by default in demo/test environments.

---

## Extension Points

| Extension Point | File | Purpose |
|---|---|---|
| `product.template` | `models/product_template.py` | Add `product_add_mode` field; override `get_single_product_variant()` |
| `sale.order` | `models/sale_order.py` | Three transient matrix fields; implement `_set_grid_up`, `_apply_grid`, `_get_matrix`, `get_report_matrixes` |
| `sale.order.line` | `models/sale_order_line.py` | Mirror `product_add_mode` from template as a related field |
| JS `SaleOrderLineProductField` | `static/src/js/sale_product_field.js` | Patch to add `_openGridConfigurator()` and intercept `_openProductConfigurator()` |
| `ir.ui.view` | `views/sale_order_views.xml` | Add invisible transient fields; add `report_grids` toggle |
| `ir.ui.view` | `views/product_template_views.xml` | Add `product_add_mode` radio group; hide optional products in matrix mode |
| `ir.ui.view` | `report/sale_report_templates.xml` | Insert matrix table into SO report |

---

## See Also

- [[Modules/sale]] — Base Sale module (sale.order, sale.order.line)
- [[Modules/product_matrix]] — Technical matrix module (grid computation, OWL dialog, QWeb templates)
- [[Modules/sale_product_configurator]] — Standard product configurator frontend
- [[Modules/purchase_product_matrix]] — Analogous purchase order matrix (no `product_add_mode` gating)
