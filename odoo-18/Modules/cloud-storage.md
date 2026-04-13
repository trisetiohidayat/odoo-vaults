---
Module: cloud_storage
Version: Odoo 18
Type: Integration
Tags: #cloud #attachments #storage #S3 #Azure #GCS
---

# Cloud Storage (`cloud_storage`)

> **Note:** This module is a framework — it provides the attachment integration hooks and UI scaffolding. Actual provider implementations (AWS S3, Azure Blob, Google Cloud Storage) must be provided by an Odoo Apps or custom extension module that inherits `cloud.storage.provider` and implements the abstract methods below.

**Module Path:** `~/odoo/odoo18/odoo/addons/cloud_storage/`

**Depends:** `mail`

**Manifest Version:** `1.0`

**License:** LGPL-3

## Overview

The `cloud_storage` module enables Odoo to store file attachments in external cloud object storage instead of the local filesystem/database. It intercepts the standard `ir.attachment` lifecycle and routes large files to cloud providers via signed URLs, keeping only a URL reference in the Odoo database.

### Architecture

```
Odoo Client (Browser)
        │
        ▼
mail_attachment_upload controller
  ── POST attachment metadata to Odoo
  ── receive upload_info (cloud signed URL)
  ── upload file directly to cloud storage (AWS S3 / Azure / GCS)
        │
        ▼
Cloud Storage (S3 / Azure Blob / GCS)
  ── stores raw binary file
  ── returns signed URL
        │
        ▼
ir.attachment record
  type = 'cloud_storage'
  url = '<provider://bucket/blob-name>'
  raw = False  (no local binary)
```

### Key Design Points

- **Dual-phase upload:** The client first creates a placeholder `ir.attachment` record in Odoo, then uploads the raw file directly to the cloud via a pre-signed URL (no proxying through Odoo).
- **On-demand download:** When the attachment is accessed, Odoo generates a fresh signed download URL and redirects the client directly to the cloud.
- **Provider-agnostic:** The `ir.attachment` model defines abstract methods (`_generate_cloud_storage_url`, `_generate_cloud_storage_download_info`, `_generate_cloud_storage_upload_info`) that each provider implements. The base module does not hardcode any provider.
- **Default minimum file size:** `20,000,000 bytes` (20 MB). Files below this threshold are stored locally unless cloud storage is forced. Configurable via `cloud_storage_min_file_size` system parameter.

---

## Model: `ir.attachment` — Extended

**File:** `~/odoo/odoo18/odoo/addons/cloud_storage/models/ir_attachment.py`

Inherits from `ir.attachment` (base). Adds cloud storage type and signed URL methods.

### Fields Added

| Field | Type | Selection | Description |
|-------|------|-----------|-------------|
| `type` | `Selection` | `'cloud_storage'` added | Attachment storage type. `ondelete='set url'` means if the cloud storage type is deleted, the type falls back to `'url'` (placeholder without binary). |

### Key Methods

#### `_post_add_create(**kwargs)`

```python
def _post_add_create(self, **kwargs):
    super()._post_add_create(**kwargs)
    if kwargs.get('cloud_storage'):
        if not self.env['ir.config_parameter'].sudo().get_param('cloud_storage_provider'):
            raise UserError(_('Cloud Storage is not enabled'))
        for record in self:
            record.write({
                'raw': False,
                'type': 'cloud_storage',
                'url': record._generate_cloud_storage_url(),
            })
```

Called after a new attachment is created. If `cloud_storage=True` was passed (set by the frontend), the attachment is converted to cloud storage type. Raises `UserError` if no provider is configured. Sets `raw=False` (binary not stored in DB) and stores the cloud blob URL.

#### `_generate_cloud_storage_blob_name()`

```python
def _generate_cloud_storage_blob_name(self):
    return f'{self.id}/{uuid.uuid4()}/{self.name}'
```

Generates a unique blob path within the bucket: `{attachment_id}/{uuid}/{original_filename}`. The UUID ensures uniqueness even if the same filename is uploaded multiple times.

#### `_generate_cloud_storage_url()`

```python
def _generate_cloud_storage_url(self):
    raise NotImplementedError()
```

Abstract method. Returns a cloud-blob URL (without signature/token) used as a stable identifier for the blob. Must be implemented by each provider. Example for S3: `https://bucket.s3.region.amazonaws.com/{id}/{uuid}/{name}`.

#### `_generate_cloud_storage_download_info()`

```python
def _generate_cloud_storage_download_info(self):
    raise NotImplementedError()
```

Abstract method. Returns a dictionary:
- `url` — cloud storage URL with authentication token/signature
- `time_to_expiry` — seconds until the signed URL expires

The client caches the redirect until 10 seconds before expiry.

