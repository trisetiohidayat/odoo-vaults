---
tags:
  - odoo
  - odoo19
  - modules
  - purchase
  - product
  - matrix
description: Complete L4 documentation for purchase_product_matrix - Grid-based variant entry for purchase orders in Odoo 19 CE.
---

# Module: purchase_product_matrix

> Grid-based variant entry for purchase orders — enables rapid multi-variant quantity input through an interactive matrix UI, analogous to `sale_product_matrix` but for procurement workflows.

**Tags:** #odoo19 #modules #purchase #product-matrix

---

## Quick Facts

| Property | Value |
|----------|-------|
| **Module ID** | `purchase_product_matrix` |
| **Type** | Community Edition (CE) |
| **Location** | `odoo/addons/purchase_product_matrix/` |
| **Odoo Version** | 19+ |
| **License** | LGPL-3 |
| **Category** | Supply Chain / Purchase |
| **Depends** | `purchase`, `product_matrix` |
| **Auto-install** | No |

---

## Purpose

`purchase_product_matrix` enables procurement teams to rapidly fill purchase orders with product variants through an interactive grid/matrix UI — the same UX pattern as the sale order matrix, but adapted for purchasing workflows. Instead of adding variants one-by-one through the standard line editor, a buyer selects a configurable product template and enters quantities directly in a matrix where rows and columns correspond to attribute value combinations (e.g., Size x Color). A single confirmation creates all relevant PO lines at once.

The module is **server-side heavy by design**: matrix computation happens in Python on the server to bypass Odoo web client viewport limitations that cap the number of rows available to JavaScript. The matrix also integrates with supplier price lists via `product.supplierinfo` to display per-variant cost adjustments in column headers.

Unlike `sale_product_matrix`, `purchase_product_matrix` does **not** require the `product_add_mode = 'matrix'` flag on the product template. Any configurable product (a product template with attribute lines) can be added to a PO via the matrix as long as it has at least one `purchase_ok = True` variant. The matrix opens when the buyer selects a product template on the PO line — there is no mode selection step.

---

## Module Dependency Chain

```
purchase
 └── purchase_product_matrix   ← this module
      └── product_matrix       ← grid computation + OWL dialog + QWeb report templates

product (implicit)
 └── product_matrix            ← product.template._get_template_matrix()
```

**Key difference from sale_product_matrix:** `sale_product_matrix` gates matrix access behind `product_add_mode = 'matrix'` on `product.template`. `purchase_product_matrix` makes the matrix available for **all** configurable products, with no per-template configuration required.

---

## Models Detail (L2)

### 1. `purchase.order` — Extended

**File:** `models/purchase.py`

#### Non-Stored Technical Fields

Three non-stored (`store=False`) fields serve as a communication channel between the OWL client-side dialog and Python onchange handlers:

```python
grid_product_tmpl_id = fields.Many2one('product.template', store=False,
    help="Technical field for product_matrix functionalities.")
grid_update = fields.Boolean(default=False, store=False,
    help="Whether the grid field contains a new matrix to apply or not.")
grid = fields.Char(store=False,
    help="Technical storage of grid. "
         "\nIf grid_update, will be loaded on the PO. "
         "\nIf not, represents the matrix to open.")
```

| Field | Type | Purpose |
|---|---|---|
| `grid_product_tmpl_id` | `Many2one` | When set by the client, triggers `_set_grid_up()` onchange to load the matrix |
| `grid_update` | `Boolean` | Flag: `True` = grid contains changes to apply; `False` = full matrix for display |
| `grid` | `Char` (JSON) | Either the full matrix (display mode) or a diff of changed cells (apply mode) |

#### `report_grids` Field

```python
report_grids = fields.Boolean(
    string="Print Variant Grids",
    default=True,
    help="If set, the matrix of configurable products will be shown on the report of this order."
)
```

Controls whether the PDF/HTML purchase order report renders variant matrices. Restricted to `base.group_no_one` (technical/debug users only).

---

### 2. `purchase.order.line` — Extended

**File:** `models/purchase.py`

Four fields added:

