# POS Self Order Sale

## Overview

- **Name:** POS Self Order Sale
- **Category:** Sales/Point of Sale
- **Depends:** `pos_sale`, `pos_self_order`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## L1 — What This Module Does

`pos_self_order_sale` is a **minimal glue module** that connects the POS self-order system with the sale (quotation) module. When a POS is switched to **kiosk self-ordering mode**, this module automatically assigns a dedicated **Kiosk Sale Team** (`crm.team`) as the sales team for the POS session.

This ensures that sale orders created through the self-order kiosk are correctly routed to the right sales team in the CRM pipeline.

---

## L2 — Field Types, Defaults, Constraints

### Models Extended

#### `res.config.settings` (via `_inherit = 'res.config.settings'`)

No new fields are defined. The module overrides a single method.

### Method Extension

#### `_onchange_pos_self_order_kiosk(self)`

```python
@api.onchange("pos_self_ordering_mode")
def _onchange_pos_self_order_kiosk(self):
    super()._onchange_pos_self_order_kiosk()

    for record in self:
        if record.pos_config_id.self_ordering_mode == 'kiosk':
            if not record.pos_crm_team_id:
                record.pos_crm_team_id = self.env.ref(
                    'pos_self_order_sale.pos_sales_team',
                    raise_if_not_found=False
                )
```

| Condition | Behavior |
|-----------|----------|
| User changes POS config to kiosk mode (`self_ordering_mode == 'kiosk'`) | If no sales team is set, auto-assigns the **Kiosk Sale Team** via `ir.model.data` reference |
| Other modes (mobile, etc.) | Does nothing; relies on `super()` |
| `pos_sales_team` reference not found | Silently skips (uses `raise_if_not_found=False`) |

The `super()` call ensures the base `pos_self_order` behavior is preserved (e.g., other onchange effects from the parent module).

### Data: Kiosk Sale Team

```xml
<!-- data/kiosk_sale_team.xml -->
<record id="pos_sales_team" model="crm.team">
    <field name="name">Kiosk Sale Team</field>
</record>
```

This is a **noupdate=1** demo data record created at module installation. It is a standard `crm.team` record, not a custom model.

### Defaults

| Setting | Default | Set By |
|---------|---------|--------|
| `pos_crm_team_id` | `pos_sales_team` (Kiosk Sale Team) | Auto-set by `_onchange_pos_self_order_kiosk` when mode == 'kiosk' |

### Constraints

No new constraints. All validation is delegated to `pos_self_order` (base module).

---

## L3 — Cross-Model, Override Pattern, Workflow Trigger

### Cross-Model Architecture

```
pos_self_order_sale
  └─ extends res.config.settings
       └── _onchange_pos_self_order_kiosk()
            └─ Sets pos_crm_team_id = ref('pos_sales_team')

pos_self_order (base)
  └─ defines _onchange_pos_self_order_kiosk() [called by super()]
  └─ defines pos_config_id / pos_crm_team_id fields

pos_sale
  └─ links sale orders to POS orders
```

### Override Pattern

**Pattern:** `@api.onchange` method extension — calls `super()` first, then adds conditional logic.

This is an **additive override** pattern: it preserves all parent behavior and only adds the kiosk-team logic on top.

### Workflow Trigger

| Trigger | Source | Action |
|---------|--------|--------|
| User opens POS Config settings form | Odoo form onchange | `_onchange_pos_self_order_kiosk` fires on `pos_self_ordering_mode` change |
| POS switched to kiosk mode | User selects 'kiosk' in dropdown | Kiosk Sale Team auto-populated if empty |

---

## L4 — Version Changes: Odoo 18 to Odoo 19

`pos_self_order_sale` is a minimal module with almost no code. There are **no behavioral changes** between Odoo 18 and Odoo 19.

| Aspect | Odoo 18 | Odoo 19 | Notes |
|--------|---------|---------|-------|
| Module existence | Yes | Yes | No changes |
| `_onchange_pos_self_order_kiosk` | Same logic | Same logic | Identical |
| `pos_sales_team` data | Same | Same | Record unchanged |
| `super()` call | Present | Present | Always called first |

This module is **fully stable** across the Odoo 18 to 19 transition.

---

## Related

- [[Modules/pos_self_order]] — Base self-order module
- [[Modules/pos_sale]] — POS + Sale integration
- [[Modules/sales_team]] — CRM Sales Team model
