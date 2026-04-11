---
Module: pos_self_order_epson_printer
Version: 18.0.0
Type: addon (meta / auto-install)
Tags: #odoo18 #pos_self_order_epson_printer #self_order #printer #epson
---

## Overview

Enables Epson ePOS printer support in kiosk self-order mode. Combines `pos_epson_printer` JS assets with `pos_self_order` kiosk frontend.

**Depends:** `pos_epson_printer`, `pos_self_order`
**Auto-install:** True (triggers when both dependencies present)

**Has no Python model files.** Pure asset/JS override bundler.

---

## Static Assets / JS Overrides

Extends `pos_self_order.assets` with:
- `pos_epson_printer/static/src/app/epson_printer.js`
- `pos_epson_printer/static/src/app/components/epos_templates.xml`
- `pos_self_order_epson_printer/static/src/**/*` (module's own overrides)

The module includes a JS override at `static/src/overrides/models/self_order_service.js` that adapts Epson printer behavior for kiosk self-order contexts.

---

## Critical Notes

1. **Meta-module pattern:** This module has no Python code — it's purely a manifest that re-bundles existing JS assets under the `pos_self_order.assets` bundle, making Epson printers available in kiosk mode.

2. **Auto-install behavior:** `installable=True`, `auto_install=True`. Odoo auto-installs it when both `pos_epson_printer` and `pos_self_order` are selected for installation together.

3. **JS override scope:** The `self_order_service.js` override adjusts printer behavior specifically for the self-order kiosk flow (e.g., order ticket printing after kiosk payment confirmation).
