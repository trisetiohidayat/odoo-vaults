---
Module: l10n_us
Version: 18.0
Type: l10n/united_states
Tags: #odoo18 #l10n #accounting #bank #routing
---

# l10n_us — United States Localizations

## Overview
The base United States localization module adds US-specific bank account handling with ABA routing numbers. It is a lightweight module with minimal footprint — it does not define a chart of accounts or taxes. Instead it provides the `aba_routing` field on `res.partner.bank` records, a validation constraint, and sets the default US paper format.

## Country
United States of America (`US`)

## Dependencies
- `base` (only)

## Key Models

### res_partner_bank.py
```python
class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    aba_routing = fields.Char(string="ABA/Routing",
        help="American Bankers Association Routing Number")

    @api.constrains('aba_routing')
    def _check_aba_routing(self):
        for bank in self:
            if bank.aba_routing and not re.match(r'^\d{1,9}$', bank.aba_routing):
                raise ValidationError(_('ABA/Routing should only contains numbers (maximum 9 digits).'))
```
Adds the ABA (American Bankers Association) routing number field to bank accounts. The constraint validates that the field contains only digits (1–9 characters). The field is visible on the bank account form; the view file `views/res_partner_bank_views.xml` hides it for IBAN-type accounts.

## Data Files
- `data/res_company_data.xml` — Sets `base.main_company` (the default Odoo company) to use `base.paperformat_us` (US Letter paper). This applies even for non-US installs as the default.
- `views/res_partner_bank_views.xml` — Inherits `base.view_partner_bank_form`, places `aba_routing` field after `bank_id`, and hides it when `acc_type == 'iban'` (since IBAN accounts don't use ABA routing).

## Paper Format
The US Letter paper format (`base.paperformat_us`) is set as the default for `base.main_company` upon module installation. This affects all standard Odoo reports to use 8.5×11 inch paper.

## Dependencies
This module is unusual in that it only depends on `base` — not on `account`. The companion module `l10n_us_account` extends this to add accounting chart functionality.

## Installation
Standard installation. No demo data. The `l10n_us_account` module depends on both `l10n_us` and `account`, and is where most accounting setup for US companies occurs.

## Historical Notes
- **Odoo 17 → 18:** Minimal change. The module structure is unchanged.
- This module deliberately avoids adding a chart of accounts; US federal tax compliance is handled by `l10n_us_account` and the broader US payroll/localization ecosystem.
