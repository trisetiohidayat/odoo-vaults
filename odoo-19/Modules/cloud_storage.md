---
type: module
module: cloud_storage
tags: [odoo, odoo19, technical, attachment, storage, cloud]
created: 2026-04-11
---

# Cloud Storage (cloud_storage)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `cloud_storage` |
| **Category** | Technical Settings |
| **License** | LGPL-3 |
| **Auto Install** | No |
| **Author** | Odoo S.A. |
| **Odoo Version** | 19.0+ |
| **New in Odoo 19** | Yes — this module does not exist in earlier Odoo versions |

## Description

The Cloud Storage module provides an abstraction layer for storing Odoo attachments in external cloud storage services instead of the local filesystem. This reduces database size, improves performance, and enables scalable attachment storage.

The module implements a provider-based architecture supporting:
- **Google Cloud Storage** (via `cloud_storage_google`)
- **Azure Blob Storage** (via `cloud_storage_azure`)

## Key Concepts

### Why Cloud Storage?

| Aspect | Local Storage | Cloud Storage |
|--------|--------------|---------------|
| Database Size | Large (attachments in DB or filestore) | Reduced |
| Scalability | Limited to server disk | Infinite (cloud provider) |
| CDN Integration | Manual setup | Native |
| Cost | Server costs only | Cloud provider fees |
| Backup | Manual | Automatic (provider) |

### Architecture Pattern

The module uses the **Strategy Pattern** with abstract methods that each provider must implement:

```
┌─────────────────────────────────────────────────────────────────┐
│                    cloud_storage Architecture                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        ir.attachment                             │
│  (Extended with 'cloud_storage' type)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ _generate_cloud_storage_url()
                              │ _generate_cloud_storage_download_info()
                              │ _generate_cloud_storage_upload_info()
                              ▼
        ┌─────────────────────┴─────────────────────┐
        │                                       │
        ▼                                       ▼
┌───────────────────┐                 ┌───────────────────┐
│cloud_storage_google│                 │cloud_storage_azure │
│                   │                 │                   │
│ - GCS bucket      │                 │ - Azure container │
│ - Service account │                 │ - SAS token       │
│ - Signed URLs     │                 │ - User delegation │
└───────────────────┘                 └───────────────────┘
```

## Module Structure

### Core Module: `cloud_storage`

The base module provides:
- Attachment type extension (`cloud_storage`)
- Abstract methods for provider implementation
- Configuration settings interface
- HTTP streaming for downloads

### Provider Modules

| Module | Provider | Credentials |
|--------|----------|-------------|
| `cloud_storage_google` | Google Cloud Storage | Service Account JSON |
| `cloud_storage_azure` | Azure Blob Storage | Tenant ID, Client ID, Secret |

### Migration Module: `cloud_storage_migration`

Handles bulk migration of attachments from local to cloud storage via cron jobs.

## Models

### ir.attachment (Extended)

The `ir.attachment` model is extended with cloud storage support.

#### New Attachment Type

```python
type = fields.Selection(
    selection_add=[('cloud_storage', 'Cloud Storage')],
    ondelete={'cloud_storage': 'set url'}
)
```

| Type | Description |
|------|-------------|
| `binary` | Stored in database or filestore |
| `url` | External URL reference |
| `cloud_storage` | Stored in configured cloud provider |

#### Key Fields

| Field | Type | Purpose |
|-------|------|---------|
| `type` | Selection | Extended with `cloud_storage` option |
| `url` | Char | Set to the cloud blob URL after upload |

#### Key Methods

```python
def _to_http_stream(self):
    """Stream attachment to HTTP response"""
    if self.type == 'cloud_storage':
        info = self._generate_cloud_storage_download_info()
        return Stream(type='url', url=info['url'])
    return super()._to_http_stream()

def _post_add_create(self, **kwargs):
    """Handle cloud storage attachment creation"""
    if kwargs.get('cloud_storage'):
        record.write({
            'raw': False,
            'type': 'cloud_storage',
            'url': record._generate_cloud_storage_url(),
        })

def _migrate_remote_to_local(self):
    """Migrate cloud storage back to binary"""
    # Downloads from cloud and stores locally
```

#### Abstract Methods (Provider Implementation Required)

