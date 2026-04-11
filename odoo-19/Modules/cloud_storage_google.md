---
type: module
module: cloud_storage_google
tags: [odoo, odoo19, technical, attachment, storage, google]
created: 2026-04-06
---

# Cloud Storage Google

## Overview
| Property | Value |
|----------|-------|
| **Name** | Cloud Storage Google |
| **Technical** | `cloud_storage_google` |
| **Category** | Technical Settings |
| **Depends** | `cloud_storage` |
| **License** | LGPL-3 |
| **External Dependencies** | `google-auth` (Python + apt) |

## Description
Extends `cloud_storage` to use Google Cloud Storage (GCS) as the attachment storage backend. Uses GCP service account credentials to generate v4 signed URLs for secure direct browser-to-storage upload and download.

## Key Models

### `ir.attachment` (Extended)
Implements the abstract cloud storage methods for Google Cloud Storage.

**URL Pattern:**
```
https://storage.googleapis.com/{bucket_name}/{blob_name}
```

**Key Methods:**
| Method | Purpose |
|--------|---------|
| `_get_cloud_storage_google_info()` | Parses GCS URL to extract `bucket_name`, `blob_name` |
| `_generate_cloud_storage_google_url(blob_name)` | Builds base GCS URL |
| `_generate_cloud_storage_google_signed_url(...)` | Generates v4 signed URL using service account credentials |
| `_generate_cloud_storage_url()` | Returns GCS blob URL (only when provider = google) |
| `_generate_cloud_storage_download_info()` | Returns signed GET URL (300s expiry) |
| `_generate_cloud_storage_upload_info()` | Returns signed PUT URL (300s expiry, expects `200`) |

### Service Account Credential Caching
Uses `google.oauth2.service_account.Credentials.from_service_account_info()`. The credential object is cached per database to avoid slow repeated credential parsing. Cache is invalidated when the service account JSON changes.

## Configuration (ir.config_parameter)
| Key | Purpose |
|-----|---------|
| `cloud_storage_google_account_info` | Service account JSON (full JSON blob) |
| `cloud_storage_google_bucket_name` | GCS bucket name |

## Technical Notes
- Requires a Google Cloud project with Cloud Storage API enabled.
- Service account needs `Storage Object Admin` role on the bucket.
- Uses HMAC-SHA256 signed URLs (v4) for authentication.
