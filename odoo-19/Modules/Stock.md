# Stock Module (WMS)

**Path:** `odoo/addons/stock/`
**Manifest:** `__manifest__.py` with `version: 1.1`, `depends: ['product', 'barcodes_gs1_nomenclature', 'digest']`
**Category:** Supply Chain/Inventory
**Application:** Yes (shows in Apps menu)

> The `stock` module is Odoo's Warehouse Management System (WMS). It manages inventory locations, stock moves, pickings, quants, lots/serials, packages, reorder points, and stock rules. It is the foundation for `stock_account`, `sale_stock`, `purchase_stock`, and `mrp_stock`.

---

## Models

### Core Models (29 total)

| Model | File | Key Role |
|-------|------|----------|
| `stock.location` | `models/stock_location.py` | Physical/virtual locations for inventory |
| `stock.warehouse` | `models/stock_warehouse.py` | Warehouses with picking types and routes |
| `stock.picking.type` | `models/stock_picking.py` | Operation types (incoming/outgoing/internal) |
| `stock.picking` | `models/stock_picking.py` | Transfers (deliveries/receipts) |
| `stock.move` | `models/stock_move.py` | Individual stock movements |
| `stock.move.line` | `models/stock_move_line.py` | Detailed operation lines (lots, qty) |
| `stock.quant` | `models/stock_quant.py` | Inventory quantities at locations |
| `stock.lot` | `models/stock_lot.py` | Lot/serial number tracking |
| `stock.package` | `models/stock_package.py` | Packages of quants |
| `stock.package.type` | `models/stock_package_type.py` | Package type (dimensions, weight) |
| `stock.rule` | `models/stock_rule.py` | Procurement rules (pull/push actions) |
| `stock.warehouse.orderpoint` | `models/stock_orderpoint.py` | Minimum stock / reorder rules |
| `stock.storage.category` | `models/stock_storage_category.py` | Storage constraints (weight, capacity) |
| `stock.route` | `models/stock_location.py` | Routes grouping rules |
| `stock.scrap` | `models/stock_scrap.py` | Scrap/waste operations |
| `stock.putaway.rule` | `models/product_strategy.py` | Putaway strategy rules |
| `stock.reference` | `models/stock_reference.py` | Reference documents linking |
| `stock.package.history` | `models/stock_package_history.py` | Package movement history |
| `stock.forecasted` | `report/stock_forecasted.py` | Forecast report model |
| `stock.storage.category.capacity` | `models/stock_storage_category.py` | Per-product/package capacity limits |

---

## L1: All Models with Fields

### `stock.location`

Hierarchical inventory locations (the core of WMS). Uses `location_id` as parent via `_parent_store = True`, enabling efficient ancestor queries via `parent_path` GIST index.

**All Fields:**
```python
name = fields.Char('Location Name', required=True)
complete_name = fields.Char("Full Location Name", compute='_compute_complete_name', recursive=True, store=True)
active = fields.Boolean('Active', default=True)
usage = fields.Selection([
    ('supplier', 'Vendor'),
    ('view', 'Virtual'),
    ('internal', 'Internal'),
    ('customer', 'Customer'),
    ('inventory', 'Inventory Loss'),
    ('production', 'Production'),
    ('transit', 'Transit'),
], default='internal', index=True, required=True)
location_id = fields.Many2one('stock.location', 'Parent Location', index=True, check_company=True)
child_ids = fields.One2many('stock.location', 'location_id', 'Contains')
child_internal_location_ids = fields.Many2many(
    'stock.location', string='Internal locations among descendants',
    compute='_compute_child_internal_location_ids', recursive=True)
parent_path = fields.Char(index=True)  # Materialized path for fast ancestor queries
company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, index=True)
removal_strategy_id = fields.Many2one('product.removal', 'Removal Strategy')
putaway_rule_ids = fields.One2many('stock.putaway.rule', 'location_in_id', 'Putaway Rules')
barcode = fields.Char(copy=False)
quant_ids = fields.One2many('stock.quant', 'location_id')
cyclic_inventory_frequency = fields.Integer("Inventory Frequency", default=0)
last_inventory_date = fields.Date("Last Inventory", readonly=True)
next_inventory_date = fields.Date("Next Expected", compute="_compute_next_inventory_date", store=True)
warehouse_view_ids = fields.One2many('stock.warehouse', 'view_location_id', readonly=True)
warehouse_id = fields.Many2one('stock.warehouse', compute='_compute_warehouse_id', store=True)
storage_category_id = fields.Many2one('stock.storage.category', string='Storage Category', check_company=True, index='btree_not_null')
replenish_location = fields.Boolean('Replenishments', copy=False, compute="_compute_replenish_location", readonly=False, store=True)
outgoing_move_line_ids = fields.One2many('stock.move.line', 'location_id')  # used to compute weight
incoming_move_line_ids = fields.One2many('stock.move.line', 'location_dest_id')  # used to compute weight
net_weight = fields.Float('Net Weight', compute="_compute_weight")
forecast_weight = fields.Float('Forecasted Weight', compute="_compute_weight")
is_empty = fields.Boolean('Is Empty', compute='_compute_is_empty', search='_search_is_empty')
```

**SQL Constraints:**
```python
_barcode_company_uniq = models.Constraint('unique (barcode,company_id)', 'The barcode for a location must be unique per company!')
_inventory_freq_nonneg = models.Constraint('check(cyclic_inventory_frequency >= 0)', ...)
_parent_path_id_idx = models.Index("(parent_path, id)")  # GIST index for hierarchical queries
```

**Key Methods:**
- `_get_putaway_strategy(product, quantity, package, packaging, additional_qty)` -- returns best location for putaway based on putaway rules and storage capacity
- `_get_weight(excluded_sml_ids)` -- computes net and forecasted weight using `_read_group` aggregation over quants and move lines
- `_get_next_inventory_date()` -- respects cyclic_inventory_frequency on location AND `company_id.annual_inventory_month/day`; returns minimum of both
- `should_bypass_reservation()` -- returns `True` for `usage in ('supplier', 'customer', 'inventory', 'production')`
- `_check_can_be_used(product, quantity, package, location_qty)` -- validates weight limits, product capacity, storage category rules
- `_is_outgoing()` -- `True` if usage is 'customer' or is child of inter-company transit location
- `name_create(name)` -- supports slash-separated names like "Parent/Child/Grandchild" for hierarchical creation
- `_search_is_empty(operator, value)` -- uses `_read_group` with `having=[('quantity:sum', '>', 0)]` to avoid loading all quants

**Why `child_internal_location_ids` is recursive:** Location hierarchies can be deep. The `recursive=True` compute walks the tree at read time (batch reading not possible). Use with caution in large trees.

**Usage Types (location.usage):**
| Usage | Purpose | Valuation |
|-------|---------|-----------|
| `supplier` | Virtual vendor receipt source | Not valued |
| `view` | Virtual/hierarchical grouping only | Not valued; cannot hold quants; cannot change usage if quants exist |
| `internal` | Physical warehouse storage | **Valued** |
| `customer` | Virtual delivery destination | Not valued |
| `inventory` | Scrap/adjustment counterpart | Valued |
| `production` | Manufacturing consumption | Valued |
| `transit` | Inter-company/warehouse transfer | Conditionally valued (if `company_id` set) |

**Edge Cases:**
- Cannot archive a location used by an active warehouse (`lot_stock_id` or `view_location_id`)
- Cannot change `usage` to `view` if location contains quants
- Cannot change `usage` of an internal location that has positive stock
- `_unlink_except_master_data`: `stock.stock_location_inter_company` is protected and cannot be deleted
- `replenish_location`: cannot have both a parent and child both set as replenish locations simultaneously (`_check_replenish_location`)

---

### `stock.warehouse`

Represents a warehouse with its own picking types, routes, and sub-locations. Warehouse creation auto-creates the entire location hierarchy and all operation types.

**All Fields:**
```python
name = fields.Char('Warehouse', required=True, default=_default_name)
active = fields.Boolean('Active', default=True)
company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, readonly=True, required=True)
partner_id = fields.Many2one('res.partner', 'Address', default=lambda self: self.env.company.partner_id, check_company=True)
view_location_id = fields.Many2one('stock.location', 'View Location', domain="[('usage', '=', 'view'), ('company_id', '=', company_id)]", required=True, check_company=True, index=True)
lot_stock_id = fields.Many2one('stock.location', 'Location Stock', domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]", required=True, check_company=True)
code = fields.Char('Short Name', required=True, size=5)
route_ids = fields.Many2many('stock.route', 'stock_route_warehouse', 'warehouse_id', 'route_id', 'Routes')
reception_steps = fields.Selection([
    ('one_step', 'Receive and Store (1 step)'),
    ('two_steps', 'Receive then Store (2 steps)'),
    ('three_steps', 'Receive, Quality Control, then Store (3 steps)'),
], 'Incoming Shipments', default='one_step', required=True)
delivery_steps = fields.Selection([
    ('ship_only', 'Deliver (1 step)'),
    ('pick_ship', 'Pick then Deliver (2 steps)'),
    ('pick_pack_ship', 'Pick, Pack, then Deliver (3 steps)'),
], 'Outgoing Shipments', default='ship_only', required=True)
wh_input_stock_loc_id = fields.Many2one('stock.location', 'Input Location', check_company=True)
wh_qc_stock_loc_id = fields.Many2one('stock.location', 'Quality Control Location', check_company=True)
wh_output_stock_loc_id = fields.Many2one('stock.location', 'Output Location', check_company=True)
wh_pack_stock_loc_id = fields.Many2one('stock.location', 'Packing Location', check_company=True)
mto_pull_id = fields.Many2one('stock.rule', 'MTO rule', copy=False)
pick_type_id = fields.Many2one('stock.picking.type', 'Pick Type', check_company=True, copy=False)
pack_type_id = fields.Many2one('stock.picking.type', 'Pack Type', check_company=True, copy=False)
out_type_id = fields.Many2one('stock.picking.type', 'Out Type', check_company=True, copy=False)
in_type_id = fields.Many2one('stock.picking.type', 'In Type', check_company=True, copy=False)
int_type_id = fields.Many2one('stock.picking.type', 'Internal Type', check_company=True, copy=False)
qc_type_id = fields.Many2one('stock.picking.type', 'Quality Control Type', check_company=True, copy=False)
store_type_id = fields.Many2one('stock.picking.type', 'Storage Type', check_company=True, copy=False)
xdock_type_id = fields.Many2one('stock.picking.type', 'Cross Dock Type', check_company=True, copy=False)
reception_route_id = fields.Many2one('stock.route', 'Receipt Route', ondelete='restrict', copy=False)
delivery_route_id = fields.Many2one('stock.route', 'Delivery Route', ondelete='restrict', copy=False)
resupply_wh_ids = fields.Many2many(
    'stock.warehouse', 'stock_wh_resupply_table', 'supplied_wh_id', 'supplier_wh_id',
    'Resupply From')
resupply_route_ids = fields.One2many('stock.route', 'supplied_wh_id', 'Resupply Routes', copy=False)
sequence = fields.Integer(default=10)
```