```python
def _generate_cloud_storage_blob_name(self):
    """Generate unique blob name: {attachment_id}/{uuid}/{filename}"""
    return f'{self.id}/{uuid.uuid4()}/{self.name}'

def _generate_cloud_storage_url(self):
    """Generate cloud blob URL (without signature)"""
    raise NotImplementedError()

def _generate_cloud_storage_download_info(self):
    """Generate signed download URL with expiry"""
    raise NotImplementedError()

def _generate_cloud_storage_upload_info(self):
    """Generate signed upload URL with expiry"""
    raise NotImplementedError()
```

### res.config.settings (Extended)

Configuration interface for cloud storage providers.

#### Configuration Fields

```python
cloud_storage_provider = fields.Selection(
    selection=[],  # Extended by provider modules
    config_parameter='cloud_storage_provider',
)

cloud_storage_min_file_size = fields.Integer(
    config_parameter='cloud_storage_min_file_size',
    default=20_000_000,  # 20MB
    help='Minimum file size for cloud storage upload'
)
```

| Field | Description |
|-------|-------------|
| `cloud_storage_provider` | Selected cloud provider |
| `cloud_storage_min_file_size` | Files larger than this use cloud storage |

### ir.http (Extended)

Extends `SessionInfo` to expose cloud storage configuration to the web client:

```python
def session_info(self):
    info = super().session_info()
    info.update(
        cloud_storage_min_file_size=self.env['ir.config_parameter']
            .get_param('cloud_storage_min_file_size', 20_000_000),
        cloud_storage_unsupported_models=list_unsupported,
    )
    return info
```

This allows the web client to decide whether to use cloud storage for a given file upload without a round-trip to the server.

## Cross-Model Integration

### ir.attachment ↔ mail

The `mail` module is a **hard dependency** (`depends = ['base_setup', 'mail']`). The mail controller (`mail.controllers.attachment.AttachmentController`) is extended to append signed upload URLs to the JSON response.

```python
# controllers/attachment.py
class CloudAttachmentController(AttachmentController):
    @route()
    def mail_attachment_upload(self, ufile, thread_id, thread_model, **kwargs):
        is_cloud_storage = kwargs.get('cloud_storage')

        # 1. Create attachment record first (with type=binary initially)
        response = super().mail_attachment_upload(...)

        # 2. If cloud storage is active, append signed upload URL
        if is_cloud_storage:
            attachment = request.env["ir.attachment"].browse(
                response.json["data"]["attachment_id"]
            ).sudo()
            response.json["upload_info"] = attachment._generate_cloud_storage_upload_info()

        return response
```

**Flow:**
1. Client requests attachment upload from mail composer
2. Mail controller creates the `ir.attachment` record (type=`binary` initially)
3. Controller returns the record ID plus a signed upload URL from the cloud provider
4. Client PUTs the file directly to cloud storage (bypassing Odoo)
5. Client confirms upload to Odoo, which updates `type='cloud_storage'` and `url=<blob_url>`

### ir.attachment ↔ documents

The `documents.mixin` model is explicitly **excluded** from cloud storage via `_get_cloud_storage_unsupported_models()`:

```python
def _get_cloud_storage_unsupported_models(self):
    models = self.env.registry.descendants(
        ['mail.thread.main.attachment'], '_inherit', '_inherits'
    )
    if 'documents.mixin' in self.env:
        models.update(...)
    return list(models)
```

**Why excluded:**
- `mail.thread.main.attachment`: Used by business code that may access raw attachment bytes — cloud storage would break those operations
- `documents.mixin`: Documents module may process files internally (preview, OCR, conversion) and requires local access

### ir.attachment ↔ base_setup

`base_setup` is a **hard dependency**. The `res.config.settings` view lives in base_setup and is extended with the cloud storage provider selection fields.

### ir.attachment ↔ cloud_storage_migration

The migration module queries `ir.attachment` for `type='binary'` records and migrates them to `type='cloud_storage'` by downloading from filestore and uploading to the cloud provider, then updating the record.

## Google Cloud Storage Integration

### Provider Module: `cloud_storage_google`

#### Configuration

| Field | Config Parameter | Description |
|-------|-----------------|-------------|
| Bucket Name | `cloud_storage_google_bucket_name` | GCS bucket name |
| Service Account Key | `cloud_storage_google_account_info` | Full JSON service account credentials |

#### URL Pattern

```
https://storage.googleapis.com/{bucket_name}/{blob_name}
```

#### Key Implementation

