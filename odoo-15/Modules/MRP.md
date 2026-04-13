# MRP — Manufacturing

Dokumentasi Odoo 15 untuk MRP module. Source: `addons/mrp/models/`

## Models

| Model | File | Description |
|---|---|---|
| `mrp.production` | `mrp_production.py` | Manufacturing Order |
| `mrp.bom` | `mrp_bom.py` | Bill of Materials |
| `mrp.workorder` | `mrp_workorder.py` | Work Order |
| `mrp.workcenter` | `mrp_workcenter.py` | Work Center |
| `mrp.routing` | `mrp_routing.py` | Routing (MO as process) |
| `mrp.unbuild` | `mrp_unbuild.py` | Unbuild Order |
| `stock_move` | `stock_move.py` | Stock Move (manufacturing) |
| `stock_production_lot` | `stock_production_lot.py` | Production Lot |
| `stock_scrap` | `stock_scrap.py` | Scrap |
| `product` | `product.py` | Product (production-related) |

## MrpProduction (Manufacturing Order)

```python
class MrpProduction(models.Model):
    _name = "mrp.production"
    _description = "Manufacturing Order"
    _order = "priority desc, date_planned_start asc, id desc"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | MO Reference (auto) |
| `origin` | Char | Source Document |
| `bom_id` | Many2one(mrp.bom) | Bill of Materials |
| `product_id` | Many2one(product.product) | Product to manufacture |
| `product_tmpl_id` | Many2one(product.template) | Product template |
| `product_qty` | Float | Quantity to produce |
| `product_uom_id` | Many2one(uom.uom) | Unit of measure |
| `qty_producing` | Float | Quantity currently producing |
| `lot_producing_id` | Many2one(stock.production.lot) | Lot being produced |
| `state` | Selection | draft/confirmed/progress/done/cancel |
| `priority` | Selection | Priority (0=Normal, 1=Urgent) |

### Dates

| Field | Type | Description |
|---|---|---|
| `date_planned_start` | Datetime | Planned start date |
| `date_planned_finished` | Datetime | Planned finish date |
| `date_start` | Datetime | Actual start |
| `date_finished` | Datetime | Actual finish |
| `date_deadline` | Datetime | Deadline |

### Components & Work Orders

| Field | Type | Description |
|---|---|---|
| `move_raw_ids` | One2many(stock.move) | Component moves (consumption) |
| `move_finished_ids` | One2many(stock.move) | Finished product moves |
| `workorder_ids` | One2many(mrp.workorder) | Work orders |
| `workorder_count` | Integer | Work order count |
| `workorder_done_count` | Integer | Completed work orders |

### Work Orders

| Field | Type | Description |
|---|---|---|
| `workorder_ids` | One2many(mrp.workorder) | Work orders |
| `move_raw_ids` | One2many(stock.move) | Material consumption |
| `move_byproduct_ids` | One2many(stock.move) | By-products |

### Location/Warehouse

| Field | Type | Description |
|---|---|---|
| `location_src_id` | Many2one(stock.location) | Component source location |
| `location_dest_id` | Many2one(stock.location) | Finished product location |
| `warehouse_id` | Many2one(stock.warehouse) | Destination warehouse |

### Company

| Field | Type | Description |
|---|---|---|
| `company_id` | Many2one(res.company) | Company |

## MrpBom (Bill of Materials)

```python
class MrpBom(models.Model):
    _name = "mrp.bom"
    _description = "Bill of Materials"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Name |
| `product_tmpl_id` | Many2one(product.template) | Product template |
| `product_id` | Many2one(product.product) | Product variant (optional) |
| `bom_line_ids` | One2many(mrp.bom.line) | Components |
| `type` | Selection | normal/kitphantom/repair |
| `code` | Char | Reference code |
| `active` | Boolean | Active |
| `sequence` | Integer | Sequence |
| `company_id` | Many2one(res.company) | Company |

### Quantities

| Field | Type | Description |
|---|---|---|
| `product_qty` | Float | Quantity produced |
| `product_uom_id` | Many2one(uom.uom) | Unit |
| `code` | Char | Reference |

