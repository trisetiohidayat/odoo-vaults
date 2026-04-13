# India - Sale Report(GST) (`l10n_in_sale`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | India - Sale Report(GST) |
| **Technical** | `l10n_in_sale` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_in`, `sale` |

## Description
Indian GST compliance for sale orders. Handles fiscal position computation based on the GST treatment of the partner (inter-state vs intra-state, SEZ, export, etc.), Place of Supply determination, and reseller dealer identification. Propagates reseller partner to the generated customer invoice.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_in` | Core Indian accounting |
| `sale` | Base sale order module |

## Technical Notes
- Country code: `in` (India)
- GST treatment: Registered, unregistered, SEZ, consumer, etc.
- Place of Supply: Determines CGST/SGST vs IGST treatment

## Models

### `sale.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_in_reseller_partner_id` | Many2one | Reseller partner (for sale to unregistered resellers — VAT/TIN required) |

**`_compute_fiscal_position_id()`** — EXTENDS `sale`. Custom fiscal position logic for India:
- SEZ: Uses ODC (Outside Disclosure of Cargo) state
- Foreign export: Uses a foreign state (non-Indian)
- Inter-state: IGST fiscal position (standard)
- Intra-state: CGST/SGST fiscal position
- Groups orders by fiscal position, then by company, using a virtual partner with the determined state

**`_prepare_invoice()`** — EXTENDS `sale`. For Indian orders, propagates `l10n_in_reseller_partner_id` to the invoice

## Related
- [Modules/l10n_in](l10n_in.md) — Core Indian accounting
- [Modules/l10n_in_pos](l10n_in_pos.md) — Indian POS
- [Modules/l10n_in_purchase_stock](l10n_in_purchase_stock.md) — Indian purchase
- [Modules/Sale](Sale.md) — Base sale order module