```python
class IrAttachment(models.Model):
    _inherit = 'ir.attachment'
    _cloud_storage_google_url_pattern = re.compile(
        r'^https://storage\.googleapis\.com/(?P<bucket_name>[\w\-.]+)/(?P<blob_name>[^?]+)$'
    )

    def _generate_cloud_storage_google_url(self, blob_name):
        bucket_name = self.env['ir.config_parameter'].get_param(
            'cloud_storage_google_bucket_name'
        )
        return f"https://storage.googleapis.com/{bucket_name}/{quote(blob_name)}"

    def _generate_cloud_storage_google_signed_url(self, bucket_name, blob_name, **kwargs):
        return generate_signed_url_v4(
            credentials=get_cloud_storage_google_credential(self.env),
            resource=f'/{bucket_name}/{quote_blob_name}',
            **kwargs,
        )
```

#### Signed URL Generation (Pure Python)

The v4 signing implementation in `utils/cloud_storage_google_utils.py` uses `google-auth` (the lightweight credential library, NOT the full `google-cloud-storage` SDK):

```python
def generate_signed_url_v4(credentials, resource, expiration,
                            method='GET', content_md5='', content_type=''):
    # 1. Build Credential Scope: {date}/{region}/storage/googapis_v4/auth/{permission}
    # 2. Build Canonical Request:
    #    {method}\n{path}\n{query_string}\n{canonical_headers}\n{signed_headers}\n{payload_hash}
    # 3. Build String to Sign:
    #    GOOG4-RSA-SHA256\n{timestamp}\n{scope}\n{canonical_request_hash}
    # 4. Sign with credentials.sign_bytes() → HMAC-SHA256
    # 5. Assemble URL query string with all signature components
```

#### Credential Caching

```python
CloudStorageGoogleCredentials = {}  # {db_name: (account_info, credential)}

def get_cloud_storage_google_credential(env):
    """Cache parsed service account JSON + Credentials object per database."""
    cached = CloudStorageGoogleCredentials.get(env.registry.db_name)
    account_info = json.loads(
        env['ir.config_parameter'].sudo().get_param('cloud_storage_google_account_info')
    )
    if cached and cached[0] == account_info:
        return cached[1]  # (account_info, credential) tuple
    credential = service_account.Credentials.from_service_account_info(account_info)
    CloudStorageGoogleCredentials[env.registry.db_name] = (account_info, credential)
    return credential
```

Cache is invalidated automatically when the service account JSON changes (different JSON → different key → new entry).

#### Upload and Download Info

| Method | HTTP Method | Response Status | Expiry |
|--------|------------|-----------------|--------|
| `_generate_cloud_storage_download_info()` | `GET` | N/A | 300s |
| `_generate_cloud_storage_upload_info()` | `PUT` | **`200`** | 300s |

> **Note:** Google Cloud Storage returns HTTP `200 OK` on a successful PUT (there is no separate "created" status for simple uploads). This differs from Azure, which returns `201 Created`. The browser client must expect `200` from GCS.

#### Setup Validation

The module validates configuration by:
1. Attempting to upload a test blob (PUT to signed URL with empty body)
2. Attempting to download the test blob (GET signed URL)
3. Configuring CORS for direct browser access (requires bucket-level CORS JSON configuration in GCP console)

```python
def _setup_cloud_storage_provider(self):
    # Check bucket access
    upload_url = IrAttachment._generate_cloud_storage_google_signed_url(
        bucket_name, blob_name, method='PUT', expiration=300
    )
    upload_response = requests.put(upload_url, data=b'', timeout=5)
    # Validate response status 200
    # Configure CORS: [{'origin': ['*'], 'method': ['GET', 'PUT'], ...}]
```

## Azure Blob Storage Integration

### Provider Module: `cloud_storage_azure`

#### Configuration

| Field | Config Parameter | Description |
|-------|-----------------|-------------|
| Account Name | `cloud_storage_azure_account_name` | Azure storage account |
| Container Name | `cloud_storage_azure_container_name` | Blob container |
| Tenant ID | `cloud_storage_azure_tenant_id` | Azure AD tenant |
| Client ID | `cloud_storage_azure_client_id` | App registration |
| Client Secret | `cloud_storage_azure_client_secret` | App secret |

#### URL Pattern

```
https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}
```

#### Key Implementation

