---
Module: quality
Version: Odoo 18
Type: Integration
---

# Quality Control (`quality`) — Not Available in Odoo 18 Core

> **IMPORTANT FINDING:** Quality control models (`quality.point`, `quality.alert`, `quality.check`, `quality.tag`) do NOT exist as a separate module in Odoo 18.0. The `quality` module was deprecated and removed after Odoo 15. In Odoo 18, quality control features are absent from the core codebase and are NOT provided via `module_quality_control` or `module_quality_control_worksheet` install flags — these fields are dead code remnants.

---

## Investigation Results

### What Exists vs. What Was Removed

**Confirmed Absent (Odoo 18.0):**
- `quality.point` — quality control inspection points
- `quality.alert` — quality non-conformance issues
- `quality.check` — individual quality check records
- `quality.tag` — tags for quality alerts and checks
- `quality.team` — quality inspection teams
- `quality.control` module directory

**Dead Code Remnants Found:**

1. **`stock/models/res_config_settings.py` (line 43-44)**
   ```python
   module_quality_control = fields.Boolean("Quality")
   module_quality_control_worksheet = fields.Boolean("Quality Worksheet")
   ```
   These fields are defined but **never used** — no `depends` install logic, no views, no data files.

2. **`mrp/models/res_config_settings.py` (line 16-17)**
   ```python
   module_quality_control = fields.Boolean("Quality")
   module_quality_control_worksheet = fields.Boolean("Quality Worksheet")
   ```
   Same — dead checkboxes in the MRP settings panel.

3. **`stock/views/res_config_settings_views.xml` (lines 25-29)** and **`mrp/views/res_config_settings_views.xml` (lines 38-43)**
   XML view entries for these checkboxes exist but activate nothing.

4. **`stock/models/stock_warehouse.py` (line 17)**
   ```python
   'three_steps': _lt('Receive in 3 steps (input + quality + stock)')
   ```
   A translatable string referencing "quality" in 3-step receipt routing — but no actual quality step is implemented.

5. **`stock/models/stock_warehouse.py` (line 1148)**
   ```python
   'name': _('%(name)s Sequence quality control', name=name)
   ```
   A sequence name for a non-existent quality control operation type.

6. **`mrp/views/mrp_workcenter_views.xml` (line 500)**
   ```xml
   <filter name="quality" string="Quality Losses" domain="[('loss_type','=','quality')]"/>
   ```
   This is an OEE (Overall Equipment Effectiveness) filter, NOT a quality control check. It filters production time losses of type `quality` (defects produced during slow cycles).

---

## Historical Context (Odoo 12–15)

The `quality` module previously provided:

| Model | Purpose |
|-------|---------|
| `quality.point` | Defined where quality checks occurred (on receipt, production, delivery, etc.) |
| `quality.alert` | Tracked non-conformances/defects discovered during operations |
| `quality.check` | Recorded the result of each inspection (pass/fail, measured values) |
| `quality.tag` | Categorized alerts and checks with tags |
| `quality.team` | Assigned quality inspectors to teams |

### Trigger Types (historically)
- `at_receipt` — trigger at incoming shipment validation
- `at_production` — trigger at manufacturing order steps
- `at_delivery` — trigger at outgoing shipment
- `at_inventory` — trigger at inventory count
- `on_request` — manual trigger by user

### Check Types (historically)
- `pass_fail` — simple pass/fail inspection
- `measure` — record a measured value against a tolerance range
- `picture` — require a picture to be attached

These models were part of the `quality` module that depended on `mrp`, `stock`, and `quality_mrp` sub-modules.

---

## Odoo 18 Quality Control Gap

In Odoo 18, organizations needing quality control must implement one of these alternatives:

### Option 1: Custom Module
Build a custom `quality` module mirroring the Odoo 12-15 implementation:
```
quality/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── quality_point.py      # quality.point
│   ├── quality_alert.py      # quality.alert
│   ├── quality_check.py      # quality.check
│   ├── quality_tag.py        # quality.tag
│   └── quality_team.py       # quality.team
├── views/
│   ├── quality_point_views.xml
│   ├── quality_alert_views.xml
│   ├── quality_check_views.xml
│   └── quality_menu.xml
└── data/
    └── quality_data.xml
```

### Option 2: Maintenance + MRP Workorder Integration
Use `maintenance.request` for non-conformance tracking:
- Create a `corrective` maintenance request when a defect is found
- Link it to the `mrp.production` or `stock.picking` via `resource_ref`
- Use `maintenance.mixin` on custom equipment models

### Option 3: Stock Scrap for Defect Tracking
When defects are found during receipt or production:
1. Use `stock.scrap` to remove defective items
2. Add a `quality_note` or `scrap_reason` to categorize defects
3. Link scrap records to `stock.picking` or `mrp.production` for traceability

