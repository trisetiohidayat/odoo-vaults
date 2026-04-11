---
type: module
module: product_matrix
tags: [odoo, odoo19, product, matrix, grid, configurator, sale, purchase, variant, owl]
created: 2026-04-06
updated: 2026-04-11
---

# Product Matrix

## Overview

| Property | Value |
|----------|-------|
| **Name** | Product Matrix |
| **Technical** | `product_matrix` |
| **Category** | Sales/Sales |
| **Version** | `1.0` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Technical base layer module providing the **matrix grid UI** for bulk product variant configuration. It does not stand alone — it is consumed by `sale_product_matrix` and `purchase_product_matrix`, which wire the grid into order workflows.

Responsibilities:
1. Computes the Cartesian product of attribute value combinations for a `product.template` via `_get_template_matrix()`
2. Renders the OWL `ProductMatrixDialog` component
3. Provides QWeb report templates for printing the grid on documents

## Dependencies

| Module | Reason |
|--------|--------|
| `account` | Used for the `section_and_note` widget (indirectly via data); not for accounting logic |

## Module Structure

```
product_matrix/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── product_template.py        # Two class extensions
├── data/
│   ├── res_groups.xml             # Group assignment (base.group_user → product.group_product_variant)
│   └── product_matrix_demo.xml    # Demo T-shirt product (9 sizes × 4 colors)
└── static/src/
    ├── js/
    │   ├── matrix_configurator_hook.js  # useMatrixConfigurator() OWL hook
    │   └── product_matrix_dialog.js     # ProductMatrixDialog OWL component
    ├── scss/
    │   └── product_matrix.scss          # Sticky header, spin-button removal, focus styles
    └── xml/
        ├── product_matrix.xml           # Grid QWeb template (dialog mode)
        └── product_matrix_dialog.xml    # Dialog wrapper QWeb template
```

---

## Models

### 1. `product.template` — Extended

**File:** `models/product_template.py`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
```

#### `_get_template_matrix(**kwargs)`

Builds the full Cartesian-product matrix grid for the template's attribute values.

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `company_id` | `int` | `self.company_id or env.company` | Company for currency conversion |
| `currency_id` | `int` | `self.currency_id` | Target currency for price conversion |
| `display_extra_price` | `bool` | `False` | Show attribute value price extras in headers |

**Returns:**
```python
{
    "header": [
        {"name": "My Company Tshirt (GRID)"},           # product name
        {"name": "Size: XS", "price": 0.0, "currency_id": 1},   # col headers
        {"name": "Size: S", "price": 0.0, "currency_id": 1},
        ...
    ],
    "matrix": [
        # Each row: [row_header_cell, data_cell, data_cell, ...]
        [
            {"name": "Color: Blue", "price": 0.0},           # row header
            {"ptav_ids": [id1, id5], "qty": 0, "is_possible_combination": True},
            {"ptav_ids": [id1, id6], "qty": 0, "is_possible_combination": True},
            ...
        ],
        ...
    ]
}
```

**L3 — How the Cartesian product is built:**

```python
attribute_ids_by_line = [line.product_template_value_ids._only_active().ids
                          for line in attribute_lines]
# [[id1,id2,id3], [id4,id5,id6]]  →  all combinations

result = [[]]
for pool in attribute_ids_by_line:
    result = [x + [y] for y in pool for x in result]
