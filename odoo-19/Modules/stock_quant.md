# `stock.quant` - Stock Quant Model

## Overview

**Model:** `stock.quant`
**Module:** `stock` (Odoo Core)
**File:** `stock/models/stock_quant.py`
**Description:** The `stock.quant` model is the **fundamental data structure** for tracking inventory quantities at a granular level. Each quant record represents a discrete quantity of a product stored at a specific location, optionally tracked by lot/serial number, package, and owner. The quant system is the backbone of Odoo's inventory valuation and traceability.

**Key Design Principles:**
- One quant per unique combination of `(product_id, location_id, lot_id, package_id, owner_id)`
- Quants are **merged automatically** when characteristics match
- Quants are **deleted automatically** when both `quantity` and `reserved_quantity` reach zero
- The quant system operates at **superuser level** (`sudo()`) to ensure data consistency
- All quantity modifications flow through `_update_available_quantity` as the single entry point

---

## L1 - Complete Field Reference

### Core Identification Fields

```python
_id = fields.Id()          # Implicit Odoo id
product_id = fields.Many2one(
    'product.product', 'Product',
    domain=lambda self: self._domain_product_id(),
    ondelete='restrict', required=True, index=True, check_company=True)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `product.product` |
| **Required** | Yes |
| **Index** | B-tree index |
| **ondelete** | `restrict` - prevents product deletion if quants exist |
| **check_company** | Yes - enforces company consistency |
| **Domain** | Dynamic - filters to storable products in inventory mode |

```python
product_tmpl_id = fields.Many2one(
    'product.template', string='Product Template',
    related='product_id.product_tmpl_id')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `product.template` (related, readonly) |
| **Purpose** | Provides template-level access without explicit storage |

```python
product_uom_id = fields.Many2one(
    'uom.uom', 'Unit',
    readonly=True, related='product_id.uom_id')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `uom.uom` (related, readonly) |
| **Purpose** | Inherits the product's default unit of measure |

```python
company_id = fields.Many2one(
    related='location_id.company_id',
    string='Company', store=True, readonly=True)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.company` (related, stored) |
| **Derivation** | Inherited from `location_id.company_id` |
| **Stored** | Explicitly stored for query performance |

---

### Location and Warehouse Fields

```python
location_id = fields.Many2one(
    'stock.location', 'Location',
    domain=lambda self: self._domain_location_id(),
    bypass_search_access=True, ondelete='restrict', required=True, index=True)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `stock.location` |
| **Required** | Yes |
| **Index** | B-tree index |
| **ondelete** | `restrict` - prevents location deletion if quants exist |
| **Domain** | Dynamic - filters to `internal` and `transit` locations in inventory mode |
| **bypass_search_access** | Allows access even if user lacks location access rights |
| **Constraint** | Cannot be a location of type `view` (enforced by `check_location_id`) |

```python
warehouse_id = fields.Many2one(
    'stock.warehouse', related='location_id.warehouse_id')
storage_category_id = fields.Many2one(
    related='location_id.storage_category_id')
cyclic_inventory_frequency = fields.Integer(
    related='location_id.cyclic_inventory_frequency')
```

| Field | Type | Purpose |
|-------|------|---------|
| `warehouse_id` | Related Many2one | Warehouse containing this location |
| `storage_category_id` | Related Many2one | Storage category of the location |
| `cyclic_inventory_frequency` | Related Integer | Inventory frequency for the location |

---

### Lot, Package, and Owner Tracking Fields

```python
lot_id = fields.Many2one(
    'stock.lot', 'Lot/Serial Number', index=True,
    ondelete='restrict', check_company=True,
    domain=lambda self: self._domain_lot_id())
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `stock.lot` |
| **Index** | B-tree index |
| **ondelete** | `restrict` - prevents lot deletion if quants exist |
| **check_company** | Yes |
| **Domain** | Dynamic - filters by product when in inventory mode |
| **Tracking** | Mandatory for products with `tracking` in (`lot`, `serial`) |
| **Constraint** | Lot's product must match quant's product (enforced by `check_lot_id`) |

```python
lot_properties = fields.Properties(
    related='lot_id.lot_properties',
    definition='product_id.lot_properties_definition',
    readonly=True)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Properties` (dynamic lot properties) |
| **Purpose** | Allows lot-specific custom properties defined on product template |
| **Definition Source** | `product_id.lot_properties_definition` |

```python
sn_duplicated = fields.Boolean(
    string="Duplicated Serial Number",
    compute='_compute_sn_duplicated',
    help="If the same SN is in another Quant")
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (computed) |
| **Computation** | Searches for same lot_id with quantity > 0 in internal/transit locations |
| **Purpose** | Detects serial number duplication violations |

