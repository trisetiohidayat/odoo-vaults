---
title: "Website Sale Mass Mailing"
module: website_sale_mass_mailing
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Website Sale Mass Mailing

## Overview

Module `website_sale_mass_mailing` — auto-generated from source code.

**Source:** `addons/website_sale_mass_mailing/`
**Models:** 2
**Fields:** 3
**Methods:** 1

## Models

### res.config.settings (`res.config.settings`)

Computing newsletter setting when changing the website in the res.config.settings page to
        show the correct value in the checkbox.

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `is_newsletter_enabled` | `Boolean` | Y | — | Y | Y | — |
| `newsletter_id` | `Many2one` | Y | — | Y | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `set_values` | |


### mailing.list (`mailing.list`)

—

**File:** `website.py` | Class: `Website`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `newsletter_id` | `Many2one` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/Website](website.md)