**SQL Constraints:**
```python
_warehouse_name_uniq = models.Constraint('unique(name, company_id)', 'The name of the warehouse must be unique per company!')
_warehouse_code_uniq = models.Constraint('unique(code, company_id)', 'The short name of the warehouse must be unique per company!')
```

**Route Configuration Impact:**
- `reception_steps = 'one_step'`: Vendor → WH/Stock (receipt goes directly to stock location)
- `reception_steps = 'two_steps'`: Vendor → WH/Input → WH/Stock
- `reception_steps = 'three_steps'`: Vendor → WH/Input → WH/Quality Control → WH/Stock
- `delivery_steps = 'ship_only'`: WH/Stock → Customer
- `delivery_steps = 'pick_ship'`: WH/Stock → WH/Output → Customer
- `delivery_steps = 'pick_pack_ship'`: WH/Stock → WH/Pack → WH/Output → Customer

**Multi-Warehouse Group Logic (`_check_multiwarehouse_group`):**
- If only 1 active warehouse per company: removes `group_stock_multi_warehouses` from base users
- If multiple active warehouses: automatically activates both `group_stock_multi_warehouses` AND `group_stock_multi_locations`

**Key Lifecycle Behavior:**
- On `create`: auto-creates all sub-locations via `_get_locations_values`, all picking types via `_create_or_update_sequences_and_picking_types`, all routes via `_create_or_update_route`
- On `write` with `reception_steps` or `delivery_steps` change: calls `_update_location_reception`, `_update_location_delivery`, `_update_reception_delivery_resupply`
- On `write` with `active=False`: raises if any ongoing moves exist on the warehouse's picking types; archives picking types, locations, and rules

---

### `stock.picking.type`

Operation types define the workflow for pickings: receipts, deliveries, or internal transfers. Each warehouse gets one of each.

**All Fields:**
```python
name = fields.Char('Operation Type', required=True, translate=True)
color = fields.Integer('Color')
sequence = fields.Integer('Sequence')
sequence_id = fields.Many2one('ir.sequence', 'Reference Sequence', check_company=True, copy=False)
sequence_code = fields.Char('Sequence Prefix', required=True)
default_location_src_id = fields.Many2one('stock.location', 'Source Location', compute='_compute_default_location_src_id', store=True, readonly=False, precompute=True, required=True)
default_location_dest_id = fields.Many2one('stock.location', 'Destination Location', compute='_compute_default_location_dest_id', store=True, readonly=False, precompute=True, required=True)
code = fields.Selection([
    ('incoming', 'Receipt'),
    ('outgoing', 'Delivery'),
    ('internal', 'Internal Transfer')
], 'Type of Operation', default='incoming', required=True)
return_picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type for Returns', index='btree_not_null', check_company=True)
show_entire_packs = fields.Boolean('Move Entire Packages', default=False)
set_package_type = fields.Boolean('Set Package Type', default=False)
warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', compute='_compute_warehouse_id', store=True, readonly=False, ondelete='cascade', check_company=True)
active = fields.Boolean('Active', default=True)
use_create_lots = fields.Boolean('Create New Lots/Serial Numbers', default=True, compute='_compute_use_create_lots', store=True, readonly=False)
use_existing_lots = fields.Boolean('Use Existing Lots/Serial Numbers', default=True, compute='_compute_use_existing_lots', store=True, readonly=False)
print_label = fields.Boolean('Generate Shipping Labels', compute="_compute_print_label", store=True, readonly=False)
show_operations = fields.Boolean('Show Detailed Operations', default=False)
reservation_method = fields.Selection([
    ('at_confirm', 'At Confirmation'),
    ('manual', 'Manually'),
    ('by_date', 'Before scheduled date')
], 'Reservation Method', required=True, default='at_confirm')
reservation_days_before = fields.Integer('Days')
reservation_days_before_priority = fields.Integer('Days when starred')
auto_show_reception_report = fields.Boolean("Show Reception Report at Validation")
auto_print_delivery_slip = fields.Boolean("Auto Print Delivery Slip")
auto_print_return_slip = fields.Boolean("Auto Print Return Slip")
auto_print_product_labels = fields.Boolean("Auto Print Product Labels")
product_label_format = fields.Selection([...], string="Product Label Format to auto-print", default='2x7xprice')
auto_print_lot_labels = fields.Boolean("Auto Print Lot/SN Labels")
lot_label_format = fields.Selection([...], string="Lot Label Format to auto-print", default='4x12_lots')
auto_print_reception_report = fields.Boolean("Auto Print Reception Report")
auto_print_reception_report_labels = fields.Boolean("Auto Print Reception Report Labels")
auto_print_packages = fields.Boolean("Auto Print Packages")
auto_print_package_label = fields.Boolean("Auto Print Package Label")
package_label_to_print = fields.Selection([('pdf', 'PDF'), ('zpl', 'ZPL')], default='pdf')
count_picking_draft = fields.Integer(compute='_compute_picking_count')
count_picking_ready = fields.Integer(compute='_compute_picking_count')
count_picking = fields.Integer(compute='_compute_picking_count')
count_picking_waiting = fields.Integer(compute='_compute_picking_count')
count_picking_late = fields.Integer(compute='_compute_picking_count')
count_picking_backorders = fields.Integer(compute='_compute_picking_count')
count_move_ready = fields.Integer(compute='_compute_move_count')
hide_reservation_method = fields.Boolean(compute='_compute_hide_reservation_method')
barcode = fields.Char('Barcode', copy=False)
company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda s: s.env.company.id, index=True)
create_backorder = fields.Selection([
    ('ask', 'Ask'), ('always', 'Always'), ('never', 'Never')
], 'Create Backorder', required=True, default='ask')
show_picking_type = fields.Boolean(compute='_compute_show_picking_type')
picking_properties_definition = fields.PropertiesDefinition("Picking Properties")
favorite_user_ids = fields.Many2many('res.users', 'picking_type_favorite_user_rel', 'picking_type_id', 'user_id')
is_favorite = fields.Boolean(compute='_compute_is_favorite', inverse='_inverse_is_favorite', search='_search_is_favorite', compute_sudo=True)
kanban_dashboard_graph = fields.Text(compute='_compute_kanban_dashboard_graph')
move_type = fields.Selection([
    ('direct', 'As soon as possible'),
    ('one', 'When all products are ready')
], 'Shipping Policy', default='direct', required=True)
```

**Key Behaviors:**
- `reservation_method = 'by_date'`: When changed, computes `reservation_date` on all non-assigned moves as `date - reservation_days_before` (or `reservation_days_before_priority` for starred moves)
- `is_favorite` uses a custom `_order_field_to_sql` to sort by user membership in `picking_type_favorite_user_rel`
- Auto-creates `ir.sequence` in `create()` if `sequence_code` is provided but `sequence_id` is not
- `count_picking_late` domain includes `('has_deadline_issue', '=', True)` for deadline-based lateness

---

### `stock.picking`

A transfer (receipt, delivery, or internal transfer) containing multiple moves and move lines. Inherits `mail.thread` and `mail.activity.mixin` for chatter.