```python
class IrAttachment(models.Model):
    _inherit = 'ir.attachment'
    _cloud_storage_azure_url_pattern = re.compile(
        r'^https://(?P<account_name>[a-z\d]{3,24})\.blob\.core\.windows\.net/(?P<container_name>[a-z\d][a-z\d-]{2,62})/(?P<blob_name>[^?]+)$'
    )

    def _generate_cloud_storage_azure_sas_url(self, **kwargs):
        token = generate_blob_sas(
            user_delegation_key=get_cloud_storage_azure_user_delegation_key(self.env),
            **kwargs
        )
        return f"{self._generate_cloud_storage_azure_url(kwargs['blob_name'])}?{token}"
```

#### User Delegation Key Caching

Azure uses OAuth2 client credentials flow to obtain a User Delegation Key, which is then used to sign SAS tokens. The key is cached for performance:

```python
CloudStorageAzureUserDelegationKeys = {}  # {db_name: (config_hash, key_or_exception)}

def get_cloud_storage_azure_user_delegation_key(env):
    """Fetch + cache User Delegation Key. Key valid 7 days, refreshed 6 days in."""
    # 1. OAuth2 client credentials → access token
    # 2. GET https://blob.core.windows.net/{account}?restype=service&comp=userdelegationkey
    # 3. Parse UserDelegationKey with signed-expiry, signed-service, signed-resource
    # 4. Cache (config_hash, key) keyed by db_name
    # 5. Refresh when: (a) 6 days elapsed, or (b) cached exception + config changed
    # 6. On ClientAuthenticationError: cache the exception to prevent retry loops
```

- **Key validity:** 7 days
- **Refresh trigger:** 6 days elapsed (1-day overlap before expiry)
- **Auth failure caching:** If Azure returns 403/401, the exception is cached so Odoo does not repeatedly call Azure with bad credentials

#### SAS Token Generation (Pure Python)

`utils/cloud_storage_azure_utils.py` implements full SAS v4 signing without the `azure-storage-blob` SDK:

```python
def generate_blob_sas(account_name, container_name, blob_name,
                      user_delegation_key, permission='r', expiry=None):
    # 1. Build string-to-sign: {account}\n{permissions}\n{start}\n{expiry}\n{canonicalized_resource}
    # 2. Sign with HMAC-SHA256 using UserDelegationKey.value
    # 3. Base64 encode signature
    # 4. Build query string: sv, sr, sp, sig, st, se (URL-encoded)
```

#### Upload and Download Info

| Method | HTTP Method | Response Status | Expiry |
|--------|------------|-----------------|--------|
| `_generate_cloud_storage_download_info()` | `GET` | N/A | 300s |
| `_generate_cloud_storage_upload_info()` | `PUT` | `201` | 300s |

The upload info also sets `x-ms-blob-type: BlockBlob` header via the SAS token, which tells Azure to create a block blob. Azure requires `201 Created` response for a successful upload.

#### Setup Validation

```python
def _setup_cloud_storage_provider(self):
    # Check blob create permission
    upload_expiry = datetime.now(timezone.utc) + timedelta(seconds=300)
    upload_url = self.env['ir.attachment']._generate_cloud_storage_azure_sas_url(
        **blob_info, permission='c', expiry=upload_expiry
    )
    upload_response = requests.put(upload_url, data=b'', headers={
        'x-ms-blob-type': 'BlockBlob',
        'Content-Type': 'application/octet-stream',
    })
    # Validate response status 201
    # Check blob read permission similarly
```

## Direct Upload vs Proxying

### Upload Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DIRECT UPLOAD FLOW                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────┐                    ┌──────────────┐                    ┌─────────────┐
│  Client │                    │  Odoo Server │                    │ Cloud Storage│
└────┬────┘                    └──────┬───────┘                    └──────┬──────┘
     │                               │                                   │
     │  1. Request upload URL        │                                   │
     │──────────────────────────────>│                                   │
     │                               │                                   │
     │  2. Generate signed URL        │                                   │
     │<──────────────────────────────│                                   │
     │                               │                                   │
     │  3. PUT file directly          │                                   │
     │────────────────────────────────────────────────────────────────>│
     │                               │                                   │
     │  4. 200/201 OK                │                                   │
     │<─────────────────────────────────────────────────────────────────│
     │                               │                                   │
     │  5. Confirm upload            │                                   │
     │──────────────────────────────>│                                   │
     │                               │  6. Create/update attachment record │
     │                               │  (type='cloud_storage', url=...)   │
     │                               │                                   │