```python
product_template_id = fields.Many2one(
    'product.template',
    string='Product Template',
    related="product_id.product_tmpl_id",
    domain=[('purchase_ok', '=', True)])

is_configurable_product = fields.Boolean(
    'Is the product configurable?',
    related="product_template_id.has_configurable_attributes")

product_template_attribute_value_ids = fields.Many2many(
    related='product_id.product_template_attribute_value_ids',
    readonly=True)

product_no_variant_attribute_value_ids = fields.Many2many(
    'product.template.attribute.value',
    string='Product attribute values that do not create variants',
    ondelete='restrict')
```

**Purpose of `product_no_variant_attribute_value_ids`:** Attribute lines with `create_variant = 'no_variant'` do not create new product variants. Instead, their values are stored directly on the PO line. This field holds those values and is used for product description generation.

#### `_get_product_purchase_description(product)`

```python
def _get_product_purchase_description(self, product):
    name = super(PurchaseOrderLine, self)._get_product_purchase_description(product)
    product_lang_no_variant_attribute_value_ids = self.with_context(
        product.env.context).product_no_variant_attribute_value_ids
    for no_variant_attribute_value in product_lang_no_variant_attribute_value_ids:
        name += "\n" + no_variant_attribute_value.attribute_id.name + ': ' + no_variant_attribute_value.name
    return name
```

Appends no-variant attribute values to the product description on the PO line. Example output: `"T-Shirt\nColor: Red\nCustom Print: Logo"`.

---

## Core Methods (L3)

### `purchase.order._set_grid_up()`

```python
@api.onchange('grid_product_tmpl_id')
def _set_grid_up(self):
    if self.grid_product_tmpl_id:
        self.grid_update = False
        self.grid = json.dumps(self._get_matrix(self.grid_product_tmpl_id))
```

**Trigger:** Set by the client when the user selects a product template and clicks "Open Matrix" or equivalent. Calls `self._get_matrix()` to compute the full Cartesian product grid with current PO line quantities overlaid, serializes to JSON, and stores in `self.grid`.

**Flow:**
1. `grid_update = False` — display mode, not apply mode
2. `_get_matrix()` returns the base matrix enriched with current line quantities
3. JSON serialization enables the client to read the grid data from the record

---

### `purchase.order._apply_grid()`

```python
@api.onchange('grid')
def _apply_grid(self):
    if self.grid and self.grid_update:
        grid = json.loads(self.grid)
        product_template = self.env['product.template'].browse(grid['product_template_id'])
        product_ids = set()
        dirty_cells = grid['changes']
        Attrib = self.env['product.template.attribute.value']
        default_po_line_vals = {}
        new_lines = []
        for cell in dirty_cells:
            # ... variant matching and line creation logic
```

**Trigger:** When the user confirms the matrix dialog, the client writes the modified cells back with `grid_update = True`. This fires the onchange on `grid`.

**Cell processing loop for each dirty cell:**

1. **Resolve variant combination:**
   ```python
   combination = Attrib.browse(cell['ptav_ids'])
   no_variant_attribute_values = combination - combination._without_no_variant_attributes()
   ```
   Splits the raw combination into variant-defining ptavs and no-variant ptavs.

2. **Create or find product variant:**
   ```python
   product = product_template._create_product_variant(combination)
   ```
   Uses the standard ORM variant creation logic. If the variant already exists, `_create_product_variant` finds it.

3. **Find existing PO lines for this variant:**
   ```python
   order_lines = self.order_line.filtered(
       lambda line: (line._origin or line).product_id == product
       and (line._origin or line).product_no_variant_attribute_value_ids == no_variant_attribute_values)
   ```
   Uses `(line._origin or line)` pattern to handle both new (unsaved) and existing lines.

4. **Compute quantity delta:**
   ```python
   old_qty = sum(order_lines.mapped('product_qty'))
   diff = qty - old_qty
   if not diff: continue
   ```

5. **Update or create:**
   - If existing lines found and `qty == 0`: remove line (draft/sent) or set qty=0 (locked)
   - If existing lines found and `qty > 0`: update quantity on first line, raise if multiple lines exist
   - If no existing line: create new PO line via `default_get` + `(0, 0, vals)` command

