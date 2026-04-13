---
Module: l10n_latam_base
Version: 18.0
Type: l10n/latam-base
Tags: #odoo18 #l10n #accounting #latam
---

# l10n_latam_base — LATAM Identification Types

## Overview
Base shared module for all LATAM country localizations. Adds the `l10n_latam.identification.type` model that extends the partner VAT field to support country-specific identification documents (national ID, RUT, CUIT, DNI, passport, etc.) beyond just VAT numbers. Also manages partner fields and company creation hooks for LATAM identification types. Required by all LATAM country modules including [Modules/l10n_ar](l10n_ar.md), [Modules/l10n_br](l10n_br.md), [Modules/l10n_cl](l10n_cl.md), [Modules/l10n_pe](l10n_pe.md), [Modules/l10n_ec](l10n_ec.md), [Modules/l10n_uy](l10n_uy.md).

## Country/Region
Multi-country (LATAM)

## Dependencies
- contacts
- base_vat

## Key Models

### `l10n_latam.identification.type`
Inherits: `models.Model`
- `_name`: `l10n_latam.identification.type`
- `_order`: `sequence`

Fields:
- `sequence` (Integer, default=10): Sort order for display
- `name` (Char, translate, required): Short name of the ID type
- `description` (Char, translate): Long description
- `active` (Boolean, default=True): Can be deactivated
- `is_vat` (Boolean): True = this is the VAT type for the country (used as default)
- `country_id` (Many2one res.country): Country this ID type belongs to

Method `_compute_display_name()`: Appends country code in parentheses when multiple countries have ID types defined. Format: `"DNI (AR)"`.

Generic ID types defined in data (no country):
- **VAT**: is_vat=True, the default fiscal tax ID
- **Passport**: Generic foreign identification
- **Foreign ID**: Foreign national document

### `res.partner` (Extended)
Inherits: `res.partner`
Added fields:
- `l10n_latam_identification_type_id` (Many2one): Identification type; `index='btree_not_null'`, `auto_join=True`, default=`it_vat`
- `vat` (Char, overridden label): Relabeled as "Identification Number"

Methods:
- `_commercial_fields()`: Returns `super() + ['l10n_latam_identification_type_id']` — propagates to child contacts
- `check_vat()`: Only validates VAT for partners where `is_vat=True`; skips passport/Foreign ID types
- `_onchange_country()`: On country change, resets identification type to the country's VAT type or generic `it_vat`

### `res.company` (Extended)
Inherits: `res.company`
Method `create(vals_list)`: On company creation, looks up the country's VAT identification type and sets it on the company's partner record.

### `account.chart.template` (Extended)
Inherits: `account.chart.template`
Method `_get_latam_document_account_journal()`: If `_localization_use_documents()` returns True for the company, sets `l10n_latam_use_documents = True` on sale and purchase journals during chart template loading.

## Post-Init Hook
`_set_default_identification_type()`: Sets default VAT identification type on all existing partners.

## Data Files
- `data/l10n_latam.identification.type.csv`: Generic identification types (VAT, Passport, Foreign ID)
- `views/res_partner_view.xml`: Identification type and number fields on partner form
- `views/l10n_latam_identification_type_view.xml`: ID type list/form view
- `security/ir.model.access.csv`: Read-only for base.group_user, read/write for base.group_partner_manager

## Security
- `base.group_user`: read-only on `l10n_latam.identification.type`
- `base.group_partner_manager`: read/write

## Installation
Install before any LATAM country localization module. The post-init hook applies defaults to existing partners.

## Historical Notes
This module originated from the Argentine requirement where CUIT (VAT) and CUIL (natural persons) are distinct from a national DNI. The pattern generalized across LATAM where many countries have multiple ID types beyond VAT. Key design decisions: `is_vat=True` type is country-specific and used as the default; only VAT-type identifications trigger VAT validation; identification type is a commercial field (propagates to child contacts). The multi-country display name with country codes was added for multi-LATAM deployments.