```

### Benefits

| Aspect | Direct Upload | Proxy Through Odoo |
|--------|--------------|-------------------|
| Server Load | Minimal | High (streams entire file) |
| Memory Usage | Client memory | Server memory |
| Speed | Fast (no intermediary) | Slow |
| Timeout Risk | Low | High for large files |

## URL Signing & Security

### Signed URLs

Cloud storage URLs are signed with:
- Expiration time
- Permissions (read/write)
- Request method restrictions

### Signature Parameters

| Provider | Method | Expiry |
|----------|--------|--------|
| Google | v4 HMAC-SHA256 Signing | 300 seconds |
| Azure | SAS Token v4 HMAC-SHA256 | 300 seconds |

### Security Analysis

#### Threat Model

| Threat | Mitigation |
|--------|------------|
| Signed URL replayed by unauthorized user | 5-minute expiry limits window |
| Signed URL scraped from logs | Signed URLs should not be logged; use `X-Goog-Signature` for Google v4 |
| Blob overwritten by attacker | URL is scoped to exact blob name; cannot enumerate other blobs |
| Malicious file uploaded | Odoo validates content-type after upload; bucket is private (no public ACL) |
| Credentials stolen from Odoo config | Service account / app registration has only Storage Object Admin permission |
| Credential abuse if Odoo is compromised | Credentials allow blob operations only on the specific bucket/container |

#### Access Control Layers

1. **Storage-level:** Cloud provider IAM role (`Storage Object Admin`) grants only blob read/write/delete — no bucket listing or ACL management
2. **URL-level:** Signed URLs encode exact permissions (`r` or `c`), blob name, and expiry
3. **Network-level (recommended):** Restrict bucket/container access to specific IP ranges via provider firewall rules
4. **Browser-level:** CORS configured to allow only the Odoo origin domain

#### CORS Configuration

Both providers require CORS configuration to allow direct browser uploads:

**Google Cloud Storage CORS JSON** (set via `gsutil cors set cors.json gs://bucket`):
```json
[{
  "origin": ["https://your-odoo-domain.com"],
  "method": ["GET", "PUT", "HEAD"],
  "responseHeader": ["Content-Type", "Content-MD5", "x-goog-content-length-range"],
  "maxAgeSeconds": 3600
}]
```

**Azure Blob Storage CORS** (set via Azure Portal or REST API):
```
Allowed Origins: https://your-odoo-domain.com
Allowed Methods: GET, PUT, HEAD
Allowed Headers: x-ms-blob-type, content-type, content-length
Max Age: 3600
```

#### Security Considerations

1. **Short Expiry:** URLs expire in 5 minutes — replay window is minimal
2. **IP Restrictions:** Can be added at provider level (firewall/VPC/service account conditions)
3. **HTTPS Only:** All URLs use HTTPS; providers enforce this
4. **Cache Control:** Download URLs include `Cache-Control: private, max-age=300` (Azure) to prevent long-term caching of sensitive attachments
5. **Private Buckets:** Both providers use private ACLs — no public access without a valid signed URL
6. **No Directory Listing:** Provider buckets/containers have no listing permission granted — only exact blob names are accessible via signed URLs

### Credential Storage

| Provider | Credential Type | Stored In |
|----------|---------------|-----------|
| Google | Service Account JSON | `ir.config_parameter` (`cloud_storage_google_account_info`) |
| Azure | Client Secret | `ir.config_parameter` (`cloud_storage_azure_client_secret`) |

Both are stored as plain text in the Odoo database `ir_config` table. Protect with database access controls and consider using a secrets manager (e.g., Vault) if compliance requires it.

## Attachment Type Selection

### Automatic Selection

Files are stored in cloud storage when:
1. Provider is configured (non-empty `cloud_storage_provider`)
2. File size >= `cloud_storage_min_file_size` (default 20 MB)
3. Model is not in unsupported list

```python
# Decision made in web client using session_info() values
if attachment_size >= cloud_storage_min_file_size:
    if model not in cloud_storage_unsupported_models:
        # Use cloud storage upload
```

### Unsupported Models

Some models should NOT use cloud storage:

