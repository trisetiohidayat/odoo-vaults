# stock.location Model — Full Depth (L4)

**Path:** `odoo/addons/stock/models/stock_location.py`
**Manifest:** `stock` (`odoo/addons/stock/__manifest__.py`) — category `Supply Chain/Inventory`, depends on `product`, `barcodes_gs1_nomenclature`, `digest`
**Odoo Version:** 19

> `stock.location` is the foundational model for Odoo's Warehouse Management System (WMS). Every stock movement, quant, picking, and routing decision is ultimately anchored to one or more location records. Locations form a strict tree hierarchy (parent/child), carry company scoping rules, and drive putaway, removal, and replenishment strategies. The module also defines `stock.route` in the same file.

---

## 1. Model Declaration

```python
class StockLocation(models.Model):
    _name = 'stock.location'
    _description = "Inventory Locations"
    _parent_name = "location_id"          # self-referential FK field name
    _parent_store = True                   # triggers ltree extension (parent_path)
    _order = 'complete_name, id'           # alphabetical by full path, then id
    _rec_names_search = ['complete_name', 'barcode']
    _check_company_auto = True             # auto-checks company consistency
```

### Key Architecture Flags

| Flag | Purpose |
|------|---------|
| `_parent_name = "location_id"` | Declares `location_id` as the self-referential FK for the tree |
| `_parent_store = True` | Materialises the full path as `parent_path` (ltree column) for fast `child_of` / `parent_of` queries |
| `_check_company_auto = True` | Framework-level company validation on all relational fields that have `check_company=True` |

---

## 2. All Fields (L1 Depth)

### 2.1 Identity Fields

#### `name` — Location Name
```python
name = fields.Char('Location Name', required=True)
```
- The short human-readable label shown in the UI.
- Not unique; uniqueness is achieved through the hierarchy (`complete_name`).
- Required — every location must have a name.
- Used as the leaf node in the `complete_name` concatenation.

#### `complete_name` — Full Location Path
```python
complete_name = fields.Char(
    "Full Location Name",
    compute='_compute_complete_name',
    recursive=True,   # special flag: also computes children when parent changes
    store=True        # stored because it is used in _order and search
)
```
- **Computed** from `name` + parent's `complete_name` separated by `/`.
- `recursive=True` tells the ORM to recompute the whole subtree whenever a parent changes.
- The root location (no parent) returns only `name`.
- Examples:
  - Root `WH/Stock` with child `WH/Stock/Shelf A`:
    - `WH/Stock` -> `complete_name = "WH/Stock"`
    - `WH/Stock/Shelf A` -> `complete_name = "WH/Stock/Shelf A"`
- `_order = 'complete_name, id'` ensures alphabetical tree-order display.

#### `display_name` — ORM Standard Field (overridden)
```python
@api.depends('name', 'location_id.complete_name', 'usage')
@api.depends_context('formatted_display_name')
def _compute_display_name(self):
    super()._compute_display_name()
    for location in self:
        has_parent = location.location_id and location.usage != 'view'
        if location.env.context.get('formatted_display_name') and has_parent:
            location.display_name = f"--{location.location_id.complete_name}/--{location.name}"
        elif has_parent:
            location.display_name = f"{location.location_id.complete_name}/{location.name}"
```
- When context `formatted_display_name` is set: prepends `--` to each path segment (used in warehouse configuration wizards for visual depth).
- Standard mode: uses the same pattern as `complete_name`.
- `view`-type locations do not show a path prefix (they are the branch nodes, not leaf shelves).

#### `barcode` — Barcode Identifier
```python
barcode = fields.Char('Barcode', copy=False)
```
- Free-form barcode / QR-code value.
- Not copied on record duplication (`copy=False`).
- `default_get` auto-fills it from `complete_name` if not provided:

```python
@api.model
def default_get(self, fields):
    res = super().default_get(fields)
    if 'barcode' in fields and 'barcode' not in res and res.get('complete_name'):
        res['barcode'] = res['complete_name']
    return res
```

#### `active` — Active Flag
```python
active = fields.Boolean('Active', default=True)
```
- Locations can be soft-deleted without removing the record.
- Deactivating a location used by an active warehouse raises `UserError`.
- Deactivating a location with child internal locations that still hold quants also raises `UserError`.

---

### 2.2 Hierarchy Fields

#### `location_id` — Parent Location
```python
location_id = fields.Many2one(
    'stock.location',
    'Parent Location',
    index=True,
    check_company=True,
)
```
- Self-referential Many2one forming the tree.
- `index=True` for fast lookups.
- `check_company=True` enforces that parent and child share the same company (or both are company-agnostic).
- A location with `usage='view'` is typically the parent of internal/transit children.

#### `child_ids` — Direct Child Locations
```python
child_ids = fields.One2many(
    'stock.location',
    'location_id',
    'Contains'
)
```
- Inverse of `location_id`.
- Used for traversing the tree downward.
- Does NOT filter by usage — a view location's children may be view, internal, or transit.

#### `child_internal_location_ids` — Internal Descendants Only
```python
child_internal_location_ids = fields.Many2many(
    'stock.location',
    string='Internal locations among descendants',
    compute='_compute_child_internal_location_ids',
    recursive=True,
)
```
```python
@api.depends('child_ids.usage', 'child_ids.child_internal_location_ids')
def _compute_child_internal_location_ids(self):
    for loc in self:
        loc.child_internal_location_ids = self.search([
            ('id', 'child_of', loc.id),
            ('usage', '=', 'internal')
        ])
```
- Returns `self` plus all recursive descendants that have `usage='internal'`.
- `recursive=True` means the ORM recomputes this for the whole subtree when any child's `usage` changes.
- This field is the primary driver of putaway and reservation scope — it defines "all physical shelves under this node".

#### `parent_path` — Materialised Tree Path (ltree)
```python
parent_path = fields.Char(index=True)
```
- Automatically maintained by the ORM because `_parent_store = True`.
- Format: `1/2/5/` where each integer is a location id from root to self.
- The trailing `/` enables prefix-match queries: `parent_path LIKE '1/2/%'`.
- Used internally for `child_of` / `parent_of` domain operators and for `warehouse_id` computation.
- Composite index defined:

```python
_parent_path_id_idx = models.Index("(parent_path, id)")
```

---

### 2.3 Classification Fields

#### `usage` — Location Type (Selection)
```python
usage = fields.Selection([
    ('supplier',  'Vendor'),
    ('view',      'Virtual'),
    ('internal',  'Internal'),
    ('customer',  'Customer'),
    ('inventory', 'Inventory Loss'),
    ('production','Production'),
    ('transit',   'Transit')
], string='Location Type', default='internal', index=True, required=True)
```