**All Fields:**
```python
name = fields.Char('Reference', default='/', copy=False, index='trigram', readonly=True)
origin = fields.Char('Source Document', index='trigram')
note = fields.Html('Notes')
backorder_id = fields.Many2one('stock.picking', 'Back Order of', copy=False, index='btree_not_null', readonly=True, check_company=True)
backorder_ids = fields.One2many('stock.picking', 'backorder_id', 'Back Orders')
return_id = fields.Many2one('stock.picking', 'Return of', copy=False, index='btree_not_null', readonly=True, check_company=True)
return_ids = fields.One2many('stock.picking', 'return_id', 'Returns')
return_count = fields.Integer('# Returns', compute='_compute_return_count', compute_sudo=False)
move_type = fields.Selection([
    ('direct', 'As soon as possible'),
    ('one', 'When all products are ready')
], 'Shipping Policy', compute='_compute_move_type', store=True, required=True, readonly=False, precompute=True)
state = fields.Selection([
    ('draft', 'Draft'),
    ('waiting', 'Waiting Another Operation'),
    ('confirmed', 'Waiting'),
    ('assigned', 'Ready'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='Status', compute='_compute_state', copy=False, index=True, readonly=True, store=True, tracking=True)
priority = fields.Selection(PROCUREMENT_PRIORITIES, string='Priority', default='0')
scheduled_date = fields.Datetime('Scheduled Date', compute='_compute_scheduled_date', inverse='_set_scheduled_date', store=True, index=True, default=fields.Datetime.now, tracking=True)
date_deadline = fields.Datetime("Deadline", compute='_compute_date_deadline', store=True)
has_deadline_issue = fields.Boolean("Is late", compute='_compute_has_deadline_issue', store=True, default=False)
date_done = fields.Datetime('Date of Transfer', copy=False)
delay_alert_date = fields.Datetime('Delay Alert Date', compute='_compute_delay_alert_date', search='_search_delay_alert_date')
json_popover = fields.Char('JSON data for the popover widget', compute='_compute_json_popover')
location_id = fields.Many2one('stock.location', "Source Location", compute="_compute_location_id", store=True, precompute=True, readonly=False, check_company=True, required=True)
location_dest_id = fields.Many2one('stock.location', "Destination Location", compute="_compute_location_id", store=True, precompute=True, readonly=False, check_company=True, required=True)
move_ids = fields.One2many('stock.move', 'picking_id', string="Stock Moves", copy=True)
has_scrap_move = fields.Boolean('Has Scrap Moves', compute='_has_scrap_move')
picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', required=True, index=True, default=_default_picking_type_id, tracking=True)
warehouse_address_id = fields.Many2one('res.partner', related='picking_type_id.warehouse_id.partner_id')
picking_type_code = fields.Selection(related='picking_type_id.code', readonly=True)
picking_type_entire_packs = fields.Boolean(related='picking_type_id.show_entire_packs')
use_create_lots = fields.Boolean(related='picking_type_id.use_create_lots')
use_existing_lots = fields.Boolean(related='picking_type_id.use_existing_lots')
partner_id = fields.Many2one('res.partner', 'Contact', check_company=True, index='btree_not_null')
company_id = fields.Many2one('res.company', string='Company', related='picking_type_id.company_id', readonly=True, store=True, index=True)
user_id = fields.Many2one('res.users', 'Responsible', tracking=True, default=lambda self: self.env.user, copy=False)
move_line_ids = fields.One2many('stock.move.line', 'picking_id', 'Operations')
packages_count = fields.Integer('Packages Count', compute='_compute_packages_count')
package_history_ids = fields.Many2many('stock.package.history', string='Transfered Packages', copy=False)
show_check_availability = fields.Boolean(compute='_compute_show_check_availability')
show_allocation = fields.Boolean(compute='_compute_show_allocation')
owner_id = fields.Many2one('res.partner', 'Assign Owner', check_company=True, index='btree_not_null')
printed = fields.Boolean('Printed', copy=False)
signature = fields.Image('Signature', copy=False, attachment=True)
is_signed = fields.Boolean('Is Signed', compute="_compute_is_signed")
is_locked = fields.Boolean(default=True, copy=False)
is_date_editable = fields.Boolean('Is Scheduled Date Editable', compute='_compute_is_date_editable')
weight_bulk = fields.Float('Bulk Weight', compute='_compute_bulk_weight')
shipping_weight = fields.Float("Weight for Shipping", digits="Stock Weight", compute='_compute_shipping_weight', readonly=False, store=True)
shipping_volume = fields.Float("Volume for Shipping", compute="_compute_shipping_volume")
product_id = fields.Many2one('product.product', 'Product', related='move_ids.product_id', readonly=True)
lot_id = fields.Many2one('stock.lot', 'Lot/Serial Number', related='move_line_ids.lot_id', readonly=True)
show_operations = fields.Boolean(related='picking_type_id.show_operations')
show_lots_text = fields.Boolean(compute='_compute_show_lots_text')
has_tracking = fields.Boolean(compute='_compute_has_tracking')
products_availability = fields.Char(string="Product Availability", compute='_compute_products_availability')
products_availability_state = fields.Selection([
    ('available', 'Available'),
    ('expected', 'Expected'),
    ('late', 'Late')
], compute='_compute_products_availability', search='_search_products_availability_state')
picking_properties = fields.Properties('Properties', definition='picking_type_id.picking_properties_definition', copy=True)
show_next_pickings = fields.Boolean(compute='_compute_show_next_pickings')
search_date_category = fields.Selection([...], string='Date Category', store=False, search='_search_date_category', readonly=True)
partner_country_id = fields.Many2one('res.country', related='partner_id.country_id')
picking_warning_text = fields.Text("Picking Instructions", compute='_compute_picking_warning_text')
reference_ids = fields.Many2many('stock.reference', related="move_ids.reference_ids", string="References", readonly=True)

_name_uniq = models.Constraint('unique(name, company_id)', 'Reference must be unique per company!')
```

**State Machine Logic (`_compute_state`):**
- Picking state is **computed from move states**, not stored directly (`store=True` for performance)
- `draft`: any move is draft OR no moves at all
- `cancel`: all moves cancelled OR scrap-only moves all done
- `done`: all moves done/cancelled AND no scrap-only anomalies
- `waiting`: source bypasses reservation AND all moves make-to-stock, OR no relevant move state
- `assigned`: source bypasses reservation OR any move `partially_available`, OR all moves assigned

**Key Action Methods:**
- `action_confirm()` -- confirms draft moves and triggers scheduler for forecasted shortages
- `action_assign()` -- confirms draft pickings first, then assigns moves in priority/deadline order
- `action_cancel()` -- cancels all moves; writes `is_locked=True`; writes `state='cancel'` for pickings with no moves
- `action_done()` -- calls `move_ids._action_done()`, writes `date_done`, triggers cascading assignments for incoming moves
- `_action_done()` -- sets `restrict_partner_id` from `owner_id`, processes moves, sends confirmation email if configured
- `_autoconfirm_picking()` -- auto-confirms pickings where moves were added after creation (via `additional=True` flag)
- `_send_confirmation_email()` -- sends via `company_id.stock_mail_confirmation_template_id` if `stock_move_email_validation` is set

**Edge Cases:**
- `partner_id` on incoming picks uses `property_stock_supplier`; on outgoing picks uses `property_stock_customer` (via `_compute_location_id` onchange)
- Changing `location_id` on a picking unreserves and attempts to re-reserve; warns if moves have chained origins
- `write()` with `picking_type_id` change renames the picking (new sequence number) and updates locations
- `unlink()` cancels and deletes all moves first, then unlinks picking

---

### `stock.move`

Individual stock movements (line items within a picking). Moves are the central record of inventory state changes. The `product_qty` field is in the product's default UoM; `product_uom_qty` is the demand in the move's UoM.