# Flat cartesian: [[id1,id4], [id1,id5], [id2,id4], ...]
args = [iter(result)] * len(first_line_attributes)
rows = itertools.zip_longest(*args)  # Regroup into rows by first attribute
```

Each row in the final matrix corresponds to one value from the **first** attribute line. The columns correspond to values from the first attribute line's values. Every cell is the Cartesian product of one row-value with one column-value.

**L3 — Row header computation:**

For each row, `row_attributes = Attrib.browse(row[0][1:])` strips the first element (column-header ID) and uses the rest as the row attribute values. This gives a clean row label. Then `_grid_header_cell()` is called on those attributes to produce the header dict with name and optional extra price.

**L3 — Combination possibility check:**

```python
is_possible_combination = self._is_combination_possible(combination)
```

This calls `product.template`'s built-in `_is_combination_possible()` method (from the `product` module), which validates the combination against attribute-line constraints (e.g., exclusion rules, pre-existing variant constraints). Cells where this returns `False` are rendered as disabled "Not available" cells.

**L2 — Why `valid_product_template_attribute_line_ids`?**

This is a `one2many` computed field on `product.template` (from the `product` module) that returns only attribute lines marked as `active`. Archived attribute lines are excluded from the matrix.

**L2 — `_only_active()`:**

Called on each `product_template_value_ids` recordset to filter out archived attribute values (those where `ptav.active = False`). Archived values should not appear in the grid.

---

### 2. `product.template.attribute.value` — Extended

**File:** `models/product_template.py`

```python
class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"
```

#### `_grid_header_cell(fro_currency, to_currency, company, display_extra=True)`

Generates a header cell dict for the matrix grid.

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `fro_currency` | `res.currency` | Source currency for price conversion |
| `to_currency` | `res.currency` | Target currency |
| `company` | `res.company` | Company record (for exchange rate date) |
| `display_extra` | `bool` | Whether to include price data (default `True`) |

**Returns:**
```python
{
    "name": "Color: Blue",           # always present
    "currency_id": 1,                # only if extra_price > 0
    "price": 10.00                   # only if extra_price > 0
}
```

**L2 — `name` concatenation:**

```python
'name': ' • '.join([attr.name for attr in self]) if self else " "
```

When called on a single ptav (e.g., a column header cell from `first_line_attributes`), `self` has one record and produces the simple name. When called on a multi-ptav `row_attributes` (from `row[0][1:]`), multiple values are joined with ` • `, producing names like `"Color: Red • Size: S"`.

The fallback `" "` (single space) for empty `self` prevents the grid from showing `"Not available"` for templates that have only one attribute line.

**L2 — `price_extra` vs final line price:**

```python
extra_price = sum(self.mapped('price_extra')) if display_extra else 0
```

`price_extra` is the **catalog surcharge** defined on the attribute value itself (set by the product manager). It is NOT the final sale price after pricelist application. The price badge in the grid header is intentionally labeled as catalog price. The comment in `matrix_templates.xml` explains: a pricelist rule may depend on the selected variant, so the `price_extra` of an attribute value is variable and cannot be accurately shown as a post-pricelist price.

**L2 — Currency conversion:**

```python
header_cell['price'] = fro_currency._convert(
    extra_price, to_currency, company, fields.Date.today())