```python
package_id = fields.Many2one(
    'stock.package', 'Package',
    domain="['|', ('location_id', '=', location_id), '&', ('location_id', '=', False), ('quant_ids', '=', False)]",
    help='The package containing this quant',
    ondelete='restrict', check_company=True, index=True)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `stock.package` |
| **Index** | B-tree index |
| **ondelete** | `restrict` |
| **check_company** | Yes |
| **Domain** | Package must be at same location or have no location/quant |
| **Package Hierarchy** | Supports nested packages via `parent_package_id` |

```python
owner_id = fields.Many2one(
    'res.partner', 'Owner',
    help='This is the owner of the quant',
    check_company=True,
    index='btree_not_null')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.partner` |
| **Index** | B-tree index with NULL handling |
| **check_company** | Yes |
| **Purpose** | Supports "consignment" inventory where owner differs from company |
| **NULL Handling** | NULL index allows efficient queries for non-consignment items |

---

### Quantity Fields (Core Business Logic)

```python
quantity = fields.Float(
    'Quantity',
    help='Quantity of products in this quant, in the default unit of measure of the product',
    readonly=True, digits='Product Unit')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Float` |
| **readonly** | Cannot be modified directly - only via `_update_available_quantity` |
| **Digits** | `Product Unit` precision |
| **Sign** | Positive = available stock, Negative = inventory discrepancy (in `inventory` locations only) |

```python
reserved_quantity = fields.Float(
    'Reserved Quantity',
    default=0.0,
    help='Quantity of reserved products in this quant, in the default unit of measure of the product',
    readonly=True, required=True, digits='Product Unit')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Float` |
| **Default** | `0.0` |
| **readonly** | Cannot be modified directly - only via `_update_reserved_quantity` |
| **Required** | Yes |
| **Digits** | `Product Unit` precision |
| **Purpose** | Tracks quantity allocated to pending stock moves |

```python
available_quantity = fields.Float(
    'Available Quantity',
    help="On hand quantity which hasn't been reserved on a transfer, in the default unit of measure of the product",
    compute='_compute_available_quantity', digits='Product Unit')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Float` (computed) |
| **Formula** | `quantity - reserved_quantity` |
| **readonly** | Always computed |
| **Can be Negative** | Yes, if reserved_quantity > quantity |

---

### Date and Meta Fields

```python
in_date = fields.Datetime(
    'Incoming Date', readonly=True, required=True,
    default=fields.Datetime.now)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Datetime` |
| **Default** | Current timestamp |
| **readonly** | Cannot be modified directly |
| **Required** | Yes |
| **Purpose** | FIFO/LIFO removal strategy ordering; oldest date = highest priority |

```python
tracking = fields.Selection(
    related='product_id.tracking', readonly=True)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Selection` (related) |
| **Values** | `none`, `lot`, `serial` |
| **Source** | `product_id.tracking` |

```python
on_hand = fields.Boolean(
    'On Hand', store=False,
    search='_search_on_hand')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (search-only) |
| **Search Method** | Delegates to `product.product._get_domain_locations()` |
| **Purpose** | Provides "On Hand" filter in inventory views |

```python
product_categ_id = fields.Many2one(
    related='product_tmpl_id.categ_id')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `product.category` (related) |
| **Purpose** | Enables category-based grouping and filtering |

```python
is_favorite = fields.Boolean(
    related='product_tmpl_id.is_favorite')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (related) |
| **Purpose** | Flags favorite products |

---

### Inventory Adjustment Fields

```python
inventory_quantity = fields.Float(
    'Counted', digits='Product Unit',
    help="The product's counted quantity.")
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Float` |
| **Digits** | `Product Unit` precision |
| **Purpose** | User-entered counted quantity during physical inventory |
| **Access** | Only visible/modifiable in inventory mode |
| **Behavior** | Setting this triggers `_set_inventory_quantity` which creates adjustment moves |

```python
inventory_quantity_auto_apply = fields.Float(
    'Inventoried Quantity', digits='Product Unit',
    compute='_compute_inventory_quantity_auto_apply',
    inverse='_set_inventory_quantity',
    groups='stock.group_stock_manager')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Float` (computed, inverse) |
| **Groups** | `stock.group_stock_manager` only |
| **compute** | Copies value from `quantity` |
| **inverse** | Calls `_set_inventory_quantity` to create adjustment moves |
| **Purpose** | Manager-level auto-apply of counted quantities |

```python
inventory_diff_quantity = fields.Float(
    'Difference',
    compute='_compute_inventory_diff_quantity',
    store=True,
    help="Indicates the gap between the product's theoretical quantity and its counted quantity.",
    readonly=True, digits='Product Unit')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Float` (computed, stored) |
| **Formula** | `inventory_quantity - quantity` (if `inventory_quantity_set`) |
| **Storage** | Stored for reporting and filtering |
| **readonly** | Always computed |

```python
inventory_date = fields.Date(
    'Scheduled',
    compute='_compute_inventory_date', store=True, readonly=False,
    help="Next date the On Hand Quantity should be counted.")
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Date` (computed, stored) |
| **Derivation** | From `location_id._get_next_inventory_date()` |
| **Purpose** | Schedules next cyclic inventory count |

```python
last_count_date = fields.Date(
    compute='_compute_last_count_date',
    help='Last time the Quantity was Updated')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Date` (computed) |
| **Computation** | Searches `stock.move.line` with `is_inventory=True` and `state=done` |
| **Purpose** | Tracks when inventory count was last performed |

```python
inventory_quantity_set = fields.Boolean(
    store=True, compute='_compute_inventory_quantity_set', readonly=False)
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (computed, stored) |
| **Triggers** | Automatically set to `True` when `inventory_quantity` is modified |
| **Purpose** | Flags quants that have pending inventory counts |

```python
is_outdated = fields.Boolean(
    'Quantity has been moved since last count',
    compute='_compute_is_outdated',
    search='_search_is_outdated')
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Boolean` (computed, searchable) |
| **Condition** | True when `inventory_quantity - inventory_diff_quantity != quantity` |
| **Search Method** | `_search_is_outdated` |
| **Purpose** | Flags quants where stock moved after counting began |

```python
user_id = fields.Many2one(
    'res.users', 'Assigned To',
    help="User assigned to do product count.",
    domain=lambda self: [('all_group_ids', 'in', self.env.ref('stock.group_stock_user').id)])