**All Fields:**
```python
sequence = fields.Integer('Sequence', default=10)
priority = fields.Selection(PROCUREMENT_PRIORITIES, 'Priority', default='0', compute="_compute_priority", store=True)
date = fields.Datetime('Date Scheduled', default=fields.Datetime.now, index=True, required=True)
date_deadline = fields.Datetime("Deadline", readonly=True, copy=False)
company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, index=True, required=True)
product_id = fields.Many2one('product.product', 'Product', check_company=True, domain="[('type', '=', 'consu')]", index=True, required=True)
product_category_id = fields.Many2one('product.category', 'Product Category', related='product_id.categ_id')
never_product_template_attribute_value_ids = fields.Many2many(
    'product.template.attribute.value', 'template_attribute_value_stock_move_rel',
    'move_id', 'template_attribute_value_id', string="Never attribute Values")
description_picking = fields.Text(string="Description Of Picking", compute='_compute_description_picking', inverse='_inverse_description_picking')
description_picking_manual = fields.Text(readonly=True)
product_qty = fields.Float('Real Quantity', compute='_compute_product_qty', inverse='_set_product_qty', digits=0, store=True, compute_sudo=True)
product_uom_qty = fields.Float('Demand', digits='Product Unit', default=0, required=True)
allowed_uom_ids = fields.Many2many('uom.uom', compute='_compute_allowed_uom_ids')
product_uom = fields.Many2one('uom.uom', "Unit", required=True, domain="[('id', 'in', allowed_uom_ids)]", compute="_compute_product_uom", store=True, readonly=False, precompute=True)
product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id')
location_id = fields.Many2one('stock.location', 'Source Location', bypass_search_access=True, index=True, required=True, compute='_compute_location_id', store=True, precompute=True, readonly=False, check_company=True)
location_dest_id = fields.Many2one('stock.location', 'Intermediate Location', required=True, readonly=False, index=True, store=True, compute='_compute_location_dest_id', precompute=True, inverse='_set_location_dest_id')
location_final_id = fields.Many2one('stock.location', 'Final Location', readonly=False, store=True, bypass_search_access=True, index=True, check_company=True)
location_usage = fields.Selection(string="Source Location Type", related='location_id.usage')
location_dest_usage = fields.Selection(string="Destination Location Type", related='location_dest_id.usage')
partner_id = fields.Many2one('res.partner', 'Destination Address', compute='_compute_partner_id', store=True, readonly=False, index='btree_not_null')
move_dest_ids = fields.Many2many('stock.move', 'stock_move_move_rel', 'move_orig_id', 'move_dest_id', 'Destination Moves', copy=False)
move_orig_ids = fields.Many2many('stock.move', 'stock_move_move_rel', 'move_dest_id', 'move_orig_id', 'Original Move', copy=False)
picking_id = fields.Many2one('stock.picking', 'Transfer', index=True, check_company=True)
state = fields.Selection([
    ('draft', 'New'),
    ('waiting', 'Waiting Another Move'),
    ('confirmed', 'Waiting'),
    ('partially_available', 'Partially Available'),
    ('assigned', 'Available'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='Status', copy=False, default='draft', index=True, readonly=True)
picked = fields.Boolean('Picked', compute='_compute_picked', inverse='_inverse_picked', store=True, readonly=False, copy=False, default=False)
price_unit = fields.Float('Unit Price', copy=False)  # User-set cost during confirmation (average/real costing)
origin = fields.Char("Source Document")
procure_method = fields.Selection([
    ('make_to_stock', 'Default: Take From Stock'),
    ('make_to_order', 'Advanced: Apply Procurement Rules')
], default='make_to_stock', required=True, copy=False)
scrap_id = fields.Many2one('stock.scrap', 'Scrap operation', readonly=True, check_company=True, index='btree_not_null')
procurement_values = fields.Json(store=False)
reference_ids = fields.Many2many('stock.reference', 'stock_reference_move_rel', 'move_id', 'reference_id', string='References')
rule_id = fields.Many2one('stock.rule', 'Stock Rule', ondelete='restrict', check_company=True)
propagate_cancel = fields.Boolean('Propagate cancel and split', default=True)
delay_alert_date = fields.Datetime('Delay Alert Date', compute="_compute_delay_alert_date", store=True)
picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', compute='_compute_picking_type_id', store=True, readonly=False, check_company=True)
is_inventory = fields.Boolean('Inventory')
inventory_name = fields.Char(readonly=True)
move_line_ids = fields.One2many('stock.move.line', 'move_id')
package_ids = fields.One2many('stock.package', string='Packages', compute="_compute_package_ids")
origin_returned_move_id = fields.Many2one('stock.move', 'Origin return move', copy=False, index=True, check_company=True)
returned_move_ids = fields.One2many('stock.move', 'origin_returned_move_id', 'All returned moves')
availability = fields.Float('Forecasted Quantity', compute='_compute_product_availability', readonly=True)
restrict_partner_id = fields.Many2one('res.partner', 'Owner', check_company=True, index='btree_not_null')
route_ids = fields.Many2many('stock.route', 'stock_route_move', 'move_id', 'route_id', 'Destination route')
warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse')
has_tracking = fields.Selection(related='product_id.tracking', string='Product with Tracking')
has_lines_without_result_package = fields.Boolean(compute="_compute_has_lines_without_result_package")
quantity = fields.Float('Quantity', compute='_compute_quantity', digits='Product Unit', inverse='_set_quantity', store=True)
show_operations = fields.Boolean(related='picking_id.picking_type_id.show_operations')
picking_code = fields.Selection(related='picking_id.picking_type_id.code', readonly=True)
show_details_visible = fields.Boolean('Details Visible', compute='_compute_show_details_visible')
is_storable = fields.Boolean(related='product_id.is_storable')
additional = fields.Boolean("Whether the move was added after the picking's confirmation", default=False)
is_locked = fields.Boolean(compute='_compute_is_locked', readonly=True)
is_initial_demand_editable = fields.Boolean('Is initial demand editable', compute='_compute_is_initial_demand_editable')
is_date_editable = fields.Boolean("Is Date Editable", compute="_compute_is_date_editable")
is_quantity_done_editable = fields.Boolean('Is quantity done editable', compute='_compute_is_quantity_done_editable')
reference = fields.Char(compute='_compute_reference', string="Reference", store=True)
move_lines_count = fields.Integer(compute='_compute_move_lines_count')
display_assign_serial = fields.Boolean(compute='_compute_display_assign_serial')
display_import_lot = fields.Boolean(compute='_compute_display_assign_serial')
next_serial = fields.Char('First SN/Lot')
next_serial_count = fields.Integer('Number of SN/Lots')
orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', 'Original Reordering Rule', index=True)
forecast_availability = fields.Float('Forecast Availability', compute='_compute_forecast_information', digits='Product Unit', compute_sudo=True)
forecast_expected_date = fields.Datetime('Forecasted Expected date', compute='_compute_forecast_information', compute_sudo=True)
lot_ids = fields.Many2many('stock.lot', compute='_compute_lot_ids', inverse='_set_lot_ids', string='Serial Numbers', readonly=False)
reservation_date = fields.Date('Date to Reserve', compute='_compute_reservation_date', store=True)
packaging_uom_id = fields.Many2one('uom.uom', 'Packaging', compute='_compute_packaging_uom_id', precompute=True, store=True)
packaging_uom_qty = fields.Float('Packaging Quantity', compute='_compute_packaging_uom_qty', store=True)
show_quant = fields.Boolean("Show Quant", compute="_compute_show_info")
show_lots_m2o = fields.Boolean("Show lot_id", compute="_compute_show_info")
show_lots_text = fields.Boolean("Show lot_name", compute="_compute_show_info")

_product_location_index = models.Index("(product_id, location_id, location_dest_id, company_id, state)")
```

**Move State Transitions:**
```
draft
  ├─ action_confirm → confirmed (or waiting if chain dependency)
  └─ _action_assign → assigned
assigned
  ├─ _action_done → done
  └─ partial unreserve → partially_available
confirmed
  ├─ stock becomes available → assigned
  └─ _action_assign → partially_available
waiting ← move_orig_ids not done
```

**Procure Methods Deep Dive:**
- `make_to_stock`: Move pulls from available stock; if insufficient, move stays `confirmed`/`partially_available`
- `make_to_order`: Move creates a procurement that triggers another rule chain; ignores source location stock
- `mts_else_mto` (in `stock.rule`): Tries stock first, falls back to MTO procurement if insufficient

**`location_dest_id` Inverse Logic (`_set_location_dest_id`):** When the destination location is changed on a move, the inverse recalculates putaway strategy for each move line and updates `location_dest_id` accordingly.

---

### `stock.move.line`

Detailed operation lines tracking specific quantities, lots, serial numbers, and packages. One picking has many move lines. Move lines are the level at which actual physical picking happens.

**All Fields:**
```python
picking_id = fields.Many2one('stock.picking', 'Transfer', bypass_search_access=True, check_company=True, index=True)
move_id = fields.Many2one('stock.move', 'Stock Operation', check_company=True, index=True)
company_id = fields.Many2one('res.company', string='Company', readonly=True, required=True, index=True)
product_id = fields.Many2one('product.product', 'Product', ondelete="cascade", check_company=True, domain="[('type', '!=', 'service')]", index=True)
allowed_uom_ids = fields.Many2many('uom.uom', compute='_compute_allowed_uom_ids')
product_uom_id = fields.Many2one('uom.uom', 'Unit', required=True, domain="[('id', 'in', allowed_uom_ids)]", compute="_compute_product_uom_id", store=True, readonly=False, precompute=True)
product_category_name = fields.Char(related="product_id.categ_id.complete_name", string="Product Category")
quantity = fields.Float('Quantity', digits='Product Unit', copy=False, store=True, compute='_compute_quantity', readonly=False)
quantity_product_uom = fields.Float('Quantity in Product UoM', digits='Product Unit', copy=False, compute='_compute_quantity_product_uom', store=True)
picked = fields.Boolean('Picked', compute='_compute_picked', store=True, readonly=False, copy=False)
package_id = fields.Many2one('stock.package', 'Source Package', ondelete='restrict', check_company=True, domain="[('location_id', '=', location_id)]")
lot_id = fields.Many2one('stock.lot', 'Lot/Serial Number', domain="[('product_id', '=', product_id)]", check_company=True)
lot_name = fields.Char('Lot/Serial Number Name')
result_package_id = fields.Many2one('stock.package', 'Destination Package', ondelete='restrict', check_company=True)
result_package_dest_name = fields.Char('Destination Package Name', related='result_package_id.dest_complete_name')
package_history_id = fields.Many2one('stock.package.history', string="Package History", index='btree_not_null')
is_entire_pack = fields.Boolean('Is added through entire package')
date = fields.Datetime('Date', default=fields.Datetime.now, required=True)
scheduled_date = fields.Datetime('Scheduled Date', related='move_id.date')
owner_id = fields.Many2one('res.partner', 'From Owner', check_company=True, index='btree_not_null')
location_id = fields.Many2one('stock.location', 'From', domain="[('usage', '!=', 'view')]", check_company=True, required=True, compute="_compute_location_id", store=True, readonly=False, precompute=True, index=True)
location_dest_id = fields.Many2one('stock.location', 'To', domain="[('usage', '!=', 'view')]", check_company=True, required=True, compute="_compute_location_id", store=True, index=True, readonly=False, precompute=True)
location_usage = fields.Selection(string="Source Location Type", related='location_id.usage')
location_dest_usage = fields.Selection(string="Destination Location Type", related='location_dest_id.usage')
lots_visible = fields.Boolean(compute='_compute_lots_visible')
picking_partner_id = fields.Many2one(related='picking_id.partner_id', readonly=True)
move_partner_id = fields.Many2one(related='move_id.partner_id', readonly=True)
picking_code = fields.Selection(related='picking_type_id.code', readonly=True)
picking_type_id = fields.Many2one('stock.picking.type', 'Operation type', compute='_compute_picking_type_id', search='_search_picking_type_id')
picking_type_use_create_lots = fields.Boolean(related='picking_type_id.use_create_lots', readonly=True)
picking_type_use_existing_lots = fields.Boolean(related='picking_type_id.use_existing_lots', readonly=True)
state = fields.Selection(related='move_id.state', store=True)
scrap_id = fields.Many2one(related='move_id.scrap_id')
is_inventory = fields.Boolean(related='move_id.is_inventory')
is_locked = fields.Boolean(related='move_id.is_locked', readonly=True)
consume_line_ids = fields.Many2many('stock.move.line', 'stock_move_line_consume_rel', 'consume_line_id', 'produce_line_id')
produce_line_ids = fields.Many2many('stock.move.line', 'stock_move_line_consume_rel', 'produce_line_id', 'consume_line_id')
reference = fields.Char(related='move_id.reference', readonly=False)
tracking = fields.Selection(related='product_id.tracking', readonly=True)
origin = fields.Char(related='move_id.origin', string='Source')
description_picking = fields.Text(related='move_id.description_picking')
quant_id = fields.Many2one('stock.quant', "Pick From", store=False)  # Dummy for detailed operation view
picking_location_id = fields.Many2one(related='picking_id.location_id')
picking_location_dest_id = fields.Many2one(related='picking_id.location_dest_id')

_free_reservation_index = models.Index(
    """(id, company_id, product_id, lot_id, location_id, owner_id, package_id)
    WHERE (state IS NULL OR state NOT IN ('cancel', 'done')) AND quantity_product_uom > 0 AND picked IS NOT TRUE"""
)
```

**`_compute_quantity` Logic:** Derives `quantity` from `quant_id` when available, clamped to the move demand (`move_demand - move_quantity`). If no quant_id, uses quant's available quantity. This onchange-derived field feeds the "done" quantity.

