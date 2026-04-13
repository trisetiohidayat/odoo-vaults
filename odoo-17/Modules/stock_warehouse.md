---
tags: [odoo, odoo17, module, stock_warehouse, warehouse]
research_depth: medium
---

# Stock Warehouse Module — Deep Reference

**Source:** `addons/stock/models/stock_warehouse.py` — class `Warehouse`

## Overview

Warehouse configuration defines locations, routes, picking types, and procurement rules for a warehouse. Creating a warehouse automatically creates a complete location hierarchy, five picking types, and all associated stock rules and routes.

## Key Model: `stock.warehouse`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Warehouse name (default: "Company - warehouse #N") |
| `code` | Char | Short code (max 5 chars) for location/path naming |
| `active` | Boolean | Archive/unarchive warehouse |
| `company_id` | Many2one | Company (required) |
| `partner_id` | Many2one | Address partner (res.partner) |
| `view_location_id` | Many2one | Root view location for this warehouse |
| `lot_stock_id` | Many2one | Main stock location (internal usage) |
| `wh_input_stock_loc_id` | Many2one | Input/staging location (receiving area) |
| `wh_qc_stock_loc_id` | Many2one | Quality control location |
| `wh_output_stock_loc_id` | Many2one | Output/staging location (shipping area) |
| `wh_pack_stock_loc_id` | Many2one | Packing zone location |
| `route_ids` | Many2many | Routes active on this warehouse |
| `resupply_wh_ids` | Many2many | Warehouses this one resupplies from |
| `resupply_route_ids` | One2many | Auto-created resupply routes |
| `reception_steps` | Selection | `one_step` / `two_steps` / `three_steps` |
| `delivery_steps` | Selection | `ship_only` / `pick_ship` / `pick_pack_ship` |
| `in_type_id` | Many2one | Receipt picking type |
| `out_type_id` | Many2one | Delivery picking type |
| `pick_type_id` | Many2one | Pick operation type |
| `pack_type_id` | Many2one | Pack operation type |
| `int_type_id` | Many2one | Internal transfer picking type |
| `mto_pull_id` | Many2one | Make-to-Order procurement rule |
| `crossdock_route_id` | Many2one | Cross-dock route |
| `reception_route_id` | Many2one | Receipt route |
| `delivery_route_id` | Many2one | Delivery route |
| `sequence` | Integer | Display order among warehouses |

### SQL Constraints

```python
_sql_constraints = [
    ('warehouse_name_uniq', 'unique(name, company_id)', 'The name of the warehouse must be unique per company!'),
    ('warehouse_code_uniq', 'unique(code, company_id)', 'The short name of the warehouse must be unique per company!'),
]
```

## Reception Steps

| Step | Key | Flow |
|------|-----|------|
| `one_step` | Receive directly | Supplier -> Stock |
| `two_steps` | Input + Stock | Supplier -> Input -> Stock |
| `three_steps` | Input + QC + Stock | Supplier -> Input -> QC -> Stock |

Locations activated per step:
- `wh_input_stock_loc_id`: active when `reception_steps != 'one_step'`
- `wh_qc_stock_loc_id`: active when `reception_steps == 'three_steps'`

## Delivery Steps

| Step | Key | Flow |
|------|-----|------|
| `ship_only` | Direct ship | Stock -> Customer |
| `pick_ship` | Pick + Ship | Stock -> Output -> Customer |
| `pick_pack_ship` | Pick + Pack + Ship | Stock -> Packing -> Output -> Customer |

Locations activated per step:
- `wh_output_stock_loc_id`: active when `delivery_steps != 'ship_only'`
- `wh_pack_stock_loc_id`: active when `delivery_steps == 'pick_pack_ship'`

## Location Hierarchy (Created on Warehouse Creation)

```
WH_VIEW (view_location_id)
├── WH/Stock          (lot_stock_id)         # main inventory location
├── WH/Input          (wh_input_stock_loc_id)  # receiving staging
├── WH/Quality        (wh_qc_stock_loc_id)    # quality control
├── WH/Output         (wh_output_stock_loc_id) # shipping staging
└── WH/Packing        (wh_pack_stock_loc_id)   # packing zone
```

Each location gets a barcode derived from the warehouse code (e.g., `WH01-STOCK`).

## Warehouse Creation Flow

When `Warehouse.create()` is called:

1. **View location** created: `usage='view'`, name = warehouse code
2. **Sub-locations** created via `_get_locations_values()` based on reception/delivery steps
3. **Sequences** and **picking types** created via `_create_or_update_sequences_and_picking_types()`
4. **Routes** (reception, delivery, crossdock) created via `_create_or_update_route()`
5. **Global rules** (MTO, Buy, etc.) created via `_create_or_update_global_routes_rules()`
6. **Resupply routes** created if `resupply_wh_ids` set via `create_resupply_routes()`
7. **Partner data** updated if `partner_id` set

