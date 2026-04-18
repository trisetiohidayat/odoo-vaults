---
title: "Cloud Storage Migration"
module: cloud_storage_migration
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Cloud Storage Migration

## Overview

Module `cloud_storage_migration` — auto-generated from source code.

**Source:** `addons/cloud_storage_migration/`
**Models:** 3
**Fields:** 19
**Methods:** 4

## Models

### cloud.storage.migration.report (`cloud.storage.migration.report`)

Initialize the SQL view for the cloud storage migration report.

**File:** `cloud_storage_migration_report.py` | Class: `CloudStorageMigrationReport`

#### Fields (11)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `res_model` | `Char` | Y | — | — | — | — |
| `res_model_name` | `Char` | Y | — | — | — | — |
| `message_sum_size` | `Integer` | — | — | — | — | — |
| `message_max_size` | `Integer` | — | — | — | — | — |
| `message_count` | `Integer` | — | — | — | — | — |
| `message_to_migrate` | `Boolean` | Y | — | — | — | — |
| `all_sum_size` | `Integer` | — | — | — | — | — |
| `all_max_size` | `Integer` | — | — | — | — | — |
| `all_count` | `Integer` | — | — | — | — | — |
| `all_to_migrate` | `Boolean` | Y | — | — | — | — |
| `has_attachment_rel` | `Boolean` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `init` | |
| `get_progress` | |


### ir.attachment (`ir.attachment`)

Migrate attachment from local binary storage to cloud storage

**File:** `ir_attachment.py` | Class: `CloudStorageAttachmentMigration`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `check_model` | `SQL` | — | — | — | — | — |
| `check_documents` | `SQL` | — | — | — | — | — |
| `query` | `SQL` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### res.config.settings (`res.config.settings`)

—

**File:** `res_config_settings.py` | Class: `CloudStorageMigrationSettings`

#### Fields (5)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `cloud_storage_migration_progress` | `Integer` | — | — | — | — | — |
| `cloud_storage_migration_message_model_ids` | `One2many` | — | — | — | Y | — |
| `cloud_storage_migration_message_models` | `Char` | — | — | — | — | — |
| `cloud_storage_migration_all_model_ids` | `One2many` | — | — | — | Y | — |
| `cloud_storage_migration_all_models` | `Char` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `get_values` | |
| `action_open_cloud_storage_migration_configurations` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
