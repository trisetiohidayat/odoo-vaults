---
Module: cloud_storage_azure
Version: 18.0.0
Type: addon
Tags: #odoo18 #azure #cloud #storage #attachment
---

## Overview

Stores `ir.attachment` files in Azure Blob Storage instead of the local database filesystem. Uses User Delegation Keys for SAS token generation, cached for 6 days, with manual invalidation support.

**Depends:** `cloud_storage`

**Key Behavior:** All file uploads/downloads go through Azure Blob Storage via signed SAS URLs (PUT for upload, GET for download). The module-level `CloudStorageAzureUserDelegationKeys` dict caches delegation keys per database.

---

## Models

### `ir.attachment` (Inherited)

**Inherited from:** `ir.attachment`

| Field | Type | Note |
|-------|------|------|
| `url` | Char | Stores `https://<account>.blob.core.windows.net/<container>/<blob>` pattern |

| Method | Returns | Note |
|--------|---------|------|
| `_get_cloud_storage_azure_info()` | dict | Parses URL: `account_name`, `container_name`, `blob_name` |
| `_generate_cloud_storage_azure_url(blob_name)` | str | Returns full blob URL |
| `_generate_cloud_storage_azure_sas_url(**kwargs)` | str | Generates SAS URL with token from UserDelegationKey |
| `_generate_cloud_storage_url()` | str | Delegates to Azure if provider == 'azure' |
| `_generate_cloud_storage_download_info()` | dict | Signed GET URL with `max-age` cache control |
| `_generate_cloud_storage_upload_info()` | dict | Signed PUT URL, `x-ms-blob-type: BlockBlob`, 201 expected response |

**URL Pattern:** `https://(?P<account_name>[a-z\d]{3,24})\.blob\.core\.windows\.net/(?P<container_name>[a-z\d][a-z\d-]{2,62})/(?P<blob_name>[^?]+)`

### `res.config.settings` (Inherited)

**Inherited from:** `res.config.settings`

| Field | Type | Note |
|-------|------|------|
| `cloud_storage_provider` | Selection | Adds `'azure'` — Azure Cloud Storage |
| `cloud_storage_azure_account_name` | Char | Config parameter |
| `cloud_storage_azure_container_name` | Char | Config parameter |
| `cloud_storage_azure_tenant_id` | Char | Azure AD tenant ID |
| `cloud_storage_azure_client_id` | Char | Azure AD client ID |
| `cloud_storage_azure_client_secret` | Char | Azure AD client secret |
| `cloud_storage_azure_invalidate_user_delegation_key` | Boolean | Invalidate cached delegation key |

| Method | Returns | Note |
|--------|---------|------|
| `_get_cloud_storage_configuration()` | dict | Returns all Azure config values |
| `_setup_cloud_storage_provider()` | — | Test-uploads and test-downloads a blob to validate credentials |
| `_check_cloud_storage_uninstallable()` | — | Prevents uninstall if any `blob.core.windows.net` attachments exist |
| `set_values()` | — | Increments `cloud_storage_azure_user_delegation_key_sequence` when invalidation flag set |

---

## Critical Notes

- **User Delegation Key Caching:** Module-level dict `CloudStorageAzureUserDelegationKeys` caches by `(db_config, key_or_exception)`. Invalidated by changing account/container/tenant/client config or by setting the `sequence` parameter.
- **SAS Token Permissions:** Upload uses `permission='c'` (create/write), download uses `permission='r'` (read).
- **Multi-container Risk:** Changing container name without migrating existing attachments risks 404 errors. Module warns via `_check_cloud_storage_uninstallable`.
- **Cache Invalidation:** `cloud_storage_azure_user_delegation_key_sequence` is incremented in `set_values` when the invalidation checkbox is ticked, forcing key regeneration.
- **`ClientAuthenticationError` Caching:** Authentication errors are cached to prevent repeated Azure AD requests on bad credentials.