```

| Attribute | Value |
|-----------|-------|
| **Type** | `Many2one` to `res.users` |
| **Domain** | User must belong to `stock.group_stock_user` |
| **Purpose** | Assigns inventory counting tasks to specific users |

---

## L2 - Domain Methods and Field-Level Behavior

### Dynamic Domain Methods

The following methods generate domain filters based on context and user permissions:

#### `_domain_location_id()`

```python
def _domain_location_id(self):
    if self.env.user.has_group('stock.group_stock_user'):
        return "[('usage', 'in', ['internal', 'transit'])] if context.get('inventory_mode') else []"
    return "[]"
```

**Logic:**
- If user is in `stock.group_stock_user` and `inventory_mode` context is set: return domain for internal/transit locations
- Otherwise: return empty domain (no filtering)

**Use Case:** When opening quants from product form (inventory mode), restrict location selection to operational locations.

#### `_domain_lot_id()`

```python
def _domain_lot_id(self):
    if self.env.user.has_group('stock.group_stock_user'):
        return ("[] if not context.get('inventory_mode') else"
            " [('product_id', '=', context.get('active_id', False))] if context.get('active_model') == 'product.product' else"
            " [('product_id.product_tmpl_id', '=', context.get('active_id', False))] if context.get('active_model') == 'product.template' else"
            " [('product_id', '=', product_id)]")
    return "[]"
```

**Logic:**
- Not in inventory mode: no filtering
- From product.product form: filter to lots of that specific product
- From product.template form: filter to lots of any variant of that template
- From quant form: filter to lots matching the selected product

#### `_domain_product_id()`

```python
def _domain_product_id(self):
    if self.env.user.has_group('stock.group_stock_user'):
        return ("[] if not context.get('inventory_mode') else"
            " [('is_storable', '=', True), ('product_tmpl_id', 'in', context.get('product_tmpl_ids', []) + [context.get('product_tmpl_id', 0)])] if context.get('product_tmpl_ids') or context.get('product_tmpl_id') else"
            " [('is_storable', '=', True)]")
    return "[]"
```

**Logic:**
- Not in inventory mode: no filtering
- In inventory mode with template context: filter to storable products in those templates
- In inventory mode without context: filter to all storable products

---

## L3 - Core Methods (Edge Cases, Override Patterns, Workflow Triggers)

### Quantity Management Methods

#### `_update_available_quantity(product_id, location_id, quantity=False, reserved_quantity=False, lot_id=None, package_id=None, owner_id=None, in_date=None)`

**Signature Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `product_id` | `product.product` | Yes | Product to update |
| `location_id` | `stock.location` | Yes | Location of the quant |
| `quantity` | `Float` | No* | Delta quantity to add/subtract |
| `reserved_quantity` | `Float` | No* | Delta reserved quantity |
| `lot_id` | `stock.lot` | No | Lot/serial number |
| `package_id` | `stock.package` | No | Package containing the quant |
| `owner_id` | `res.partner` | No | Owner of the goods |
| `in_date` | `Datetime` | No | Incoming date for the operation |

*At least one of `quantity` or `reserved_quantity` must be provided.

**Internal Logic:**

1. **Validation**: Raises `ValidationError` if neither quantity nor reserved_quantity provided
2. **Superuser Mode**: Runs as `sudo()` for data consistency
3. **Gather Existing Quants**: Calls `_gather()` to find matching quants with same characteristics
4. **Lot Filtering** (if `lot_id` provided):
   - For positive `quantity`: only quants with lot_id match
   - For negative `quantity`: avoid removing from negative quants without lot
5. **In-Date Calculation**:
   - Collects existing quants' `in_date` values
   - Takes the minimum (oldest) date
   - Falls back to current time if no valid dates
6. **Locking**: Uses `try_lock_for_update()` on the first matching quant
7. **Update Strategy**:
   - If quant exists: increment `quantity` and/or `reserved_quantity`
   - If no quant exists: create new quant record
8. **Return**: Tuple of `(available_quantity, in_date)`

**Edge Cases:**

```python
# Example: Negative quantity on quant with lot
# When removing stock, quants without lots don't absorb negative quantities from tracked quants
if product_id.uom_id.compare(quantity, 0) > 0:
    quants = quants.filtered(lambda q: q.lot_id)
else:
    quants = quants.filtered(lambda q: product_id.uom_id.compare(q.quantity, 0) > 0 or q.lot_id)
