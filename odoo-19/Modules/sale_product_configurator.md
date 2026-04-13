---
title: sale_product_configurator
tags:
  - odoo
  - odoo19
  - sale
  - product-configurator
  - modules
description: Product and combo configurator for sale order lines — dialog-based variant selection, optional products, exclusions, and attribute customization.
---

# sale_product_configurator

> **Note on naming:** In Odoo 19, the product configurator is not a standalone module. The server-side logic lives in `sale/controllers/product_configurator.py`, while the frontend lives in `sale/static/src/js/product_configurator_dialog/`. This document covers all configurator-related code in the `sale` module, including the companion `sale_product_matrix` module.

## Module Overview

**Category:** Sales/Sales
**Depends:** `sale_management`, `sale_product_matrix`, `event_sale` (test module)
**Key files:**

- `sale/controllers/product_configurator.py` — HTTP API endpoints (server side)
- `sale/controllers/combo_configurator.py` — HTTP API endpoints for combo products
- `sale/static/src/js/product_configurator_dialog/product_configurator_dialog.js` — OWL dialog component
- `sale/static/src/js/combo_configurator_dialog/combo_configurator_dialog.js` — OWL combo dialog
- `sale/models/product_template.py` — `_get_configurator_display_price` hook, `optional_product_ids`
- `sale/models/sale_order_line.py` — attribute tracking fields

The configurator has **no Python transient model** (wizard). All state is held client-side in the OWL `ProductConfiguratorDialog` component. Server endpoints are stateless JSON-RPC routes.

---

## Server-Side API

### `SaleProductConfiguratorController`

**Module:** `sale.controllers.product_configurator`
**Inherits:** `odoo.http.Controller`

---

#### `GET /sale/product_configurator/get_values`

Fetches full product configuration data: attribute lines, exclusions, pricing, optional products.

**Route:** `/sale/product_configurator/get_values`
**Auth:** `user`
**Type:** `jsonrpc`
**Readonly:** `True`

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `product_template_id` | `int` | Yes | `product.template` ID |
| `quantity` | `int` | Yes | Quantity for price computation |
| `currency_id` | `int` | Yes | `res.currency` ID |
| `so_date` | `str` | Yes | ISO-8601 date string of the `sale.order` |
| `product_uom_id` | `int\|None` | No | `uom.uom` ID |
| `company_id` | `int\|None` | No | `res.company` ID |
| `pricelist_id` | `int\|None` | No | `product.pricelist` ID |
| `ptav_ids` | `list(int)\|None` | No | Pre-selected `product.template.attribute.value` IDs (the combination) |
| `only_main_product` | `bool` | No | If `True`, skips optional products (used when editing a combo item) |

**Returns:**

```python
{
    'products': [
        {
            'product_tmpl_id': int,
            'id': int | False,           # product.product ID, False if template only (dynamic attrs)
            'description_sale': str | False,
            'display_name': str,
            'price': float,
            'quantity': int,
            'uom': {'id': int, 'display_name': str},
            'attribute_lines': [
                {
                    'id': int,              # product.template.attribute.line ID
                    'attribute': {
                        'id': int,
                        'name': str,
                        'display_type': str,  # 'radio', 'select', 'color', 'pill', 'multi'
                    },
                    'attribute_values': [
                        {
                            'id': int,
                            'name': str,
                            'price_extra': float,       # converted to SO currency
                            'html_color': str | False,
                            'image': str | False,
                            'is_custom': bool,
                        }
                    ],
                    'selected_attribute_value_ids': [int, ...],
                    'create_variant': str,  # 'always', 'dynamic', 'no_variant'
                }
            ],
            'exclusions': dict,              # {str(ptav_id): [excluded_ptav_id, ...]}
            'archived_combinations': list,   # combinations whose variant was archived
            'parent_exclusions': dict,       # exclusions driven by parent product combination
            'available_uoms': [{'id', 'display_name'}] | None,
        }
    ],
    'optional_products': [/* same structure, plus parent_product_tmpl_id */],
    'currency_id': int,
}
```

**Internal logic:**

