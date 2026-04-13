# Stock — Inventory Management

Dokumentasi Odoo 15 untuk Stock module. Source: `addons/stock/models/`

## Models

| Model | File | Description |
|---|---|---|
| `stock.picking.type` | `stock_picking.py` | Operation Type (Receipt, Delivery) |
| `stock.picking` | `stock_picking.py` | Transfer/Delivery Order |
| `stock.move` | `stock_move.py` | Stock Movement |
| `stock.move.line` | `stock_move_line.py` | Detailed Operation (move lines) |
| `stock.quant` | `stock_quant.py` | Stock Quant (actual inventory) |
| `stock.location` | `stock_location.py` | Warehouse Locations |
| `stock.warehouse` | `stock_warehouse.py` | Warehouse |
| `stock.production.lot` | `stock_production_lot.py` | Lot/Serial Number |
| `stock.scrap` | `stock_scrap.py` | Scrap Order |
| `stock.rule` | `stock_rule.py` | Procurement Rule |
| `stock.orderpoint` | `stock_orderpoint.py` | Reordering Rule |
| `stock.package_level` | `stock_package_level.py` | Package tracking |
| `stock.package_type` | `stock_package_type.py` | Package type |
| `stock.storage_category` | `stock_storage_category.py` | Storage category |

## StockLocation Hierarchy

```
Warehouse
└── Location (Stock)
    ├── WH/Stock (Main Stock)
    │   ├── WH/Stock/Shelf A
    │   └── WH/Stock/Shelf B
    ├── WH/Output (Packing)
    └── WH/Input (Receiving)
```

## StockPicking Fields

```python
class StockPicking(models.Model):
    _name = "stock.picking"
    _description = "Transfer"
    _order = "priority desc, date_scheduled, id desc"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Operation reference |
| `picking_type_id` | Many2one(stock.picking.type) | Operation Type |
| `state` | Selection | draft/assigned/done/cancel |
| `scheduled_date` | Datetime | Scheduled date |
| `date_deadline` | Datetime | Deadline |
| `date_done` | Datetime | Done date |
| `partner_id` | Many2one(res.partner) | Partner |
| `location_id` | Many2one(stock.location) | Source location |
| `location_dest_id` | Many2one(stock.location) | Destination |
| `move_ids` | One2many(stock.move) | Moves |
| `move_line_ids` | One2many(stock.move.line) | Detailed operations |
| `origin` | Char | Source document |
| `company_id` | Many2one(res.company) | Company |
| `note` | Text | Notes |
| `owner_id` | Many2one(res.partner) | Owner |
| `group_id` | Many2one(procurement.group) | Procurement group |

### Picking Type Codes

| Code | Description |
|---|---|
| `incoming` | Receipt (Vendor → Stock) |
| `outgoing` | Delivery (Stock → Customer) |
| `internal` | Internal Transfer (Stock → Stock) |

### Picking States

| State | Description |
|---|---|
| `draft` | Draft (created manually) |
| `waiting` | Waiting another operation |
| `confirmed` | Confirmed (assigned) |
| `assigned` | Ready to process |
| `done` | Completed |
| `cancel` | Cancelled |

## StockMove Fields

```python
class StockMove(models.Model):
    _name = "stock.move"
    _description = "Stock Move"
    _order = "sequence, id"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Description |
| `picking_id` | Many2one(stock.picking) | Parent picking |
| `product_id` | Many2one(product.product) | Product |
| `product_uom_qty` | Float | Quantity to move |
| `product_uom` | Many2one(uom.uom) | Unit of measure |
| `quantity_done` | Float | Quantity actually moved |
| `location_id` | Many2one(stock.location) | Source |
| `location_dest_id` | Many2one(stock.location) | Destination |
| `state` | Selection | draft/assigned/done/cancel |
| `priority` | Selection | Priority (0-1) |
| `rule_id` | Many2one(stock.rule) | Rule that generated this |
| `procure_method` | Selection | Make to stock/order |
| `origin` | Char | Source |
| `group_id` | Many2one(procurement.group) | Group |
| `partner_id` | Many2one(res.partner) | Partner |
| `scrapped` | Boolean | Is scrapped |