```

**Override Pattern:**
Override this method to add custom valuation logic or trigger external integrations when quantities change.

**Workflow Trigger:**
This is the **only method** that should modify `quantity` or `reserved_quantity` fields. All stock operations (moves, picking validations, scrap) flow through this method.

#### `_update_reserved_quantity(product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None, strict=False)`

**Purpose:** Increase or decrease `reserved_quantity` on quants without changing `quantity`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `quantity` | `Float` | Positive = reserve, Negative = unreserve |
| `strict` | `Boolean` | If True, exact location/lot match required |

**Internal Logic:**

1. **Gather Quants**: Uses `_gather()` with removal strategy
2. **FIFO Processing**: Iterates quants ordered by `in_date` (oldest first)
3. **Packaging UOM**: Respects packaging reserve method if context contains `packaging_uom_id`
4. **UOM Conversion**: Handles unit of measure rounding differences
5. **Serial Number Check**: For tracking='serial', only allows integer quantities

**Edge Cases:**

```python
# Negative reserved quantity handling
negative_reserved_quantity = defaultdict(float)
for quant in quants:
    if product_id.uom_id.compare(quant.quantity - quant.reserved_quantity, 0) < 0:
        negative_reserved_quantity[(quant.location_id, quant.lot_id, ...)] += quant.quantity - quant.reserved_quantity
```

**Return:** Tuple of `(reserved_quantity, reserved_quants)` where `reserved_quants` is a list of `(quant, quantity_reserved)` tuples.

#### `_get_available_quantity(product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, allow_negative=False)`

**Purpose:** Calculate available quantity for a product at a location.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strict` | `Boolean` | False | Exact characteristics match |
| `allow_negative` | `Boolean` | False | Allow negative return value |

**Internal Logic:**

1. **Gather Quants**: Calls `_gather()` to find matching quants
2. **For Untracked Products** (`tracking='none'`):
   - Sum all quantities minus reserved quantities
   - If `allow_negative=False`, return max(0, calculated)
3. **For Tracked Products**:
   - Build per-lot available quantity map
   - Handle untracked quantities separately
   - Return sum of positive available quantities only

**Edge Cases:**

```python
# Handling untracked quants when lot_id is specified
if not quant.lot_id and strict and lot_id:
    continue
```

---

### Quant Gathering and Manipulation Methods

#### `_gather(product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, qty=0)`

**Purpose:** Retrieve quants matching specified characteristics, optionally applying removal strategy.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `strict` | `Boolean` | If True, exact match on all characteristics |
| `qty` | `Float` | If provided and removal_strategy='least_packages', optimize package selection |

**Domain Construction:**

```python
# Strict mode: exact match
domains = [
    ('product_id', '=', product_id.id),
    ('lot_id', 'in', [False, lot_id.id if lot_id else False]),
    ('package_id', '=', package_id.id if package_id else False),
    ('owner_id', '=', owner_id.id if owner_id else False),
    ('location_id', '=', location_id.id),  # exact location
]

# Non-strict mode: child_of location, lot/package optional
domains = [
    ('product_id', '=', product_id.id),
    ('lot_id', 'in', [lot_id.id, False]),  # lot or untracked
    ('package_id', '=', package_id.id if package_id else False),
    ('owner_id', '=', owner_id.id if owner_id else False),
    ('location_id', 'child_of', location_id.id),  # location hierarchy
]
```

**Removal Strategy Application:**

| Strategy | Order | Implementation |
|----------|-------|----------------|
| `fifo` | `in_date ASC, id` | Oldest in-date consumed first |
| `lifo` | `in_date DESC, id DESC` | Newest in-date consumed first |
| `closest` | None | Sort by `complete_name, -id` |
| `least_packages` | A* algorithm | Minimize package count |

**Edge Cases:**

```python
# least_packages strategy uses A* pathfinding
if removal_strategy == 'least_packages' and qty:
    domain = self._run_least_packages_removal_strategy_astar(domain, qty)
```

#### `_merge_quants()`

**Purpose:** Deduplicate quants that share identical characteristics. Called during `_quant_tasks()` to handle race conditions where concurrent transactions create duplicate quants.

**SQL Implementation:**

```sql
WITH dupes AS (
    SELECT min(id) as to_update_quant_id,
        (array_agg(id ORDER BY id))[2:] as to_delete_quant_ids,
        GREATEST(0, SUM(reserved_quantity)) as reserved_quantity,
        SUM(inventory_quantity) as inventory_quantity,
        SUM(quantity) as quantity,
        MIN(in_date) as in_date
    FROM stock_quant
    WHERE location_id in %s AND product_id in %s
    GROUP BY product_id, company_id, location_id, lot_id, package_id, owner_id
    HAVING count(id) > 1
)
UPDATE stock_quant q SET
    quantity = d.quantity,
    reserved_quantity = d.reserved_quantity,
    inventory_quantity = d.inventory_quantity,
    in_date = d.in_date
FROM dupes d WHERE d.to_update_quant_id = q.id;
DELETE FROM stock_quant WHERE id = ANY(SELECT unnest(to_delete_quant_ids) FROM dupes);
```

**Key Behaviors:**
- Uses `MIN(id)` as the survivor quant (lowest ID kept)
- Combines quantities by summation
- Takes `MIN(in_date)` to preserve oldest incoming date
- Wrapped in `savepoint()` to prevent transaction rollback on error
- Logs errors but does not raise - merge failures are non-fatal

#### `_unlink_zero_quants()`

**Purpose:** Remove quants that have become empty (both `quantity` and `reserved_quantity` are zero).

**Conditions for Deletion:**
- `quantity` rounds to 0 at 6 decimal precision
- `reserved_quantity` rounds to 0 at 6 decimal precision
- `inventory_quantity` rounds to 0 or is NULL
- `user_id` is NULL (not assigned to a user)

