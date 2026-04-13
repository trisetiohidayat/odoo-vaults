# Product Comparison

## Overview

| Property | Value |
|---|---|
| **Technical Name** | `website_sale_comparison` |
| **Category** | Website/Website |
| **Depends** | `website_sale` |
| **Summary** | Allow shoppers to compare products based on their attributes |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Auto-install** | `True` |
| **Installable** | `True` |
| **Version** | `1.0` |

## What It Does

This module adds a product comparison tool to the eCommerce shop. Shoppers can add products to a comparison list (stored in a browser cookie, max 4 products) and view them side-by-side at `/shop/compare`. Products are displayed in a table organized by attribute categories. Each product page also gains an optional "Specifications" table (toggled via the Customize menu) that shows attributes grouped by their eCommerce category.

Configuration lives in **Website > Configuration > Attributes & Variants**. The module adds a `category_id` field to `product.attribute` records, allowing admin to group attributes into named categories (e.g., "General Features", "Technical Specs") that control the layout order on both the comparison page and the per-product specifications table.

---

## Models

### `product.attribute.category`

_new model introduced by this module_

Groups `product.attribute` records into named sections for display ordering on the comparison page and product page specifications table. Does not exist in `product`; introduced here.

**Fields**

| Field | Type | Required | Default | Index | Help |
|---|---|---|---|---|---|
| `name` | `Char` | Yes | — | No | Category name. Supports `translate=True`. |
| `sequence` | `Integer` | No | `10` | Yes | Controls display order via `_order = 'sequence, id'`. |
| `attribute_ids` | `One2many` (`product.attribute`, `category_id`) | No | — | No | Inverse of `category_id` on `product.attribute`. Shows attributes in this category. Note: the domain `[('category_id', '=', False)]` on the inverse means the tree view only shows uncategorized attributes, preventing double-assignment in the UI. |

**Key Design Notes**
- `sequence` is indexed for fast sorting in large catalogs.
- `attribute_ids` is display-only; the owning side is `product.attribute.category_id`.
- The domain on `attribute_ids` in the backend view (`[('category_id', '=', False)]`) prevents a category from listing itself as one of its own members, but does not enforce this constraint at ORM level — assignment is controlled by writing `category_id` on `product.attribute`.

**Security** (via `ir.model.access.csv`)
- `base.group_public`: read-only
- `base.group_portal`: read-only
- `base.group_user`: read-only
- `sales_team.group_sale_manager`: read + write + create + unlink

The Sale Manager gets write access so they can reorder categories. Regular employees and public users are read-only.

---

### `product.attribute` — Extended

_inherits `product.attribute`_

**Fields Added by This Module**

| Field | Type | Required | Default | Index | Help |
|---|---|---|---|---|---|
| `category_id` | `Many2one` (`product.attribute.category`) | No | `False` | Yes | eCommerce category grouping. Setting this on an attribute assigns it to a named section in the comparison table and product specifications table. |

**Why `category_id` exists**
Without this field, attributes display in arbitrary sequence order on the comparison table. `category_id` provides a semantic grouping (e.g., "Display", "Processor", "Battery") so shoppers see related attributes grouped together rather than interleaved.

**Override Pattern**: Classic `_inherit = 'product.attribute'` extension. No method overrides.

**L3 — Cross-model Relationships**
- O2O side of `product.attribute.category.attribute_ids` (owning side).
- `product.template.attribute.line` references `product.attribute` via `attribute_id`; `_prepare_categories_for_display()` on the line reads `attribute_id.category_id`.
- On the comparison page, attributes are collected via `product.product.product_tmpl_id.valid_product_template_attribute_line_ids.attribute_id` → then `.category_id.sorted()`.

---

### `product.template.attribute.line` — Extended

_inherits `product.template.attribute.line`_

**Methods Added by This Module**

#### `_prepare_categories_for_display()`

Groups this recordset's attribute lines by the `category_id` of their `attribute_id`, returning an `OrderedDict` keyed by category. Used on the product page to render the optional specifications table.

**Signature**
```python
def _prepare_categories_for_display(self) -> OrderedDict
```

**Return Value Structure**
```
OrderedDict({
    product.attribute.category: product.template.attribute.line recordset,
    ...
})
```

**Logic, Step by Step**