| Value | UI Label | Physical? | Can hold quants | Description |
|-------|----------|-----------|-----------------|-------------|
| `supplier` | Vendor | No | No | Virtual origin for inbound receipts from vendors. |
| `view` | Virtual | No | **No** | Purely structural — a branch node in the tree. Cannot contain products; changing a non-empty location to `view` is forbidden. |
| `internal` | Internal | **Yes** | **Yes** | Physical warehouse shelves, bins, areas. The only location type that holds stock. |
| `customer` | Customer | No | No | Virtual destination for outbound deliveries. |
| `inventory` | Inventory Loss | No | No | Counterpart for stock corrections (e.g., physical inventory adjustments). Also used for scrap. |
| `production` | Production | No | No | Virtual counterpart for manufacturing operations (consumes components, produces finished goods). |
| `transit` | Transit | **Yes** (logical) | **Yes** | Inter-company or inter-warehouse transfer staging area. Quants in transit are still counted as "on hand" but are in a holding state. |

**Constraint — scrap location check:**
```python
@api.constrains('usage')
def _check_scrap_location(self):
    for record in self:
        if record.usage == 'inventory' and self.env['stock.picking.type'].search_count(
            [('code', '=', 'mrp_operation'),
             ('default_location_dest_id', '=', record.id)],
            limit=1
        ):
            raise ValidationError(_(
                "You cannot set a location as a scrap location when it is assigned as a "
                "destination location for a manufacturing type operation."
            ))
```
This prevents a location from being simultaneously used as both a scrap sink and a MRP destination.

**Constraint — converting non-empty internal location:**
```python
if 'usage' in values and values['usage'] == 'view':
    if self.mapped('quant_ids'):   # check this record AND children
        raise UserError(_("This location's usage cannot be changed to view as it contains products."))
```

---

### 2.4 Company and Partner Fields

#### `company_id` — Company Scoping
```python
company_id = fields.Many2one(
    'res.company',
    'Company',
    default=lambda self: self.env.company,
    index=True,
)
```
- **Multi-company scoping**: if set, the location belongs to that company and is invisible to users of other companies (enforced by `ir.rule`).
- If empty, the location is shared across all companies.
- Changing `company_id` on an existing location raises `UserError` — company reassignment is forbidden after creation. Archive and recreate instead.
- Default: the current user's default company.

#### Warehouse Location Shortcuts (NOT on `stock.location`)

The following fields are on `stock.warehouse`, not `stock.location`:

| Field on `stock.warehouse` | Points to | Purpose |
|----------------------------|-----------|---------|
| `view_location_id` | `stock.location` (usage=view) | Top-level view node for the warehouse tree |
| `lot_stock_id` | `stock.location` (usage=internal) | Default stock location (stock room) |
| `wh_input_stock_loc_id` | `stock.location` (usage=internal) | Receiving/staging area |
| `wh_qc_stock_loc_id` | `stock.location` (usage=internal) | Quality control hold area |
| `wh_output_stock_loc_id` | `stock.location` (usage=internal) | Shipping staging area |
| `wh_pack_stock_loc_id` | `stock.location` (usage=internal) | Packing area |
| `return_location_id` | `stock.location` (usage=internal) | Returns processing area |
| `crossdock_location_id` | `stock.location` (usage=internal) | Cross-dock staging (via `stock.wh_crossdock` module) |

> Note: In earlier versions (Odoo ≤ 15) these were stored as `partner_id`-less `stock.location` records with special `completion` compute methods. In Odoo 16+, these are primarily managed through `stock.warehouse` and its routing helper methods.

#### `warehouse_id` — Computed Warehouse Assignment
```python
warehouse_id = fields.Many2one(
    'stock.warehouse',
    compute='_compute_warehouse_id',
    store=True,
)
```
```python
@api.depends('warehouse_view_ids', 'location_id')
def _compute_warehouse_id(self):
    warehouses = self.env['stock.warehouse'].search([
        ('view_location_id', 'parent_of', self.ids)
    ])
    warehouses = warehouses.sorted(
        lambda w: w.view_location_id.parent_path,
        reverse=True   # deepest view location first
    )
    view_by_wh = OrderedDict((wh.view_location_id.id, wh.id) for wh in warehouses)
    self.warehouse_id = False
    for loc in self:
        if not loc.parent_path:
            continue
        path = {int(loc_id) for loc_id in loc.parent_path.split('/')[:-1]}
        for view_location_id in view_by_wh:
            if view_location_id in path:
                loc.warehouse_id = view_by_wh[view_location_id]
                break
```
- Resolves the nearest ancestor `view_location_id` that belongs to a warehouse.
- `reverse=True` on the sort ensures the most specific (deepest) warehouse is assigned when a location belongs to multiple warehouse trees.
- `store=True` — the warehouse assignment is cached because it is used in many stock rules.

---

### 2.5 Putaway and Removal Strategy Fields

#### `putaway_rule_ids` — Putaway Rules
```python
putaway_rule_ids = fields.One2many(
    'stock.putaway.rule',
    'location_in_id',
    'Putaway Rules'
)
```
- Rules that apply when a product arrives at this location.
- `stock.putaway.rule` model (`product_strategy.py`):
  - `location_in_id`: the "when product arrives in" location (parent node).
  - `location_out_id`: the suggested "store to sublocation" (child leaf).
  - `product_id` / `category_id` / `package_type_ids`: specificity filters.
  - `sequence`: priority — higher = evaluated first.
  - `sublocation`: strategy for choosing among children (`no`, `last_used`, `closest_location`).