**SQL Implementation:**
```python
query = """SELECT id FROM stock_quant
    WHERE (round(quantity::numeric, %s) = 0 OR quantity IS NULL)
      AND round(reserved_quantity::numeric, %s) = 0
      AND (round(inventory_quantity::numeric, %s) = 0 OR inventory_quantity IS NULL)
      AND user_id IS NULL;"""
```

**Performance Note:**
Uses direct SQL query instead of ORM search for robustness against concurrent modifications.

#### `_clean_reservations()`

**Purpose:** Reconcile reserved quantities between quants and move lines, fixing inconsistencies.

**Logic:**

1. **Read Reserved Quantities** from both:
   - `stock.quant.reserved_quantity` grouped by (product, location, lot, package, owner)
   - `stock.move_line.quantity` for moves in assigned/waiting/confirmed states

2. **Compare and Fix**:
   - If location bypasses reservation: clear all reservations
   - If quantities don't match: adjust to match move lines
   - If reserved quantity > available: flag for unreservation

3. **Apply Corrections** via `_update_reserved_quantity()`

#### `_quant_tasks()`

**Purpose:** Scheduled task entry point that runs three cleanup operations:
```python
def _quant_tasks(self):
    self._merge_quants()       # Deduplicate concurrent quants
    self._clean_reservations() # Fix reservation inconsistencies
    self._unlink_zero_quants() # Remove empty quants
```

Called by:
- `_get_quants_action()` (when opening quant views)
- `action_view_inventory()` (when opening inventory mode)

Can be skipped via config parameter `stock.skip_quant_tasks`.

---

### Inventory Adjustment Methods

#### `_apply_inventory(date=None)`

**Purpose:** Create stock moves to reconcile counted quantities with system quantities.

**Called By:**
- `action_apply_inventory()` (from UI)
- `_set_inventory_quantity()` (from auto-apply)

**Flow:**

1. Set `inventory_quantity_set = True`
2. For each quant, calculate `inventory_diff_quantity`
3. Create inventory adjustment moves:
   - If `diff > 0` (more counted): Move from `property_stock_inventory` location to quant's location
   - If `diff < 0` (less counted): Move from quant's location to `property_stock_inventory` location
4. Move lines inherit lot_id and package_id from the quant
5. Validate moves via `_action_done()`
6. Update `inventory_date` to next scheduled date
7. Clear `inventory_quantity` via `action_clear_inventory_quantity()`

**Move Values Structure:**
```python
{
    'product_id': quant.product_id.id,
    'product_uom': quant.product_uom_id.id,
    'product_uom_qty': abs(quant.inventory_diff_quantity),
    'company_id': quant.company_id.id,
    'state': 'confirmed',
    'location_id': source_location.id,
    'location_dest_id': dest_location.id,
    'restrict_partner_id': quant.owner_id.id,
    'is_inventory': True,
    'picked': True,
    'move_line_ids': [(0, 0, {...})]
}
```

**Edge Cases:**
- If called from `from_inverse_qty` context and `inventory_diff_quantity = 0`: skip move creation
- If `date` parameter provided: override move date

#### `_get_inventory_move_values(qty, location_id, location_dest_id, package_id=False, package_dest_id=False)`

**Purpose:** Prepare dictionary of values for creating an inventory adjustment stock move.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `qty` | `Float` | Quantity to move (always positive) |
| `location_id` | `stock.location` | Source location |
| `location_dest_id` | `stock.location` | Destination location |
| `package_id` | `stock.package` | Source package (optional) |
| `package_dest_id` | `stock.package` | Destination package (optional) |

**Returns:** Dictionary suitable for `stock.move.create()`

#### `_set_inventory_quantity()`

**Purpose:** Inverse method for `inventory_quantity_auto_apply`. Called when manager sets a new counted quantity.

**Conditions:**
- Only executes in inventory mode (`_is_inventory_mode()`)
- Compares new value against current `quantity`
- If different: sets `inventory_quantity` and triggers `action_apply_inventory()`

---

### Inventory Mode Methods

#### `_is_inventory_mode()`

```python
@api.model
def _is_inventory_mode(self):
    return self.env.context.get('inventory_mode') and self.env.user.has_group('stock.group_stock_user')
```

**Conditions for True:**
1. Context contains `inventory_mode` key
2. Current user belongs to `stock.group_stock_user`

**Behavior Differences:**

| Aspect | Inventory Mode | Normal Mode |
|--------|---------------|-------------|
| `inventory_quantity` editable | Yes | No |
| Can create quants | Yes (restricted fields) | No |
| Can modify certain fields | Yes (lot_id, package_id, etc.) | No |
| Creates adjustment moves | Yes | No |

#### `_get_inventory_fields_create()` and `_get_inventory_fields_write()`

```python
def _get_inventory_fields_create(self):
    return ['product_id', 'owner_id'] + self._get_inventory_fields_write()

def _get_inventory_fields_write(self):
    return [
        'inventory_quantity', 'inventory_quantity_auto_apply',
        'inventory_diff_quantity', 'inventory_date', 'user_id',
        'inventory_quantity_set', 'is_outdated', 'lot_id',
        'location_id', 'package_id'
    ]
```

**Forbidden Fields in Inventory Mode:**
```python
def _get_forbidden_fields_write(self):
    return ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id']
```

These cannot be modified in inventory mode. Changing them requires normal quant deletion/recreation.

---

### Search and Display Methods

#### `_search_on_hand(operator, value)`

**Purpose:** Handle search on the virtual `on_hand` field, which delegates to product's available quantity.