### By-products

| Field | Type | Description |
|---|---|---|
| `byproduct_ids` | One2many(mrp.bom.byproduct) | By-products |

## MrpBomLine

```python
class MrpBomLine(models.Model):
    _name = "mrp.bom.line"
    _description = "Bill of Materials Line"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `bom_id` | Many2one(mrp.bom) | Parent BOM |
| `product_id` | Many2one(product.product) | Component product |
| `product_qty` | Float | Quantity needed |
| `product_uom_id` | Many2one(uom.uom) | Unit of measure |
| `sequence` | Integer | Order |
| `operation_id` | Many2one(mrp.routing.workcenter) | Work center operation |
| `bom_id` | Many2one(mrp.bom) | Parent BOM |

## MrpWorkorder

```python
class MrpWorkorder(models.Model):
    _name = "mrp.workorder"
    _description = "Work Order"
    _order = "sequence, id"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Work order name |
| `production_id` | Many2one(mrp.production) | Parent MO |
| `workcenter_id` | Many2one(mrp.workcenter) | Work Center |
| `operation_id` | Many2one(mrp.routing.workcenter) | Routing operation |
| `state` | Selection | pending/ready/in_production/done/cancel |
| `sequence` | Integer | Work order sequence |

### Time Tracking

| Field | Type | Description |
|---|---|---|
| `duration_expected` | Float | Expected duration (min) |
| `duration` | Float | Actual duration |
| `duration_unit` | Float | Duration per unit |
| `date_start` | Datetime | Start time |
| `date_finished` | Datetime | Finish time |

### Quantities

| Field | Type | Description |
|---|---|---|
| `qty_production` | Float | MO quantity |
| `qty_produced` | Float | Done quantity |
| `qty_reported` | Float | Qty from tablets |

### Operations/Lines

| Field | Type | Description |
|---|---|---|
| `workorder_line_ids` | One2many(mrp.workorder.line) | Work instruction lines |
| `time_ids` | One2many(mrp.workcenter.productivity) | Time tracking entries |

## MrpWorkcenter

```python
class MrpWorkcenter(models.Model):
    _name = "mrp.workcenter"
    _description = "Work Center"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Work center name |
| `code` | Char | Short code |
| `sequence` | Integer | Sequence |
| `active` | Boolean | Active |
| `company_id` | Many2one(res.company) | Company |

### Capacity

| Field | Type | Description |
|---|---|---|
| `capacity` | Float | Capacity per hour |
| `time_efficiency` | Float | Efficiency (%) |
| `color` | Integer | Color |
| `costs_hour` | Float | Cost per hour |
| `costs_hour_account_id` | Many2one(account.analytic.account) | Analytic account |

### Working Hours

| Field | Type | Description |
|---|---|---|
| `workcenter_load` | Float | Load |
| `time_start` | Float | Preparation time |
| `time_stop` | Float | Post-production time |

### Resource

| Field | Type | Description |
|---|---|---|
| `resource_id` | Many2one(resource.resource) | Resource |
| `resource_type` | Selection | user/material |

## Production State Machine

```
draft → confirmed → in_progress → done
  ↓        ↓             ↓          ↓
cancel   cancel        cancel     done
```

## Action Methods

```python
def action_confirm(self):
    """Confirm MO (draft → confirmed)"""
    self.move_ids.write({'state': 'confirmed'})
    self.write({'state': 'confirmed'})
    return True

def action_assign(self):
    """Reserve components"""
    self.move_ids.action_assign()

def action_produce(self):
    """Produce (create finished move)"""
    for mo in self:
        quantity = mo.qty_producing or mo.product_qty
        # Create move_finished_id with quantity_done

def action_mark_done(self):
    """Mark as done (in_progress → done)"""
    self.write({'state': 'done', 'date_finished': fields.Datetime.now()})

def action_cancel(self):
    """Cancel MO"""
    self.move_ids.write({'state': 'cancel'})
    self.write({'state': 'cancel'})
```

## See Also
- [[Modules/Stock]] — Component/finished goods moves
- [[Modules/Product]] — BoM product
- [[Modules/Account]] — Work center costs