1. Resolves `company_id` into `request.update_context(allowed_company_ids=[...])` — critical for multi-company security
2. Filters `ptav_ids` to only those belonging to the requested `product_template_id`
3. Auto-fills missing `no_variant` attributes with `_only_active()[:1]` default values
4. If no `ptav_ids` provided, falls back to `_get_first_possible_combination()` — respects exclusion rules
5. For optional products: passes **all** PTAVs of the parent's attribute lines (not just the selected combination) to `_get_attribute_exclusions` so cross-product exclusions are computed correctly
6. Strips `pricelist_rule_id` from returned dict — internal field not meant for client

**Exclusions logic (L4 detail):**

```
exclusions dict: {ptav_id_A: [ptav_id_B, ...]}  # A excludes B
parent_exclusions dict: {ptav_id_parent: [ptav_id_child_excluded, ...]}  # from parent combination
archived_combinations: [[ptav_id, ...], ...]  # combinations with inactive variants
```

When a variant is archived (e.g., attribute value removed after SO use), its PTAVs are included in `archived_combinations`. The client marks those PTAVs as `excluded=true` to prevent selection, but the exclusion is soft — the UI shows them differently rather than blocking outright.

---

#### `POST /sale/product_configurator/create_product`

Creates a new `product.product` variant when dynamic attributes are involved.

**Route:** `/sale/product_configurator/create_product`
**Auth:** `user`
**Type:** `jsonrpc`
**Methods:** `POST`

**Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `product_template_id` | `int` | Yes | `product.template` ID |
| `ptav_ids` | `list(int)` | Yes | `product.template.attribute.value` IDs |

**Returns:** `int` — created `product.product` ID

**Failure modes:**

