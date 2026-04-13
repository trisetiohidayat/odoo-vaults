---
Module: l10n_be_pos_sale
Version: 18.0
Type: l10n/be
Tags: #odoo18 #l10n #pos
---

# l10n_be_pos_sale

## Overview
Link module between `pos_sale` and `l10n_be`. Adds Belgian POS sale reporting data to the POS session data bundle, specifically making intra-community VAT tax IDs available to the POS frontend for correct tax calculation on B2B EU sales in Belgium.

## Country
[Belgium](Modules/account.md) 🇧🇪

## Dependencies
- pos_sale
- [l10n_be](Modules/account.md)

## Key Models

### PosSession
`models/pos_session.py` — extends `pos.session`
- `_load_pos_data()` — override: for Belgian companies, looks up the intra-community fiscal position (`fiscal_position_template_3`) via `account.chart.template` and adds `_intracom_tax_ids` (tax_dest_id IDs from fiscal position tax lines) to the session data bundle's main config object

## Data Files
No data files.

## Chart of Accounts
Inherits from [l10n_be](Modules/account.md).

## Tax Structure
Inherits from [l10n_be](Modules/account.md).

## Fiscal Positions
Intra-community fiscal position (`fiscal_position_template_3`) from [l10n_be](Modules/account.md): maps domestic Belgian VAT to 0% intra-community (reverse charge).

## EDI/Fiscal Reporting
Not applicable (POS module).

## Installation
`auto_install: True` — auto-installed when both `pos_sale` and `l10n_be` are installed.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; this is a lightweight glue module for Belgian POS + Sale integration
- Intra-community tax availability at POS level is important for B2B Belgian transactions (Belgium has significant cross-border trade)
- The `fiscal_position_template_3` reference to the Belgian chart's intra-community fiscal position is the key data link

**Performance Notes:**
- `_load_pos_data` runs once per session open; negligible overhead
- Single fiscal position lookup; cached within session