---
title: "Crm Iap Enrich"
module: crm_iap_enrich
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Crm Iap Enrich

## Overview

Module `crm_iap_enrich` — auto-generated from source code.

**Source:** `addons/crm_iap_enrich/`
**Models:** 2
**Fields:** 3
**Methods:** 4

## Models

### reveal (`reveal`)

Handle from the service and enrich the lead accordingly

        :param iap_response: dict{lead_id: company data or False}

**File:** `crm_lead.py` | Class: `CrmLead`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `iap_enrich_done` | `Boolean` | Y | — | — | — | — |
| `show_enrich_button` | `Boolean` | Y | — | — | — | — |
| `all_lead_ids` | `OrderedSet` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `create` | |
| `iap_enrich` | |


### res.config.settings (`res.config.settings`)

—

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `get_values` | |
| `set_values` | |




## Related

- [Modules/Base](base.md)
- [Modules/CRM](CRM.md)