- If variant already exists: `product_template._create_product_variant` returns the existing one; no duplicate is created
- If combination is excluded or invalid: variant creation fails silently (the combination won't be created)

---

#### `POST /sale/product_configurator/update_combination`

Called when the user changes a PTAV selection — returns updated price, name, and basic info.

**Route:** `/sale/product_configurator/update_combination`
**Auth:** `user`
**Type:** `jsonrpc`
**Methods:** `POST`
**Readonly:** `True`

**Parameters:** Same as `get_values` minus `only_main_product`

**Returns:** Basic product info dict (same keys as returned by `_get_basic_product_information`)

**Performance note:** This endpoint is called on every attribute selection change. It uses `_get_basic_product_information` which skips attribute line computation — only pricing and display name are recalculated. For high-cardinality attributes (e.g., >20 values), consider debouncing client-side.

---

#### `GET /sale/product_configurator/get_optional_products`

Fetches optional products when the main product's combination changes.

**Route:** `/sale/product_configurator/get_optional_products`
**Auth:** `user`
**Type:** `jsonrpc`
**Readonly:** `True`

**Parameters:** Same as `update_combination`, plus `parent_ptav_ids` (the parent product's combination)

**Key logic:** `parent_combination` is constructed as `parent_ptav_ids + ptav_ids` (child's ptavs appended), ensuring cross-product exclusion rules are respected when recomputing which optional products are valid.

---

### Helper Methods

#### `_get_product_information(product_template, combination, currency, pricelist, so_date, ...)`

Full product data for the configurator dialog.

**Returned dict keys (full):**

| Key | Type | Description |
|---|---|---|
| `product_tmpl_id` | `int` | Template ID |
| `id` | `int\|False` | Variant ID (False if no variant exists yet) |
| `description_sale` | `str\|False` | Sale description |
| `display_name` | `str` | Template + combination name |
| `price` | `float` | Computed price |
| `quantity` | `int` | Quantity |
| `uom` | `dict` | UoM with id and display_name |
| `attribute_lines` | `list` | PTALs with PTAVs and selected values |
| `exclusions` | `dict` | Intra-product exclusions |
| `archived_combinations` | `list` | Archived variant combinations |
| `parent_exclusions` | `dict` | Cross-product exclusions |
| `available_uoms` | `list\|None` | Multiple UoMs (if applicable) |

**Price extra computation (`_get_ptav_price_extra`):**

```python
ptav.currency_id._convert(
    ptav.price_extra,          # stored in ptav's own currency
    currency,                  # SO's currency
    request.env.company,       # current company
    date.date(),               # SO date for exchange rate
)
```

The `price_extra` field on `product.template.attribute.value` is stored in the PTAV's own currency (usually company currency). This conversion handles multi-currency scenarios in the SO line.

---

#### `_get_basic_product_information(product_or_template, pricelist, combination, **kwargs)`

Returns only `id`, `description_sale`, `display_name`, `price`. Used for fast updates.

**Special handling:** If the product is a template (not a variant), the `id` is explicitly set to `False` and the combination name is appended to `display_name`:

```python
display_name = "Product Name (Color: Red, Size: L)"
```

This ensures the user sees which variant is configured even before the `product.product` record is created.

---

### `SaleComboConfiguratorController`

**Module:** `sale.controllers.combo_configurator`

Combo products (`product.template.type == 'combo'`) are a separate product type where customers pick items from predefined combinations. The combo configurator is a distinct dialog that nests inside the product configurator when a combo item has configurable attributes.

---

#### `GET /sale/combo_configurator/get_data`

**Route:** `/sale/combo_configurator/get_data`
**Auth:** `user`
**Type:** `jsonrpc`
**Readonly:** `True`

Returns full combo product data including all `combo_ids` and their `combo_item_ids`.

**Returns:**

```python
{
    'product_tmpl_id': int,
    'display_name': str,
    'quantity': int,
    'price': float,
    'combos': [
        {
            'id': int,            # product.combo ID
            'name': str,
            'combo_items': [
                {
                    'id': int,
                    'extra_price': float,
                    'is_preselected': bool,
                    'is_selected': bool,
                    'is_configurable': bool,   # has no_variant or custom PTAVs
                    'product': {
                        'id': int,
                        'product_tmpl_id': int,
                        'display_name': str,
                        'ptals': [...],
                        'description': str,
                        ...  # additional data from _get_additional_configurator_data
                    }
                }
            ]
        }
    ],
    'currency_id': int,
}
```

**`is_configurable` detection logic:**

```python
is_configurable = any(
    ptal.attribute_id.create_variant == 'no_variant' and ptal._is_configurable()
    for ptal in combo_item.product_id.attribute_line_ids
) or any(
    ptav.is_custom
    for ptav in combo_item.product_id.product_template_attribute_value_ids
)
```

A combo item product is configurable if it has either:
1. `no_variant` attributes that are configurable (display_type != 'multi' and value_count > 1)
2. Custom PTAVs (`is_custom=True`, e.g., text engraving)

**`is_preselected` logic:**

```python
is_preselected = len(combo.combo_item_ids) == 1 and not is_configurable
```

A combo item is auto-selected if its combo has only one item and that item is not configurable.

---

#### `GET /sale/combo_configurator/get_price`

Returns only the computed combo price (used for quantity changes without re-fetching full data).

---

## `sale_order_line` Fields for Configurator

**Model:** `sale.order.line`

| Field | Type | Description |
|---|---|---|
| `product_template_attribute_value_ids` | `Many2many` (related) | Links to `product.template.attribute.value` records for the selected variant |
| `product_custom_attribute_value_ids` | `One2many` → `product.attribute.custom.value` | Custom text values entered by customer (e.g., engraving text) |
| `product_no_variant_attribute_value_ids` | `Many2many` → `product.template.attribute.value` | `no_variant` attribute values tracked on the line (extra price, description) |
| `is_configurable_product` | `Boolean` (related) | `product_template_id.has_configurable_attributes` — True if the product needs the configurator |
| `selected_combo_items` | `Char` | Local storage (JSON) of selected combo items for combo product lines |
| `combo_item_id` | `Many2one` → `product.combo.item` | If this SOL is a combo item, links back to the combo item |

---

### `_compute_custom_attribute_values`

**Purpose:** Sanitizes `product_custom_attribute_value_ids` on load.

If the product's attribute lines have been modified (e.g., attribute value removed from template after SO creation), invalid custom values are removed:

```python
valid_values = line.product_id.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids
for pacv in line.product_custom_attribute_value_ids:
    if pacv.custom_product_template_attribute_value_id not in valid_values:
        line.product_custom_attribute_value_ids -= pacv
```

**L4 detail:** `valid_product_template_attribute_line_ids` only includes PTALs where all values are active (`ptav_active=True`). Archived attribute values are excluded from the valid set, preventing stale custom values from being retained.

---

### `_compute_no_variant_attribute_values`

Same sanitization for `no_variant` attributes:

```python
valid_values = line.product_id.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids
for ptav in line.product_no_variant_attribute_value_ids:
    if ptav._origin not in valid_values:
        line.product_no_variant_attribute_value_ids -= ptav
```

---

### `_get_sale_order_line_multiline_description_variants`

Appends configurator-specific text to the line description for reporting and portal display:

```python
# 1. No-variant attributes with single value are described (except multi-checkbox)
for ptav in no_variant_ptavs:
    name += "\n" + ptav.display_name

# 2. Multi-checkbox attributes grouped per attribute
for pta, ptavs in groupby(multi_ptavs):
    name += "\nColor: Red, Blue"

# 3. Custom text values
for pacv in sorted_custom_ptav:
    name += "\n" + pacv.display_name  # e.g., "Engraving: Happy Birthday"
```

---

## `product.template` Extension

**Model:** `product.template`
**Inherits:** `product.template`

### `optional_product_ids`

```python
optional_product_ids = fields.Many2many(
    comodel_name='product.template',
    relation='product_optional_rel',
    column1='src_id',
    column2='dest_id',
    string="Optional Products",
    check_company=True,
)
```

Stored in `product_optional_rel` (many2many). When the configurator dialog opens for a main product, optional products are loaded from this relation and checked against `_should_show_product`.

** `_should_show_product` logic (overrideable hook):**

```python
def _should_show_product(self, product_template, parent_combination):
    return True  # Always show by default
```

Override in `website_sale` to hide optional products that are not available for the current website.

---

### Hook Methods

#### `_get_configurator_display_price(product_or_template, quantity, date, currency, pricelist, **kwargs)`

Hook for customizing display price in overriding modules. Returns `(price, pricelist_rule_id)`.

**Odoo 18→19 change:** The signature was extended with `**kwargs` to allow passing additional context without breaking overrides.

#### `_get_configurator_price(product_or_template, quantity, date, currency, pricelist, **kwargs)`

Lower-level hook: actually computes the price via `pricelist._get_product_price_rule()`.

**Override pattern (from code comments):**

```
sale: _get_configurator_price → returns base price
website_sale: overrides to apply website-specific prices + taxes
sale_subscription: overrides to compute subscription-specific prices
website_sale_subscription: computes subscription price THEN applies taxes
```

Two separate hooks allow independent override ordering.

#### `_get_additional_configurator_data(product_or_template, date, currency, pricelist, **kwargs)`

Hook for appending module-specific data (e.g., `website_sale` adds `sales_delay`, `website_url` to product data).

---

## `ProductConfiguratorDialog` (OWL Component)

**File:** `sale/static/src/js/product_configurator_dialog/product_configurator_dialog.js`
**Framework:** OWL 2.x
**Template:** `sale.ProductConfiguratorDialog`

### Props

| Prop | Type | Description |
|---|---|---|
| `productTemplateId` | `Number` | The `product.template` ID |
| `ptavIds` | `Number[]` | Pre-selected PTAV IDs |
| `customPtavs` | `{id, value}[]` | Pre-filled custom values |
| `quantity` | `Number` | Initial quantity |
| `productUOMId` | `Number` (optional) | Unit of measure |
| `companyId` | `Number` (optional) | Company context |
| `pricelistId` | `Number` (optional) | Pricelist |
| `currencyId` | `Number` (optional) | Currency |
| `selectedComboItems` | `{name}[]` (optional) | Combo items (nested configurator) |
| `soDate` | `String` | SO date as ISO string |
| `size` | `String` | Dialog size: `sm\|md\|lg\|xl\|fs\|fullscreen` |
| `edit` | `Boolean` | If `True`, optional products panel is hidden |
| `options` | `Object` | `{canChangeVariant, showQuantity, showPrice, showPackaging}` |
| `save` | `Function` | Callback when confirmed |
| `discard` | `Function` | Callback when cancelled |

### State

```javascript
state = {
    products: [],          // Selected products (moved from optionalProducts)
    optionalProducts: [], // Available optional products
}
```

### Key Client-Side Methods

#### `_checkExclusions(product)`

Marks PTAVs as `excluded` based on three exclusion sources:

1. **Product exclusions** (`exclusions` dict): Within-product mutual exclusions defined via `product.template.attribute.value.exclude_for`
2. **Parent exclusions** (`parent_exclusions` dict): Exclusions from the parent product's combination (when optional products are involved)
3. **Archived combinations** (`archived_combinations`): Variants archived because their attribute values were removed after the product was used in an SO

**Archived combination logic (L4):**

```javascript
// If the combination matches an archived variant entirely, mark all PTAVs excluded
if (ptavCommon.length === combination.length) {
    // Full match: mark all excluded
}
// If one PTAV differs, only disable the differing one (partial archive)
else if (ptavCommon.length === (combination.length - 1)) {
    // Partial: only the non-matching PTAV is excluded
}
```

This preserves the archived combination as a reference while making it clear the combination is unavailable.

#### `_isPossibleCombination(product)`

```javascript
return product.attribute_lines.every(ptal =>
    ptal.attribute_values
        .filter(ptav => selectedPtavIds.has(ptav.id))
        .every(ptav => !ptav.excluded)
);
```

Returns `False` if any selected PTAV has `excluded=true`. Prevents the confirm action from proceeding.

#### `onConfirm(options)`

1. Validates `isPossibleConfiguration()`
2. For each product with dynamic attributes (`create_variant === "dynamic"`) and no existing `id`: calls `/sale/product_configurator/create_product` to create the variant
3. Calls `props.save(mainProduct, additionalProducts, options)` with selected products
4. Closes dialog

**Performance note:** Products with `create_variant === "always"` (standard variants) are never created here — they must exist in the database. Only `dynamic` variants are created on-the-fly.

---

## `ComboConfiguratorDialog` (OWL Component)

**File:** `sale/static/src/js/combo_configurator_dialog/combo_configurator_dialog.js`
**Nested usage:** When a combo item's product is configurable, this dialog opens `ProductConfiguratorDialog` as a sub-dialog with `edit=true` and all options disabled (`canChangeVariant: false`, `showQuantity: false`, `showPrice: false`, `showPackaging: false`).

### State

```javascript
state = {
    selectedComboItems: Map(comboId -> selectedOrProvidedComboItem),
    quantity: Number,
    basePrice: Number,
    isLoading: Boolean,
}
```

### `_getComboItemData` (server-side helper)

**Decision tree for combo item state:**

```
is_configurable?
├─ YES: requires product configurator sub-dialog
└─ NO:
    is_preselected? (len(combo.combo_item_ids) == 1)
    ├─ YES: auto-selected, is_selected=true
    └─ NO: not selected until user clicks
```

---

## Cross-Module Integrations

| Module | Integration Point | Purpose |
|---|---|---|
| `website_sale` | `_should_show_product` override | Hide optional products unavailable on current website |
| `website_sale` | `_get_additional_configurator_data` override | Adds `sales_delay`, `website_url` to product data |
| `website_sale` | `_get_configurator_display_price` override | Applies website pricing + tax display rules |
| `sale_subscription` | `_get_configurator_display_price` override | Computes subscription-aware pricing |
| `sale_subscription` | `_get_configurator_price` override | Subscription price computation |
| `website_sale_stock` | `product_configurator_dialog` copy | Stock-aware configurator |
| `point_of_sale` | `product_configurator_popup` copy | POS configurator for variants |
| `event_sale` | Test module dependencies | Tests configurator with event tickets |

---

## Edge Cases and Failure Modes

### 1. Archived variant with active combination
When an attribute value is removed from a template after being used in a confirmed SO:
- The `product.product` is **archived** (not deleted) to preserve SO referential integrity
- The configurator returns the archived combination in `archived_combinations`
- The client marks those PTAVs as `excluded=true`
- `onConfirm` will still succeed for `dynamic` variants — the archived variant is not re-created

### 2. `no_variant` attributes with single value
If a `no_variant` attribute has only one value, it is pre-selected automatically:

```python
unconfigured_ptals = (
    product_template.attribute_line_ids - combination.attribute_line_id
).filtered(lambda ptal: ptal.attribute_id.display_type != 'multi')
combination += unconfigured_ptals.mapped(
    lambda ptal: ptal.product_template_value_ids._only_active()[:1]
)
```

The `[:1]` takes the first active value as default.

### 3. Multi-company security
`company_id` from the SO is passed to the RPC and set via `request.update_context(allowed_company_ids=[company_id])`. This ensures:
- Pricelist rules are evaluated for the correct company
- Attribute exclusions are computed for the correct company's product data
- Currency conversions use the correct company's currency

### 4. Currency conversion in `price_extra`
`ptav.price_extra` is stored in the PTAV's currency (usually the company default). The configurator converts to the SO's currency using `date.date()` (SO date) as the conversion date — not `today()`, ensuring consistent pricing even if exchange rates change after the SO is created.

### 5. `selected_combo_items` local storage
For combo product lines, `selected_combo_items` is stored as a `Char` field (not a relation) to avoid database overhead for pre-confirmation selections. It is serialized JSON, populated on `onConfirm` and deserialized when opening the dialog in `edit` mode.

### 6. Duplicate attribute lines (same attribute on multiple PTALs)
Supported since Odoo 19 (test added: `test_multiple_attribute_lines_same_attribute`). The `attrs_map` uses `ptal.attribute_id.id` as key — when the same attribute appears on multiple PTALs, the second entry overwrites the first in the dict. The client-side rendering uses the PTAL object directly (not the map), so both lines render correctly with their own selected values.

---

## Performance Considerations

| Operation | Concern | Mitigation |
|---|---|---|
| `get_values` (initial load) | Reads all PTAVs, computes exclusions | Uses `filtered()` on active records only |
| `update_combination` (on PTAV change) | Called on every selection change | Returns minimal data (no attribute lines) |
| `get_optional_products` | Re-fetches all optional products on every change | Only called when main product's combination changes |
| `_get_attribute_exclusions` | N+1 if called per product | Called once per product in `_get_product_information` |
| Combo item data | Reads all `combo_item_ids` per combo | `sudo()` used to avoid access rights overhead in controller |

---

## Historical Changes (Odoo 18 → 19)

| Change | Impact |
|---|---|
| `_get_configurator_display_price` signature added `**kwargs` | Allows passing extra params without breaking overrides |
| `_get_configurator_price` split from `_get_configurator_display_price` | Enables independent override ordering for `website_sale_subscription` |
| `product_template_id` field made independently editable | Previously always derived from `product_id`; now can be set separately for configurator UX without writing `product_id` |
| `get_single_product_variant` extended with `is_combo` check | Combo products now use the combo configurator instead of the standard variant configurator |
| `archived_combinations` returned in `get_values` | New in 19 — handles archived variants after attribute removal |
| `test_multiple_attribute_lines_same_attribute` test | New in 19 — verifies same attribute on multiple PTALs works without KeyError |

---

## Security Considerations

- All routes require `auth='user'` — anonymous access is blocked
- `company_id` parameter is trusted (set from the SO's company, not user-supplied); multi-company record rules apply
- `_get_additional_configurator_data` is a hook — overriding modules must not expose sensitive fields
- Portal access for configured lines follows standard SO access control; no extra ACLs are needed since attribute values are linked to existing products the user already has access to

---

## See Also

- [Modules/sale](Sale.md) — Sale order base
- [Modules/product](Product.md) — Product and attribute definitions
- [Modules/sale_management](sale_management.md) — Sale management features
- [Modules/website_sale_product_configurator](website_sale_product_configurator.md) — Website-side configurator (EE)
- [Modules/sale_product_matrix](sale_product_matrix.md) — Grid-based matrix entry