**`_onchange_serial_number` Logic:**
- Auto-sets `quantity = 1` for serial tracking products
- Validates no duplicate serial numbers across sibling move lines
- Validates the serial number exists at the source location (via `stock.quant._check_serial_number`); suggests the correct location if not
- Raises `UserError` if quantity is not exactly 1.0 for serial products

**`_apply_putaway_strategy`:** Called when a result package is set; iterates by outermost package and computes the best destination location using `_get_putaway_strategy`, respecting storage category capacity, weight limits, and product-specific rules.

---

### `stock.quant`

The fundamental unit of inventory tracking: a quantity of a product at a location, optionally tied to a lot, package, and owner. Quants are the **only write-once records** in the stock module (with rare exceptions). The `_rec_name = 'product_id'` means list views show the product name.

**All Fields:**
```python
product_id = fields.Many2one('product.product', 'Product', domain=lambda self: self._domain_product_id(), ondelete='restrict', required=True, index=True, check_company=True)
product_tmpl_id = fields.Many2one('product.template', string='Product Template', related='product_id.product_tmpl_id')
product_uom_id = fields.Many2one('uom.uom', 'Unit', readonly=True, related='product_id.uom_id')
is_favorite = fields.Boolean(related='product_tmpl_id.is_favorite')
company_id = fields.Many2one(related='location_id.company_id', string='Company', store=True, readonly=True)
location_id = fields.Many2one('stock.location', 'Location', domain=lambda self: self._domain_location_id(), bypass_search_access=True, ondelete='restrict', required=True, index=True)
warehouse_id = fields.Many2one('stock.warehouse', related='location_id.warehouse_id')
storage_category_id = fields.Many2one(related='location_id.storage_category_id')
cyclic_inventory_frequency = fields.Integer(related='location_id.cyclic_inventory_frequency')
lot_id = fields.Many2one('stock.lot', 'Lot/Serial Number', index=True, ondelete='restrict', check_company=True, domain=lambda self: self._domain_lot_id())
lot_properties = fields.Properties(related='lot_id.lot_properties', definition='product_id.lot_properties_definition', readonly=True)
sn_duplicated = fields.Boolean(string="Duplicated Serial Number", compute='_compute_sn_duplicated')
package_id = fields.Many2one('stock.package', 'Package', domain="['|', ('location_id', '=', location_id), '&', ('location_id', '=', False), ('quant_ids', '=', False)]", ondelete='restrict', check_company=True, index=True)
owner_id = fields.Many2one('res.partner', 'Owner', help='This is the owner of the quant', check_company=True, index='btree_not_null')
quantity = fields.Float('Quantity', readonly=True, digits='Product Unit')
reserved_quantity = fields.Float('Reserved Quantity', default=0.0, readonly=True, required=True, digits='Product Unit')
available_quantity = fields.Float('Available Quantity', compute='_compute_available_quantity', digits='Product Unit')
in_date = fields.Datetime('Incoming Date', readonly=True, required=True, default=fields.Datetime.now)
tracking = fields.Selection(related='product_id.tracking', readonly=True)
on_hand = fields.Boolean('On Hand', store=False, search='_search_on_hand')
product_categ_id = fields.Many2one(related='product_tmpl_id.categ_id')

# Inventory fields
inventory_quantity = fields.Float('Counted', digits='Product Unit')
inventory_quantity_auto_apply = fields.Float('Inventoried Quantity', digits='Product Unit', compute='_compute_inventory_quantity_auto_apply', inverse='_set_inventory_quantity', groups='stock.group_stock_manager')
inventory_diff_quantity = fields.Float('Difference', compute='_compute_inventory_diff_quantity', store=True, readonly=True, digits='Product Unit')
inventory_date = fields.Date('Scheduled', compute='_compute_inventory_date', store=True, readonly=False)
last_count_date = fields.Date(compute='_compute_last_count_date')
inventory_quantity_set = fields.Boolean(store=True, compute='_compute_inventory_quantity_set', readonly=False)
is_outdated = fields.Boolean('Quantity has been moved since last count', compute='_compute_is_outdated', search='_search_is_outdated')
user_id = fields.Many2one('res.users', 'Assigned To', domain=lambda self: [('all_group_ids', 'in', self.env.ref('stock.group_stock_user').id)])
```

**Inventory Mode (`_is_inventory_mode`):** True when `context.get('inventory_mode')` is set. In this mode:
- Users can create quants directly (creates empty quants at specified locations)
- `write()` is restricted: cannot change `product_id`, `location_id`, `lot_id`, `package_id`, or `owner_id`
- `_gather()` is used to find or create matching quants during inventory adjustment
- `inventory_quantity` triggers `_apply_inventory()` which creates a stock move with `is_inventory=True`

**`_gather()` Removal Strategy:** The method that underpins `_get_available_quantity` and reservation. It applies removal strategy (FIFO/LIFO/FEFO/Closest/Least Packages) to determine which quants to consider first. The `least_packages` strategy uses A* pathfinding to minimize number of packages selected.

**Removal Strategies (`_get_removal_strategy`):**
- Cascades from `product_id.categ_id.removal_strategy_id` → `location_id.removal_strategy_id` (walked up parent locations) → default `'fifo'`
- Order: FIFO = `in_date ASC, id`; LIFO = `in_date DESC, id DESC`; Closest = sorted by `complete_name`; FEFO = managed by `stock_account` via `removal_date` field

**`_compute_last_count_date`:** Aggregates the max `date` from all done inventory move lines matching the quant's product/lot/package/owner/location, considering both source and destination locations (since inventory moves consume and create quants at the same location).

**Quant Constraints:**
- `check_product_id`: raises if product is not storable
- `check_location_id`: raises if location usage is 'view'
- `check_lot_id`: raises if lot's product doesn't match quant's product
- `check_quantity()`: validates that serial number quants at non-inventory locations never exceed 1.0

---

### `stock.lot`

Lot and serial number tracking. Inherits `mail.thread` and `mail.activity.mixin` for traceability notifications. Name uniqueness is enforced by `_check_unique_lot` at SQL level.

**All Fields:**
```python
name = fields.Char('Lot/Serial Number', required=True, compute='_compute_name', store=True, readonly=False, help="Unique Lot/Serial Number", index='trigram', precompute=True)
ref = fields.Char('Internal Reference')
product_id = fields.Many2one('product.product', 'Product', index=True, domain="[('tracking', '!=', 'none'), ('is_storable', '=', True)]", required=True, check_company=True, tracking=True)
product_uom_id = fields.Many2one('uom.uom', 'Unit', related='product_id.uom_id')
quant_ids = fields.One2many('stock.quant', 'lot_id', 'Quants', readonly=True)
product_qty = fields.Float('On Hand Quantity', compute='_product_qty', search='_search_product_qty')
note = fields.Html(string='Description')
display_complete = fields.Boolean(compute='_compute_display_complete')
company_id = fields.Many2one('res.company', 'Company', index=True, store=True, readonly=False, compute='_compute_company_id')
delivery_ids = fields.Many2many('stock.picking', compute='_compute_delivery_ids', string='Transfers')
delivery_count = fields.Integer('Delivery order count', compute='_compute_delivery_ids')
partner_ids = fields.Many2many('res.partner', compute='_compute_partner_ids', search='_search_partner_ids')
lot_properties = fields.Properties('Properties', definition='product_id.lot_properties_definition', copy=True)
location_id = fields.Many2one('stock.location', 'Location', compute='_compute_single_location', store=True, readonly=False, inverse='_set_single_location', domain="[('usage', '!=', 'view')]", group_expand='_read_group_location_id')
```

**`_compute_name` Logic:** If `name` is empty and `product_id` is set, auto-generates from `product_id.lot_sequence_id.next_by_id()`. This means the lot sequence on the product template controls automatic serial number generation.

**`generate_lot_names(first_lot, count)`:** Splits the input on the last numeric sequence found (e.g., "BATCH-001" → "BATCH-" prefix, "001" suffix, padding=3). Generates sequential names. Handles cases where the input has no digits by appending "0".

**SQL Constraint (no Python decorator):**
```python
@api.constrains('name', 'product_id', 'company_id')
def _check_unique_lot(self):
    # Groups by company_id, product_id, name -- raises if count > 1
    # Uses sudo() to detect cross-company conflicts
```

**`_search_product_qty`:** Handles operators `> < >= <= = !=` on computed `product_qty`; efficiently uses `_read_group` to aggregate without loading individual quants. Includes zero-value lots when operator makes sense (e.g., `>= 0`).

**`_set_single_location`:** If a lot has quants in exactly one location, the user can write `location_id` directly to move all those quants. Uses `quant.move_quants()` and respects `unpack` if the lot's quants span multiple packages.

**Tracking Types:**
- `none` -- No lot/serial tracking
- `lot` -- Batch tracking (groups of items; multiple quants can have same lot)
- `serial` -- Individual serial numbers; each quant must have `quantity <= 1`; duplicates in internal/transit locations are flagged via `sn_duplicated`

---

### `stock.package`

Packages containing quants and/or nested child packages. Uses `_parent_store = True` for hierarchical queries. Packages are recursive: a parent package contains child packages.

