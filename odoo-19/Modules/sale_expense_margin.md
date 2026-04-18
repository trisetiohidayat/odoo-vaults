---
title: "Sale Expense Margin"
module: sale_expense_margin
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Sale Expense Margin

## Overview

Module `sale_expense_margin` — auto-generated from source code.

**Source:** `addons/sale_expense_margin/`
**Models:** 2
**Fields:** 1
**Methods:** 0

## Models

### account.move.line (`account.move.line`)

—

**File:** `account_move_line.py` | Class: `AccountMoveLine`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### sale.order.line (`sale.order.line`)

—

**File:** `sale_order_line.py` | Class: `SaleOrderLine`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `expense_id` | `Many2one` | Y | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Sale](Sale.md)