6. **After all cells processed:**
   ```python
   if product_ids:
       if new_lines:
           self.update(dict(order_line=new_lines))
       for line in self.order_line.filtered(lambda line: line.product_id.id in product_ids):
           line._product_id_change()  # Recompute prices
   ```

**Key difference from sale matrix:** After updating lines, `_product_id_change()` is called to recompute supplier prices for the new/modified lines. This is necessary because `purchase.order.line` pricing depends on `product_id` (supplierinfo pricelists), unlike `sale.order.line` where pricing is set upfront and not recomputed on variant change.

---

### `purchase.order._get_matrix(product_template)`

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
        currency_id=self.currency_id)
    if self.order_line:
        lines = matrix['matrix']
        order_lines = self.order_line.filtered(
            lambda line: line.product_template_id == product_template)
        for line in lines:
            for cell in line:
                if not cell.get('name', False):
                    matching = order_lines.filtered(
                        lambda ol: has_ptavs(ol, cell['ptav_ids']))
                    if matching:
                        cell.update({'qty': sum(matching.mapped('product_qty'))})
    return matrix
```

**Unlike `sale_product_matrix`:** The `display_extra_price=True` flag is NOT passed to `_get_template_matrix()`. The purchase matrix does not show extra attribute prices in headers — supplier prices are dynamic based on `product.supplierinfo` records and are computed per line, not per attribute value.

**`has_ptavs` helper:** Combines `product_template_attribute_value_ids` and `product_no_variant_attribute_value_ids` into a single sorted list for matching. Both must match exactly for the cell to show a quantity.

---

### `purchase.order.get_report_matrixes()`

```python
def get_report_matrixes(self):
    """Reporting method."""
    matrixes = []
    if self.report_grids:
        grid_configured_templates = (
            self.order_line.filtered('is_configurable_product').product_template_id)
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

**Unlike `sale_product_matrix.get_report_matrixes()`:** There is no `product_add_mode == 'matrix'` filter. In purchase, the matrix is always available for configurable products, so all configurable products with multiple lines appear in the report. The comment notes:
> "configurable products are only configured through the matrix in purchase, so no need to check product_add_mode."

**Row pruning logic:** Only rows where at least one non-header cell has `qty != 0` are included in the report, keeping the output clean.

---

### `purchase.order._must_delete_date_planned(field_name)`

```python
def _must_delete_date_planned(self, field_name):
    return super()._must_delete_date_planned(field_name) or field_name == "grid"
```

Adds `"grid"` to the list of fields whose `date_planned` must be deleted when the field value changes. This ensures the planned date is cleared when the matrix is opened/applied, forcing the user to reconsider delivery scheduling for the newly added lines.

---

## Views

**File:** `views/purchase_views.xml`

### Purchase Order Form View

**View ID:** `purchase_order_form_matrix`
**Inherits:** `purchase.purchase_order_form`

**Three invisible technical fields inserted after `partner_id`:**
```xml
<field name="grid" invisible="1"/>
<field name="grid_product_tmpl_id" invisible="1"/>
<field name="grid_update" invisible="1"/>
```

**PO line list columns modified:**
- `product_id` column is made invisible (`column_invisible="1"`)
- `product_template_id` replaces it with a `pol_product_many2one` widget
- `product_template_attribute_value_ids`, `product_no_variant_attribute_value_ids`, `is_configurable_product` are added as invisible columns

```xml
<field name="product_template_id"
    string="Product"
    readonly="state in ('purchase', 'to approve', 'cancel')"
    required="not display_type"
    optional="show"
    context="{'partner_id': parent.partner_id}"
    options="{'show_label_warning': True}"
    widget="pol_product_many2one"/>
```

The `pol_product_many2one` widget is the purchase-specific product selector that triggers the matrix dialog for configurable products.

**`report_grids` toggle in `other_info` group:**
```xml
<field name="report_grids" groups="base.group_no_one"/>
```

---

## The `product_matrix` Base Layer

The `product_matrix` module (`odoo/addons/product_matrix/`) provides the foundational matrix computation and dialog rendering that both `sale_product_matrix` and `purchase_product_matrix` depend on.

