---
title: "Cloud Storage Azure"
module: cloud_storage_azure
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Cloud Storage Azure

## Overview

Module `cloud_storage_azure` — auto-generated from source code.

**Source:** `addons/cloud_storage_azure/`
**Models:** 2
**Fields:** 7
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
    cloud_storage_azure_account_name, cloud_storage_azure_container_name:
        if changed and old container names are still in use, you should
        promise the current application 

**File:** `res_config_settings.py` | Class: `ResConfigSettings`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `cloud_storage_provider` | `Selection` | — | — | — | — | — |
| `cloud_storage_azure_account_name` | `Char` | — | — | — | — | — |
| `cloud_storage_azure_container_name` | `Char` | — | — | — | — | — |
| `cloud_storage_azure_tenant_id` | `Char` | — | — | — | — | — |
| `cloud_storage_azure_client_id` | `Char` | — | — | — | — | — |
| `cloud_storage_azure_client_secret` | `Char` | — | — | — | — | — |
| `cloud_storage_azure_invalidate_user_delegation_key` | `Boolean` | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `set_values` | |




## Related

- [Modules/Base](base.md)
- [Modules/Base](base.md)