**All Fields:**
```python
name = fields.Char('Package Reference', copy=False, index='trigram', required=True)
complete_name = fields.Char("Full Package Name", compute='_compute_complete_name', recursive=True, store=True)
dest_complete_name = fields.Char("Package Name At Destination", compute='_compute_dest_complete_name', recursive=True)
quant_ids = fields.One2many('stock.quant', 'package_id', 'Bulk Content', readonly=True, domain=['|', ('quantity', '!=', 0), ('reserved_quantity', '!=', 0)])
contained_quant_ids = fields.One2many('stock.quant', compute="_compute_contained_quant_ids", search="_search_contained_quant_ids")
content_description = fields.Char('Contents', compute="_compute_content_description")
package_type_id = fields.Many2one('stock.package.type', 'Package Type', index=True)
location_id = fields.Many2one('stock.location', 'Location', compute='_compute_package_info', index=True, readonly=False, store=True, recursive=True)
location_dest_id = fields.Many2one('stock.location', 'Destination location', compute='_compute_location_dest_id', search="_search_location_dest_id")
company_id = fields.Many2one('res.company', 'Company', compute='_compute_package_info', index=True, readonly=True, store=True, recursive=True)
owner_id = fields.Many2one('res.partner', 'Owner', compute='_compute_owner_id', search='_search_owner', readonly=True, compute_sudo=True)
parent_package_id = fields.Many2one('stock.package', 'Container', index='btree_not_null')
child_package_ids = fields.One2many('stock.package', 'parent_package_id', string='Contained Packages')
all_children_package_ids = fields.One2many('stock.package', compute='_compute_all_children_package_ids', search="_search_all_children_package_ids")
package_dest_id = fields.Many2one('stock.package', 'Destination Container', index='btree_not_null')
outermost_package_id = fields.Many2one('stock.package', 'Outermost Destination Container', compute="_compute_outermost_package_id", search="_search_outermost_package_id", recursive=True)
child_package_dest_ids = fields.One2many('stock.package', 'package_dest_id', 'Assigned Contained Packages')
move_line_ids = fields.One2many('stock.move.line', compute="_compute_move_line_ids", search="_search_move_line_ids")
picking_ids = fields.Many2many('stock.picking', string='Transfers', compute='_compute_picking_ids', search="_search_picking_ids")
shipping_weight = fields.Float(string='Shipping Weight')
valid_sscc = fields.Boolean('Package name is valid SSCC', compute='_compute_valid_sscc')
pack_date = fields.Date('Pack Date', default=fields.Date.today)
parent_path = fields.Char(index=True)
json_popover = fields.Char('JSON data for popover widget', compute='_compute_json_popover')
```

**`_compute_contained_quant_ids`:** Recursively includes quants from all child packages (grandchildren, etc.), not just direct children.

**`_compute_package_info`:** `location_id` and `company_id` are computed from quants if any exist; otherwise from child packages if they all agree. This means packages inherit location/company from their contents.

**`_has_issues()` / `json_popover`:** Detects if a package's move lines have conflicting destination locations (packages spanning multiple sub-locations), and shows a warning popover.

---

### `stock.picking.type` (see L1 section above) -- Additional notes

**Reservation Methods:**
- `at_confirm`: Quants reserved immediately on `action_confirm`
- `manual`: Reserved only on explicit `action_assign`
- `by_date`: Reserved on a computed `reservation_date` (moves in the future); dates are computed when the picking type is saved with this setting

**Auto-printing Flags:** These trigger on `action_done` of the picking. Multiple can be active simultaneously. Labels use ZPL (Zebra) or PDF formats based on `package_label_to_print`.

---

### `stock.rule`

Individual procurement rules within a route. Defines what happens when a procurement is triggered.

**All Fields:**
```python
name = fields.Char('Name', required=True, translate=True)
active = fields.Boolean('Active', default=True)
action = fields.Selection([
    ('pull', 'Pull From'),
    ('push', 'Push To'),
    ('pull_push', 'Pull & Push')
], string='Action', default='pull', required=True, index=True)
sequence = fields.Integer('Sequence', default=20)
company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, index=True)
location_dest_id = fields.Many2one('stock.location', 'Destination Location', required=True, check_company=True, index=True)
location_src_id = fields.Many2one('stock.location', 'Source Location', check_company=True, index=True)
location_dest_from_rule = fields.Boolean("Destination location origin from rule", default=False)
route_id = fields.Many2one('stock.route', 'Route', required=True, ondelete='cascade', index=True)
route_company_id = fields.Many2one(related='route_id.company_id', string='Route Company')
procure_method = fields.Selection([
    ('make_to_stock', 'Take From Stock'),
    ('make_to_order', 'Trigger Another Rule'),
    ('mts_else_mto', 'Take From Stock, if unavailable, Trigger Another Rule')
], string='Supply Method', default='make_to_stock', required=True)
route_sequence = fields.Integer('Route Sequence', related='route_id.sequence', store=True, compute_sudo=True)
picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type', required=True, check_company=True, domain="[('code', 'in', picking_type_code_domain)] if picking_type_code_domain else []")
picking_type_code_domain = fields.Json(compute='_compute_picking_type_code_domain')
delay = fields.Integer('Lead Time', default=0)
partner_address_id = fields.Many2one('res.partner', 'Partner Address', check_company=True)
propagate_cancel = fields.Boolean('Cancel Next Move', default=False)
propagate_carrier = fields.Boolean('Propagation of carrier', default=False)
warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', check_company=True, index=True)
auto = fields.Selection([
    ('manual', 'Manual Operation'),
    ('transparent', 'Automatic No Step Added')
], string='Automatic Move', default='manual', required=True)
rule_message = fields.Html(compute='_compute_action_message')
push_domain = fields.Char('Push Applicability')
```

**Procurement.Group (`stock.move.group_id`):** When rules create moves, they are grouped by `procurement.group` (linked to sale order lines, purchase orders, etc.). This allows moves from the same source document to be automatically linked.

---

### `stock.warehouse.orderpoint`

Minimum stock / reorder point rules. One rule per (product, location, company) tuple.

**All Fields:**
```python
name = fields.Char('Name', copy=False, required=True, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('stock.orderpoint'))
trigger = fields.Selection([('auto', 'Auto'), ('manual', 'Manual')], string='Trigger', default='auto', required=True)
active = fields.Boolean('Active', default=True)
snoozed_until = fields.Date('Snoozed')
warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', compute="_compute_warehouse_id", store=True, readonly=False, precompute=True, check_company=True, ondelete="cascade", required=True, index=True)
location_id = fields.Many2one('stock.location', 'Location', index=True, compute="_compute_location_id", store=True, readonly=False, precompute=True, ondelete="cascade", required=True, check_company=True)
product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id')
product_id = fields.Many2one('product.product', 'Product', domain="[('is_storable', '=', True)]", ondelete='cascade', required=True, check_company=True, index=True)
product_category_id = fields.Many2one('product.category', name='Product Category', related='product_id.categ_id')
product_uom = fields.Many2one('uom.uom', 'Unit', related='product_id.uom_id')
product_uom_name = fields.Char(string='Product unit of measure label', related='product_uom.display_name', readonly=True)
product_min_qty = fields.Float('Min Quantity', digits='Product Unit', required=True, default=0.0)
product_max_qty = fields.Float('Max Quantity', digits='Product Unit', required=True, default=0.0, compute='_compute_product_max_qty', readonly=False, store=True)
allowed_replenishment_uom_ids = fields.Many2many('uom.uom', compute='_compute_allowed_replenishment_uom_ids')
replenishment_uom_id = fields.Many2one('uom.uom', 'Multiple', domain="[('id', 'in', allowed_replenishment_uom_ids)]")
replenishment_uom_id_placeholder = fields.Char(compute='_compute_replenishment_uom_id_placeholder')
company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
allowed_location_ids = fields.One2many(comodel_name='stock.location', compute='_compute_allowed_location_ids')
rule_ids = fields.Many2many('stock.rule', string='Rules used', compute='_compute_rules')
lead_horizon_date = fields.Date(compute='_compute_lead_days')
lead_days = fields.Float(compute='_compute_lead_days')
route_id = fields.Many2one('stock.route', string='Route', domain="['|', ('product_selectable', '=', True), ('rule_ids.action', 'in', ['buy', 'manufacture'])]", inverse='_inverse_route_id')
route_id_placeholder = fields.Char(compute='_compute_route_id_placeholder')
effective_route_id = fields.Many2one('stock.route', search='_search_effective_route_id', compute='_compute_effective_route_id')
qty_on_hand = fields.Float('On Hand', readonly=True, compute='_compute_qty', digits='Product Unit')
qty_forecast = fields.Float('Forecast', readonly=True, compute='_compute_qty', digits='Product Unit')
qty_to_order = fields.Float('To Order', compute='_compute_qty_to_order', inverse='_inverse_qty_to_order', search='_search_qty_to_order', digits='Product Unit')
qty_to_order_computed = fields.Float('To Order Computed', store=True, compute='_compute_qty_to_order_computed', digits='Product Unit')
qty_to_order_manual = fields.Float('To Order Manual', digits='Product Unit')
days_to_order = fields.Float(compute='_compute_days_to_order')
unwanted_replenish = fields.Boolean('Unwanted Replenish', compute="_compute_unwanted_replenish")
show_supply_warning = fields.Boolean(compute="_compute_show_supply_warning")
deadline_date = fields.Date("Deadline", compute="_compute_deadline_date", store=True, readonly=True)

_product_location_check = models.Constraint(
    'unique (product_id, location_id, company_id)',
    'A replenishment rule already exists for this product on this location.',
)
```

**SQL Constraint:** Enforces one orderpoint per (product, location, company) at DB level.

**`_compute_deadline_date` Logic:**
1. If `qty_on_hand < product_min_qty`: deadline is today
2. Otherwise: projects future stock levels by simulating incoming/outgoing moves up to `horizon_days` (a company-level config parameter)
3. Finds the first date where projected qty falls below `product_min_qty`
4. Subtracts `lead_days` from that date to get the order deadline

**`_compute_lead_days`:** Aggregates rule-level delays across buy/manufacture/pull steps. Uses `stock.rule._get_lead_days()` which walks the route chain.

---

### `stock.route`