### `product.template._get_template_matrix()`

Returns a dict with two keys:
- `header`: Array of column header cells for the first attribute line. Each cell is a dict: `{ name: "Color: Red", price: 10.00, currency_id: 1 }` or `{ name: "Size: L" }`.
- `matrix`: 2D array of rows. Each row starts with a row header cell (has `'name'` key) followed by data cells. Data cells: `{ ptav_ids: [1, 3, 5], qty: 0, is_possible_combination: True }`.

The matrix represents the **Cartesian product** of all valid attribute lines of the template. It uses `itertools.zip_longest` to interleave the attribute value ID pools into rows, where each column intersection is one possible combination.

### `product.template.attribute.value._grid_header_cell()`

Computes the extra price for a header cell. In `purchase_product_matrix`, `display_extra_price` is not passed, so header cells do not show price extras — supplier prices are computed per variant via `_product_id_change()`, not from attribute value price extras.

---

## Version Changes: Odoo 18 to 19 (L4)

### Architecture Consistency

Both `sale_product_matrix` and `purchase_product_matrix` use the **identical architecture** in Odoo 18 and Odoo 19:
- Three non-stored technical fields (`grid_product_tmpl_id`, `grid_update`, `grid`)
- Server-side Python matrix computation via `_get_matrix()`
- Client-side OWL matrix dialog via `product_matrix` module
- Onchange-based round-trip (display → edit → apply)

The Odoo 19 changes are **incremental improvements**, not architectural rewrites.

### `_must_delete_date_planned` Addition

**Odoo 18:** No override existed. Changing the `grid` field did not clear `date_planned` on PO lines.

**Odoo 19:** The `_must_delete_date_planned` override was added to explicitly clear `date_planned` when the grid is modified. This prevents a scenario where a user configures a matrix of variants with a specific delivery date, then the matrix is applied but the date_planned remains stale (inherited from a prior line or default).

### `display_extra_price` Behavior

**Odoo 18:** `purchase_product_matrix._get_matrix()` called `_get_template_matrix()` without `display_extra_price`, consistent with Odoo 19 behavior.

**Odoo 19:** Same behavior. Supplier prices are dynamic and cannot be precomputed from attribute value extras alone.

### Client-Side `pol_product_many2one` Widget

The `pol_product_many2one` widget (defined in the `purchase` module) was enhanced in Odoo 19 to properly integrate with the matrix configurator for configurable products. This is a `purchase` module change, not a `purchase_product_matrix` change, but it is required for the matrix to open correctly.

---

## Cross-Module Integration Map

```
purchase_product_matrix
├── purchase
│   ├── purchase.order         ← grid fields, _set_grid_up, _apply_grid, _get_matrix
│   ├── purchase.order.line     ← product_template_id, is_configurable_product,
│   │                              product_no_variant_attribute_value_ids,
│   │                              _get_product_purchase_description
│   └── pol_product_many2one   ← widget that triggers matrix for configurable products
│
└── product_matrix             ← _get_template_matrix, ProductMatrixDialog OWL component,
                                   QWeb report templates
    └── product
        └── product.template   ← has_configurable_attributes, attribute lines, variants
```

---

## Extension Points

| Extension Point | File | Purpose |
|---|---|---|
| `purchase.order` | `models/purchase.py` | Three transient grid fields; implement `_set_grid_up`, `_apply_grid`, `_get_matrix`, `get_report_matrixes`, `_must_delete_date_planned` |
| `purchase.order.line` | `models/purchase.py` | Mirror template fields; implement `_get_product_purchase_description` |
| `ir.ui.view` | `views/purchase_views.xml` | Add invisible transient fields to PO form; add `report_grids` toggle; replace product_id column with product_template_id widget |

---

## See Also

- [[Modules/purchase]] — Base Purchase module (purchase.order, purchase.order.line)
- [[Modules/product_matrix]] — Technical matrix module (grid computation, OWL dialog, QWeb templates)
- [[Modules/sale_product_matrix]] — Analogous sale order matrix (uses `product_add_mode` gating)