1. Reads `self.attribute_id` — the related `product.attribute` records.
2. Creates an `OrderedDict` keyed by each category (sorted by `category_id.sequence`).
3. Handles uncategorized attributes: if any `pa.category_id` is falsy (category is not set), a `product.attribute.category` record with id=0 / empty browse is inserted as the fallback key. This ensures all attributes appear in the table even without a category assigned.
4. Iterates over `self` (the lines), adding each line to the correct category bucket via `|=` (recordset union).

**Why this method exists**
The product page's specifications table needs to render a row per attribute category, then rows within each category per attribute line. Without grouping, attributes would appear in arbitrary database order. The method also handles the `no_variant` edge case — if a line's attribute is `create_variant=False`, all possible values should be shown, not just those tied to a specific combination.

**L3 — Trigger**
Called during QWeb rendering of `website_sale_comparison.specifications_table`. Not called by ORM; purely a presentation helper.

**L3 — Failure Modes**
- Returns empty `OrderedDict` if `self` is empty or all attribute lines have `attribute_id` with no `category_id` and the empty-category bucket is never populated (should not happen — step 3 always adds the fallback key).
- If a `product.attribute` record referenced by a line is deleted, the attribute is silently dropped from the result set (ORM behavior).

**Performance Note**
Called twice on the product page: once for the main specifications section and once for the accordion variant. Consider caching in the template if the product page is slow with many attribute lines.

---

### `product.product` — Extended

_inherits `product.product`_

**Methods Added by This Module**

#### `_prepare_categories_for_display()`

Groups all products in `self` (a recordset of variants being compared) by category → attribute → product, returning a nested `OrderedDict`. Used to build the comparison table columns.

**Signature**
```python
def _prepare_categories_for_display(self) -> OrderedDict
```

**Return Value Structure**
```
OrderedDict({
    product.attribute.category: OrderedDict({
        product.attribute: OrderedDict({
            product.product: product.template.attribute.value recordset,
            ...
        })
    })
})
```

**Logic, Step by Step**

1. Collects all valid attribute lines for the product template via `self.product_tmpl_id.valid_product_template_attribute_line_ids.attribute_id`, then sorts by category.
2. Builds the outer `OrderedDict` keyed by sorted categories (same fallback for uncategorized as above).
3. For each attribute `pa`:
   - Creates a per-attribute inner `OrderedDict`.
   - For each `product` in `self` (the comparison recordset):
     - Tries to find `product_template_attribute_value` records where `attribute_id == pa`.
     - If found: uses that recordset.
     - If not found (attribute is `no_variant` / `create_variant=False`): falls back to `product.attribute_line_ids.filtered(...).value_ids` — shows all possible values for that attribute across all combinations.
4. Returns the fully nested structure used by the QWeb template to render one table row per attribute, with one cell per product.

**Why the `no_variant` fallback matters**
When an attribute has `create_variant=False`, Odoo does not create variants for every combination. The comparison table should still display all possible values for that attribute — the fallback ensures this.

**L3 — Trigger**
Called during QWeb rendering of `website_sale_comparison.product_compare`, specifically via `<t t-set="attrib_categories" t-value="products._prepare_categories_for_display()"/>`.

**L3 — Failure Modes**
- If `self` contains variants from different product templates, `valid_product_template_attribute_line_ids` will differ per variant — the method collects across all templates but a given attribute may not exist on all products, leading to cells with a dash (`-`).
- If `product_tmpl_id` differs across records in `self`, the `attributes` collection uses all attribute lines across all templates. A product without that attribute gets the fallback `value_ids` logic.

#### `_get_image_1024_url()`

Returns the local URL for the product's `image_1024` field.

**Signature**
```python
def _get_image_1024_url(self) -> str
```

**Requires**: `self.ensure_one()`

**Implementation**
```python
return self.env['website'].image_url(self, 'image_1024')
```

**Why it exists**
The comparison table needs a consistent, publicly accessible image URL. Using `image_url` helper rather than `image_1024` directly ensures proper URL generation including signed tokens if the website is configured for it.

---

## Controllers

### `WebsiteSaleProductComparison`

`odoo.http.Controller`

#### `product_compare()`

Renders the product comparison page at `GET /shop/compare`.

**Route**
```
/shop/compare
type=http, auth=public, website=True, sitemap=False
```

**Parameters (`**post`)**
| Parameter | Type | Source | Notes |
|---|---|---|---|
| `products` | string (comma-separated IDs) | `post.get('products')` | Querystring, e.g. `?products=1,2,3` |

**Logic**