**All Fields:**
```python
name = fields.Char('Route', required=True, translate=True)
active = fields.Boolean('Active', default=True)
sequence = fields.Integer('Sequence', default=0)
rule_ids = fields.One2many('stock.rule', 'route_id', 'Rules', copy=True)
product_selectable = fields.Boolean('Applicable on Product', default=True)
product_categ_selectable = fields.Boolean('Applicable on Product Category')
warehouse_selectable = fields.Boolean('Applicable on Warehouse')
package_type_selectable = fields.Boolean('Applicable on Package Type')
supplied_wh_id = fields.Many2one('stock.warehouse', 'Supplied Warehouse', index='btree_not_null')
supplier_wh_id = fields.Many2one('stock.warehouse', 'Supplying Warehouse')
company_id = fields.Many2one('res.company', 'Company')
product_ids = fields.Many2many('product.template', 'stock_route_product', 'route_id', 'product_id', 'Products', copy=False, check_company=True)
categ_ids = fields.Many2many('product.category', 'stock_route_categ', 'route_id', 'categ_id', 'Product Categories', copy=False)
warehouse_domain_ids = fields.One2many('stock.warehouse', compute='_compute_warehouses')
warehouse_ids = fields.Many2many('stock.warehouse', 'stock_route_warehouse', 'route_id', 'warehouse_id', 'Warehouses', copy=False, domain="[('id', 'in', warehouse_domain_ids)]")
```

**Route Activation Behavior (`write`):** When a route is deactivated, all its rules are also archived. When reactivated, rules are unarchived only if their destination location is active.

---

### `stock.storage.category`

**All Fields:**
```python
name = fields.Char('Storage Category', required=True)
max_weight = fields.Float('Max Weight', digits='Stock Weight')
capacity_ids = fields.One2many('stock.storage.category.capacity', 'storage_category_id', copy=True)
product_capacity_ids = fields.Many2one('stock.storage.category.capacity', compute="_compute_storage_capacity_ids", inverse="_set_storage_capacity_ids")
package_capacity_ids = fields.Many2one('stock.storage.category.capacity', compute="_compute_storage_capacity_ids", inverse="_set_storage_capacity_ids")
allow_new_product = fields.Selection([
    ('empty', 'If the location is empty'),
    ('same', 'If all products are same'),
    ('mixed', 'Allow mixed products')
], default='mixed', required=True)
location_ids = fields.One2many('stock.location', 'storage_category_id')
company_id = fields.Many2one('res.company', 'Company')
weight_uom_name = fields.Char(string='Weight unit', compute='_compute_weight_uom_name')

_positive_max_weight = models.Constraint('CHECK(max_weight >= 0)', 'Max weight should be a positive number.')
```

**`stock.storage.category.capacity` Sub-model:**
```python
storage_category_id = fields.Many2one('stock.storage.category', ondelete='cascade', required=True, index=True)
product_id = fields.Many2one('product.product', 'Product', ondelete='cascade', check_company=True, index='btree_not_null')
package_type_id = fields.Many2one('stock.package.type', 'Package Type', ondelete='cascade', check_company=True, index='btree_not_null')
quantity = fields.Float('Quantity', required=True)
product_uom_id = fields.Many2one(related='product_id.uom_id')
company_id = fields.Many2one('res.company', 'Company', related="storage_category_id.company_id")

_positive_quantity = models.Constraint('CHECK(quantity > 0)', 'Quantity should be a positive number.')
_unique_product = models.Constraint('UNIQUE(product_id, storage_category_id)', 'Multiple capacity rules for one product.')
_unique_package_type = models.Constraint('UNIQUE(package_type_id, storage_category_id)', 'Multiple capacity rules for one package type.')
```

---

### `stock.scrap`

**All Fields:**
```python
name = fields.Char('Reference', default=lambda self: _('New'), copy=False, readonly=True, required=True)
company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
origin = fields.Char(string='Source Document')
product_id = fields.Many2one('product.product', 'Product', domain="[('type', '=', 'consu')]", required=True, check_company=True)
allowed_uom_ids = fields.Many2many('uom.uom', compute='_compute_allowed_uom_ids')
product_uom_id = fields.Many2one('uom.uom', 'Unit', domain="[('id', 'in', allowed_uom_ids)]", compute="_compute_product_uom_id", store=True, readonly=False, precompute=True, required=True)
tracking = fields.Selection(string='Product Tracking', readonly=True, related="product_id.tracking")
lot_id = fields.Many2one('stock.lot', 'Lot/Serial', domain="[('product_id', '=', product_id)]", check_company=True)
package_id = fields.Many2one('stock.package', 'Package', check_company=True)
owner_id = fields.Many2one('res.partner', 'Owner', check_company=True)
move_ids = fields.One2many('stock.move', 'scrap_id')
picking_id = fields.Many2one('stock.picking', 'Picking', check_company=True)
location_id = fields.Many2one('stock.location', 'Source Location', compute='_compute_location_id', store=True, required=True, precompute=True, domain="[('usage', '=', 'internal')]", check_company=True, readonly=False)
scrap_location_id = fields.Many2one('stock.location', 'Scrap Location', compute='_compute_scrap_location_id', store=True, required=True, precompute=True, domain="[('usage', '=', 'inventory')]", check_company=True, readonly=False)
scrap_qty = fields.Float('Quantity', required=True, digits='Product Unit', compute='_compute_scrap_qty', default=1.0, readonly=False, store=True)
state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string='Status', default="draft", readonly=True, tracking=True)
date_done = fields.Datetime('Date', readonly=True)
should_replenish = fields.Boolean(string='Replenish Quantities')
scrap_reason_tag_ids = fields.Many2many('stock.scrap.reason.tag', string='Scrap Reason')
```

**Key Methods:**
- `do_scrap()`: Creates a draft move, calls `move._action_done(is_scrap=True)`, marks scrap as done, optionally triggers replenishment
- `_prepare_move_values()`: Sets `picked=True` and links move lines to lot/package/owner
- `check_available_qty()`: Validates sufficient stock exists at `location_id` (only for storable products)

---

## L2: Picking Types, Location Usage, Quant Reservation, UoM

### Picking Type Workflows

**Incoming (Receipts):**
```
Vendor → [incoming picking type] → WH/Stock
```

**Outgoing (Deliveries):**
```
WH/Stock → [outgoing picking type] → Customer
```

**Internal Transfers:**
```
Internal Location A → [internal picking type] → Internal Location B
```

### Location Usage Patterns

**Standard Warehouse Structure (created by `_get_locations_values`):**
```
View Location (warehouse.view_location_id)  [usage='view']
  └── WH/Stock (lot_stock_id)  [usage='internal']
       └── Zones/Sublocations  [usage='internal']
  └── WH/Input (wh_input_stock_loc_id)  [usage='internal']
  └── WH/Quality Control (wh_qc_stock_loc_id)  [usage='internal']
  └── WH/Output (wh_output_stock_loc_id)  [usage='internal']
  └── WH/Pack (wh_pack_stock_loc_id)  [usage='internal']
```

### Quant Reservation Mechanism

Quants are reserved when a picking is confirmed and assigned. The separation of `quantity` and `reserved_quantity` is a performance optimization:

```
picking.action_assign()
  → stock.move._action_assign()
       → stock.quant._update_reserved_quantity(product_id, location_id, qty,
             lot_id=lot, package_id=pkg, owner_id=owner)
  → reserved_quantity increases on matching quants
  → available_quantity (= quantity - reserved_quantity) decreases
```

**Unreservation on Cancel:**
```
picking.action_cancel() → move._action_cancel()
  → stock.quant._update_reserved_quantity(..., qty=negative)
  → reserved_quantity restored
```

---

## L3: Picking Workflow, Move Chaining, Backorders, Chain Count

### Picking Workflow (Full State Machine)

```
User Action                    System Action
───────────────────────────────────────────────────────────────────
[Create Picking]              state='draft', name='/'
action_confirm()              Confirms moves: state='confirmed'/'waiting'
                              If make_to_order: triggers procurement
action_assign()               Reserves quants: state='assigned'/'partially_available'
                              (or immediately assigned if source bypasses reservation)
[pick products]               Updates move lines (quantity done, lots, packages)
_action_done()               Creates/moves quants: state='done'
                              If partial: creates backorder via wizard
action_cancel()              Cancels moves, unreserves quants: state='cancel'
```

### Backorder Creation

Triggered when a picking is validated with `quantity < product_uom_qty`:
1. `action_done()` calls `move._action_done(cancel_backorder=...)`
2. If `cancel_backorder` is not set: `move._split()` creates a backorder move
3. Backorder picking is created with `backorder_id` pointing to parent
4. Wizard `stock.backorder.confirmation` handles user confirmation (`create_backorder = 'ask' | 'always' | 'never'`)

### Move Chaining

Moves are chained via `move_orig_ids` / `move_dest_ids`:
- **Pull rules**: Downstream demand pulls from upstream stock; creates `move_dest_ids` pointing to downstream move
- **Push rules**: Upstream arrival pushes to a destination; `push_domain` controls applicability
- **Chaining with `propagate_cancel=True`** (default): Canceling an upstream move cascades to cancel downstream moves
- **MTO chain**: Purchase order receipt → incoming picking → push rule → WH/Stock

### Chain Count (Cyclic Inventory)

**`_compute_next_inventory_date`** respects both:
1. `location.cyclic_inventory_frequency` (location-specific days)
2. `company.annual_inventory_month` + `company.annual_inventory_day` (company-wide annual count)

Takes the **minimum** of both dates.

**Workflow:**
```
Scheduled date reached → User enters inventory_quantity
  → _set_inventory_quantity → action_apply_inventory
  → Creates stock.move (is_inventory=True) with move lines
  → _action_done updates quants: in_date reset to now
  → location.last_inventory_date = today
```

---

## L4: Quant Reservation Performance, Lot/Serial Traceability, Odoo 18→19 Changes

### Quant Reservation Performance

The `reserved_quantity` / `quantity` split is architecturally significant:

1. **No row-level lock contention on reservation**: Reservation atomically increments `reserved_quantity` on existing quant rows. The quant's actual `quantity` is only changed when a move is `done`, not during reservation.

2. **Partial reservation across quants**: If demand is 10 and quants are [(lot A, 6), (lot B, 5)], `_update_reserved_quantity` reserves 6 from A and 4 from B in a single batched update.

