---
Module: cloud_storage_google
Version: 18.0.0
Type: addon
Tags: #odoo18 #google #cloud #storage #attachment
---

## Overview

Stores `ir.attachment` files in Google Cloud Storage instead of the local database filesystem. Uses Google service account credentials with V4 signed URLs for direct browser-to-GCS upload/download.

**Depends:** `cloud_storage`

**Key Behavior:** All uploads/downloads go through GCS via signed URLs. Service account JSON key is stored (base64) and decoded at runtime to generate V4 signed URLs. CORS is automatically configured on the bucket on setup.

---

## Models

### `ir.attachment` (Inherited)

**Inherited from:** `ir.attachment`

| Method | Returns | Note |
|--------|---------|------|
| `_get_cloud_storage_google_info()` | dict | Parses URL: `bucket_name`, `blob_name` |
| `_generate_cloud_storage_google_url(blob_name)` | str | Returns `https://storage.googleapis.com/<bucket>/<blob>` |
| `_generate_cloud_storage_google_signed_url(...)` | str | Calls `generate_signed_url_v4` utility with GCS credentials |
| `_generate_cloud_storage_url()` | str | Delegates to GCS if provider == 'google' |
| `_generate_cloud_storage_download_info()` | dict | Signed GET URL for download |
| `_generate_cloud_storage_upload_info()` | dict | Signed PUT URL for upload |

**URL Pattern:** `https://storage\.googleapis\.com/(?P<bucket_name>[\w\-.]+)/(?P<blob_name>[^?]+)`

### `res.config.settings` (Inherited)

**Inherited from:** `res.config.settings`

| Field | Type | Note |
|-------|------|------|
| `cloud_storage_provider` | Selection | Adds `'google'` — Google Cloud Storage |
| `cloud_storage_google_bucket_name` | Char | GCS bucket name |
| `cloud_storage_google_service_account_key` | Binary | JSON key file (store=False) |
| `cloud_storage_google_account_info` | Char | Decoded JSON key content (config parameter) |

| Method | Returns | Note |
|--------|---------|------|
| `get_values()` | dict | Encodes `account_info` to base64 for UI display |
| `_compute_cloud_storage_google_account_info()` | — | Decodes binary to JSON string |
| `_setup_cloud_storage_provider()` | — | Tests PUT/GET permissions; auto-configures CORS on bucket |
| `_get_cloud_storage_configuration()` | dict | Returns bucket name and account info |
| `_check_cloud_storage_uninstallable()` | — | Prevents uninstall if any `storage.googleapis.com` attachments exist |

---

## Critical Notes

- **Credentials Caching:** Module-level `CloudStorageGoogleCredentials` dict caches by `(account_info, credential)`. Invalidated when the stored service account JSON changes.
- **CORS Auto-Configuration:** On `_setup_cloud_storage_provider`, PATCHes the bucket's CORS settings to allow `GET` and `PUT` from any origin with `Content-Type` header. This is required for direct browser uploads.
- **V4 Signed URLs:** Use `generate_signed_url_v4` from `cloud_storage_google_utils`. Expiration times come from `ir.attachment._cloud_storage_download_url_time_to_expiry` and `_upload_url_time_to_expiry`.
- **Service Account Scopes:** Credentials are created with default scopes. On setup, explicitly request `devstorage.full_control` scope for CORS PATCH call.
- **Uninstall Protection:** `_check_cloud_storage_uninstallable` checks for any attachments with `type='cloud_storage'` and GCS URL pattern before allowing uninstall.