#### `_generate_cloud_storage_upload_info()`

```python
def _generate_cloud_storage_upload_info(self):
    raise NotImplementedError()
```

Abstract method. Returns a dictionary:
- `upload_url` — cloud storage pre-signed upload URL
- `method` — HTTP method for upload (e.g., `'PUT'`)
- `response_status` — expected HTTP status for a successful upload
- `headers` — optional dict of headers to include in the upload request

#### `_to_http_stream()`

```python
def _to_http_stream(self):
    if (self.type == 'cloud_storage' and
          self.env['res.config.settings']._get_cloud_storage_configuration()):
        self.ensure_one()
        info = self._generate_cloud_storage_download_info()
        stream = Stream(type='url', url=info['url'])
        if 'time_to_expiry' in info:
            stream.max_age = max(info['time_to_expiry'] - 10, 0)
        return stream
    return super()._to_http_stream()
```

Overridden to intercept streaming requests for cloud attachments. Instead of reading local binary, generates a signed download URL and returns an HTTP redirect (`Stream(type='url')`). The `max_age` is set to expire 10 seconds before the signed URL expires to prevent stale URL errors.

#### `_get_cloud_storage_unsupported_models()`

```python
def _get_cloud_storage_unsupported_models(self):
    return list(self.env.registry.descendants(
        ['mail.thread.main.attachment'], '_inherit', '_inherits'))
```

Returns a list of model names whose attachments must never be stored in the cloud. These are models that read attachment binary data in business logic (e.g., `mail.thread.main.attachment`). Cloud-hosted binary would break that code. This list is sent to the client via `session_info`.

### L4 Notes — How Signed URLs Work

Cloud storage providers use pre-signed URLs as temporary, time-limited access tokens:

1. **Upload:** Odoo's controller returns a pre-signed `PUT` URL to the client. The client uploads directly to the cloud bucket — the file never passes through Odoo's WSGI server.
2. **Download:** When serving an attachment, Odoo generates a pre-signed `GET` URL and returns it as a redirect. The browser downloads directly from the cloud.

**Expiry times** (class-level constants):
- Upload URL TTL: 300 seconds (5 minutes)
- Download URL TTL: 300 seconds (5 minutes)

This is a security design: even if a signed URL is intercepted, it becomes invalid after 5 minutes.

---

## Model: `res.config.settings` — Extended

**File:** `~/odoo/odoo18/odoo/addons/cloud_storage/models/res_config_settings.py`

**Inherits:** `res.config.settings` (base settings wizard)

### Fields Added

| Field | Type | Config Parameter | Description |
|-------|------|---------|-------------|
| `cloud_storage_provider` | `Selection` | `cloud_storage_provider` | Selection of cloud provider. Set to `[]` by default; actual provider options are added by the implementing module. |
| `cloud_storage_min_file_size` | `Integer` | `cloud_storage_min_file_size` | Minimum file size in bytes for cloud storage to be used. Default: `20_000_000` (20 MB). |

### Key Methods

#### `_get_cloud_storage_configuration()`

```python
def _get_cloud_storage_configuration(self):
    return {}
```

Abstract hook. Returns the provider configuration dict (credentials, bucket name, region, etc.). Returns empty dict if not fully configured. Override in provider module.

#### `_setup_cloud_storage_provider()`

```python
def _setup_cloud_storage_provider(self):
    pass
```

Called after saving settings if provider configuration is valid. Can be used to validate credentials, create buckets, etc. Stub in base; implement in provider module.

#### `_check_cloud_storage_uninstallable()`

```python
def _check_cloud_storage_uninstallable(self):
    pass
```

Called before changing providers. Raises `UserError` if any existing attachments rely on the current provider, blocking the change until those attachments are migrated.

#### `set_values()`

```python
def set_values(self):
    ICP = self.env['ir.config_parameter']
    cloud_storage_configuration_before = ICP.get_param('cloud_storage_provider')
    if cloud_storage_provider_before and self.cloud_storage_provider != cloud_storage_provider_before:
        self._check_cloud_storage_uninstallable()
    super().set_values()
    cloud_storage_configuration = self._get_cloud_storage_configuration()
    if not cloud_storage_configuration and self.cloud_storage_provider:
        raise UserError(_('Please configure the Cloud Storage before enabling it'))
    if cloud_storage_configuration and cloud_storage_configuration != cloud_storage_configuration_before:
        self._setup_cloud_storage_provider()
```

Flow:
1. If the provider is being changed, check if any attachments use the old provider.
2. Save values via `super()`.
3. Validate that the new provider is fully configured before allowing it to be set.
4. If configuration changed and is valid, run provider setup.

---

## Model: `ir.http` — Extended