3. **`_free_reservation_index`**: A partial B-tree index on `(id, company_id, product_id, lot_id, location_id, owner_id, package_id)` where `state IS NULL OR state NOT IN ('cancel', 'done') AND quantity_product_uom > 0 AND picked IS NOT TRUE`. This index makes reservation lookups fast even with millions of move lines.

4. **`_product_location_index`**: Composite index on `(product_id, location_id, location_dest_id, company_id, state)` for move-level availability queries.

5. **`_read_group` over `_search`**: Methods like `_get_available_quantity`, `_compute_is_empty`, and `_get_weight` all use `_read_group` (SQL aggregation) rather than loading individual records, enabling constant-time aggregation regardless of quant volume.

6. **`quants_cache` context**: During inventory mode import, quants are cached in context to avoid redundant `_gather` searches within the same batch.

### Lot/Serial Traceability

**Traceability Links:**
- `stock.lot.quant_ids` -- all quants containing this lot (including across locations)
- `stock.quant.lot_id` -- the lot in this quant
- `stock.move.line.lot_id` -- lot used in each operation line
- `stock.move.origin_returned_move_id` -- return moves link back to original
- `stock.lot.delivery_ids` -- all pickings this lot was delivered in (computed via iterative move line search)

**FEFO (First Expired First Out):** Requires `expiration_date` on `stock.lot`. The `stock_account` module populates `removal_date` from `use_date` / `life_date`. `_get_removal_strategy` returns `'fifo'` as default, but FEFO is implemented via the `removal_date` field with the same FIFO ordering logic.

**Duplicate Serial Number Detection (`_compute_sn_duplicated`):** Groups quants by lot_id where `tracking='serial'`, `quantity > 0`, and `location_id.usage in ('internal', 'transit')`. Any lot appearing in more than one such quant is flagged as duplicated.

### Odoo 18 → 19 Changes in Stock

| Area | Odoo 18 | Odoo 19 |
|------|---------|---------|
| Quant search | `search()` with domain | Optimized `_read_group` for aggregation |
| Move line reservation fields | `reserved_*` fields (qty, uom) | Replaced by `quantity` + `quantity_product_uom` computed fields |
| Forecast report | `stock.forecasted` model | Enhanced with `forecast_availability` on `stock.move` |
| Serial number model | `stock.production.lot` (legacy name) | Now `stock.lot` |
| Package hierarchy | Flat packages | Full recursive hierarchy with `parent_package_id`, `all_children_package_ids`, `outermost_package_id` |
| Storage category | Basic capacity rules | Extended with `product_capacity_ids` and `package_capacity_ids` via sub-model |
| Return wizard | Separate `stock_picking_return` | Integrated; `return_id`/`return_ids` fields added directly to `stock.picking` |
| Reservation method | Simple checkbox | Three-option selection: `at_confirm`, `manual`, `by_date` with `reservation_days_before` |
| Deadline tracking | `date_deadline` on moves | `date_deadline` and `has_deadline_issue` on pickings; `deadline_date` on orderpoints |
| Picking state computation | Stored | Computed from move states with `store=True` for performance |
| Move line picking relation | Plain Many2one | `bypass_search_access=True` for performance in large picking contexts |
| Package history | Not tracked | `package_history_id` on move lines; `stock.package.history` for done transfers |
| Removal strategy | FIFO/LIFO/FEFO/Closest | Added `least_packages` using A* pathfinding algorithm |

### Security Considerations

**Record Rules:** `stock.quant` has no explicit `ir.rule` defined in the base module. However:
- `location_id.company_id` scoping limits visible quants via location access
- `stock.group_stock_user` grants read/write on quants
- `stock.group_stock_manager` grants delete access

**Field Groups (Access Control):**
- `inventory_quantity_auto_apply` is restricted to `stock.group_stock_manager` only
- `last_count_date` on quants uses `_read_group` aggregation (SQL-level, bypasses record rules on quants themselves)

**Multi-Company:** Locations are scoped by `company_id`. Internal locations without a company are shared. Transit locations with a company are company-specific. `stock.route` without a company is shared across companies.

**SQL Injection Protection:** All dynamic SQL is constructed via `odoo.tools.SQL` (safe interpolation) rather than string formatting.

### Edge Cases and Known Pitfalls

1. **Moving a lot to a new single location** (`_set_single_location` on `stock.lot`): Only works if the lot's quants are in exactly one location. If spread across multiple locations, raises `UserError`.

2. **Serial number at multiple locations** (`sn_duplicated`): A serial number appearing in more than one internal/transit location quant triggers the duplicate flag. This can happen legitimately during transfer in-progress states.

3. **`least_packages` removal strategy memory**: The A* pathfinding in `_run_least_packages_removal_strategy_astar` catches `MemoryError` and falls back to the original domain, logging a warning. This prevents OOM on extremely large package sets.

4. **Cascading cancellations with `propagate_cancel=False`**: If a rule has `propagate_cancel=False` and the move it created is cancelled, the upstream moves are NOT cancelled. This can lead to orphaned procurements.

5. **Changing `reception_steps`/`delivery_steps` on active warehouse**: The system creates new locations but does NOT migrate existing stock. Existing quants remain at their current locations.

6. **`immediate_transfer` field (deprecated)**: The old "Immediate Transfer" checkbox that skipped `action_assign` was a common source of unreserved stock issues. Odoo 19 still supports it via `stock.picking.type` setting but recommends standard workflow.

7. **Cross-company quants**: A quant at a location without a `company_id` is considered universal. `stock.quant._gather()` uses `sudo()` internally for company-independent operations. Mixing universal and company-specific locations in multi-company setups can lead to confusing stock visibility.

8. **Return pickings**: When a picking is returned, `return_id` points to the original. Returns use the `return_picking_type_id` on the picking type. The original picking's `return_ids` is updated accordingly.

---

## Key Module Dependencies

```
stock
  ├── product (product.product, uom)
  ├── barcodes_gs1_nomenclature
  └── digest (for KPI emails)
      │
      └── [stock_account auto-installs on top]
          └── account (stock valuation journal entries)
```

---

## Wizard Reference

| Wizard | File | Purpose |
|--------|------|---------|
| `stock.backorder.confirmation` | `wizard/stock_backorder_confirmation.py` | Confirm/cancel partial delivery creation |
| `stock.picking.return` | `wizard/stock_picking_return.py` | Return products to vendor/customer |
| `stock.inventory.adjustment.name` | `wizard/stock_inventory_adjustment_name.py` | Set inventory adjustment name |
| `stock.inventory.conflict` | `wizard/stock_inventory_conflict.py` | Resolve counted vs reserved conflicts |
| `stock.inventory.warning` | `wizard/stock_inventory_warning.py` | Warn on low stock during operation |
| `stock.package.destination` | `wizard/stock_package_destination.py` | Select destination for packages |
| `stock.quant.relocate` | `wizard/stock_quant_relocate.py` | Move quants between locations |
| `stock.put.in.pack` | `wizard/stock_put_in_pack.py` | Put selected move lines into a package |
| `stock.orderpoint.snooze` | `wizard/stock_orderpoint_snooze.py` | Snooze reorder point alerts |
| `product.replenish` | `wizard/product_replenish.py` | Manual replenishment trigger |
| `stock.rules.report` | `wizard/stock_rules_report.py` | Report on routes and rules |
| `stock.warn.insufficient.qty` | `wizard/stock_warn_insufficient_qty.py` | Warn when insufficient stock on scrap |
| `stock.replenishment.info` | `wizard/stock_replenishment_info.py` | Show replenishment details |

---

## Report Reference

| Report | Model | Purpose |
|--------|-------|---------|
| Stock Quantity | `stock.report.stock_quantity` | Current on-hand by product/location |
| Stock Reception | `stock.report.stock_reception` | PDF delivery slip |
| Stock Rule | `stock.report.stock_rule` | Route action plan |
| Stock Traceability | `stock.report.stock_traceability` | Lot genealogy |
| Stock Forecasted | `stock.forecasted` | Future stock based on MRP |
| Product Label | `stock.report.product_label` | Print product/barcode labels |
| Lot Label | `stock.report.lot_barcode` | Print lot/serial labels |
| Picking Operations | `stock.report.stockpicking_operations` | Detailed operations PDF |
| Delivery Slip | `stock.report.delivery_slip` | Delivery note |
| Stock Inventory | `stock.report.stockinventory` | Physical inventory report |
| Location Barcode | `stock.report.location_barcode` | Print location barcode labels |
| Package Barcode | `stock.report.package_barcode` | Print package barcode labels |

---

## Security

**Groups:**
- `stock.group_stock_user` -- Basic stock operations (create pickings, do transfers)
- `stock.group_stock_manager` -- Full stock management (delete quants, manage routes, configure warehouses)
- `stock.group_stock_multi_locations` -- Multiple warehouse/location access (auto-activated when >1 warehouse exists)
- `stock.group_production_lot` -- Lot/serial tracking access
- `stock.group_tracking_lot` -- Package tracking access
- `stock.group_warning_stock` -- Partner picking warnings
- `stock.group_reception_report` -- Reception report visibility

**Record Rules:** Internal locations are company-scoped. Transit locations without a company are globally accessible. View locations have no specific rules.

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| `stock_account` | Automatic valuation entries (stock.quant → account.move) |
| `stock_landed_costs` | Landed cost allocation to inventory |
| `stock_barcode` | Barcode scanning UI for pickings |
| `sale_stock` | Sale → Delivery integration (SO picking policy) |
| `purchase_stock` | Purchase → Receipt integration (PO control policy) |
| `mrp_stock` | Manufacturing → consumption integration |
| `pos_restaurant` | POS inventory integration |
| `stock_picking_batch` | Batch processing of multiple pickings |
| `stock_dropshipping` | Dropshipping route management |
| `stock_enterprise` | Advanced WMS features (waves, putaway strategies) |
| `stock_accountant` | Enhanced accounting integration |
