# Account Add GLN

**Module:** `account_add_gln`
**Category:** Accounting/Accounting
**Depends:** `account`
**Auto-install:** True
**License:** LGPL-3

## Overview

Adds a Global Location Number (GLN) field to partners. GLN is used to identify stock locations and is mandatory on UBL/CII eInvoices. This module is intended to be merged into the core `account` module in a future version.

## Models

### `res.partner` (inherited)
Extends `res.partner` with:

| Field | Type | Description |
|-------|------|-------------|
| `global_location_number` | Char | Global Location Number (GLN) |

## Usage

The GLN can be set on partner records (particularly delivery addresses) and is used in electronic invoice formats (UBL/CII) to identify locations.

## Technical Notes

- Auto-installed when `account` is installed.
- Adds a view extension for the partner form.
