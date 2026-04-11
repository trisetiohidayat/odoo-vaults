---
Module: l10n_din5008_repair
Version: 18.0
Type: l10n/din5008
Tags: #odoo18 #l10n #reporting #document_layout #repair #din5008
---

# l10n_din5008_repair — DIN 5008 Repair Orders

## Overview
This module extends `l10n_din5008` (the base DIN 5008 document standard) to apply DIN 5008-compliant formatting to repair order reports. It adds a `l10n_din5008_printing_date` transient field and extends the repair order report template to inject the partner address and VAT ID into the DIN 5008 address block.

## Country
Germany (`DE`), Switzerland (`CH`) — inherits country context from `l10n_din5008`

## Dependencies
- `l10n_din5008`
- `repair`

## Key Models

### repair.py
```python
class RepairOrder(models.Model):
    _inherit = 'repair.order'

    l10n_din5008_printing_date = fields.Date(default=fields.Date.today, store=False)
```
Adds a non-stored printing date field to `repair.order`. This is used by the report template to display a "printed on" date. `store=False` ensures it is not persisted — it recomputes from the current date each time the report is generated.

## Data Files

### report/din5008_repair_order_layout.xml
Extends `l10n_din5008.external_layout_din5008` via QWeb template inheritance (`external_layout_din5008_repairorder`):

For `repair.order` documents, injects the partner address before the main address block:
- Partner name and address via `t-field="o.partner_id"` with contact widget
- Partner VAT/Tax ID: uses the fiscal country's `vat_label` or falls back to "Tax ID"

### report/din5008_repair_templates.xml
Template fragment for repair order-specific document information (similar to `l10n_din5008_purchase`'s approach). Adds:
- Repair order name/number
- Repair lot/serial reference (if applicable)
- Operation type and responsible team

## Installation
Auto-installs when both `l10n_din5008` and `repair` are installed.

## Historical Notes
- **Odoo 17 → 18:** New in Odoo 18. Previously, repair order printing was handled by the `repair` module's own templates or by country-specific modules.
- The `l10n_din5008_printing_date` field follows the same pattern as `l10n_din5008`'s invoice/due/delivery date wizard fields — transient, non-stored fields used only in report context.