```

Uses the ORM's `_convert()` method on `res.currency` with today's date. This respects the company's multi-currency settings.

**L3 — Why sum and not per-value display?**

The method sums all `price_extra` values in `self`. When called on column headers (single-ptav recordsets), this is a single value. When called on row headers (multi-ptav recordsset), this sums all row-attribute price extras. This lets the row header display the combined extra price of all row-level attribute values.

---

## Data Files

### `res_groups.xml`

```xml
<record id="base.group_user" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('product.group_product_variant'))]"/>
</record>
```

**Purpose:** Makes all standard internal users (`base.group_user`) implicitly members of `product.group_product_variant`. This grants the variant management access needed to open the matrix configurator. This is the only security-related data in the module.

### `product_matrix_demo.xml`

Creates a demo product template "My Company Tshirt (GRID)" with:
- **Attribute lines:** Size (XS through 5XL, 9 values) and Color (Blue, Pink, Yellow, Gold, 4 values)
- **Grid size:** 9 rows × 4 columns = 36 cells = 36 possible variant combinations
- The template is NOT set to `product_add_mode = 'matrix'` here — that is set by `sale_product_matrix`'s demo data override

---

## JavaScript Frontend

### `useMatrixConfigurator()` — OWL Hook

**File:** `static/src/js/matrix_configurator_hook.js`

```javascript
export function useMatrixConfigurator() {
    const dialog = useService("dialog");
    const open = async (record, edit) => {
        const rootRecord = record.model.root;
        await rootRecord.update({
            grid_product_tmpl_id: record.data.product_template_id,
        });
        // Build updatedLineAttributes array for edit mode
        ...
        openDialog(rootRecord, rootRecord.data.grid, pt_id, updatedLineAttributes);
        if (!edit) {
            rootRecord.data.order_line.delete(record);  // Remove stub line
        }
    };
    return { open };
}
```

**L3 — Stub line removal:**

When opening the matrix for a **new** line (`edit=false`), the user has already selected a product template before the dialog opens, which creates a stub `order_line` record in the current record. The hook deletes this stub after reading the matrix data to avoid leaving a dirty draft line on the form.

**L3 — `editedCellAttributes` for edit mode:**

```javascript
const updatedLineAttributes = [];
for (const ptnvav of record.data.product_no_variant_attribute_value_ids.records) {
    updatedLineAttributes.push(ptnvav.resId);
}
for (const ptav of record.data.product_template_attribute_value_ids.records) {
    updatedLineAttributes.push(ptav.resId);
}
updatedLineAttributes.sort((a, b) => a - b);
```

Collects both variant-defining (`ptav`) and no-variant (`ptnvav`) attribute value IDs from the existing line being edited, sorts them, and passes them to the dialog. The dialog uses this to auto-focus the matching input cell on mount.

### `ProductMatrixDialog` — OWL Component

**File:** `static/src/js/product_matrix_dialog.js`

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `header` | `Object` | `infos.header` — column header array |
| `rows` | `Object` | `infos.matrix` — 2D array of row arrays |
| `editedCellAttributes` | `String` | Comma-separated sorted ptav IDs to auto-focus |
| `product_template_id` | `Number` | Template ID, included in the change payload |
| `record` | `Object` | The root form record (sale/purchase order), used for `update()` |

**Template:** `product_matrix.dialog` (from `product_matrix_dialog.xml`) — wraps `product_matrix.matrix` in an OWL `Dialog` with a `Confirm` and `Discard` footer.

**`_onConfirm()` — Input extraction:**

```javascript
_onConfirm() {
    const inputs = document.getElementsByClassName('o_matrix_input');
    let matrixChanges = [];
    for (let matrixInput of inputs) {
        if (matrixInput.value && matrixInput.value !== matrixInput.attributes.value.nodeValue) {
            matrixChanges.push({
                qty: parseFloat(matrixInput.value),
                ptav_ids: matrixInput.attributes.ptav_ids.nodeValue.split(",").map(id => parseInt(id)),
            });
        }
    }
    if (matrixChanges.length > 0) {
        this.props.record.update({
            grid: JSON.stringify({
                changes: matrixChanges,
                product_template_id: this.props.product_template_id
            }),
            grid_update: true
        });
    }
    this.props.close();
}
```

**L3 — Diff-based writes:**

Only cells whose `value` differs from the original `value` attribute (the `nodeValue` of the `value` attribute on the input element) are included in `matrixChanges`. This avoids writing unchanged cells back to the server.

**L3 — Input attribute storage:**

```html
<input type="number"
       t-att="{'ptav_ids': cell.ptav_ids, 'value': cell.qty}"/>
```

The input element stores both `ptav_ids` (combination) and `value` (current qty) as HTML attributes. The `ptav_ids` is stored as a comma-separated string; `_onConfirm()` splits it back to an array.

**L3 — Auto-focus on mount:**

```javascript
onMounted(() => {
    if (this.props.editedCellAttributes.length) {
        const inputs = document.getElementsByClassName('o_matrix_input');
        const relevantInput = Array.from(inputs).filter(
            (matrixInput) =>
                matrixInput.attributes.ptav_ids.nodeValue === this.props.editedCellAttributes
        )[0];
        if (relevantInput) {
            relevantInput.select();
        } else {
            // Falls back to first input if no-variant attrs don't map to a cell
            inputs[0].select();
        }
    } else {
        document.getElementsByClassName('o_matrix_input')[0].select();
    }
});
```

**L3 — Hotkey for Enter confirmation:**

```javascript
useHotkey("enter", () => this._onConfirm(), {
    bypassEditableProtection: true,
    area: () => productMatrixRef.el,
});
```

The `bypassEditableProtection: true` flag allows the Enter key to fire from within `<input>` cells. The `area` restricts the hotkey to the matrix table, preventing unintended confirmation when pressing Enter elsewhere in the dialog.

### `format(cell)` — Price Badge Formatter

```javascript
_format({price, currency_id}) {
    if (!price) { return ""; }
    const sign = price < 0 ? '-' : '+';
    const formatted = formatMonetary(Math.abs(price), { currencyId: currency_id });
    return markup(`&nbsp;${sign}&nbsp;${formatted}&nbsp;`);
}
```

Formats the extra price as `+ $10.00` with a sign prefix. Used in both the dialog grid and the report template. `markup()` marks the string as pre-formatted HTML to prevent escaping.

---

## QWeb Report Templates

### `product_matrix.matrix` (Inline QWeb)

**File:** `views/matrix_templates.xml`

Used by the QWeb report system to render a read-only matrix on sale orders and pickings.

```xml
<table class="o_view_grid o_product_variant_grid table table-sm table-striped table-bordered">
    <thead>
        <tr>
            <th t-foreach="grid['header']" ...>
                <span t-esc="column_header['name']"/>
                <!-- extra_price badge -->
            </th>
        </tr>
    </thead>
    <tbody>
        <tr t-foreach="grid['matrix']" t-as="row">
            <!-- Row header cells (have 'name') render as <th> with label -->
            <!-- Data cells (no 'name') render as <td> showing qty -->
        </tr>
    </tbody>