1. Parses `post.get('products', '')` → splits on `,` → filters `isdigit()` → casts to `int` → `product_ids` list.
2. If `product_ids` is empty: `request.redirect('/shop')`.
3. Calls `request.env['product.product'].search([('id', 'in', product_ids)])` — this is the access check. Odoo internally verifies `read` access for each ID; inaccessible records are silently dropped from the result set.
4. Renders `website_sale_comparison.product_compare` template with `products` (with context `display_default_code=False` to hide internal default codes).

**Access Control**
- `auth='public'` — no login required.
- `website=True` — website-aware record rules applied (e.g., `website_published` domain).
- The `search()` call implicitly enforces read access via ACL and record rules.

**L3 — Failure Modes**
- If a user manually edits the URL to include IDs they do not have access to, those products are silently excluded from the result. The comparison page renders with fewer columns than expected.
- `search()` does not preserve order — if the user requests `products=3,1,2`, the order of columns may not match. This is a known UX quirk; the template renders in whatever order `search()` returns.

#### `get_product_data()`

JSON-RPC endpoint returning structured product data for the comparison bottom bar.

**Route**
```
/shop/compare/get_product_data
type=jsonrpc, auth=public, website=True
```

**Parameters**
| Parameter | Type | Notes |
|---|---|---|
| `product_ids` | array of int | IDs from the cookie |

**Return Value**
```python
[
    {
        'id': int,
        'display_name': str,
        'website_url': str,
        'image_url': str,
        'price': float,
        'prevent_zero_price_sale': bool,
        'currency_id': int,
        'strikethrough_price': float,   # optional, only if has_discounted_price or compare_list_price > price
    }
]
```

**Logic**

1. Searches `product.product` for each ID (access check via `search()`).
2. For each product, calls `product._get_combination_info_variant()` to get display name, price, etc.
3. Strikethrough price inclusion logic:
   - If `has_discounted_price` is `True`: include `list_price` as strikethrough.
   - Else if `compare_list_price` exists and is greater than `price`: include `compare_list_price`.
   - Otherwise: `strikethrough_price` omitted from the response.

**L3 — Security Considerations**
- Same access pattern as `product_compare()` — the `search()` call enforces record rules.
- `auth='public'` means any website visitor can call this endpoint. No sensitive data is exposed beyond product name, URL, price, and image.
- The `prevent_zero_price_sale` field controls whether the "Contact Us" button appears instead of "Add to Cart" — this prevents purchases at zero price for products marked accordingly.

---

## Views and Templates

### Backend Views (`website_sale_comparison_view.xml`)

**`product.attribute.category` Tree View** (`product_attribute_category_tree_view`)
- Editable bottom list with drag handles (`widget="handle"`) on `sequence`.
- Shows `name`, `attribute_ids` (many2many_tags).
- Menuitem placed under `website_sale.menu_catalog`, `base.group_no_one` (hidden from most users, only accessible to technical/admin users).

**`product.attribute.category` Action** (`product_attribute_category_action`)
- `res_model`: `product.attribute.category`
- `view_mode`: `list`
- `path`: `attribute-categories`

**Product Attribute Form Extension** (`product_attribute_view_form`)
- Inherits `website_sale.product_attribute_view_form` (not `product.attribute_view_form`) — adds `category_id` to the eCommerce-specific section of the attribute form.

**Product Attribute List Extension** (`product_attribute_tree_view_inherit`)
- Inherits `product.attribute_tree_view` — appends `category_id` column after `name`.

---

### Frontend Templates (`website_sale_comparison_template.xml`)

#### Comparison Button Injection

**`website_sale_comparison.add_to_compare`** (inherits `website_sale.shop_product_buttons`, priority=32)
- XPaths into `div.o_wsale_product_action_row`.
- Shows "Compare" button (`fa-exchange` icon) only if `product.valid_product_template_attribute_line_ids` exists (i.e., product has attributes to compare).
- Renders a placeholder (`o_add_compare_placeholder`) for products without attributes to maintain grid alignment.
- Button data attributes: `data-product-template-id`, `data-product-product-id`, `data-action="o_comparelist"`.
- Calls `_prepare_categories_for_display()` and `_get_first_possible_variant_id()` to determine availability.

**`website_sale_comparison.product_add_to_compare`** (inherits `website_sale.cta_wrapper`, priority=8)
- Injects "Add to compare" button into the product detail page CTA area.
- Responsive button classes adjusted based on active views (`cta_wrapper_large`, `product_add_to_wishlist`, etc.).

#### Specifications Table