```python
def _get_cloud_storage_unsupported_models(self):
    models = self.env.registry.descendants(
        ['mail.thread.main.attachment'], '_inherit', '_inherits'
    )
    if 'documents.mixin' in self.env:
        models.update(...)
    return list(models)
```

**Why excluded:**
- `mail.thread.main.attachment`: Business code may access attachment data as bytes; cloud storage would break those operations
- `documents.mixin`: Documents may be processed internally (preview, OCR, conversion) and requires local file access

## Migration Module

### Module: `cloud_storage_migration`

Handles bulk migration from local filestore to cloud storage.

#### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cloud_storage_min_file_size` | 20MB | Minimum file size |
| `cloud_storage_migration_max_file_size` | 1GB | Maximum file size |
| `cloud_storage_migration_max_batch_file_size` | 10GB | Batch limit |
| `cloud_storage_migration_message_models` | — | Models to migrate |
| `cloud_storage_migration_all_models` | — | Migrate all models |
| `cloud_storage_migration_min_attachment_id` | — | Resume checkpoint |

#### Cron Job

```python
def _cron_migrate_local_to_cloud_storage(self):
    """Migrate attachments via cron"""
    # 1. Query binary attachments not yet migrated
    # 2. Download file from filestore
    # 3. Upload to cloud storage
    # 4. Update attachment to cloud_storage type
    # 5. Commit checkpoint to resume if interrupted
```

#### Migration Process

1. **Identify:** Find binary attachments matching criteria
2. **Download:** Read file from local filestore
3. **Upload:** POST to cloud storage via signed URL
4. **Update:** Change type to `cloud_storage`, set URL, clear binary
5. **Checkpoint:** Save `cloud_storage_migration_min_attachment_id` for resumability

#### Configuration Example

```
cloud_storage_migration_message_models = mail.thread,mail.message
cloud_storage_migration_min_file_size = 10000000  # 10MB
cloud_storage_migration_max_batch_file_size = 5000000000  # 5GB
```

## Controller: Attachment

### Route Extension

The module extends `mail.controllers.attachment.AttachmentController`:

```python
class CloudAttachmentController(AttachmentController):
    @route()
    def mail_attachment_upload(self, ufile, thread_id, thread_model, **kwargs):
        is_cloud_storage = kwargs.get('cloud_storage')

        # Create attachment record first
        response = super().mail_attachment_upload(...)

        if is_cloud_storage:
            # Append upload info to response
            attachment = request.env["ir.attachment"].browse(
                response.json["data"]["attachment_id"]
            ).sudo()
            response.json["upload_info"] = attachment._generate_cloud_storage_upload_info()

        return response
```

**Critical ordering:** The attachment record is created BEFORE the signed upload URL is returned. This ensures the attachment has a valid ID (used in the blob name: `{id}/{uuid}/{name}`) and an `id` before any cloud operation begins.

## CDN Integration

### How CDN Works with Cloud Storage

```
┌─────────────────────────────────────────────────────────────────┐
│                    CDN INTEGRATION                               │
└─────────────────────────────────────────────────────────────────┘

Client ──────────────────────────────────────────────────────────────►
    │                                                             │
    │  1. Request attachment (CDN URL)                            │
    │                                                             │
    ├─────────────────────────────────────────────────────────────► CDN Edge
    │                                                             │
    │  Cache HIT?                                                 │
    │                                                             │
    ├──── Yes ──────────────────────────────────────────────────► │
    │       Return cached file                                    │
    │                                                             │
    ├──── No ───────────────────────────────────────────────────► │
    │       Fetch from Cloud Storage (origin)                     │
    │       Cache at edge                                         │
    │       Return file                                           │
```

### CDN URL Configuration

Set CDN base URL in provider configuration:
- Google Cloud Storage: Use Cloud CDN with backend bucket
- Azure Blob Storage: Use Azure CDN with storage account as origin

The signed download URL can be replaced with a CDN URL if a CDN is configured, since CDN URLs are typically long-lived (or invalidated on demand).

### Cache Headers

```python
# Azure example
cache_control='private, max-age=300'  # 5 minutes browser cache
```

## Performance Considerations

### Direct Upload Benefits

| Metric | Direct to Cloud | Through Odoo |
|--------|---------------|--------------|
| Peak server bandwidth | None during upload | O(attachment size) |
| Server CPU | None during upload | For streaming large files |
| Upload parallelism | Browser → cloud directly | Serial: browser → Odoo → cloud |
| Concurrent large uploads | No Odoo bottleneck | Odoo becomes bottleneck |