</table>
```

**L3 — `get_report_matrixes()` filtering:**

`get_report_matrixes()` (in `sale_product_matrix`) filters the matrix before passing it to this template:
- Excludes rows where all non-header cells have `qty == 0` (empty rows)
- This is applied per-template before appending to the returned array

**L2 — CSS classes:**

- `o_view_grid` — base grid class for potential further styling
- `o_product_variant_grid` — semantic class for variant grids
- `table table-sm` — compact table sizing
- `table-striped table-bordered` — visual clarity

---

## Styles

**File:** `static/src/scss/product_matrix.scss`

| Selector | Purpose |
|----------|---------|
| `.o_matrix_input_table` | Base table wrapper |
| `.o_matrix_ps` / `.o_matrix_pe` | Left/right padding (padding-start / padding-end) via Bootstrap variables |
| `.o_matrix_input::-webkit-spin-button` | Hides number input arrows cross-browser for consistent alignment |
| `.o_matrix_input_td:focus-within` | Bottom-border highlight on the data cell when the input inside has focus |
| `thead { position: sticky; top: 0; z-index: 10 }` | Sticky column headers during scroll for large matrices |

**L4 — Sticky header design decision:**

For matrices with many rows (e.g., 9 sizes × 4 colors = 36 rows), the sticky header ensures column labels remain visible while scrolling down. This is critical for usability in large grids.

---

## L4: Performance, Security, Historical Context

### Performance Implications

**1. Full matrix computation server-side:**

`_get_template_matrix()` runs on the Odoo server in Python. The Cartesian product of all attribute values is computed and serialized in one pass. For a template with `N` total attribute values spread across `L` lines, the total number of cells is `Π(values_per_line)`. Performance benchmarks:

| Configuration | Cells | Assessment |
|---|---|---|
| 2 lines × 4 values each | 16 | Trivial |
| 2 lines × 9 + 4 values | 36 | Lightweight |
| 3 lines × 5 values each | 125 | Moderate |
| 4 lines × 5 values each | 625 | Large but manageable |

**2. `_is_combination_possible()` called per cell:**

The method calls `self._is_combination_possible(combination)` for every cell in the matrix. Each call involves a search for exclusion rules and attribute-line constraints. For a 625-cell matrix, this is 625 separate checks. This is the primary performance concern for large matrices. The `product` module's implementation uses cached results where possible.

**3. No O2M lazy-loading issue:**

By computing the matrix in Python and serializing to JSON, the module bypasses the Odoo web client's lazy-loading limitation where only the first ~40 rows of a one2many are loaded in the form view. The full matrix is always available.

**4. JSON serialization round-trip:**

The `json.dumps()` / `json.loads()` in onchange handlers adds negligible overhead for typical matrix sizes. The payload is a flat structure of arrays.

### Security Considerations

**1. Group assignment via demo data:**

The `res_groups.xml` file adds `product.group_product_variant` as an implied group of `base.group_user`. This means every internal user automatically gets variant management access. This is appropriate because the matrix is fundamentally a variant management interface.

**2. No field-level ACLs:**

The `product_add_mode` field (added by `sale_product_matrix`) has no `groups` attribute. Any user who can edit the product template can switch the mode. This is intentional — the mode only affects the UX on sale orders.

**3. No raw SQL:**

All database operations use the ORM's `browse()`, `write()`, `create()`, and `filtered()` methods. No `self.env.cr.execute()` calls exist in the module.

**4. `report_grids` restricted to `base.group_no_one`:**

The "Print Variant Grids" toggle on sale orders is visible only to users with technical/debug access (`base.group_no_one`), as defined in `sale_product_matrix`. Regular salespersons should not control this.

### Odoo 17 → 18 → 19 Historical Changes

**Odoo 17:**

First introduction of the matrix entry UI as `sale_product_matrix`. The dialog was implemented using OWL 1.x. Matrix data was stored via a similar transient field pattern.

**Odoo 18:**

No major architectural changes to the core matrix computation in `product_matrix`. The `product_add_mode` field was introduced in `sale_product_matrix` for explicit per-template mode selection.

**Odoo 19:**

Key changes:
1. **OWL 2.x migration:** The JS code was updated to use OWL 2.x patterns. `Component`, `onMounted`, `markup`, `useRef`, and `useHotkey` are all from the OWL 2.x API.
2. **Hook-based architecture:** The `useMatrixConfigurator()` hook replaces older patching patterns, using `useService("dialog")` and OWL component composition.
3. **`_get_template_matrix()` is stable:** The method signature and behavior are unchanged from Odoo 18.
4. **SCSS sticky headers:** The `position: sticky` CSS was added in Odoo 19 to improve usability of large grids.

### Edge Cases

**1. Single attribute line:**

When the template has only one attribute line, the matrix degenerates to a single row. The `_grid_header_cell()` method returns `" "` (a space) as the row label when `self` is empty, preventing "Not available" from rendering in the row header.

**2. Archived attribute values:**

`_only_active()` filters archived ptav records. Archived attribute values should not appear in the grid. This is enforced both in `_get_template_matrix()` and in `sale_product_matrix`'s `_get_matrix()` overlay.

**3. No-variant attributes:**

These do not create new variants but are stored on the SOL as `product_no_variant_attribute_value_ids`. The `sale_product_matrix._apply_grid()` method handles these separately via `_without_no_variant_attributes()`. In the grid itself, no-variant attribute lines are not rendered as separate rows or columns — only variant-defining attribute lines contribute to the Cartesian product.

**4. Dynamic attribute lines (`create_variant = 'dynamic'`):**

When an attribute line has `create_variant = 'dynamic'`, the variant may not exist until the combination is saved. `_create_product_variant()` is called on-demand in `_apply_grid()`. The matrix still shows the cell as `is_possible_combination` based on constraints, but the product record is created only when the user confirms.

**5. Impossibly constrained combinations:**

If the template has attribute exclusion rules (via `product.template.attribute.line.exclude_for` or similar), `_is_combination_possible()` will return `False` for those cells. The cell is rendered with "Not available" text and no input field.

**6. Zero `price_extra`:**

When an attribute value has no extra price, `_grid_header_cell()` returns a dict without `price` or `currency_id` keys. The QWeb template's `t-if="price"` check handles this gracefully — no badge is rendered.

---

## Integration Points

### With `sale_product_matrix`

The primary consumer. Adds:
- `product_add_mode` Selection field on `product.template`
- Three transient fields on `sale.order`: `grid`, `grid_product_tmpl_id`, `grid_update`
- `report_grids` Boolean on `sale.order`
- `_set_grid_up()`, `_apply_grid()`, `_get_matrix()`, `get_report_matrixes()` on `sale.order`
- JS patch on `SaleOrderLineProductField` to open the dialog

### With `purchase_product_matrix`

Analogous to `sale_product_matrix` but for purchase orders. Uses the same `_get_template_matrix()` from `product_matrix` but with `display_extra_price=False` (extra prices are not shown for purchases since they represent optional catalog surcharges on sales, not on costs).

### With `product` module

- `product.template`: Provides `_is_combination_possible()` and `valid_product_template_attribute_line_ids`
- `product.template.attribute.line`: Defines attribute lines (values per line)
- `product.template.attribute.value`: Provides `price_extra`, `_without_no_variant_attributes()`
- `product.product`: Created dynamically via `_create_product_variant()`

---

## See Also

- [[Modules/product]] — Product template, attribute lines, variant creation logic
- [[Modules/sale_product_matrix]] — Sale order grid entry (primary consumer)
- [[Modules/purchase_product_matrix]] — Purchase order grid entry
- [[Modules/sale_product_configurator]] — Standard single-variant configurator dialog