**`website_sale_comparison.product_attributes_body`** (inherits `website_sale.product`)
- Replaces `div#product_attributes_simple` with the structured specifications table.
- Renders only if `attrib_categories` is truthy.
- Two-column layout (`col-lg-6`) splits categories left/right.
- Calls `_prepare_categories_for_display()` to get the grouped attribute lines.

**`website_sale_comparison.accordion_specs_item`** (inherits `website_sale.product_accordion`)
- Adds a Specifications accordion section before `more_information_accordion_item`.
- Supports single vs. multiple categories — shows "Specifications" label when one category, "Others" when more.
- Calls `_prepare_categories_for_display()` twice (once for condition, once for rendering) — potential optimization target.

**`website_sale_comparison.specifications_table`**
- Renders one `<tr>` per attribute line within a category.
- Filters to only show attributes with `len(ptal.value_ids) > 1` in the multi-value section — attributes with a single value are shown in the `single_value_attributes` block via `_prepare_single_value_for_display()`.
- Single-value rows use `_only_active()` on `product_template_value_ids` to show only the current combination's value.

#### Comparison Page

**`website_sale_comparison.product_compare`**
- Main comparison page template.
- Sticky mini-overview bar at top (initially hidden, appears on scroll).
- Table layout with one column per product:
  - Product image + name + price (with strikethrough for discounts).
  - "Add to Cart" / "Contact Us" CTA button.
  - Attribute rows grouped by category.
  - Tags row (if `website_sale.product_tags` view active).
- Bottom bar with "Back to shop" and "Remove all" buttons.
- Responsive `overflow-x-auto` wrapper for horizontal scrolling on mobile.

---

## JavaScript Client-Side Logic

### `website_sale_comparison_utils.js` (static module)

Plain JavaScript utility module (no OWL component). All functions operate on a browser cookie named `comparison_product_ids`.

**Constants**
```javascript
const COMPARISON_PRODUCT_IDS_COOKIE_NAME = 'comparison_product_ids';
const MAX_COMPARISON_PRODUCTS = 4;
const COMPARISON_EVENT = 'comparison_products_changed';
```

**Core Functions**

| Function | Purpose |
|---|---|
| `getComparisonProductIds()` | Reads and parses cookie. Returns `[]` if cookie absent. |
| `setComparisonProductIds(productIds, bus)` | Writes to cookie, then notifies listeners via EventBus. |
| `addComparisonProduct(productId, bus)` | Adds to Set (dedupes), saves. Enforces max size client-side. |
| `removeComparisonProduct(productId, bus)` | Removes from Set, saves. |
| `clearComparisonProducts(bus)` | Deletes cookie, notifies listeners, re-enables product buttons. |
| `notifyComparisonListeners(bus)` | Dispatches `CustomEvent(COMPARISON_EVENT)` on the event bus. |
| `enableDisabledProducts(productIds)` | Re-enables comparison buttons for removed product IDs. |
| `updateDisabled(el, isDisabled)` | Sets `el.disabled` and toggles `.disabled` CSS class. |

**L3 — Max Products Enforcement**
`MAX_COMPARISON_PRODUCTS = 4` is a client-side constant. The server-side `product_compare()` controller does not enforce a maximum — it renders whatever products are in the cookie. The UI should prevent adding a 5th product, but there is no server-side guard. If a user manipulates the cookie directly to add more than 4 IDs, the comparison page will display all of them.

**L3 — Cookie Scope**
The cookie is set with default scope (path=`/`), making it accessible site-wide. Since `website=True` is used, the cookie should ideally be website-scoped, but the current implementation uses a global cookie. This means the comparison list is shared across all website languages/pages on the same domain.

### `ProductComparisonBottomBar` (OWL Component)

Renders the sticky bottom comparison bar showing products in the comparison list.

**State**
```javascript
this.state = useState({ products: new Map() });  // id -> productData map
```

**Lifecycle**
- `onWillStart`: calls `_loadProducts()` on mount.
- Listens to `comparison_products_changed` bus event; reloads on any change.

**`_loadProducts()` Logic**
1. Gets product IDs from cookie.
2. If empty: clears the map and returns.
3. Calls `rpc('/shop/compare/get_product_data', { product_ids })`.
4. Clears map and repopulates from response.

**Reactive Properties**
- `comparisonUrl`: rebuilds from current map keys on each access.
- `productCount`: returns `state.products.size`.

### `ProductRow` (OWL Component)

Renders a single product entry in the bottom bar.