**Implementation:**
```python
def _search_on_hand(self, operator, value):
    if operator != 'in':
        return NotImplemented
    return self.env['product.product']._get_domain_locations()[0]
```

#### `_search_is_outdated(operator, value)`

**Purpose:** Search for quants where quantity differs from counted quantity.

```python
def _search_is_outdated(self, operator, value):
    if operator != 'in':
        return NotImplemented
    quant_ids = self.search([('inventory_quantity_set', '=', True)])
    quant_ids = quant_ids.filtered(
        lambda quant: quant.product_uom_id.compare(
            quant.inventory_quantity - quant.inventory_diff_quantity,
            quant.quantity
        )
    ).ids
    return [('id', 'in', quant_ids)]
```

#### `_compute_display_name()`

**Purpose:** Generate human-readable quant identifier for UI display.

**Format (with `formatted_display_name` context):**
```
Location Name    --Package--    --Lot/Serial--
```

**Format (default):**
```
location_name - lot_name - package_name - owner_name
```

#### `_compute_last_count_date()`

**Purpose:** Find the most recent inventory count operation affecting this quant.

**Search Scope:**
- `stock.move.line` records with:
  - `state = 'done'`
  - `is_inventory = True`
  - Matching product, lot, package, owner
  - Location matches quant's location (as source or destination)

**Implementation:** Uses `_read_group()` for efficient aggregation.

---

### Serial Number Validation Methods

#### `_check_serial_number(product_id, lot_id, company_id, source_location_id=None, ref_doc_location_id=None)`

**Purpose:** Validate serial number assignments to prevent duplicates and incorrect location usage.

**Scenarios:**

| Scenario | Condition | Result |
|----------|-----------|--------|
| Assigning existing SN | `source_location_id` is None | Error if SN exists in any internal/customer location |
| Using SN from wrong location | `source_location_id` not in SN's locations | Warning with recommended correct location |
| SN in customer location | No ref_doc_location | Error message without auto-correction |

**Return:** Tuple of `(message, recommended_location)`

#### `check_quantity()`

**Purpose:** Validate that no tracked product has invalid quantities.

**Constraint:** For `tracking='serial'` products, each lot can only have quantity of 0 or 1 in non-inventory locations.

```python
@api.constrains('product_id')
def check_quantity(self):
    sn_quants = self.filtered(
        lambda q: q.product_id.tracking == 'serial'
        and q.location_id.usage != 'inventory'
        and q.lot_id
    )
    for product, location, lot, qty in groups:
        if product.uom_id.compare(abs(qty), 1) > 0:
            raise ValidationError(_('The serial number has already been assigned...'))
```

---

### Quant Relocation Method

#### `move_quants(location_dest_id=False, package_dest_id=False, message=False, unpack=False, up_to_parent_packages=False)`

**Purpose:** Directly relocate quants by creating inventory moves.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `location_dest_id` | `stock.location` | Target location |
| `package_dest_id` | `stock.package` | Target package (optional) |
| `message` | `String` | Reference for the generated move |
| `unpack` | `Boolean` | If True, remove from package |
| `up_to_parent_packages` | `stock.package` | Upper limit for parent package movement |

**Validation:**
- All quants must belong to same company
- All quants must have a company
- All quants must have positive quantity

---

### View Action Methods

#### `_get_quants_action(extend=False)`

**Returns:** Action dictionary to open quant list view.

**Behavior:**
- Sets `inventory_report_mode` context
- Selects view based on user permissions:
  - Manager + inventory mode: editable tree view
  - Others: readonly tree view
- Opens with graph and pivot views if `extend=True`

#### `_set_view_context()`

**Purpose:** Configure context based on user permissions and multi-location settings.

**Logic:**
```python
def _set_view_context(self):
    # If no multi-location access, restrict to user's warehouse
    if not user_has_multi_location:
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_user.id)])
        self = self.with_context(
            default_location_id=warehouse.lot_stock_id.id,
            hide_location=not always_show_loc
        )

    # Enable inventory mode for stock users
    if user_has_stock_user:
        self = self.with_context(inventory_mode=True)

    return self
```

---

## L4 - Performance, Security, and Historical Changes

### Performance Optimizations

#### Quants Cache (`quants_cache`)

The system uses a context-based cache to reduce database queries during batch operations:

```python
# In _gather()
quants_cache = self.env.context.get('quants_cache')
if quants_cache is not None and strict and removal_strategy != 'least_packages':
    res = self.env['stock.quant']
    if lot_id:
        res |= quants_cache[product_id.id, location_id.id, lot_id.id, package_id.id, owner_id.id]
    res |= quants_cache[product_id.id, location_id.id, False, package_id.id, owner_id.id]
```

**Usage in `stock_move_line._action_done()`:**
```python
quants_cache = self.env['stock.quant']._get_quants_by_products_locations(
    mls_todo.product_id, mls_todo.location_id | mls_todo.location_dest_id,
    extra_domain=['|', ('lot_id', 'in', mls_todo.lot_id.ids), ('lot_id', '=', False)])

for ml in mls_todo.with_context(quants_cache=quants_cache):
    # Operations use cached quants
```

#### SQL-Based Operations

Key performance-critical operations use raw SQL:

1. **`_merge_quants()`**: Single UPDATE + DELETE statement
2. **`_unlink_zero_quants()`**: Direct SELECT then unlink
3. **`_read_group_select()`**: Custom aggregates for `available_quantity:sum`

