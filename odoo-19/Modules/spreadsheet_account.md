---
title: "Spreadsheet Account"
module: spreadsheet_account
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Spreadsheet Account

## Overview

Module `spreadsheet_account` — auto-generated from source code.

**Source:** `addons/spreadsheet_account/`
**Models:** 2
**Fields:** 4
**Methods:** 7

## Models

### account.account (`account.account`)

Fetch data for ODOO.CREDIT, ODOO.DEBIT and ODOO.BALANCE formulas
        The input list looks like this::

            [{
                date_range: {
                    range_type: "year"
         

**File:** `account.py` | Class: `AccountAccount`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `balance_domain` | `Domain` | — | — | — | — | — |
| `pnl_domain` | `Domain` | — | — | — | — | — |
| `account_id_domain` | `Domain` | — | — | — | — | — |
| `default_domain` | `Domain` | — | — | — | — | — |


#### Methods (6)

| Method | Description |
|--------|-------------|
| `spreadsheet_move_line_action` | |
| `spreadsheet_fetch_debit_credit` | |
| `spreadsheet_fetch_residual_amount` | |
| `spreadsheet_fetch_partner_balance` | |
| `get_account_group` | |
| `spreadsheet_fetch_balance_tag` | |


### res.company (`res.company`)

—

**File:** `res_company.py` | Class: `ResCompany`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_fiscal_dates` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
