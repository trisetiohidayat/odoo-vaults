---
title: "Spreadsheet Dashboard"
module: spreadsheet_dashboard
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Spreadsheet Dashboard

## Overview

Module `spreadsheet_dashboard` — auto-generated from source code.

**Source:** `addons/spreadsheet_dashboard/`
**Models:** 3
**Fields:** 19
**Methods:** 3

## Models

### spreadsheet.dashboard (`spreadsheet.dashboard`)

—

**File:** `spreadsheet_dashboard.py` | Class: `SpreadsheetDashboard`

#### Fields (10)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `name` | `Char` | — | — | — | — | Y |
| `dashboard_group_id` | `Many2one` | — | — | — | — | Y |
| `sequence` | `Integer` | — | — | — | — | — |
| `sample_dashboard_file_path` | `Char` | — | — | — | — | — |
| `is_published` | `Boolean` | — | — | — | — | — |
| `company_ids` | `Many2many` | — | — | — | — | — |
| `group_ids` | `Many2many` | — | — | — | — | — |
| `favorite_user_ids` | `Many2many` | Y | — | — | — | — |
| `is_favorite` | `Boolean` | Y | — | — | — | — |
| `main_data_model_ids` | `Many2many` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_toggle_favorite` | |
| `copy_data` | |


### spreadsheet.dashboard.group (`spreadsheet.dashboard.group`)

—

**File:** `spreadsheet_dashboard_group.py` | Class: `SpreadsheetDashboardGroup`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `name` | `Char` | — | — | — | — | Y |
| `dashboard_ids` | `One2many` | — | — | — | — | — |
| `published_dashboard_ids` | `One2many` | — | — | — | — | — |
| `sequence` | `Integer` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### spreadsheet.dashboard.share (`spreadsheet.dashboard.share`)

—

**File:** `spreadsheet_dashboard_share.py` | Class: `SpreadsheetDashboardShare`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `dashboard_id` | `Many2one` | Y | — | — | — | Y |
| `excel_export` | `Binary` | Y | — | Y | — | Y |
| `access_token` | `Char` | Y | — | Y | — | Y |
| `full_url` | `Char` | Y | — | Y | — | — |
| `name` | `Char` | Y | — | Y | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `action_get_share_url` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