### Download Path

When a user views an attachment, the request goes through Odoo's `_to_http_stream()`:

```python
def _to_http_stream(self):
    if self.type == 'cloud_storage':
        info = self._generate_cloud_storage_download_info()
        return Stream(type='url', url=info['url'])  # Redirect to signed cloud URL
    return super()._to_http_stream()
```

The download uses a **stream redirect** — Odoo generates a signed URL and returns it to the browser, which then fetches directly from the cloud. Odoo is not in the data path for downloads either.

### Signed URL Caching

Credentials are cached per database:
- Google: `CloudStorageGoogleCredentials` dict (invalidated on JSON change)
- Azure: `CloudStorageAzureUserDelegationKeys` dict (7-day key lifetime, refreshed 6 days in)

Generating a signed URL requires an HMAC-SHA256 operation but no network call (credentials are cached in-memory). This makes URL generation fast (~microseconds) even under high load.

### Memory Efficiency

The migration module streams files rather than loading them entirely into memory:

```python
# Download from filestore in chunks
with open(full_path, 'rb') as f:
    while chunk := f.read(64 * 1024):
        upload_file.write(chunk)
```

## Override Pattern: Adding a New Provider

To add a new cloud storage provider (e.g., `cloud_storage_s3`), follow this pattern:

### 1. Module Structure

```
cloud_storage_s3/
├── __manifest__.py          # depends: cloud_storage
├── models/
│   └── ir_attachment.py     # Implement abstract methods
└── utils/
    └── cloud_storage_s3_utils.py  # Pure Python signing logic
```

### 2. __manifest__.py

```python
{
    'name': 'Cloud Storage Amazon S3',
    'version': '1.0',
    'category': 'Technical Settings',
    'depends': ['cloud_storage'],
    'data': [],
    'license': 'LGPL-3',
}
```

### 3. ir.attachment Extension

```python
from odoo.addons.cloud_storage.models.ir_attachment import AbstractCloudStorageProvider

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _setup_cloud_storage_provider(self):
        """Register S3 as a provider option."""
        super()._setup_cloud_storage_provider()
        # Append 's3' to cloud_storage_provider selection
        # (handled via _inherit on res.config.settings)

    def _generate_cloud_storage_url(self):
        self.ensure_one()
        if self.env['ir.config_parameter'].get_param('cloud_storage_provider') == 's3':
            return self._generate_cloud_storage_s3_url(self._generate_cloud_storage_blob_name())
        return super()._generate_cloud_storage_url()

    def _generate_cloud_storage_download_info(self):
        self.ensure_one()
        provider = self.env['ir.config_parameter'].get_param('cloud_storage_provider')
        if provider == 's3':
            return {
                'url': generate_presigned_url(...),
                'method': 'GET',
                'expiration': self._cloud_storage_download_url_time_to_expiry,
            }
        return super()._generate_cloud_storage_download_info()

    def _generate_cloud_storage_upload_info(self):
        self.ensure_one()
        provider = self.env['ir.config_parameter'].get_param('cloud_storage_provider')
        if provider == 's3':
            return {
                'url': generate_presigned_post_url(...),
                'method': 'PUT',
                'response_status': 200,
                'expiration': self._cloud_storage_upload_url_time_to_expiry,
            }
        return super()._generate_cloud_storage_upload_info()
```

### 4. Provider Guard Pattern

Each provider method should begin with a guard check:

```python
def _generate_cloud_storage_url(self):
    self.ensure_one()
    if self.env['ir.config_parameter'].get_param('cloud_storage_provider') != 's3':
        return super()._generate_cloud_storage_url()  # defer to next provider
    # S3-specific implementation...
```

This allows multiple provider modules to coexist — the first matching provider handles the request.

### 5. Required Abstract Methods to Implement

| Method | Must Return |
|--------|-------------|
| `_generate_cloud_storage_url()` | Unsigned blob URL (used as record value) |
| `_generate_cloud_storage_download_info()` | `{'url': str, 'method': 'GET', 'expiration': int}` |
| `_generate_cloud_storage_upload_info()` | `{'url': str, 'method': str, 'response_status': int, 'expiration': int}` |

### 6. res.config.settings Extension

