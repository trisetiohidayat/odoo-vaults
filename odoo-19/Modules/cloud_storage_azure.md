---
type: module
module: cloud_storage_azure
tags: [odoo, odoo19, technical, attachment, storage, azure]
created: 2026-04-06
---

# Cloud Storage Azure

## Overview
| Property | Value |
|----------|-------|
| **Name** | Cloud Storage Azure |
| **Technical** | `cloud_storage_azure` |
| **Category** | Technical Settings |
| **Depends** | `cloud_storage` |
| **License** | LGPL-3 |

## Description
Extends `cloud_storage` to use Microsoft Azure Blob Storage as the attachment storage backend. Uses Azure User Delegation Keys to generate SAS (Shared Access Signature) tokens for secure direct browser-to-storage upload and download.

## Key Models

### `ir.attachment` (Extended)
Implements the abstract cloud storage methods for Azure Blob Storage.

**URL Pattern:**
```
https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}
```

**Key Methods:**
| Method | Purpose |
|--------|---------|
| `_get_cloud_storage_azure_info()` | Parses Azure Blob URL to extract `account_name`, `container_name`, `blob_name` |
| `_generate_cloud_storage_azure_url(blob_name)` | Builds base Azure blob URL |
| `_generate_cloud_storage_azure_sas_url(**kwargs)` | Generates SAS token URL using User Delegation Key |
| `_generate_cloud_storage_url()` | Returns Azure blob URL (only when provider = azure) |
| `_generate_cloud_storage_download_info()` | Returns SAS-signed private download URL with cache headers (300s expiry) |
| `_generate_cloud_storage_upload_info()` | Returns SAS-signed PUT upload URL (300s expiry, expects `201`, sets `x-ms-blob-type: BlockBlob`) |

### User Delegation Key Caching
The User Delegation Key is cached for 7 days (refreshed every 6 days). Cache is keyed by database name + full configuration hash. If Azure authentication fails, a `ValidationError` is cached to prevent retry loops until config changes or `cloud_storage_azure_user_delegation_key_sequence` is bumped.

## Configuration (ir.config_parameter)
| Key | Purpose |
|-----|---------|
| `cloud_storage_azure_account_name` | Azure storage account name |
| `cloud_storage_azure_container_name` | Blob container name |
| `cloud_storage_azure_tenant_id` | Azure AD tenant ID |
| `cloud_storage_azure_client_id` | App registration client ID |
| `cloud_storage_azure_client_secret` | App registration secret |
| `cloud_storage_azure_user_delegation_key_sequence` | Bump to invalidate cached key |

## Technical Notes
- Requires Azure Blob Storage account with RBAC (Storage Blob Data Contributor role for the app registration).
- Uses `azure.storage.blob` SAS v4 tokens via User Delegation Keys.