### Option 4: MRP Repair Module
The `mrp_repair` module provides structured repair workflows:
- Can be used for return-repair scenarios (e.g., customer returns a defective product)
- Tracks parts consumed, operations performed, and final outcome
- Integrates with `stock.picking` for component moves

---

## L4: Implementing Quality Control in Odoo 18

### Recommended Architecture for Custom Quality Module

#### `quality.point` — Control Point Definition
```python
class QualityPoint(models.Model):
    _name = 'quality.point'
    _description = 'Quality Control Point'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company')
    product_ids = fields.Many2many('product.product')
    product_category_id = fields.Many2one('product.category')

    # Where to trigger
    operation_type = fields.Selection([
        ('receipt', 'Receipt'),
        ('delivery', 'Delivery'),
        ('production', 'Production'),
        ('scrap', 'Scrap'),
        ('custom', 'Custom'),
    ])
    picking_type_ids = fields.Many2many('stock.picking.type')

    # What to check
    check_type = fields.Selection([
        ('pass_fail', 'Pass/Fail'),
        ('measure', 'Measure'),
        ('picture', 'Picture'),
    ])
    norm_ids = fields.One2many('quality.test.norm', 'point_id')

    # Scheduling
    frequency = fields.Selection([
        ('all', 'Every Operation'),
        ('random', 'Random Sample'),
        ('periodic', 'Periodic'),
    ])
    percentage = fields.Float('Sample %', default=100.0)

    # Instructions
    instruction_type = fields.Selection([
        ('text', 'Text'), ('pdf', 'PDF'), ('url', 'URL'),
    ])
    instruction = fields.Html()

    team_id = fields.Many2one('quality.team')
    user_id = fields.Many2one('res.users', 'Responsible')
```

#### `quality.alert` — Non-Conformance Record
```python
class QualityAlert(models.Model):
    _name = 'quality.alert'
    _description = 'Quality Alert'

    name = fields.Char(required=True, copy=False)
    stage_id = fields.Many2one('quality.alert.stage')
    priority = fields.Selection([('0','Low'),('1','Normal'),('2','High')])
    company_id = fields.Many2one('res.company')

    # Origin
    product_id = fields.Many2one('product.product')
    lot_id = fields.Many2one('stock.lot')
    picking_id = fields.Many2one('stock.picking')
    production_id = fields.Many2one('mrp.production')

    # Description
    description = fields.Html()
    tag_ids = fields.Many2many('quality.tag')

    # Resolution
    user_id = fields.Many2one('res.users', 'Assigned to')
    close_date = fields.Date()
    solution_type = fields.Selection([
        ('repair', 'Repair/Re-work'),
        ('scrap', 'Scrap'),
        ('accept', 'Accept with deviation'),
        ('return', 'Return to supplier'),
    ])

    tag_ids = fields.Many2many('quality.tag')
```

#### `quality.check` — Inspection Record
```python
class QualityCheck(models.Model):
    _name = 'quality.check'
    _description = 'Quality Check'

    name = fields.Char(related='point_id.name')
    point_id = fields.Many2one('quality.point')
    production_id = fields.Many2one('mrp.production')
    picking_id = fields.Many2one('stock.picking')
    lot_id = fields.Many2one('stock.lot')
    product_id = fields.Many2one('product.product')

    # Result
    success = fields.Boolean('Passed')
    check_date = fields.Datetime(default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', 'Checked by')

    # Measurements
    measure_value = fields.Float()
    measure_min = fields.Float()
    measure_max = fields.Float()

    # Picture
    picture = fields.Binary()

    alert_ids = fields.One2many('quality.alert', 'check_id')
    notes = fields.Html()
```

---

## OEE "Quality Losses" vs. Quality Control

The `quality_losses` referenced in `mrp_workcenter_views.xml` is an OEE metric:

**OEE = Availability × Performance × Quality**

- **Availability Loss**: Downtime during planned production time
- **Performance Loss**: Slow cycles vs. ideal cycle time
- **Quality Loss**: Defective parts produced during fast cycles or slow cycles

```
Quality Loss % = (Defective Parts / Total Parts Produced) × 100
```

This is **not** the same as quality control inspection. It measures manufacturing yield, not whether products passed inspection.

---

## Verification Notes

| Check | Result |
|-------|--------|
| `quality` module directory in addons | Not found |
| `quality.point` Python class definition | Not found |
| `quality.alert` Python class definition | Not found |
| `quality.check` Python class definition | Not found |
| `quality.tag` Python class definition | Not found |
| `module_quality_control` install logic | Dead code — defined but no effect |
| `module_quality_control_worksheet` install logic | Dead code — defined but no effect |
| Quality-related picking types in stock | None implemented |
| Quality operation type in stock.picking.type | None implemented |
| Quality-triggered stock moves | None implemented |

**Conclusion:** The `quality` module was removed from Odoo 16+. Quality control functionality is a gap in Odoo 18 core. Implement via custom module or third-party apps.

---

## Tags

#odoo #odoo18 #quality #quality-control #deprecated #gap
