---
tags: [odoo, odoo17, module, report]
---

# Report Module

**Status: NOT PRESENT in Odoo 17**

In Odoo 17, `base_report` / `report` is no longer a standalone module. Report infrastructure is now part of the `web` and `report` (or `base_report`) addons with significant changes.

## Historical Context

In earlier Odoo versions, `base_report` provided:
- `ir.actions.report` model for report definitions
- QWeb template engine for report rendering
- PDF generation via WKHtmlToPdf

## Odoo 17 Report Stack

| Component | Module | Description |
|-----------|--------|-------------|
| Report action | `ir.actions.report` | Still exists in `base` (or `report`) |
| QWeb templates | `ir.ui.view` with `type='qweb'` | Report XML templates |
| PDF rendering | `report` / `base` | Uses WKHtmlToPdf or built-in |
| Report designer | `base_report_designer` | External designer plugin |

## See Also
- [Core/HTTP Controller](odoo-18/Core/HTTP Controller.md) — Report download routes
- [Modules/Account](Modules/account.md) — Financial report templates
