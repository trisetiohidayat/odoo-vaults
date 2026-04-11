---
type: module
module: l10n_bg_edi
tags: [odoo, odoo19, l10n, localization, bulgaria, edi, einvoicing]
created: 2026-04-06
---

# Bulgaria EDI (`l10n_bg_edi`)

## Status

**Not available** in Odoo 19 standard distribution.

There is **no `l10n_bg_edi` module** in the Odoo 19 CE (Community Edition) addons at `/Users/tri-mac/odoo/odoo19/odoo/addons/l10n_bg_edi`.

Bulgarian EDI/e-invoicing compliance is not implemented as a separate module in Odoo 19.

## Available Module

For Bulgarian accounting, use [[Modules/l10n_bg]] which provides:
- Bulgarian Chart of Accounts
- Bulgarian VAT (ДДС) structure
- Tax reporting data
- [[Modules/l10n_bg_ledger]] for extended Bulgarian ledger reporting

## Bulgarian E-Invoicing Background

### National System

Bulgaria does not yet have a mandatory B2G/B2B e-invoicing mandate comparable to Hungary's NAV or Romania's ANAF systems. The European Commission's e-invoicing country page for Bulgaria should be consulted for current requirements.

### EDI Approach

Without a dedicated EDI module, Bulgarian companies can use:
- [[Modules/account_edi_ubl_cii]] - Standard UBL/CII format for PEPPOL network
- PEPPOL network access via [[Modules/account_peppol]] for B2G compliance
- Manual compliance with Bulgarian tax authority requirements

## Implementation Options

For Bulgarian companies requiring EDI:

1. **PEPPOL Network** (via [[Modules/account_peppol]]):
   - Register with a PEPPOL Service Provider (SMP)
   - Send/receive UBL 2.1 invoices via PEPPOL
   - B2G compliance through PEPPOL Access Point

2. **Custom Development**:
   - Implement Bulgarian-specific CIUS based on EN 16931
   - Integrate with National Revenue Agency (НАП) if required

3. **Third-party EDI Provider**:
   - Use an external EDI gateway
   - Map Odoo invoices to provider's format

## Related Modules

| Module | Status |
|--------|--------|
| [[Modules/l10n_bg]] | Available - Bulgarian accounting |
| [[Modules/l10n_bg_ledger]] | Available - Bulgarian ledger |
| `l10n_bg_edi` | **Does not exist** |

## See Also

- [[Modules/l10n_bg]] - Bulgarian accounting
- [[Modules/l10n_bg_ledger]] - Bulgarian ledger
- [European Commission - e-invoicing Bulgaria](https://ec.europa.eu/cefdigital/wiki/display/CEFDIGITAL/Bulgaria)
