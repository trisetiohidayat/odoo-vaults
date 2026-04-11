---
Module: l10n_fr_pos_cert
Version: 1.1
Type: l10n/france/pos
Tags: #odoo18 #l10n #france #pos #cgi-286 #certification #inalterability
---

# l10n_fr_pos_cert

## Overview
French VAT anti-fraud certification module for Point of Sale (CGI art. 286, I. 3 bis). This add-on enforces the French legal requirements for inalterability, security, storage, and archiving of POS sales data for B2C transactions. Required for any retailer using Odoo POS in France to private individuals. The module implements hash-chaining of POS orders, automatic sale closings (daily/monthly/annual), and integrates with Odoo Enterprise's Certificate of Conformity download.

## Country
France

## Dependencies
- `l10n_fr_account` (French accounting base)
- `point_of_sale` (Point of Sale application)

## Key Models

### `AccountSaleClosing` (`account.sale.closing`)
`_name: 'account.sale.closing'` -- Stores periodic (daily/monthly/annual) POS sale closing totals. Each closing record stores:
- `date_closing_stop` / `date_closing_start` -- Period bounds
- `total_interval` -- Period total of B2C receivable accounts
- `cumulative_total` -- Grand total from installation/start
- `frequency` -- daily | monthly | annually
- `last_order_hash` -- Hash of last POS order included (for chain integrity)
- `last_order_id` -- Reference to the last POS order in the period
- `sequence_number` -- Unique sequence per frequency per company

Read-only; records cannot be modified or deleted after creation. Inherits `account.move` hash-chaining for tamper evidence.

### `pos_config` (`pos.config`)
Inherits: `pos.config`
Adds French-specific POS configuration:
- Enables secure sequence (`l10n_fr_closing_sequence_id`) on POS config
- Forces sequence on orders for inalterability

### `pos_session` (`pos.session`)
Inherits: `pos.session`
French POS sessions are closed with a hash chain verification. Sessions cannot be reopened once closed.

### `pos_order` (`pos.order`)
Inherits: `pos.order`
Adds `l10n_fr_secure_sequence_number` field -- monotonically increasing secure sequence number for B2C orders. This number is used in hash chaining.

### `PosOrderLine` (`pos.order.line`)
Inherits: `pos.order.line`
Adds French-specific line behavior for the inalterability chain.

### `AccountFiscalPosition` (`account.fiscal.position`)
Inherits: `account.fiscal.position`
French fiscal positions for B2C VAT handling.

### `ResCompany` (`res.company`)
Inherits: `res.company`
Company-level settings for French POS certification: secure sequence configuration, closing sequence.

## Data Files
- `data/account_sale_closure_cron.xml` -- CRON job for automatic daily/monthly/annual closing computation

## Cron Jobs
`l10n_fr_pos_cert.account_sale_closing_cron` runs:
- Daily at end of day: computes daily closing totals
- Monthly: computes monthly closing totals
- Annual: computes annual closing totals

## Inalterability Mechanism
1. Each `pos.order` gets a `l10n_fr_secure_sequence_number` when paid
2. Each `account.sale.closing` record stores the hash of the last included order
3. Hash chain: `closing_N.hash == hash(closing_N.last_order, closing_N-1.hash)`
4. Enterprise users can download the "Certificate of Conformity" (auto-generated PDF with hash chain)

## CGI 286 I-3 bis Requirements
- Inalterability: No cancellation or modification of POS orders after closing (implemented via write/unlink overrides)
- Security: Hash-chaining algorithm (SHA-256 based)
- Storage: Automatic closing records (daily/monthly/annual)
- Access: Certificate of Conformity download for tax audit

## Installation
Auto-installs with `l10n_fr_account` when a French company sets up POS. Required before any B2C POS sales in France.

## Historical Notes
- Odoo 18 v1.1: Enhanced hash-chaining and certificate download
- Odoo 17: Initial certification module; relied on `l10n_fr` and `account`
