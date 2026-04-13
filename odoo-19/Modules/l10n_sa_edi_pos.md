# Saudi Arabia - E-invoicing (POS) (`l10n_sa_edi_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Saudi Arabia - E-invoicing (POS) |
| **Technical** | `l10n_sa_edi_pos` |
| **Category** | Accounting/Localizations/EDI |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_sa_pos`, `l10n_sa_edi` |
| **Auto-install** | `l10n_sa_pos` |

## Description
ZATCA Phase 2 e-invoicing integration for Point of Sale in Saudi Arabia. Generates UBL 2.1 XML invoices compliant with ZATCA requirements for POS transactions, including simplified invoices (B2C) with QR codes and cryptographic signatures. Links POS orders to their generated e-invoices.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_sa_pos` | Saudi POS base |
| `l10n_sa_edi` | Core ZATCA e-invoicing (UBL 2.1, Phase 2) |

## Technical Notes
- Country code: `sa` (Saudi Arabia)
- Format: UBL 2.1 (ZATCA profile)
- Standard: Phase 2 simplified invoices (B2C/B2B)
- Module has Python model files

## Models

### `account.edi.xml.ubl_21.zatca` (Extended — `l10n_sa_edi_pos/models/account_edi_xml_ubl_21_zatca.py`)
Inherits from `l10n_sa_edi` ZATCA EDI builder.

| Method | Description |
|--------|-------------|
| `_l10n_sa_get_payment_means_code()` | EXTENDS base. When the invoice is a simplified ZATCA invoice (`_l10n_sa_is_simplified()`) AND has `pos_order_ids.payment_ids`, reads the payment method type from the first POS payment record. Otherwise falls back to the parent method |

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_sa_invoice_qr_code_str` | Char (related) | Related to `account_move.l10n_sa_qr_code_str` |
| `l10n_sa_invoice_edi_state` | Selection (related) | Related to `account_move.edi_state` |

### `res.company` (Extended)
L10n_sa_edi_pos does not add fields but the `l10n_sa_edi` company-level ZATCA settings (API credentials, certificate, e-invoice mode) apply to POS companies using this module.

## How It Works
1. POS order is closed and invoiced
2. `account.move` is created linked to the POS order
3. E-invoice XML is generated via `l10n_sa_edi` (inherits `account.edi.xml.ubl_21.zatca`)
4. POS `pos.order` record shows ZATCA QR code string and EDI state via related fields
5. For simplified invoices paid via POS terminal, payment means code is sourced from POS payment method type

## Related
- [Modules/l10n_sa_edi](l10n_sa_edi.md) — Core ZATCA e-invoicing
- [Modules/l10n_sa_pos](l10n_sa_pos.md) — Saudi POS base
- [Modules/l10n_sa_withholding_tax](l10n_sa_withholding_tax.md) — Saudi withholding tax
