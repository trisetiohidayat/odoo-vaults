# Sale Project Stock Account

## Overview
- **Name:** Sale Project Stock Account
- **Category:** Services/Project
- **Depends:** `sale_project`, `project_stock_account`
- **Auto-install:** Yes
- **License:** LGPL-3

## Description
Technical bridge module. Combines `sale_project` and `project_stock_account` to ensure that when a sale order generates both project tasks and stock pickings, the picking-level analytic accounting integrates cleanly with the project profitability panel.

This module has no models of its own — it exists solely to enforce correct installation order and auto-install the full stack.

## Related
- [Modules/sale_project](Modules/sale_project.md) - SO to project/task generation
- [Modules/project_stock_account](Modules/project_stock_account.md) - Picking analytic moves in project profitability