#### `_read_group_select` Custom Aggregates

```python
def _read_group_select(self, aggregate_spec, query):
    if aggregate_spec == 'available_quantity:sum':
        sql_quantity = self._read_group_select('quantity:sum', query)
        sql_reserved_quantity = self._read_group_select('reserved_quantity:sum', query)
        return SQL("%s - %s", sql_quantity, sql_reserved_quantity)
```

This allows grouping by available quantity directly in pivot/graph views.

#### Least Packages Strategy (A* Algorithm)

For the `least_packages` removal strategy, an A* pathfinding algorithm minimizes package count:

```python
def _run_least_packages_removal_strategy_astar(self, domain, qty):
    # Fetches all packages with available quantity
    # Uses priority queue to find minimum package combination
    # Returns domain filter for selected packages
```

**Complexity:** O(n log n) where n is number of packages.

---

### Security Considerations

#### Record-Level Security

**ACL Configuration:**
- `stock.group_stock_user`: Can read quants
- `stock.group_stock_manager`: Can modify quants, access `inventory_quantity_auto_apply`

**Field-Level Security:**
```python
inventory_quantity_auto_apply = fields.Float(
    ...
    groups='stock.group_stock_manager'  # Only managers can auto-apply
)
```

**Quant Deletion:**
Only `stock.group_stock_manager` can manually delete quants. Regular users must set quantity to 0 and let `_unlink_zero_quants()` handle cleanup.

#### Multi-Company Security

Quants inherit company from `location_id.company_id`. All operations should respect company boundaries:

```python
# In _update_available_quantity
self = self.sudo()  # Runs as superuser but still respects company rules
```

#### Forbidden Operations

```python
# In write()
forbidden_fields = ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id']
if self._is_inventory_mode() and any(field in forbidden_fields):
    raise UserError(_("Quant's editing is restricted..."))
```

Cannot change a quant's fundamental identity characteristics - must delete and recreate.

---

### Odoo 18 to Odoo 19 Changes

#### Major Changes

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| `lot_id` field | Standard Many2one | Added `check_company=True` |
| `_clean_reservations()` | Basic comparison | Enhanced with `should_bypass_reservation()` check |
| `is_storable` | Used `type == 'product'` | Uses `is_storable` computed field |
| Serial validation | `check_quantity()` only | Added `_check_serial_number()` for pre-validation |
| Quant tasks | Called via cron | Called on-demand in view actions |
| `_update_available_quantity()` | Simple lock | Uses `try_lock_for_update(allow_referencing=True)` |

#### Deprecations

- `product_id.type == 'product'` replaced with `product_id.is_storable`
- Direct `quantity` writes deprecated in favor of inventory adjustment flow

#### New Features in Odoo 19

1. **Properties on Lots**: `lot_properties` field for dynamic lot attributes
2. **Package Hierarchy**: `set_parent_package()` for nested package moves
3. **GS1 Barcode Generation**: `_get_gs1_barcode()` for barcode scanning
4. **Aggregate Barcodes**: `get_aggregate_barcodes()` for multi-quant scanning
5. **Inventory Conflict Wizard**: Handles outdated quant conflicts
6. **Quant Relocate Wizard**: Dedicated relocation workflow

---

### Quant Lifecycle

```
                    ┌──────────────────────────────────────────────────────────────┐
                    │                    QUANT LIFECYCLE                           │
                    └──────────────────────────────────────────────────────────────┘

  ┌─────────┐      ┌──────────────┐      ┌───────────────┐      ┌─────────────┐
  │ CREATE  │ ───► │   UPDATE     │ ───► │    MERGE       │ ───► │   DELETE     │
  │         │      │              │      │                │      │             │
  └─────────┘      └──────────────┘      └───────────────┘      └─────────────┘
       │                   │                      │                      │
       │                   │                      │                      │
       ▼                   ▼                      ▼                      ▼
  ┌─────────┐        ┌───────────┐        ┌───────────┐         ┌─────────┐
  │ Via     │        │ Via       │        │ Automatic │         │ Via     │
  │ Move    │        │ Reserve/  │        │ via       │         │ Zero    │
  │ Confirm │        │ Unreserve │        │ _merge_   │         │ Quantity │
  │         │        │           │        │ quants()  │         │ Cleanup  │
  └─────────┘        └───────────┘        └───────────┘         └─────────┘


  CREATION PATH:
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  stock.move._action_done()                                                 │
  │       │                                                                    │
  │       ▼                                                                    │
  │  stock.move.line._action_done()                                             │
  │       │                                                                    │
  │       ▼                                                                    │
  │  _synchronize_quant(quantity, location_dest_id)                            │
  │       │                                                                    │
  │       ▼                                                                    │
  │  stock.quant._update_available_quantity(product, location, qty, ...)      │
  │       │                                                                    │
  │       ├──► Quant exists? ──► UPDATE quantity                              │
  │       │                                                                    │
  │       └──► Quant doesn't exist? ──► CREATE new quant                       │
  └────────────────────────────────────────────────────────────────────────────┘


  RESERVATION PATH:
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  stock.move._action_assign()                                               │
  │       │                                                                    │
  │       ▼                                                                    │
  │  stock.quant._update_reserved_quantity(product, location, qty, ...)        │
  │       │                                                                    │
  │       ▼                                                                    │
  │  Iterate quants by removal strategy                                        │
  │       │                                                                    │
  │       ├──► Reserve from oldest quants (FIFO)                              │
  │       │                                                                    │
  │       └──► Update reserved_quantity on matched quants                       │
  └────────────────────────────────────────────────────────────────────────────┘


  INVENTORY ADJUSTMENT PATH:
  ┌────────────────────────────────────────────────────────────────────────────┐
  │  User sets inventory_quantity on quant                                      │
  │       │                                                                    │
  │       ▼                                                                    │
  │  _set_inventory_quantity() inverse                                         │
  │       │                                                                    │
  │       ▼                                                                    │
  │  action_apply_inventory()                                                  │
  │       │                                                                    │
  │       ▼                                                                    │
  │  _apply_inventory()                                                        │
  │       │                                                                    │
  │       ├──► diff > 0: Move from Inventory location → Quant location          │
  │       │                                                                    │
  │       └──► diff < 0: Move from Quant location → Inventory location          │
  │                                                                            │
  │       ▼                                                                    │
  │  stock.move._action_done() (validates move, updates quants)                │
  └────────────────────────────────────────────────────────────────────────────┘
```

