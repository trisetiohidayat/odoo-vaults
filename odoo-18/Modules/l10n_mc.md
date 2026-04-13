---
Module: l10n_mc
Version: 18.0
Type: l10n/monaco
Tags: #odoo18 #l10n #accounting #monaco
---

# l10n_mc — Monaco Accounting

## Overview
The Monaco accounting module provides the country-specific chart of accounts for Monaco. Monaco follows French accounting standards (Plan Comptable Général / PCG) and the module extends `l10n_fr_account` rather than providing a standalone chart. Monaco's tax system is closely aligned with France — VAT (TVA) at 20% standard rate applies, with reduced rates for certain goods and services.

## Country
Monaco (`MC`)

## Dependencies
- `l10n_fr_account` (French accounting chart — Monaco is账务ly integrated with France)
- [account](account.md)

## Key Models
No Python model files in this module. Monaco does not define its own chart template; it reuses the French chart (`l10n_fr_account`) and relies on the French chart's account codes and tax templates. The `account.chart.template` methods from `l10n_fr_account` handle account mapping for Monégasque companies.

## Data Files
None (no `data/`, `demo/`, or `views/` directories in this module). All data is inherited from `l10n_fr_account`.

## Chart of Accounts
Inherits the French PCG (Plan Comptable Général) chart from `l10n_fr_account`. The French chart uses 6-digit numeric codes aligned with the official French accounting plan. Since Monaco follows French accounting law (Loi de finances and PCG), this is the correct approach.

## Tax Structure
Inherits from `l10n_fr_account`. Monaco VAT (TVA) rates match France:
- Standard rate: **20%** (Code A)
- Intermediate rate: **10%** (Code C — restaurants, transport, housing)
- Reduced rate: **5.5%** (Code B — food, books, culture)
- Special rate: **2.1%** (Code D — medicines, press)

French fiscal positions and tax tags are reused for Monaco.

## Fiscal Positions
Fiscal positions (national, intra-EU, export) are defined in `l10n_fr_account` and automatically apply to Monégasque companies through the French chart template inheritance.

## Installation
Auto-installs with `account`. When installed for a Monégasque company, it installs `l10n_fr_account` first (if not already present) and then applies the French chart as the Monégasque chart.

## Historical Notes
- **Odoo 17 → 18:** Minimal change — module structure unchanged.
- Monaco has a unique legal status: it is not part of the EU but has a customs union with France. French VAT rules apply; Monaco does not issue separate national tax returns for VAT but is covered by the French system.
- The `l10n_mc` module is intentionally minimal — all substantive accounting data comes from the French localization. This reflects Monaco's de facto integration into the French fiscal system.
