---
Module: l10n_gcc_pos
Version: 18.0
Type: l10n/gcc
Tags: #odoo18 #l10n #accounting #gcc #pos
---

# l10n_gcc_pos

## Overview
Point of Sale localization for GCC countries. Provides POS UI assets (JS components) and enforces country configuration on POS session open. Integrates `l10n_gcc_invoice` bilingual invoice output into the POS receipt flow.

## Region
Gulf Cooperation Council (GCC)

## Dependencies
- point_of_sale
- l10n_gcc_invoice

## Key Models

### `pos_config` (`pos.config`)
Inherits `pos.config`. Overrides `open_ui()` to validate that the company has a country set before opening a POS session. Raises `UserError` if no country is configured.

### POSOrder / pos_order
See `l10n_sa_pos` for the Saudi-specific POS order extension. This module only provides shared assets.

## Data Files
No data files.

## Chart of Accounts
No chart of accounts.

## Tax Structure
No taxes.

## Installation
Auto-installed with POS and `l10n_gcc_invoice` installed. Requires country set on company before POS can be opened in a GCC context.

## Historical Notes
- Odoo 18 new module
- Validates company country before POS open — prevents misconfiguration in GCC multi-country deployments