## StockQuant

```python
class StockQuant(models.Model):
    _name = "stock.quant"
    _description = "Quants"
    _auto = False  # No table, view
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `product_id` | Many2one(product.product) | Product |
| `location_id` | Many2one(stock.location) | Location |
| `quantity` | Float | Available quantity |
| `reserved_quantity` | Float | Reserved quantity |
| `company_id` | Many2one(resock.company) | Company |
| `lot_id` | Many2one(stock.production.lot) | Lot/Serial |
| `package_id` | Many2one(stock.quant.package) | Package |
| `owner_id` | Many2one(res.partner) | Owner |
| `in_date` | Datetime | Incoming date |

## StockWarehouse

```python
class StockWarehouse(models.Model):
    _name = "stock.warehouse"
    _description = "Warehouse"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Warehouse name |
| `code` | Char | Short code (WH/XX) |
| `company_id` | Many2one(res.company) | Company |
| `partner_id` | Many2one(res.partner) | Address |
| `lot_stock_id` | Many2one(stock.location) | Stock location |
| `location_id` | Many2one(stock.location) | View location |
| `view_location_id` | Many2one(stock.location) | Parent view location |
| `code` | Char | Code |
| `reception_steps` | Selection | 1-step/2-step/3-step receipt |
| `delivery_steps` | Selection | 1-step/2-step/3-step delivery |

### Auto-created Locations (per warehouse):

| Location | Usage |
|---|---|
| `view_location_id` | Parent view (WH/Stock) |
| `lot_stock_id` | Physical stock location |
| `wh_input_stock_loc_id` | Receiving area |
| `wh_output_stock_loc_id` | Shipping area |
| `wh_pack_stock_loc_id` | Packing area |

## StockPickingType

```python
class PickingType(models.Model):
    _name = "stock.picking.type"
    _description = "Picking Type"
    _order = 'sequence, id'
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Operation type name |
| `sequence_code` | Char | Short code (IN/OUT/INT) |
| `code` | Selection | incoming/outgoing/internal |
| `color` | Integer | Kanban color |
| `sequence` | Integer | Order in kanban |
| `sequence_id` | Many2one(ir.sequence) | Numbering sequence |
| `default_location_src_id` | Many2one(stock.location) | Default source |
| `default_location_dest_id` | Many2one(stock.location) | Default destination |
| `warehouse_id` | Many2one(stock.warehouse) | Warehouse |
| `use_create_lots` | Boolean | Allow lot creation |
| `use_existing_lots` | Boolean | Allow existing lots |
| `show_operations` | Boolean | Show detailed operations |
| `reservation_method` | Selection | at_confirm/manual/by_date |
| `return_picking_type_id` | Many2one(stock.picking.type) | Return type |

## Action Methods

```python
# Pick confirmation / processing
def action_assign(self):
    """Reserve quantities (draft → assigned)"""
    self.move_ids.write({'state': 'assigned'})
    return True

def action_confirm(self):
    """Confirm picking (draft → confirmed/assigned)"""
    self.move_ids.write({'state': 'confirmed'})

def do_unreserve(self):
    """Unreserve quantities"""
    for move in self.move_ids:
        move.write({'state': 'waiting'})

def action_done(self):
    """Mark as done, update quant"""
    self.move_ids.write({'state': 'done'})
    self.write({'date_done': fields.Datetime.now()})

def action_cancel(self):
    """Cancel picking"""
    self.move_ids.write({'state': 'cancel'})
```

## Workflow

```
1. Order (SO/PO) creates procurement
2. Procurement creates StockMove
3. StockMove grouped into StockPicking (per picking_type)
4. User confirms picking (action_assign)
5. User enters quantities (quantity_done)
6. User validates (action_done) → stock.quant updated
```

## See Also
- [Modules/Sale](Modules/Sale.md) — Sale order delivery
- [Modules/Purchase](Modules/Purchase.md) — Purchase receipt
- [Modules/MRP](Modules/MRP.md) — Manufacturing moves
- [Modules/Account](Modules/Account.md) — Stock valuation