**File:** `~/odoo/odoo18/odoo/addons/cloud_storage/models/ir_http.py`

**Inherits:** `ir.http` (abstract base for HTTP routing)

### Key Methods

#### `session_info()`

```python
def session_info(self):
    res = super().session_info()
    ICP = self.env['ir.config_parameter'].sudo()
    if ICP.get_param('cloud_storage_provider'):
        res['cloud_storage_min_file_size'] = ICP.get_param(
            'cloud_storage_min_file_size', DEFAULT_CLOUD_STORAGE_MIN_FILE_SIZE)
        res['cloud_storage_unsupported_models'] = \
            self.env['ir.attachment']._get_cloud_storage_unsupported_models()
    return res
```

Extends the web session info sent to the client. If a cloud provider is configured, includes:
- `cloud_storage_min_file_size` — minimum size threshold for cloud uploads
- `cloud_storage_unsupported_models` — list of model names whose attachments must not use cloud storage

---

## Controller: `mail_attachment_upload`

**File:** `~/odoo/odoo18/odoo/addons/cloud_storage/controllers/attachment.py`

**Inherits:** `mail.controllers.attachment.AttachmentController`

Extends the standard attachment upload endpoint to support cloud storage.

### Route: `mail_attachment_upload` (override)

```python
@route()
@add_guest_to_context
def mail_attachment_upload(self, ufile, thread_id, thread_model, is_pending=False, **kwargs):
    is_cloud_storage = kwargs.get('cloud_storage')
    if (is_cloud_storage and
        not request.env['ir.config_parameter'].sudo().get_param('cloud_storage_provider')):
        return request.make_json_response({
            'error': _('Cloud storage configuration has been changed. Please refresh the page.')
        })
    response = super().mail_attachment_upload(ufile, thread_id, thread_model, is_pending, **kwargs)
    if not is_cloud_storage:
        return response
    data = response.json
    if data.get("error"):
        return response
    # Append upload URL so client can upload directly to cloud
    attachment = request.env["ir.attachment"].browse(
        data["data"]["ir.attachment"][0]["id"]).sudo()
    data["upload_info"] = attachment._generate_cloud_storage_upload_info()
    return request.make_json_response(data)
```

Flow:
1. If `cloud_storage=True` in request kwargs but no provider is configured, return error (prevents broken uploads).
2. Delegates to the parent `AttachmentController` which creates the DB record via `ir.attachment.create()`.
3. If not cloud storage, returns normal response.
4. On cloud storage success, appends `upload_info` (pre-signed upload URL) to the response so the frontend can upload the file directly to the cloud.

---

## Performance & Operational Considerations

### When to Use Cloud Storage

| Use Case | Recommendation |
|----------|---------------|
| Small files (< 20 MB), infrequent | Local storage (default) |
| Large files, high volume | Cloud storage — reduces Odoo server I/O |
| Attachments in chatter (emails) | Local only — `mail.thread.main.attachment` models excluded |
| Read-heavy workloads | Cloud CDN in front of bucket for global latency |
| GDPR/DSFA data residency | Choose region-compliant cloud provider |
| Mixed attachments | Use min file size threshold (default 20 MB) |

### What Happens Without a Provider Module

The base `cloud_storage` module alone does nothing — `cloud_storage_provider` selection is empty, and all abstract methods raise `NotImplementedError`. A provider-specific module (Odoo Apps from the Odoo Store or a custom module) must:

1. Extend the `cloud_storage_provider` selection to include the provider name.
2. Implement `_generate_cloud_storage_url`, `_generate_cloud_storage_download_info`, `_generate_cloud_storage_upload_info` in `ir.attachment`.
3. Implement `_get_cloud_storage_configuration` and `_setup_cloud_storage_provider` in `res.config.settings`.
4. Potentially override `_check_cloud_storage_uninstallable` if migration tooling is needed.

### Provider-Agnostic Blob Naming

All providers use the same blob name format: `{attachment_id}/{uuid}/{original_filename}`. This means:
- Each attachment has a stable, unique blob path.
- Deleting an attachment does not automatically delete the cloud blob (the blob must be cleaned up separately).
- Changing providers without migrating blobs will break existing attachments (the uninstallability check blocks this).

### Odoo Apps Implementing This Module

As of Odoo 18, no official Odoo S.A. cloud storage provider modules are bundled. Provider implementations are available as third-party Apps or must be custom-developed.

---

## Navigation

Menu: **Settings → General Settings → Cloud Storage** (app section in res.config settings form)

Access: Requires Settings access (group System)

Related: [Core/BaseModel](Core/BaseModel.md) (ir.attachment CRUD), [Modules/Mail](Modules/Mail.md) (chatter attachments)