#### `removal_strategy_id` — Removal Strategy
```python
removal_strategy_id = fields.Many2one(
    'product.removal',
    'Removal Strategy',
)
```
- `product.removal` is a simple master-data model with `name` and `method` Char fields.
- Standard removal strategies (defined in stock data):
  - `FIFO` — First In, First Out (by `last_inventory_date` of the quant's lot).
  - `LIFO` — Last In, First Out.
  - `FEFO` — First Expired, First Out (by `use_date` / `expiration_date` on the lot — requires `lot.expiration_time` fields).
  - `Closest Location` — nearest location to the picking destination.
  - `Least Packages` — prefer packages with the least quantity.
- Removal strategy is enforced at:
  - **Stock move line reservation** (which lot/quant to pick from).
  - **Automatic picking generation** in warehouse operations.
- Falls back to parent location's strategy if not set here.

#### `storage_category_id` — Storage Category
```python
storage_category_id = fields.Many2one(
    'stock.storage.category',
    string='Storage Category',
    check_company=True,
    index='btree_not_null',
)
```
- Links the location to a `stock.storage.category` record that defines:
  - `max_weight`: maximum total weight of all quants in this location.
  - `allow_new_product`: `empty` (only when location is empty), `same` (only same product), `mixed` (default).
  - `product_capacity_ids`: maximum quantity per specific product.
  - `package_capacity_ids`: maximum quantity per package type.
- Storage category constraints are enforced in `_check_can_be_used()`.

---

### 2.6 Replenishment Fields

#### `replenish_location` — Enable Replenishment
```python
replenish_location = fields.Boolean(
    'Replenishments',
    copy=False,
    compute="_compute_replenish_location",
    readonly=False,
    store=True,
)
```
- Only meaningful for `usage='internal'` locations.
- When `True`, this location can be selected as a replenishment target in orderpoints / reorder rules.
- **Constraint** (no parent/child overlap):
```python
@api.constrains('replenish_location', 'location_id', 'usage')
def _check_replenish_location(self):
    for loc in self:
        if loc.replenish_location:
            replenish_wh_location = self.search([
                ('id', '!=', loc.id),
                ('replenish_location', '=', True),
                '|',
                    ('location_id', 'child_of', loc.id),
                    ('location_id', 'parent_of', loc.id),
            ], limit=1)
            if replenish_wh_location:
                raise ValidationError(_(
                    'Another parent/sub replenish location %s exists, '
                    'if you wish to change it, uncheck it first',
                    replenish_wh_location.name
                ))
```
- Only one location in any ancestor/descendant chain can be marked as replenishment source.

```python
@api.depends('usage')
def _compute_replenish_location(self):
    for loc in self:
        if loc.usage != 'internal':
            loc.replenish_location = False
```
- Automatically cleared when `usage` is changed away from `internal`.

---

### 2.7 Cyclic Inventory Fields

#### `cyclic_inventory_frequency` — Inventory Frequency (Days)
```python
cyclic_inventory_frequency = fields.Integer(
    "Inventory Frequency",
    default=0,
    help="When different than 0, inventory count date for products stored at "
         "this location will be automatically set at the defined frequency."
)
```
- `0` means no cyclic inventory is scheduled.
- Positive integer: days between consecutive physical inventory counts.
- DB constraint:
```python
_inventory_freq_nonneg = models.Constraint(
    'check(cyclic_inventory_frequency >= 0)',
    'The inventory frequency (days) for a location must be non-negative',
)
```

#### `last_inventory_date` — Date of Last Inventory
```python
last_inventory_date = fields.Date(
    "Last Inventory",
    readonly=True,
)
```
- Set automatically by the inventory adjustment workflow (`stock.inventory`).
- Used as the base date for computing `next_inventory_date`.

#### `next_inventory_date` — Computed Next Inventory Date
```python
next_inventory_date = fields.Date(
    "Next Expected",
    compute="_compute_next_inventory_date",
    store=True,
)
```
```python
@api.depends('cyclic_inventory_frequency', 'last_inventory_date', 'usage', 'company_id')
def _compute_next_inventory_date(self):
    for location in self:
        if (location.company_id and
                location.usage in ['internal', 'transit'] and
                location.cyclic_inventory_frequency > 0):
            try:
                if location.last_inventory_date:
                    days_until = (
                        location.cyclic_inventory_frequency
                        - (fields.Date.today() - location.last_inventory_date).days
                    )
                    if days_until <= 0:
                        location.next_inventory_date = fields.Date.today() + timedelta(days=1)
                    else:
                        location.next_inventory_date = (
                            location.last_inventory_date
                            + timedelta(days=location.cyclic_inventory_frequency)
                        )
                else:
                    location.next_inventory_date = (
                        fields.Date.today() + timedelta(days=location.cyclic_inventory_frequency)
                    )
            except OverflowError:
                raise UserError(_(
                    "The selected Inventory Frequency (Days) creates a date "
                    "too far into the future."
                ))
        else:
            location.next_inventory_date = False
```

---

### 2.8 Weight Computation Fields

#### `net_weight` — Current Net Weight
```python
net_weight = fields.Float('Net Weight', compute="_compute_weight")
```

#### `forecast_weight` — Forecasted Weight
```python
forecast_weight = fields.Float('Forecasted Weight', compute="_compute_weight")
```

```python
@api.depends('outgoing_move_line_ids.quantity_product_uom',
             'incoming_move_line_ids.quantity_product_uom',
             'outgoing_move_line_ids.state',
             'incoming_move_line_ids.state',
             'outgoing_move_line_ids.product_id.weight',
             'outgoing_move_line_ids.product_id.weight',
             'quant_ids.quantity',
             'quant_ids.product_id.weight')
def _compute_weight(self):
    weight_by_location = self._get_weight()
    for location in self:
        location.net_weight = weight_by_location[location]['net_weight']
        location.forecast_weight = weight_by_location[location]['forecast_weight']
```

```python
def _get_weight(self, excluded_sml_ids=False):
    """Returns {location: {'net_weight': float, 'forecast_weight': float}}"""
    if not excluded_sml_ids:
        excluded_sml_ids = set()
    Product = self.env['product.product']
    StockMoveLine = self.env['stock.move.line']

    # 1. Sum quants at this location
    quants = self.env['stock.quant']._read_group(
        [('location_id', 'in', self.ids)],
        groupby=['location_id', 'product_id'],
        aggregates=['quantity:sum'],
    )
    # 2. Outgoing moves pending (reduce forecast)
    base_domain = Domain('state', 'not in', ['draft', 'done', 'cancel']) \
               & Domain('id', 'not in', tuple(excluded_sml_ids))
    outgoing_mls = StockMoveLine._read_group(
        Domain('location_id', 'in', self.ids) & base_domain,
        groupby=['location_id', 'product_id'],
        aggregates=['quantity_product_uom:sum'],
    )
    # 3. Incoming moves pending (increase forecast)
    incoming_mls = StockMoveLine._read_group(
        Domain('location_dest_id', 'in', self.ids) & base_domain,
        groupby=['location_dest_id', 'product_id'],
        aggregates=['quantity_product_uom:sum'],
    )
    # 4. Bulk-fetch product weights (1 query)
    products = Product.union(*(p for __, p, __ in quants + outgoing_mls + incoming_mls))
    products.fetch(['weight'])

    result = defaultdict(lambda: defaultdict(float))
    for loc, product, qty in quants:
        result[loc]['net_weight'] += qty * product.weight
        result[loc]['forecast_weight'] += qty * product.weight

    for loc, product, qty in outgoing_mls:
        result[loc]['forecast_weight'] -= qty * product.weight

    for dest_loc, product, qty in incoming_mls:
        result[dest_loc]['forecast_weight'] += qty * product.weight

    return result
```

**Weight semantics:**
- `net_weight` = weight of quants currently physically on-hand (`stock.quant.quantity`).
- `forecast_weight` = `net_weight` + weight of incoming pending moves - weight of outgoing pending moves.
- Used for warehouse capacity planning, especially in multi-level racking where shelf load limits must not be exceeded.

---

### 2.9 Quant and Move Line Relation Fields

#### `quant_ids` — On-Hand Quants at This Location
```python
quant_ids = fields.One2many('stock.quant', 'location_id')
```
- Every `stock.quant` record belongs to exactly one location.
- Used in `write()` to check whether a location contains products before changing its `usage` to `view`.

#### `outgoing_move_line_ids` — Pending Outgoing Moves
```python
outgoing_move_line_ids = fields.One2many('stock.move.line', 'location_id')
```
- Used in `_compute_weight` and `_check_can_be_used`.
- Only move lines in non-terminal states (`draft`, `cancel`, `done`) affect capacity planning.

#### `incoming_move_line_ids` — Pending Incoming Moves
```python
incoming_move_line_ids = fields.One2many('stock.move.line', 'location_dest_id')
```
- Inverse of `location_dest_id` on `stock.move.line`.
- Used in `_compute_weight` for forecast weight.

---

### 2.10 Empty-State Field

#### `is_empty` — Computed Empty State
```python
is_empty = fields.Boolean(
    'Is Empty',
    compute='_compute_is_empty',
    search='_search_is_empty',
)
```
```python
def _compute_is_empty(self):
    groups = self.env['stock.quant']._read_group(
        [('location_id.usage', 'in', ('internal', 'transit')),
         ('location_id', 'in', self.ids)],
        ['location_id'],
        ['quantity:sum']
    )
    groups = dict(groups)
    for location in self:
        location.is_empty = groups.get(location, 0) <= 0

def _search_is_empty(self, operator, value):
    if operator != 'in':
        return NotImplemented
    location_ids = [
        loc_id
        for loc_id, in self.env['stock.quant']._read_group(
            [('location_id.usage', 'in', ['internal', 'transit'])],
            ['location_id'],
            having=[('quantity:sum', '>', 0)]
        )
    ]
    return [('id', 'not in', location_ids)]
```
- `search='_search_is_empty'` allows filtering the location tree by "is empty" in the UI.
- Only `internal` and `transit` locations are checked; `view`, `customer`, `supplier`, `production`, `inventory` are always considered non-empty conceptually.

---

## 3. Constraints (L2 Depth)

### 3.1 Database-Level Constraints

| Constraint | SQL | Message |
|------------|-----|---------|
| `_barcode_company_uniq` | `unique(barcode, company_id)` | The barcode for a location must be unique per company! |
| `_inventory_freq_nonneg` | `check(cyclic_inventory_frequency >= 0)` | The inventory frequency (days) for a location must be non-negative |
| `_parent_path_id_idx` | `index (parent_path, id)` | Performance index for ltree prefix queries |

### 3.2 Python-Level Constraints (`@api.constrains`)

| Method | Trigger | Error |
|--------|---------|-------|
| `_check_replenish_location` | `replenish_location` change | Cannot have two replenishment locations in the same ancestor/descendant chain |
| `_check_scrap_location` | `usage` change to `inventory` | Cannot use as scrap if already assigned as MRP destination |

---

## 4. CRUD and Lifecycle Methods (L2-L3 Depth)

### 4.1 `name_create` — Slash-Separated Hierarchical Creation
```python
@api.model
def name_create(self, name):
    if name:
        name_split = name.split('/')
        parent_location = self.env['stock.location'].search([
            ('complete_name', '=', '/'.join(name_split[:-1])),
        ], limit=1)
        new_location = self.create({
            'name': name.split('/')[-1],
            'location_id': parent_location.id if parent_location else False,
        })
        return new_location.id, new_location.display_name
    return super().name_create(name)
```
**L3 — Business logic:** Accepts `WH/Stock/Aisle 1` as input and automatically creates the correct parent/child hierarchy:
- Splits by `/`.
- Looks up the first `N-1` segments as the parent via `complete_name`.
- Creates the leaf node with the last segment as `name`.
- If parents don't exist, only the leaf is created (silently skips missing parents).
- Used by `stock.warehouse` to bulk-create the full warehouse location tree with a single `name_create('WH/Stock')` call.

### 4.2 `write` — Guarded Field Updates

The `write` override enforces five business rules before delegating to `super`:

```python
def write(self, vals):
    # Rule 1: company reassignment forbidden
    if 'company_id' in vals:
        for location in self:
            if location.company_id.id != vals['company_id']:
                raise UserError(_(
                    "Changing the company of this record is forbidden at this point, "
                    "you should rather archive it and create a new one."
                ))

    # Rule 2: cannot convert a non-empty location to 'view'
    if 'usage' in vals and vals['usage'] == 'view':
        if self.mapped('quant_ids'):
            raise UserError(_(
                "This location's usage cannot be changed to view as it contains products."
            ))

    # Rule 3: cannot convert an internal location with positive stock
    if 'usage' in vals:
        modified_locations = self.filtered(lambda l: l.usage != vals['usage'])
        if self.env['stock.quant'].search_count([
            ('location_id', 'in', modified_locations.ids),
            ('quantity', '>', 0),
        ], limit=1):
            raise UserError(_("Internal locations having stock can't be converted"))

    # Rule 4: cannot archive a warehouse's primary location
    if 'active' in vals and not vals['active']:
        for location in self:
            warehouses = self.env['stock.warehouse'].search([
                ('active', '=', True),
                '|',
                    ('lot_stock_id', '=', location.id),
                    ('view_location_id', '=', location.id),
            ], limit=1)
            if warehouses:
                raise UserError(_(
                    "You cannot archive location %(location)s because it is used by "
                    "warehouse %(warehouse)s",
                    location=location.display_name,
                    warehouse=warehouses.display_name
                ))

    # Rule 5: cascade deactivation to children; check quants first
    if 'active' in vals:
        if not self.env.context.get('do_not_check_quant'):
            children = self.env['stock.location'].with_context(active_test=False).search([
                ('id', 'child_of', self.ids)
            ])
            internal_children = children.filtered(lambda l: l.usage == 'internal')
            quants = self.env['stock.quant'].search([
                '&', '|',
                    ('quantity', '!=', 0),
                    ('reserved_quantity', '!=', 0),
                ('location_id', 'in', internal_children.ids)
            ])
            if quants and not vals['active']:
                raise UserError(_(
                    "You can't disable locations %s because they still contain products.",
                    ', '.join(quants.mapped('location_id.display_name'))
                ))
            else:
                # Cascade to children without re-checking (to avoid recursion)
                super(StockLocation, children - self).with_context(
                    do_not_check_quant=True
                ).write({'active': vals['active']})

    res = super().write(vals)
    self.invalidate_model(['warehouse_id'])
    return res
```

**L3 — Cascade deactivation:** When a parent location is deactivated, all descendants are also deactivated. The `do_not_check_quant` context flag prevents recursive re-entering of the quant check.

### 4.3 `create` — Invalidate Warehouse Cache

```python
@api.model_create_multi
def create(self, vals_list):
    res = super().create(vals_list)
    self.invalidate_model(['warehouse_id'])
    return res
```

**L3 — Why invalidate `warehouse_id`?** The warehouse assignment is cached (`store=True`). When new locations are created inside a warehouse tree, they may fall under an existing warehouse — the cache must be refreshed so `_compute_warehouse_id` recomputes on the next access. This is a write-through cache invalidation pattern.

### 4.4 `unlink` — Recursive Cascade Delete
```python
def unlink(self):
    return super(StockLocation, self.search([('id', 'child_of', self.ids)])).unlink()
```
**L3 — Override pattern:** Rather than deleting just `self`, it expands to all descendants via the `child_of` domain before calling `super`. This ensures the ltree `parent_path` integrity is preserved (child records with dangling `parent_path` references would cause DB errors). Also protected by `_unlink_except_master_data`:

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_master_data(self):
    inter_company_location = self.env.ref('stock.stock_location_inter_company')
    if inter_company_location in self:
        raise ValidationError(_('The %s location is required by the Inventory app and cannot be deleted, but you can archive it.', inter_company_location.name))
```
**L3 — Master data protection:** The special inter-company transit location (used for cross-company transfers) cannot be deleted even via `unlink`. It can only be archived. The `@api.ondelete(at_uninstall=False)` decorator means this protection is enforced during normal operation but bypassed during module uninstall (to allow clean removal).

### 4.5 `copy_data` — Append "(copy)" on Duplication
```python
def copy_data(self, default=None):
    default = dict(default or {})
    vals_list = super().copy_data(default=default)
    if 'name' not in default:
        for location, vals in zip(self, vals_list):
            vals['name'] = _("%s (copy)", location.name)
    return vals_list
```
- When using the UI "Duplicate" action, the new location name is auto-suffixed with ` (copy)`.
- The `complete_name` for the copy will reflect the new parent context.

---

## 5. Business Logic Methods (L3 Depth)

### 5.1 Putaway Strategy — `_get_putaway_strategy`

```python
def _get_putaway_strategy(
    self,
    product,
    quantity=0,
    package=None,
    packaging=None,
    additional_qty=None
):
    """
    Returns the stock.location where the product should be put away.
    If no compliant putaway rule is found, returns `self` (the input location).
    The quantity is in the product's default UOM.
    """
    self = self._check_access_putaway()
    products = self.env.context.get('products', self.env['product.product']) | product

    # Resolve package type
    package_type = self.env['stock.package.type']
    if package:
        package_type = package.package_type_id
    elif packaging:
        package_type = packaging.package_type_id

    # Build category hierarchy for rule matching
    categ = products.categ_id if len(products.categ_id) == 1 else self.env['product.category']
    categs = categ
    while categ.parent_id:
        categ = categ.parent_id
        categs |= categ

    # Filter applicable rules by specificity (most specific first)
    putaway_rules = self.putaway_rule_ids.filtered(lambda rule:
        (not rule.product_id or rule.product_id in products) and
        (not rule.category_id or rule.category_id in categs) and
        (not rule.package_type_ids or package_type in rule.package_type_ids)
    ).sorted(
        key=lambda r: (
            bool(r.package_type_ids),    # package type rules first
            bool(r.product_id),          # then product-specific rules
            bool(r.category_id == categs[:1]),  # same-category before parent
            bool(r.category_id),          # then parent category
        ),
        reverse=True   # highest priority (most specific) first
    )

    putaway_location = None
    locations = self.env.context.get("locations")
    if not locations:
        locations = self.child_internal_location_ids

    if putaway_rules:
        qty_by_location = defaultdict(lambda: 0)
        if locations.storage_category_id:
            # Package-based capacity tracking
            if package and package.package_type_id:
                move_line_data = self.env['stock.move.line']._read_group([
                    ('id', 'not in', list(self.env.context.get('exclude_sml_ids', set()))),
                    ('result_package_id.package_type_id', '=', package_type.id),
                    ('state', 'not in', ['draft', 'cancel', 'done']),
                ], ['location_dest_id'], ['result_package_id:count_distinct'])
                quant_data = self.env['stock.quant']._read_group([
                    ('package_id.package_type_id', '=', package_type.id),
                    ('location_id', 'in', locations.ids),
                ], ['location_id'], ['package_id:count_distinct'])
                qty_by_location.update({loc.id: count for loc, count in move_line_data})
                for loc, count in quant_data:
                    qty_by_location[loc.id] += count
            else:
                # Product-based capacity tracking
                move_line_data = self.env['stock.move.line']._read_group([
                    ('id', 'not in', list(self.env.context.get('exclude_sml_ids', set()))),
                    ('product_id', '=', product.id),
                    ('location_dest_id', 'in', locations.ids),
                    ('state', 'not in', ['draft', 'done', 'cancel']),
                ], ['location_dest_id'],
                   ['quantity:array_agg', 'product_uom_id:recordset'])
                quant_data = self.env['stock.quant']._read_group([
                    ('product_id', '=', product.id),
                    ('location_id', 'in', locations.ids),
                ], ['location_id'], ['quantity:sum'])
                qty_by_location.update({loc.id: qty for loc, qty in quant_data})
                for loc, qty_list, uoms in move_line_data:
                    current = sum(
                        ml_uom._compute_quantity(float(qty), product.uom_id)
                        for qty, ml_uom in zip(qty_list, uoms)
                    )
                    qty_by_location[loc.id] += current

        if additional_qty:
            for loc_id, qty in additional_qty.items():
                qty_by_location[loc_id] += qty

        putaway_location = putaway_rules._get_putaway_location(
            product, quantity, package, packaging, qty_by_location
        )

    if not putaway_location:
        putaway_location = locations[0] if locations and self.usage == 'view' else self

    return putaway_location
```

**L3 — Algorithm breakdown:**
1. Resolve package type from `package` or `packaging` parameter.
2. Build the full product category ancestor chain for category-level rule matching.
3. Filter `putaway_rule_ids` by product, category, and package type — rule specificity is then sorted in descending order.
4. If `locations` (child internal locations) share a `storage_category_id`, compute `qty_by_location` from both quants and pending move lines (for accurate real-time capacity).
5. Delegate final location selection to the rule's `_get_putaway_location()` method, which applies the rule's `sublocation` strategy (`no`, `last_used`, `closest_location`).
6. Fallback: return the first child internal location if `self` is a `view`, otherwise return `self`.

### 5.2 Storage Capacity Check — `_check_can_be_used`

```python
def _check_can_be_used(self, product, quantity=0, package=None, location_qty=0):
    """Returns True if product/package can be stored; False otherwise."""
    self.ensure_one()
    if self.storage_category_id:
        forecast_weight = self._get_weight(
            self.env.context.get('exclude_sml_ids', set())
        )[self]['forecast_weight']
        if package and package.package_type_id:
            if self.storage_category_id.max_weight < forecast_weight + \
                    sum(sml.quantity_product_uom * sml.product_id.weight
                        for sml in self.env['stock.move.line'].search([
                            ('result_package_id', '=', package.id),
                            ('state', 'not in', ['done', 'cancel'])
                        ])):
                return False
            package_cap = self.storage_category_id.package_capacity_ids.filtered(
                lambda pc: pc.package_type_id == package.package_type_id
            )
            if package_cap and location_qty >= package_cap.quantity:
                return False
        else:
            if self.storage_category_id.max_weight < forecast_weight + product.weight * quantity:
                return False
            product_cap = self.storage_category_id.product_capacity_ids.filtered(
                lambda pc: pc.product_id == product
            )
            if product_cap and location_qty >= product_cap.quantity:
                return False
            if product_cap and quantity + location_qty > product_cap.quantity:
                return False

        positive_quant = self.quant_ids.filtered(
            lambda q: q.product_id.uom_id.compare(q.quantity, 0) > 0
        )
        if self.storage_category_id.allow_new_product == "empty" and positive_quant:
            return False
        if self.storage_category_id.allow_new_product == "same":
            product = product or self.env.context.get('products')
            if (positive_quant and positive_quant.product_id != product) or len(product) > 1:
                return False
            if self.env['stock.move.line'].search_count([
                ('product_id', '!=', product.id),
                ('state', 'not in', ('done', 'cancel')),
                ('location_dest_id', '=', self.id),
            ], limit=1):
                return False
    return True
```

**L3 — Capacity constraints enforced:**
- `max_weight`: total weight of all products already in location plus incoming weight must not exceed limit.
- `package_capacity_ids`: maximum number of packages of a given type per location.
- `product_capacity_ids`: maximum quantity of a specific product per location.
- `allow_new_product`: `empty` (location must be completely empty), `same` (only the existing product), `mixed` (any products).

### 5.3 Bypass Reservation — `should_bypass_reservation`

```python
def should_bypass_reservation(self):
    self.ensure_one()
    return self.usage in ('supplier', 'customer', 'inventory', 'production')
```
- Returns `True` for virtual location types that should never be reserved.
- Used in `stock.move` to decide whether to call `_action_assign()` reservation logic.
- `internal` and `transit` locations ARE subject to reservation.

### 5.4 Outgoing Classification — `_is_outgoing`

```python
def _is_outgoing(self):
    self.ensure_one()
    if self.usage == 'customer':
        return True
    inter_comp_location = self.env.ref(
        'stock.stock_location_inter_company',
        raise_if_not_found=False
    )
    return self._child_of(inter_comp_location)
```
- Returns `True` if a move FROM this location is an "outgoing" move.
- Also `True` for locations that are descendants of the special inter-company transit location.
- Used in `stock.picking` and `stock.move` to classify move direction for reporting.

### 5.5 Child-of Check — `_child_of`

```python
def _child_of(self, other_location):
    self.ensure_one()
    return self.parent_path.startswith(other_location.parent_path)
```
- Efficient path-comparison using the pre-materialised `parent_path`.
- Used by `_is_outgoing` and internally by `stock.rule` for route applicability checks.

### 5.6 Next Inventory Date — `_get_next_inventory_date`

```python
def _get_next_inventory_date(self):
    """3-level fallback for next inventory date."""
    if self.usage not in ['internal', 'transit']:
        return False
    next_inv = False
    company_inv_date = False

    # Level 1: company-level annual inventory
    if self.company_id.annual_inventory_month:
        today = fields.Date.today()
        annual_inv_month = int(self.company_id.annual_inventory_month)
        annual_inv_day = max(self.company_id.annual_inventory_day, 1)
        max_day = calendar.monthrange(today.year, annual_inv_month)[1]
        annual_inv_day = min(annual_inv_day, max_day)
        company_inv_date = today.replace(month=annual_inv_month, day=annual_inv_day)
        if company_inv_date <= today:
            max_day = calendar.monthrange(today.year + 1, annual_inv_month)[1]
            annual_inv_day = min(annual_inv_day, max_day)
            company_inv_date = company_inv_date.replace(year=today.year + 1, day=annual_inv_day)

    # Level 2: location-level cyclic inventory
    if self.next_inventory_date:
        next_inv = min(self.next_inventory_date, company_inv_date) \
            if company_inv_date else self.next_inventory_date
    elif self.company_id.annual_inventory_month:
        next_inv = company_inv_date

    return next_inv
```

**L3 — Fallback chain:**
1. If the location has a specific `next_inventory_date` (cyclic inventory), use it.
2. Else if the company has an annual inventory month set, use that.
3. Otherwise, no scheduled inventory.

---

## 6. Cross-Model Integration (L3 Depth)

### 6.1 Warehouse Creation (`stock.warehouse`)

When a `stock.warehouse` is created, it generates a complete location tree:

```
view_location_id  (usage='view')
  └── lot_stock_id       (usage='internal')  -- main stock room
  └── wh_input_stock_loc_id    (usage='internal')  -- receiving
  └── wh_qc_stock_loc_id        (usage='internal', optional)
  └── wh_output_stock_loc_id    (usage='internal') -- shipping
  └── wh_pack_stock_loc_id      (usage='internal', optional)
```

The `_get_input_output_locations()` helper on `stock.warehouse` resolves these based on the selected `reception_steps` and `delivery_steps` (one_step / two_steps / three_steps / pick_ship / pick_pack_ship).

### 6.2 Cross-Dock Logic

Cross-docking routes skip the stock room entirely. The cross-dock location is an internal location that:
- Receives from `in_type_id` (vendor).
- Immediately feeds `out_type_id` (customer delivery).
- Does NOT update `stock.quant` in the traditional sense — moves through the cross-dock location as a pass-through.
- Created by `stock.wh_crossdock` module.

### 6.3 Route Assignment

`stock.route` records link to `stock.location` through `stock.rule`:
- `rule.location_src_id`: source location for pull rules.
- `rule.location_dest_id`: destination location for push rules.
- Routes (`stock.route.warehouse.select`) compute the applicable warehouse locations dynamically based on the warehouse's location hierarchy.

---

## 7. Performance Considerations (L4 Depth)

### 7.1 Query Patterns

| Operation | Query Type | Index Used |
|-----------|-----------|------------|
| `child_of` domain | `parent_path LIKE 'X/Y/%'` | `_parent_path_id_idx` (composite) |
| `parent_of` domain | `parent_path LIKE '%/X/%'` or startswith | `parent_path` (single column) |
| Warehouse lookup | `parent_of(view_location_id)` then OrderedDict | `_parent_path_id_idx` |
| Empty location search | `having quantity:sum > 0` | none (full scan on filtered quants) |

### 7.2 `_compute_child_internal_location_ids` — Known Performance Concern

```python
def _compute_child_internal_location_ids(self):
    for loc in self:
        loc.child_internal_location_ids = self.search([
            ('id', 'child_of', loc.id),
            ('usage', '=', 'internal')
        ])
```
- This method is flagged in the code comment: `# batch reading optimization is not possible because the field has recursive=True`.
- `recursive=True` fields cannot use the ORM's batch prefetch optimisation — each location triggers a separate `search()`.
- In locations with deep trees and many internal descendants (e.g., 100+ shelves), this can generate N+1 queries.
- **Mitigation strategies:**
  - Use context `location_ids` to pre-filter the child scope in `_get_putaway_strategy`.
  - Cache `child_internal_location_ids` at the application level for read-heavy workloads.
  - Consider splitting deep warehouse trees into shallower sub-trees.

### 7.3 `_get_weight` — Bulk Fetch Pattern

The `_get_weight` method is deliberately designed to avoid N+1:
1. A single `_read_group` on `stock.quant` fetches all location/product/quantity combinations.
2. A single `_read_group` on `stock.move.line` for outgoing moves.
3. A single `_read_group` on `stock.move.line` for incoming moves.
4. One bulk `Product.union(...).fetch(['weight'])` call — all product weights in a single query.
5. The result dict is then iterated per location — O(1) per location, no additional queries.

### 7.4 `warehouse_id` Computation

The `OrderedDict` pattern for `view_by_wh` reduces the warehouse lookup from O(N*M) (for each location, scan each warehouse) to O(N+M):
1. All warehouses that are ancestors are fetched in one `search()`.
2. Sorted and indexed into an OrderedDict once.
3. Each location's `parent_path` is parsed into a set and looked up in the dict.

---

## 8. Security (L4 Depth)

### 8.1 Multi-Company Record Rules

`stock.location` is covered by standard Odoo multi-company record rules:
- If `company_id` is set: users can only see locations belonging to their allowed companies.
- If `company_id` is empty: the location is shared (visible to all companies).
- Record rules domain: `[('company_id', 'in', company_ids)]` applied to all non-admin users.

### 8.2 Access Control

Standard `ir.model.access` entries for `stock.location`:
- `stock.group_stock_manager`: full CRUD.
- `stock.group_stock_user`: read + write (no delete of locations used by quants or warehouses).
- Portal users: no direct access to `stock.location`.

### 8.3 `_check_access_putaway`

```python
def _check_access_putaway(self):
    return self
```
- Hook method (currently a no-op pass-through).
- Can be overridden in custom modules to add access control checks before putaway strategy is computed.
- Example override: restrict putaway suggestions to users with `stock.group_stock_user`.

---

## 9. Odoo 18 to 19 Changes (L4 Historical)

### 9.1 `removal_strategy_id` Help Text Expanded

The help text for `removal_strategy_id` was expanded in Odoo 19 to document the `Least Packages` strategy, which was added as a new standard strategy. Previously only FIFO, LIFO, Closest Location, and FEFO were documented.

### 9.2 `storage_category_id` and `index='btree_not_null'`

```python
storage_category_id = fields.Many2one(
    'stock.storage.category',
    string='Storage Category',
    check_company=True,
    index='btree_not_null',   # new in Odoo 19
)
```
The `index='btree_not_null'` was added in Odoo 19 to improve performance of queries that filter on `storage_category_id IS NOT NULL` (common in storage capacity planning reports).

### 9.3 `_check_can_be_used` — New Product Capacity Tracking

In Odoo 18, storage category capacity checks were simpler. Odoo 19 introduced `product_capacity_ids` and `package_capacity_ids` on `stock.storage.category` with separate One2many `capacity_ids` field and computed inverses. The `_check_can_be_used` method was updated to handle per-product and per-package-type capacity limits.

### 9.4 `name_create` with Slash-Separated Paths

The slash-separated `name_create` support for auto-creating hierarchical location trees was already present in Odoo 18 but remains an important pattern for warehouse creation wizards.

### 9.5 Removal of `complete_name` Stored Recompute

In Odoo 18, `complete_name` was sometimes manually recomputed via `_parent_store_sync`. In Odoo 19, the `recursive=True` flag on the compute method handles subtree recomputation automatically when a parent name changes — no manual sync is needed.

### 9.6 `sublocation` Field on `stock.putaway.rule`

```python
sublocation = fields.Selection([
    ('no', 'No'),
    ('last_used', 'Last Used'),
    ('closest_location', 'Closest Location')
], default='no')
```
This field was added in Odoo 18/19 to give finer control over which sublocation within a storage category is selected during putaway. Previously only the `sequence` priority was available.

### 9.7 `_get_weight` — Domain-Based Read Group

Odoo 19 refactored `_get_weight` to use the `Domain` helper class for constructing complex domain expressions in `_read_group`. This replaces older tuple-based domain syntax. The `Domain` class builds SQL `WHERE` clauses more efficiently for PostgreSQL, reducing query planning overhead on large move line tables.


---

## 10. `stock.route` Model (Same File)

`stock.location.py` defines both `StockLocation` and `StockRoute`:

```python
class StockRoute(models.Model):
    _name = 'stock.route'
    _description = "Inventory Routes"
    _order = 'sequence'
    _check_company_auto = True
```

### 10.1 All Fields (L1)

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | `Char` | required | Translated (`translate=True`) — appears in route selection dropdowns |
| `active` | `Boolean` | `True` | Archivable; cascading archive to `rule_ids` |
| `sequence` | `Integer` | `0` | Default sort order |
| `rule_ids` | One2many `stock.rule` | — | Rules on this route; cascade archive on route deactivation |
| `product_selectable` | `Boolean` | `True` | Route appears in product form Inventory tab |
| `product_categ_selectable` | `Boolean` | `False` | Route appears in product category form |
| `warehouse_selectable` | `Boolean` | `False` | Route selectable on warehouse; used as default for warehouse products |
| `package_type_selectable` | `Boolean` | `False` | Route appears on package type form (from `stock_packing` module) |
| `supplied_wh_id` | Many2one `stock.warehouse` | — | Target warehouse for inter-warehouse resupply routes; `index='btree_not_null'` |
| `supplier_wh_id` | Many2one `stock.warehouse` | — | Source warehouse for resupply routes |
| `company_id` | Many2one `res.company` | `self.env.company` | Company scoping; route is invisible to other companies |
| `product_ids` | Many2many `product.template` | — | Products that have this route assigned |
| `categ_ids` | Many2many `product.category` | — | Product categories that have this route assigned |
| `warehouse_domain_ids` | One2many (computed) | — | Warehouses belonging to `company_id`; used as domain for `warehouse_ids` |
| `warehouse_ids` | Many2many `stock.warehouse` | — | Warehouses where this route is active; domain-limited to `warehouse_domain_ids` |

### 10.2 Route Activation Cascade (`write`)

```python
def write(self, vals):
    if 'active' in vals:
        rules = self.with_context(active_test=False).rule_ids.sudo().filtered(
            lambda rule: rule.location_dest_id.active
        )
        if vals['active']:
            rules.action_unarchive()
        else:
            rules.action_archive()
    return super().write(vals)
```

**L3 — Cascade semantics:**
- Archiving a route archives all its rules — even rules whose destination locations are themselves still active.
- Unarchiving a route unarchives only those rules whose destination location is active. This prevents re-activating rules pointing to deleted or archived locations.
- `.sudo()` is used to bypass record rules when auto-archiving (the stock manager performing the route archive has rights to all rules regardless of company scoping).

### 10.3 Route Applicability — `_is_valid_resupply_route_for_product`

```python
def _is_valid_resupply_route_for_product(self, product):
    return False
```

**L3 — Stub for override:** This method is designed to be overridden by `stock_dropshipping` (or similar) to check if a resupply route is valid for a given product. The base class always returns `False`, preventing standard routes from being used for resupply without an override.

### 10.4 `warehouse_domain_ids` Compute

```python
@api.depends('company_id')
def _compute_warehouses(self):
    for loc in self:
        domain = [('company_id', '=', loc.company_id.id)] if loc.company_id else []
        loc.warehouse_domain_ids = self.env['stock.warehouse'].search(domain)
```

**L2 — Domain-limiting pattern:** `warehouse_ids` uses a dynamic domain based on `warehouse_domain_ids`. This ensures that when a route's company is changed, the warehouse selection UI is immediately restricted to only warehouses of the new company — preventing inconsistent company scoping on the route's rules.

### 10.5 `_onchange_warehouse_selectable`

```python
@api.onchange('warehouse_selectable')
def _onchange_warehouse_selectable(self):
    if not self.warehouse_selectable:
        self.warehouse_ids = [(5, 0, 0)]
```

**L2 — Data cleanup:** When the user unchecks `warehouse_selectable`, the `warehouse_ids` selection is cleared. This prevents stale warehouse assignments from persisting after the route is no longer warehouse-selectable.

### 10.6 `_check_company_consistency` Constraint

```python
@api.constrains('company_id')
def _check_company_consistency(self):
    for route in self:
        if not route.company_id:
            continue
        for rule in route.rule_ids:
            if route.company_id.id != rule.company_id.id:
                raise ValidationError(_(
                    "Rule %(rule)s belongs to %(rule_company)s while the route belongs to %(route_company)s.",
                    rule=rule.display_name,
                    rule_company=rule.company_id.display_name,
                    route_company=route.company_id.display_name,
                ))
```

**L3 — Cross-model company consistency:** Routes and their rules must share the same company. Since `stock.rule` has `check_company=True` on its `route_id` field, this constraint is largely redundant for single-record writes — the ORM would block it anyway. However, it guards against bulk `write` operations that might otherwise slip through.

---

## 11. Module Manifest and Init (L3)

From `stock/__manifest__.py`:
- **Name:** `Inventory`
- **Version:** `1.1`
- **Category:** `Supply Chain/Inventory`
- **Sequence:** `25`
- **Depends:** `product`, `barcodes_gs1_nomenclature`, `digest`
- **Demo data:** 5 XML files including `stock_storage_category_demo.xml` (creates storage categories)
- **Pre-init hook:** `pre_init_hook` — runs before module install (used for schema migrations or data fixes)
- **Post-init hook:** `_assign_default_mail_template_picking_id` — assigns mail templates to picking types after installation
- **Uninstall hook:** `uninstall_hook` — cleanup on module removal
- **Application:** `True` — appears in the Apps menu

From `stock/models/__init__.py`:
```python
from . import stock_location   # location + route
from . import stock_move
from . import stock_move_line
from . import stock_orderpoint
from . import stock_lot
from . import stock_picking
from . import stock_quant
from . import stock_reference
from . import stock_replenish_mixin
from . import stock_rule
from . import stock_warehouse
from . import stock_scrap
from . import product
from . import product_catalog_mixin
from . import stock_package_history
from . import stock_package_type
from . import stock_package
from . import stock_storage_category
from . import product_strategy   # putaway rule model
from . import barcode
from . import ir_actions_report
from . import res_company
from . import res_partner
from . import res_users
from . import res_config_settings
```

**L3 — Location is first:** `stock_location` is imported before `stock_warehouse` because warehouse creation depends on location existence. `product_strategy` (which defines `stock.putaway.rule`) is imported after the main models since it references both location and product models.

---

## 12. Edge Cases and Failure Modes (L4)

### 12.1 Empty `parent_path` on New Locations

Locations created without a parent have `parent_path = ''` until the ORM's parent store mechanism updates it. Code that relies on `parent_path` for path operations (e.g., `_child_of`) on newly created records may fail:

```python
def _child_of(self, other_location):
    self.ensure_one()
    return self.parent_path.startswith(other_location.parent_path)  # ''.startswith('1/2/') = False
```

**Mitigation:** Use `self.flush()` or access another computed field to trigger the parent store before calling `_child_of` on brand-new records.

### 12.2 Inter-Company Transit Location Not Found

`_is_outgoing()` uses `self.env.ref('stock.stock_location_inter_company')`:

```python
inter_comp_location = self.env.ref('stock.stock_location_inter_company', raise_if_not_found=False)
```

If the `stock` data file (`stock_data.xml`) has not been loaded (e.g., demo mode or migration scenario), this returns `False` and `_is_outgoing` falls back to the `usage == 'customer'` check only. This can break inter-company transfer detection.

### 12.3 Cyclic Inventory Overflow

`_compute_next_inventory_date` catches `OverflowError`:

```python
except OverflowError:
    raise UserError(_("The selected Inventory Frequency (Days) creates a date too far into the future."))
```

**Failure mode:** If `cyclic_inventory_frequency` is set to a value like `365000` (1000 years), adding it to `last_inventory_date` raises `OverflowError`. The user sees a translated `UserError` rather than a raw Python traceback.

### 12.4 `putaway_rule_ids` Rule Priority Tie-Breaking

When multiple rules have identical specificity (same `product_id`, `category_id`, `package_type_ids`):

```python
putaway_rules = putaway_rules.sorted(
    key=lambda r: (
        bool(r.package_type_ids),
        bool(r.product_id),
        bool(r.category_id == categs[:1]),
        bool(r.category_id),
    ),
    reverse=True
)
```

If two rules have identical keys, the one with the higher `id` wins (stable sort). In practice, rules should have distinct `sequence` values — but if not, rule creation order determines the winner. This is a silent, non-deterministic fallback.

### 12.5 `barcode` Uniqueness Race Condition

The `_barcode_company_uniq` constraint is a DB-level unique index on `(barcode, company_id)`:

```python
_barcode_company_uniq = models.Constraint(
    'unique (barcode,company_id)',
    'The barcode for a location must be unique per company!',
)
```

If two users simultaneously create locations with the same barcode under the same company, one will get a `psycopg2.IntegrityError` — not a user-friendly `ValidationError`. This is typically mitigated by adding `copy=False` to the barcode field (preventing duplicates during copy) and using `default_get` to auto-fill from `complete_name`.


---

## 13. Tags

#odoo, #odoo19, #stock, #stock.location, #stock.route, #wms, #warehouse, #location-hierarchy, #putaway, #removal-strategy, #quant, #storage-category, #cyclic-inventory, #ltree, #parent_path, #company-scoping, #multi-company, #route, #resupply
