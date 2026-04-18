---
title: "Cloud Storage Google"
module: cloud_storage_google
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Cloud Storage Google

## Overview

Module `cloud_storage_google` — auto-generated from source code.

**Source:** `addons/cloud_storage_google/`
**Models:** 2
**Fields:** 4
**Methods:** 1

## Models

### ir.attachment (`ir.attachment`)

—

**File:** `ir_attachment.py` | Class: `IrAttachment`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.config.settings (`res.config.settings`)

Instructions:
    cloud_storage_google_bucket_name: if changed and the old bucket name
        are still in use, you should promise the current service account
        has the permission to access the

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (4)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `cloud_storage_provider` | `Selection` | — | — | — | — | — |
| `cloud_storage_google_bucket_name` | `Char` | — | — | — | — | — |
| `cloud_storage_google_service_account_key` | `Binary` | Y | — | — | Y | — |
| `cloud_storage_google_account_info` | `Char` | Y | — | — | Y | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `get_values` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