---

### Related Models

| Model | Relationship | Purpose |
|-------|-------------|---------|
| `stock.move.line` | Creates/updates quants | Detailed stock operations |
| `stock.move` | Orchestrates move lines | Higher-level move management |
| `stock.location` | `location_id` reference | Location properties |
| `stock.lot` | `lot_id` reference | Lot/serial tracking |
| `stock.package` | `package_id` reference | Package management |
| `product.product` | `product_id` reference | Product properties |
| `res.partner` | `owner_id` reference | Consignment ownership |
| `stock.inventory` | Uses quants | Inventory adjustment records |

---

### Configuration Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `stock.skip_quant_tasks` | `False` | Skip merge/clean tasks on view open |
| `stock.merge_only_same_date` | `False` | Only merge moves with same date |
| `stock.merge_ignore_date_deadline` | `False` | Ignore date_deadline when merging |
| `stock.agg_barcode_max_length` | `400` | Max length for aggregate barcodes |
| `stock.barcode_separator` | None | Character to separate barcode segments |

---

### Common Error Messages

| Error | Cause | Resolution |
|-------|-------|------------|
| "The serial number has already been assigned" | SN quant quantity > 1 | Recount or correct quantity |
| "Quant's editing is restricted" | Attempt to change forbidden field | Delete and recreate quant |
| "You cannot take products from or deliver products to a location of type view" | Attempt to use view location | Select non-view location |
| "The Lot/Serial number is linked to another product" | Lot's product mismatch | Select correct lot |
| "It is not possible to unreserve more products than you have in stock" | Attempted unreserve > reserved | Correct reservation quantity |

---

## Quick Reference

### Key Method Signatures

```python
# Core quantity operations
stock.quant._update_available_quantity(product_id, location_id, quantity, lot_id, package_id, owner_id, in_date)
stock.quant._update_reserved_quantity(product_id, location_id, quantity, lot_id, package_id, owner_id, strict)
stock.quant._get_available_quantity(product_id, location_id, lot_id, package_id, owner_id, strict, allow_negative)

# Quant manipulation
stock.quant._gather(product_id, location_id, lot_id, package_id, owner_id, strict, qty)
stock.quant._merge_quants()
stock.quant._unlink_zero_quants()
stock.quant._clean_reservations()

# Inventory operations
stock.quant._apply_inventory(date)
stock.quant.action_apply_inventory()
stock.quant._set_inventory_quantity()

# Queries
stock.quant._get_removal_strategy(product_id, location_id)
stock.quant._get_removal_strategy_order(strategy)
stock.quant._get_reserve_quantity(product_id, location_id, quantity, uom_id, lot_id, package_id, owner_id, strict)

# Validation
stock.quant.check_quantity()
stock.quant.check_lot_id()
stock.quant.check_location_id()
stock.quant._check_serial_number(product_id, lot_id, company_id, source_location_id, ref_doc_location_id)
```

### Field Summary Table

| Field | Type | Stored | Computed | Required | Editable |
|-------|------|--------|----------|----------|----------|
| `product_id` | Many2one | Yes | No | Yes | No |
| `location_id` | Many2one | Yes | No | Yes | No |
| `lot_id` | Many2one | Yes | No | No | In Inventory Mode |
| `package_id` | Many2one | Yes | No | No | In Inventory Mode |
| `owner_id` | Many2one | Yes | No | No | No |
| `quantity` | Float | Yes | No | Yes | Via Operations Only |
| `reserved_quantity` | Float | Yes | No | Yes | Via Operations Only |
| `available_quantity` | Float | No | Yes | No | Read-only |
| `in_date` | Datetime | Yes | No | Yes | No |
| `inventory_quantity` | Float | No | No | No | In Inventory Mode |
| `inventory_diff_quantity` | Float | Yes | Yes | No | Read-only |
| `inventory_date` | Date | Yes | Yes | No | In Inventory Mode |
| `last_count_date` | Date | No | Yes | No | Read-only |
| `inventory_quantity_set` | Boolean | Yes | Yes | No | In Inventory Mode |
| `is_outdated` | Boolean | No | Yes | No | Read-only |
| `sn_duplicated` | Boolean | No | Yes | No | Read-only |
