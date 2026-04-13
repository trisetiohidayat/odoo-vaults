---
type: module
module: cloud_storage_migration
tags: [odoo, odoo19, technical, attachment, migration, cloud]
created: 2026-04-06
---

# Cloud Storage Migration

## Overview
| Property | Value |
|----------|-------|
| **Name** | Cloud Storage Migration |
| **Technical** | `cloud_storage_migration` |
| **Category** | Technical Settings |
| **Depends** | `cloud_storage` |
| **License** | LGPL-3 |

## Description
Migrates existing local (binary) attachments to cloud storage. Provides a reporting dashboard and cron-based batch migration of attachments by model.

## Key Models

### `cloud.storage.migration.report` (Auto=False SQL View)
Read-only model backed by a SQL view that aggregates attachment statistics per model.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `res_model` | Char | Technical model name |
| `res_model_name` | Char (computed) | Display name from `ir.model` |
| `message_sum_size` | Integer | Total size (MB) of attachments linked to mail messages |
| `message_max_size` | Integer | Largest message attachment (MB) |
| `message_count` | Integer | Count of message-linked attachments |
| `message_to_migrate` | Boolean (computed) | Whether message attachments for this model are scheduled |
| `all_sum_size` | Integer | Total size (MB) of all attachments for this model |
| `all_max_size` | Integer | Largest attachment (MB) for this model |
| `all_count` | Integer | Total attachment count |
| `all_to_migrate` | Boolean (computed) | Whether all attachments for this model are scheduled |
| `has_attachment_rel` | Boolean (computed) | Whether this model has a relational field linking to `ir.attachment` |

**SQL View:**
Joins `ir_attachment` with `message_attachment_rel` to compute per-model totals. Filters to `type = 'binary'`, non-residual attachments with file sizes.

**Migration Scheduling:**
- `all_to_migrate`: True if model is in `cloud_storage_migration_all_models` ICP
- `message_to_migrate`: True if model is in `cloud_storage_migration_message_models` ICP

**Method:** `get_progress()` - Returns 0-100 percentage based on `cloud_storage_migration_min_attachment_id` / `cloud_storage_migration_max_attachment_id` ICP values.

## Data / Cron
- `data/ir_cron.xml` - Scheduled action for batch migration
- `data/data.xml` - Initial migration configuration

## Related Modules
- [Modules/cloud_storage](cloud_storage.md)
- [Modules/cloud_storage_azure](cloud_storage_azure.md)
- [Modules/cloud_storage_google](cloud_storage_google.md)
