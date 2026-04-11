---
Module: l10n_sa_edi_pos
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #saudi-arabia #pos
---

# l10n_sa_edi_pos

## Overview
Adds ZATCA (Zakat, Tax and Customs Authority) e-invoicing support to the Point of Sale for Saudi Arabia. Building on `l10n_sa_edi` and `l10n_sa_pos`, this module ensures POS orders and invoices produce ZATCA-compliant UBL 2.1 XML with the correct payment means code derived from the POS payment method.

## EDI Format / Standard
UBL 2.1 (ZATCA simplified invoice profile). Hash + QR code generation per ZATCA specifications.

## Dependencies
- `l10n_sa_pos` -- Saudi POS configuration (company settings)
- `l10n_sa_edi` -- Core ZATCA e-invoicing (UBL builder, send logic)
- `point_of_sale` -- POS framework

## Key Models

### `pos.order` (`l10n_sa_edi_pos.pos_order`)
Inherits: `pos.order`

Fields (related/computed):
- `l10n_sa_invoice_qr_code_str` -- Related: `account_move.l10n_sa_qr_code_str`
- `l10n_sa_invoice_edi_state` -- Related: `account_move.edi_state`

Displays the ZATCA QR code and EDI state from the linked account move on the POS order form.

### `pos.config` (`l10n_sa_edi_pos.pos_config`)
Inherits: `pos.config`

Mirror of company ZATCA settings via related fields.

### `account.move` (`l10n_sa_edi_pos.account_move`)
Inherits: `account.move`

Overrides `l10n_sa_edi` behavior when the invoice originates from a POS order.

### `account.edi.xml.ubl_21.zatca` (`l10n_sa_edi_pos.account_edi_xml_ubl_21_zatca`)
Inherits: `account.edi.xml.ubl_21.zatca`

- `_l10n_sa_get_payment_means_code()` -- When invoice is simplified (POS order, no invoice) and has `pos_order_ids.payment_ids`, reads the payment method type from the first POS payment to populate the `PaymentMeansCode` in the UBL XML

## Data Files
No data XML files.

## How It Works
1. POS order is paid and (optionally) invoiced
2. Account move is created with ZATCA EDI format
3. If order is paid via POS payment method, `_l10n_sa_get_payment_means_code()` overrides the payment means code using the POS payment method type rather than the journal's default
4. UBL 2.1 XML is generated with ZATCA-specific fields (QR code, hash, etc.)
5. QR code and state are reflected on the POS order form via related fields

## Installation
Install after `l10n_sa_edi` and `point_of_sale`. Auto-installs. Requires ZATCA production or sandbox credentials configured on the company.

## Historical Notes
ZATCA Phase 2 compliance (simplified invoices via POS) was mandated in Saudi Arabia starting 2023. The `l10n_sa_edi_pos` module bridges the gap between the POS payment method and the ZATCA UBL XML. The payment means code override is significant because the default account journal payment method may not reflect the actual cash/card payment method used at the POS.