Add S3 configuration fields to `res.config.settings`:

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cloud_storage_provider = fields.Selection(
        selection_add=[('s3', 'Amazon S3')],  # Append to existing options
        ondelete={'s3': 'set default'},
    )
    cloud_storage_s3_bucket_name = fields.Char(
        config_parameter='cloud_storage_s3_bucket_name',
    )
    cloud_storage_s3_access_key = fields.Char(
        config_parameter='cloud_storage_s3_access_key',
    )
    cloud_storage_s3_secret_key = fields.Char(
        config_parameter='cloud_storage_s3_secret_key',
    )
```

## Version Change: Odoo 18 to Odoo 19

### New Module

`cloud_storage` is **new in Odoo 19**. It does not exist in Odoo 18 or earlier versions.

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| cloud_storage module | Does not exist | New module |
| Attachment types | `binary`, `url` | `binary`, `url`, `cloud_storage` |
| External storage | Manual (custom code) | Native module |

### No Upgrade Path from Odoo 18

There is no standard migration path from Odoo 18 custom cloud storage implementations. The `cloud_storage_migration` module can migrate existing local attachments (type=`binary`) to cloud storage within Odoo 19, but Odoo 18 custom implementations would need custom migration scripts.

## Multi-Company Considerations

### Per-Company Configuration

Currently, cloud storage is configured **globally per Odoo instance**:

| Setting | Scope |
|---------|-------|
| Provider | Global |
| Credentials | Global |
| Bucket/Container | Global |

There is no per-company cloud storage configuration in Odoo 19.

### Best Practices

1. **Separate Buckets:** Use different buckets per environment (prod/staging/dev)
2. **Naming Convention:** Include environment or company identifier in blob names if per-company isolation is required
3. **Access Control:** Use IAM roles for fine-grained permissions
4. **Multi-company:** If per-company isolation is required, implement `company_id` filtering in the blob name generation and configure separate buckets per company in the cloud provider

## Limitations

### Current Limitations

| Limitation | Description |
|------------|-------------|
| No Per-Attachment Provider | All attachments use the same provider |
| No CDN Config | No native CDN URL setting in Odoo; handled externally |
| No Encryption at Rest | Relies on provider encryption; no Odoo-managed customer keys |
| No Versioning | Blobs are overwritten on re-upload; no version history |
| No Per-Company Storage | Global configuration only |
| No Cloud-to-Cloud Copy | Migration module downloads to Odoo server before uploading |

### Provider-Specific Limits

| Provider | Limit |
|----------|-------|
| Google Cloud Storage | 5 TB max blob size |
| Azure Blob Storage | 4.75 TB max blob size |

## Related Documentation

- [Modules/base_setup](modules/base_setup.md) - Base configuration
- [Modules/mail](modules/mail.md) - Mail attachments
- [Modules/documents](modules/documents.md) - Document management
- [Modules/cloud_storage_google](modules/cloud_storage_google.md) - Google Cloud Storage provider
- [Modules/cloud_storage_azure](modules/cloud_storage_azure.md) - Azure Blob Storage provider
- [Modules/cloud_storage_migration](modules/cloud_storage_migration.md) - Migration module

## Appendix: Configuration Checklist

### Google Cloud Storage

- [ ] Create GCS bucket with uniform access control
- [ ] Create service account with Storage Object Admin role
- [ ] Download JSON key file
- [ ] Configure bucket CORS for web client access
- [ ] Enter bucket name and upload key in Odoo settings

### Azure Blob Storage

- [ ] Create Azure Blob Storage account
- [ ] Create container with private access
- [ ] Register app in Azure AD
- [ ] Grant Storage Blob Data Contributor role
- [ ] Enter account name, container name, and app credentials in Odoo

## Appendix: Migration Commands

### Manual Migration

```bash
# Trigger migration cron manually
./odoo-bin shell -c odoo.conf -d db_name << EOF
env['ir.attachment']._cron_migrate_local_to_cloud_storage()
EOF
```

### Verify Migration

```sql
-- Check migration progress
SELECT
    COUNT(*) FILTER (WHERE type = 'binary') as local,
    COUNT(*) FILTER (WHERE type = 'cloud_storage') as cloud,
    COUNT(*) FILTER (WHERE type = 'url') as url
FROM ir_attachment;
```

### Rollback Migration

```python
# Migrate back to local (one attachment at a time)
attachment = env['ir.attachment'].browse(attachment_id)
attachment._migrate_remote_to_local()
```