**Props**
```javascript
{
    id: Number,
    display_name: String,
    website_url: String,
    image_url: String,
    price: Number,
    strikethrough_price: { type: Number, optional: true },
    prevent_zero_price_sale: Boolean,
    currency_id: Number,
}
```

**`removeProduct()`**
1. Calls `removeComparisonProduct(this.props.id, bus)`.
2. Calls `enableDisabledProducts([this.props.id], false)` — re-enables the "Add to Compare" button on the product card.

---

## Data Files

### `website_sale_comparison_data.xml`

Creates a single demo category:
```xml
<record id="product_attribute_category_general_features">
    <field name="name">General Features</field>
    <field name="sequence">1</field>
</record>
```

This provides an example category out-of-the-box for administrators to assign attributes to.

### `website_sale_comparison_demo.xml`

Loads demo data via `loaded_demo_data` flag in tests.

---

## Security

### ACL (`ir.model.access.csv`)

| ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_product_attribute_category_public_public` | `model_product_attribute_category` | `base.group_public` | 1 | 0 | 0 | 0 |
| `access_product_attribute_category_public_portal` | `model_product_attribute_category` | `base.group_portal` | 1 | 0 | 0 | 0 |
| `access_product_attribute_category_public_employee` | `model_product_attribute_category` | `base.group_user` | 1 | 0 | 0 | 0 |
| `access_product_attribute_category_public_saleman` | `model_product_attribute_category` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |

**Security Analysis**
- Category model is low-risk: just grouping metadata.
- Read access granted to all authenticated and public users.
- Write access restricted to Sale Manager group.
- No unlink restriction beyond the saleman group (all write-group users can delete).
- The comparison page itself (`/shop/compare`) uses `auth='public'` — record rules on `product.product` control what products are visible. Products must satisfy `website_published=True` or be accessible via the user's access rights.

---

## Module Uninstall Behavior

The test `test_01_website_sale_comparison_remove` documents a critical behavior: the module's view (`product_attributes_body`) is inherited by custom views (COW views). When the module is uninstalled, `ir.module.module.module_uninstall()` triggers `_remove_copied_views()` which deletes all inherited views including:
- The base `product_attributes_body` view (generic).
- Any website-specific COW copies of `product_attributes_body`.
- Any view inheriting `product_attributes_body` (e.g., custom views with `inherit_id` pointing to it).

This ensures clean removal without leaving orphaned inherited views that would raise errors on product page load.

---

## Assets

| Bundle | Files |
|---|---|
| `web.assets_frontend` | `static/src/interactions/**/*`, `static/src/scss/*.scss`, `static/src/js/**/*` |
| `web.assets_tests` | `static/tests/**/*` |
| `website.website_builder_assets` | `static/src/website_builder/**/*` |

The SCSS files add comparison-specific styling; the JS files include the interactions (OWL components) for the comparison UI.

---

## Related Modules

- [Modules/website_sale](modules/website_sale.md) — Base eCommerce module; provides the product pages, shop layout, and cart.
- [Modules/Product](modules/product.md) — Core product models (`product.product`, `product.template`, `product.attribute`).
- [Modules/website_sale_comparison_wishlist](modules/website_sale_comparison_wishlist.md) — Bridges comparison with wishlist functionality (if installed).

---

## Tags

`#odoo`, `#odoo19`, `#modules`, `#website`, `#e-commerce`, `#product-comparison`

---

## Key Edge Cases and Gotchas

1. **Cookie-based comparison list**: No server-side session. If a user opens a comparison in a different browser/device, the list is empty. There is no persistence across devices.

2. **Products without attributes**: Products with no `valid_product_template_attribute_line_ids` do not get a Compare button — the template checks `isCompareAvailable` before rendering.

3. **Multi-website**: The cookie is global, not per-website. Comparing products on Website A will show those products in the comparison list on Website B (same domain).

4. **Uncategorized attributes**: Always appear under the empty/fallback category key in both `_prepare_categories_for_display()` methods.

5. **NoVariant attributes**: `_prepare_categories_for_display()` on `product.product` falls back to `attribute_line_ids.value_ids` to show all possible values.

6. **Access control on compare page**: Products the user cannot read are silently dropped from the comparison — users may see fewer products than they expected if they lack access to some.

7. **Strikethrough price**: The comparison template prioritizes `compare_list_price` over `has_discounted_price` for strikethrough display. Both cannot be shown simultaneously in the current template logic.

8. **View uninstall cleanup**: Custom views that inherit `product_attributes_body` will be deleted when this module is uninstalled — cannot be recovered without a database restore.