## Routes Created

### Reception Route (`reception_route_id`)

| Warehouse Steps | Routing |
|----------------|---------|
| `one_step` | Supplier -> Stock (pull, make_to_order) |
| `two_steps` | Supplier -> Input (pull) + Input -> Stock (pull_push) |
| `three_steps` | Supplier -> Input (pull) + Input -> QC (pull_push) + QC -> Stock (pull_push) |

### Delivery Route (`delivery_route_id`)

| Warehouse Steps | Routing |
|----------------|---------|
| `ship_only` | Stock -> Customer (pull) |
| `pick_ship` | Stock -> Output (pull) + Output -> Customer (pull) |
| `pick_pack_ship` | Stock -> Pack (pull) + Pack -> Output (pull) + Output -> Customer (pull) |

### Cross-Dock Route (`crossdock_route_id`)

Active when `reception_steps != 'one_step'` AND `delivery_steps != 'ship_only'`:

```
Input -> Output (pull, make_to_order)
Output -> Customer (pull)
```

## MTO (Make-to-Order) Rule

The MTO procurement rule (`mto_pull_id`) is created as a global route rule:

```python
'mto_pull_id': {
    'procure_method': 'mts_else_mto',
    'action': 'pull',
    'auto': 'manual',
    'route_id': 'stock.route_warehouse0_mto',  # Replenish on Order (MTO)
    'propagate_carrier': True,
}
```

Location and picking type for MTO rule are derived from `get_rules_dict()[warehouse_id][delivery_steps]`.

## Resupply Routes (`create_resupply_routes()`)

For each supplier warehouse in `resupply_wh_ids`:

1. **Inter-warehouse route** created: `name = "WH: Supply from SupplierWH"`
2. **Pull rules** created:
   - Supplier WH Stock -> Transit -> This WH Receipt (pull, propagate_warehouse)
   - Supplier WH Stock -> Transit (MTO rule, if `ship_only`)
3. Transit location: internal if same company, inter-warehouse if different

## Key Helper Methods

| Method | Purpose |
|--------|---------|
| `get_rules_dict()` | Returns full routing table per warehouse/step |
| `_get_rule_values()` | Generates `stock.rule` values for a routing |
| `_get_picking_type_create_values()` | Default vals for the 5 picking types |
| `_get_sequence_values()` | `ir.sequence` vals for each picking type |
| `_get_input_output_locations()` | Returns (input_loc, output_loc) based on steps |
| `_find_or_create_global_route()` | Finds/creates a global route by xml_id or name |

## `write()` Behavior

When `reception_steps` or `delivery_steps` changes:

1. Missing locations are created via `_create_missing_locations()`
2. Location `active` states are updated via `_update_location_reception()` / `_update_location_delivery()`
3. Picking type defaults and barcodes are updated via `_create_or_update_sequences_and_picking_types()`
4. Routes and rules are updated via `_create_or_update_route()`
5. MTO and global rules updated via `_create_or_update_global_routes_rules()`

When `active` changes:
- Picking types, rules, and locations are archived/restored
- Raises `UserError` if ongoing moves exist for that warehouse's picking types

## `get_rules_dict()` Routing Table

```python
{
    warehouse.id: {
        'one_step':   [Routing(supplier, lot_stock, in_type, 'pull')],
        'two_steps':  [Routing(supplier, input, in_type, 'pull'),
                       Routing(input, lot_stock, int_type, 'pull_push')],
        'three_steps':[Routing(supplier, input, in_type, 'pull'),
                       Routing(input, qc, int_type, 'pull_push'),
                       Routing(qc, lot_stock, int_type, 'pull_push')],
        'crossdock':  [Routing(input, output, int_type, 'pull'),
                       Routing(output, customer, out_type, 'pull')],
        'ship_only':  [Routing(lot_stock, customer, out_type, 'pull')],
        'pick_ship':  [Routing(lot_stock, output, pick_type, 'pull'),
                       Routing(output, customer, out_type, 'pull')],
        'pick_pack_ship': [Routing(lot_stock, pack, pick_type, 'pull'),
                           Routing(pack, output, pack_type, 'pull'),
                           Routing(output, customer, out_type, 'pull')],
        'company_id': warehouse.company_id.id,
    }
}
```

## See Also

- [Modules/stock](odoo-18/Modules/stock.md) — `stock.location`, `stock.picking`
- [Modules/stock_picking_type](odoo-17/Modules/stock_picking_type.md) — operation types
- [Modules/stock_rule](odoo-19/Modules/stock_rule.md) — procurement rules
- [Modules/stock_picking_batch](odoo-18/Modules/stock_picking_batch.md) — batch transfers
