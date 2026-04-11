---
Module: l10n_ar_withholding
Version: 18.0
Type: l10n/accounting
Tags: #odoo18 #l10n #accounting #argentina #withholding
---

# l10n_ar_withholding

## Overview
Allows Argentine companies to register withholding taxes during invoice payment. Withholdings are computed based on earnings scales (tablas de ganancias) per partner/tax combination and recorded on the payment journal entry as additional tax lines. Works in tandem with `l10n_ar` and `l10n_latam_check`.

## EDI Format / Standard
Not an EDI module. Handles Argentine tax withholding mechanics.

## Dependencies
- `l10n_ar` -- Argentine localization
- `l10n_latam_check` -- LATAM check/payment support

## Key Models

### `account.move` (`l10n_ar_withholding.account_move`)
Inherits: `account.move`

Fields (from parent `l10n_ar`):
- `l10n_ar_withholding_ids` -- One2many to withholding lines (tax + partner + payment-monthly basis)

Methods extend the parent withholding logic for Argentine-specific earnings scale calculations.

### `account.payment` (`l10n_ar_withholding.account_payment`)
Inherits: `account.payment`

- `l10n_ar_withholding_ids` -- Related to move's withholdings
- `_synchronize_to_moves()` -- When a payment with withholdings is modified, strips all withholding lines from the move (sync mechanism not yet fully implemented)

### `account.tax` (`l10n_ar_withholding.account_tax`)
Inherits: `account.tax`

Adds Argentine withholding-specific fields for earnings tax configuration.

### `l10n_ar.earnings.scale` (`l10n_ar_withholding.l10n_ar_earnings_scale`)
Stands alone: no `_inherit`.

- `name` -- Char (required, translateable)
- `line_ids` -- One2many to `l10n_ar.earnings.scale.line`

Represents a bracket-based earnings withholding table (artisanal/professional income tax).

### `l10n_ar.earnings.scale.line` (`l10n_ar_withholding.l10n_ar_earnings_scale_line`)
Stands alone: no `_inherit`.

- `scale_id` -- Many2one to earnings scale
- `from_amount` / `to_amount` -- Monetary brackets
- `fixed_amount` -- Fixed amount for bracket
- `percentage` -- Percentage rate for bracket
- `excess_amount` -- "S/ Exceeding" column value for computation

Computation: `(taxable_amount - excess_amount) * percentage + fixed_amount`

### `l10n_ar.partner.tax` (`l10n_ar_withholding.l10n_ar_partner_tax`)
Stands alone: no `_inherit`.

Stores per-partner withholding tax configuration (which tax, which scale, etc.).

### `res.company` / `res.config.settings` / `res.partner` / `account.chart.template`
Extension models for configuration and partner withholding setup.

## Data Files
- `data/earnings_table_data.xml` -- Earnings scale bracket data
- `views/` -- Partner, tax, payment, config view extensions

## How It Works
1. Invoice is posted; withholding is deferred (not yet registered)
2. When payment is registered via `account.payment.register`, the withholding lines are computed based on partner + tax + cumulative monthly basis
3. Earnings scale lookup: taxable amount is mapped against scale brackets (from_amount/to_amount ranges) to find the applicable percentage and fixed amount
4. Withholding lines are written to the payment's journal entry
5. If the payment is later modified, withholding lines are stripped and must be recomputed

## Installation
Install after `l10n_ar`. The `post_init_hook` `_l10n_ar_wth_post_init` configures initial Argentine tax settings.

## Historical Notes
The Argentine withholding system (`l10n_ar_withholding`) predates Odoo 18; this module refines the payment-level withholding flow. The earnings scale mechanism (progressive brackets with fixed + percentage components) is specific to Argentine income tax law (Impuesto a las Ganancias).
