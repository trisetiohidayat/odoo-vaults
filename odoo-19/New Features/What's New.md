---
type: new-feature
version: 19.0
tags: [odoo, odoo19, new, features, changes]
created: 2026-04-06
updated: 2026-04-14
---

# What's New in Odoo 19

## Overview

Odoo 19 brings significant improvements across the entire ERP platform, focusing on modern authentication, cloud-native integrations, enhanced collaboration tools, and streamlined business workflows. This release introduces major architectural changes in the ORM layer, new hardware integration capabilities via the IoT framework, pan-European e-invoicing through PEPPOL, and a completely rebuilt HTML editor with real-time collaboration support.

This document provides a high-level summary of the most impactful new features. For deep-dive technical details on each feature area, see [New Features/Whats-New-Deep](New Features/Whats-New-Deep.md). For API-level changes, see [New Features/API Changes](New Features/API Changes.md).

## Authentication: Passkeys (WebAuthn)

**Module:** `auth_passkey` (CE, auto-installed with `base_setup`)

Odoo 19 introduces native passkey authentication using the WebAuthn (FIDO2) standard. Passkeys replace traditional passwords with cryptographic key pairs that are more secure and phishing-resistant.

**Key capabilities:**
- Registration flow generates `auth.passkey.key` records linked to `res.users` via `auth_passkey_key_ids` (one2many)
- Uses the `_vendor/webauthn` Python library (bundled) for cryptographic operations
- Registration calls `_start_registration()` which generates `generate_registration_options()` from the webauthn library, storing the challenge in the session
- Verification calls `_verify_registration_response()` which stores the `credential_id` as `credential_identifier` (base64url-encoded) and the `credential_public_key` in a separate column (updated via raw SQL after create, since the field has an inverse that is intentionally empty for security)
- Login flow calls `_start_auth()` to generate authentication options, then `_verify_auth()` using `verify_authentication_response()`
- The `_login()` method in `res.users` is overridden to intercept `credential['type'] == 'webauthn'` and look up the user by `credential_identifier`
- `_check_credentials()` validates the authentication response, updates `sign_count` for replay-attack prevention, and returns `{'uid': ..., 'auth_method': 'passkey', 'mfa': 'skip'}`
- Session tokens are recomputed via `_compute_session_token()` when passkeys are created or deleted, with `auth_passkey_key_ids` included in `_get_session_token_fields()`
- Public key is stored as a varchar column (dynamically added via `init()` if missing) and computed via `_compute_public_key()` / `_inverse_public_key()` for ORM access, but the actual private key data is never exposed to the ORM layer

**Related:** [Modules/auth_passkey](Modules/auth_passkey.md)

## HTML Editor: Collaborative Rich Text

**Module:** `html_editor` (CE, auto-installed with `base`)

The HTML editor in Odoo 19 is a complete rewrite providing a plugin-based, collaborative rich text editing experience. It replaces the legacy `web_editor` field implementation with a modern architecture.

**Key architectural components:**

- **Plugin system** (`static/src/core/plugins/`): Extensible plugin architecture where each plugin extends the editor's capabilities. Plugins handle formatting, media embedding, table manipulation, and more.
- **Collaborative editing** (`static/src/others/collaboration/`): Uses Odoo's bus (`bus.bus`) and WebSocket infrastructure for real-time co-editing. Changes are broadcast via `im_bus` channels.
- **Powerbox** (`static/src/main/powerbox/`): Command palette for inserting specific content types, dynamic placeholders, and embedded components directly within the editor.
- **Link popover**: Enhanced link editing with URL validation, preview, and accessibility attributes.
- **History tracking** (`html_field_history_mixin`): Every change to an HTML field is tracked. The mixin stores revision data as `fields.Json` under `html_field_history`. Each revision contains the raw diff patch (generated using `generate_patch()` from a custom `diff_utils` module) and metadata (user, timestamp). `_compute_metadata()` strips patch data to return only revision metadata. The mixin uses `prefetch=False` on the history field for performance.
- **Embedded components** (`static/src/others/embedded_components/`): Support for embedding Odoo views, snippets, and dynamic content within HTML fields.
- **Image cropping** via Cropper.js (`static/lib/cropperjs/`), integrated as an asset bundle `html_editor.assets_image_cropper`.
- **Field integration** via `ir_http` and `ir_websocket` models. The `ir_http` model adds `CONTEXT_KEYS = ['editable', 'edit_translations', 'translatable']` for editor context detection.
- **Sanitization**: Uses DOMPurify (`static/lib/dompurify/`) for XSS prevention. Sanitization settings are configurable per field via the `sanitize`, `sanitize_tags`, `sanitize_attributes` field attributes.

**Related:** [Modules/html_editor](Modules/html_editor.md)

## IoT Integration: Hardware Proxy Framework

**Modules:** `iot_base`, `iot_drivers` (CE)

Odoo 19 introduces a redesigned IoT integration framework. The `iot_base` module provides the Odoo-side device management UI, while `iot_drivers` provides the hardware communication layer that runs on an IoT box (Raspberry Pi).

**Architecture overview:**

```
Odoo Server
    └── iot_base (Web client backend)
            └── iot_drivers (runs on IoT box)
                    ├── Driver (base class in drivers/driver.py)
                    │       └── specific device drivers (printer, scale, camera, etc.)
                    ├── Manager (main.py)
                    │       └── manages driver lifecycle, contacts Odoo server
                    ├── WebsocketClient
                    │       └── bidirectional communication
                    ├── EventManager
                    │       └── device event pub/sub
                    └── Tools: certificate, helpers, wifi, upgrade
```

**Driver base class** (`Driver` in `iot_drivers/driver.py`):
- Extends `Thread` for async operation
- Registered automatically via `__init_subclass__` into the global `drivers` list
- `supported(device)` classmethod: override to detect if a device is handled by this driver
- `action(data)` method: dispatches device actions, stores `owner` (session_id) in `self.data`, calls `_actions` dict entries
- Handles duplicate action detection via `action_unique_id` (LRU cache of 256 entries)
- Non-printer/payment devices publish events via `event_manager.device_changed()`
- `disconnect()`: stops the thread and removes the device from `iot_devices`

**Manager class** (`Manager` in `iot_drivers/main.py`):
- Runs as a daemon thread on the IoT box
- `_get_domain()`: computes IoT box domain from IP + certificate subject (e.g., `192-168-1-1.example.com`)
- `_get_changes_to_send()`: tracks device list changes, IP changes, version changes
- `_send_all_devices()`: POSTs IoT box info and device list to `/iot/setup` endpoint, with 5 retries and exponential backoff
- On startup: loads nginx config, checks git branch, manages certificates, downloads IoT handlers from Odoo server, loads drivers, starts interface listeners, establishes WebSocket connection
- Scheduled daily tasks: certificate validity check, log level reset, git branch check

**Key IoT tools** (`iot_drivers/tools/`):
- `certificate.py`: Manages TLS certificates for secure server communication
- `helpers.py`: MAC address, IP, identifier, token, nginx server management, IoT handler download/loading
- `wifi.py`: Wi-Fi reconnection logic
- `system.py`: Platform detection (`IS_RPI`)
- `route.py`: Routing table management
- `upgrade.py`: Git branch management for handler updates

**Related:** [Modules/iot_base](Modules/iot_base.md)

## Accounting: PEPPOL E-Invoicing

**Module:** `account_peppol` (CE)

PEPPOL (Pan-European Public Procurement OnLine) is a network for cross-border e-invoicing and procurement. Odoo 19 integrates directly with the PEPPOL network through the `account_peppol` module.

**Key components:**

- **Participant registration** via `wizard/peppol_registration.py`: Multi-step wizard for registering as a PEPPOL sender/receiver. Handles company identification, endpoint discovery, and SMP (Service Metadata Publisher) registration.
- **EDI proxy client** (`account_edi_proxy_client` dependency): All PEPPOL traffic flows through Odoo's EDI proxy infrastructure, which acts as a intermediary for secure message delivery. Companies are identified by `account_edi_proxy_client.user` records.
- **UBL format support** (`account_edi_ubl_cii` dependency): Peppol documents are exchanged in Peppol BIS Billing 3.0 UBL 2.1 format.
- **Company-level configuration** (`res_company.py` extension):
  - `account_peppol_proxy_state`: Selection field tracking registration status (`not_registered`, `sender`, `smp_registration`, `receiver`, `rejected`)
  - `account_peppol_contact_email`: Primary contact for PEPPOL communications
  - `account_peppol_phone_number`: Mobile number used for identification (validated via `phonenumbers` Python library)
  - `account_peppol_edi_user`: Many2one to `account_edi_proxy_client.user`
- **Endpoint validation rules** defined per country in `PEPPOL_ENDPOINT_RULES`:
  - Sweden (0007): Swedish org number, 10 digits
  - Denmark (0184): Danish CVR
  - Norway (0192): Norwegian org number, 9 digits
  - Belgium (0208): Belgian VAT, 10 digits
  - EAN-13 (0088): Generic EAN identifier
- **Document exchange** via `account_move_send.py`: Invoices can be sent through PEPPOL directly from the send wizard.
- **Supported countries** (26 European countries listed in manifest): Austria, Belgium, Switzerland, Cyprus, Czech Republic, Germany, Denmark, Estonia, Spain, Finland, France, Greece, Ireland, Iceland, Italy, Lithuania, Luxembourg, Latvia, Malta, Netherlands, Norway, Poland, Portugal, Romania, Sweden, Slovenia.

**Related:** [Modules/account_peppol](Modules/account_peppol.md)

## Cloud Storage: Azure and Google Integrations

**Modules:** `cloud_storage` (base), `cloud_storage_azure`, `cloud_storage_google` (CE)

Odoo 19 introduces cloud-native file storage for chatter attachments. Instead of storing files in the local Odoo filestore, attachments can be offloaded to Azure Blob Storage or Google Cloud Storage.

**Architecture:**

- `cloud_storage` is the base module (depends on `base_setup`, `mail`)
  - Provides the settings UI (`views/settings.xml`) for configuring cloud provider credentials
  - Central API for storing/retrieving attachments from any cloud provider
  - Static assets for the settings UI in `web.assets_backend`
- `cloud_storage_azure` depends on `cloud_storage`
  - Uses Azure Blob Storage SDK
  - Configures Azure `account_name`, `account_key` (or SAS token), and `container_name` in settings
  - `uninstall_hook` cleans up Azure-specific configuration
- `cloud_storage_google` depends on `cloud_storage`
  - Uses Google Cloud Storage (via `google-cloud-storage` Python SDK)
  - Configures via `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON) or GCS HMAC keys

**How it works:**
- When cloud storage is enabled, `ir.attachment` records continue to work as normal from the ORM perspective
- The `ir_attachment` model is extended to redirect file storage to the cloud provider
- Attachment URLs in the mail composer (chatter) point to signed cloud storage URLs
- Reduces Odoo server disk usage for high-volume attachment scenarios

## Manufacturing: Subcontracting Portal

**Module:** `mrp_subcontracting` (CE, depends on `mrp`)

Odoo 19's subcontracting module enables subcontractors to manage manufacturing operations through a dedicated web portal, without requiring direct Odoo backend access.

**Key models and features:**

- `mrp.production` extended with subcontracting fields:
  - `subcontractor_id`: Many2one to `res.partner` — restricts portal access to the specific subcontractor
  - `bom_product_ids`: Computed Many2many of products used in the BoM (used to filter the portal product list)
  - `incoming_picking`: Related to the subcontracting receipt picking via `move_dest_ids`
  - `move_line_raw_ids`: Inverse field for recording component consumption (records tracked components consumed by the subcontractor)
- **Portal views** (`subcontracting_portal_views.xml`): Subcontractors can view their production orders, record component usage, and mark operations as done
- **Subcontracting portal controller**: Custom web controllers render the subcontractor-specific views
- **Security**:
  - Record rules restrict `mrp.production` access based on `subcontractor_id` matching the portal user's partner
  - Portal users cannot write to unauthorized fields; `_get_writeable_fields_portal_user()` defines allowed fields
  - The `write()` method on `mrp.production` explicitly checks `self.env.user._is_portal()` and raises `AccessError` for unauthorized fields
- **Stock moves**: `stock.move` is extended with subcontracting-specific behavior including `stock_rule`, `stock_move`, `stock_move_line` extensions
- **Portal-specific asset bundle** in manifest: The `mrp_subcontracting.webclient` asset bundle includes a custom subset of the web framework (Bootstrap SCSS, OWL, jQuery) to render the portal independently

**Related:** [Modules/mrp_subcontracting](Modules/mrp_subcontracting.md)

## Point of Sale: Self-Order

**Module:** `pos_self_order` (CE, auto-installs with `pos_restaurant`)

Odoo 19 POS Self-Order allows customers to browse the menu and place orders using their own smartphone, with QR-code-based session joining.

**Architecture:**
- Depends on `pos_restaurant` (table-based POS) and `http_routing`, `link_tracker`
- **Self-order flow**:
  1. Customer scans a QR code displayed at the table (links to `/pos-self-order/<session_token>`)
  2. Session token identifies the specific POS session and table
  3. Customer browses the product catalog, customizes items, and adds to cart
  4. Order is submitted to the POS session in real-time
  5. POS operator sees the order appear on their screen and prepares it
- **Presets** (`pos_preset_view.xml`): Restaurants can pre-configure "preset" orders (e.g., "Set Menu A") that customers can quickly select
- **Custom links** (`custom_link_views.xml`): Branded short URLs for the self-order portal
- **Offline support**: Uses IndexedDB (`models/utils/indexed_db.js`) to cache product data locally
- **Payment integration**: Supports external payment terminals (Adyen, Stripe via `pos_self_order_adyen`, `pos_self_order_stripe` variants)
- **POS QR ordering button** (`backend/qr_order_button/`): Backend button that generates the QR code for a specific table/session

**Related:** [Modules/pos_self_order](Modules/pos_self_order.md)

## Website: Theme Builder and Page Builder

**Modules:** `website`, `website_theme` (CE)

Odoo 19 significantly improves the website building experience.

**Theme builder improvements:**
- Visual theme customization with live SCSS compilation
- Improved color palette and typography controls
- Bootstrap 5 variables integration (via SCSS overrides in `web/static/lib/bootstrap/scss/`)
- Dark mode support built into the theme architecture

**Page builder enhancements:**
- New snippet library with improved drag-and-drop
- Better grid system based on CSS Grid and Flexbox
- Real-time preview of custom snippets
- Improved SEO controls integrated directly into the editor

**Related:** [Modules/website](Modules/website.md)

## HR and Attendance

**Modules:** `hr`, `hr_attendance`, `hr_timesheet` (CE)

**New attendance features:**
- Improved geolocation-based attendance validation
- Better mobile experience for clock-in/clock-out
- Integration with `hr_holidays` for leave-aware attendance

**Timesheet improvements:**
- Enhanced project task time tracking
- Better approval workflows
- Improved mobile timer

## ORM API Changes

Odoo 19 introduces significant changes to the ORM decorator API. Key changes verified against source code:

| Change | Status | Details |
|--------|--------|---------|
| `@api.one` | **REMOVED** | Not in `api/__init__.py` exports; was deprecated in Odoo 11 |
| `@api.multi` | **REMOVED** | Not in exports; was the implicit default since Odoo 11 |
| `@api.model_create_multi` | **ACTIVE** | Explicit decorator for batch create methods; automatically applied by `@api.model` to `create()` |
| `@api.model` | **ENHANCED** | Automatically applies `@model_create_multi` to `create()` method |
| `@api.private` | **NEW** | Decorator marking methods as non-RPC-callable |
| `@api.readonly` | **NEW** | Decorator indicating method can run on a readonly cursor |
| `fields.Json` | **ACTIVE** | JSON field type (since Odoo 17); stores patch/history data |
| `Cast` field | **NOT FOUND** | No `Cast` field class in Odoo 19 fields |

For complete API verification details, see [New Features/API Changes](New Features/API Changes.md).

## New Modules Summary

| Module | Category | Purpose |
|--------|----------|---------|
| `auth_passkey` | Authentication | WebAuthn passkey login |
| `html_editor` | Rich Text | Collaborative HTML editing with history |
| `iot_base` | IoT | Device management UI |
| `iot_drivers` | IoT | Hardware communication framework |
| `account_peppol` | Accounting | PEPPOL e-invoicing network |
| `cloud_storage` | Storage | Cloud attachment storage base |
| `cloud_storage_azure` | Storage | Azure Blob Storage integration |
| `cloud_storage_google` | Storage | Google Cloud Storage integration |
| `mrp_subcontracting` | Manufacturing | Subcontractor portal |
| `mrp_subcontracting_dropshipping` | Manufacturing | Subcontracting with dropship |
| `mrp_subcontracting_account` | Manufacturing | Subcontracting cost accounting |
| `mrp_subcontracting_landed_costs` | Manufacturing | Landed costs for subcontracting |
| `pos_self_order` | POS | Customer self-ordering via smartphone |
| `pos_self_order_adyen` | POS | Adyen payment for self-order |
| `pos_self_order_stripe` | POS | Stripe payment for self-order |
| `pos_self_order_razorpay` | POS | Razorpay payment for self-order |
| `pos_self_order_sale` | POS | Sale order link for self-order |
| `pos_self_order_pine_labs` | POS | Pine Labs payment terminal |
| `pos_self_order_qfpay` | POS | QFPay integration |
| `partnership` | Partnership | Partnership management |
| `project_stock` | Project | Inventory management in projects |
| `website_event_track_live` | Website | Live event streaming |
| `data_recycle` | Technical | Automatic data lifecycle management |

## Removed/Consolidated Modules

- Legacy payment provider modules removed from core (providers now in separate `payment_*` repositories)
- Some older web utility modules consolidated into `web` core

## Related Documents

- [New Features/API Changes](New Features/API Changes.md) — Verified ORM decorator changes, field types, and new APIs
- [New Features/Whats-New-Deep](New Features/Whats-New-Deep.md) — Comprehensive deep-dive into all major new features
- [Core/BaseModel](BaseModel.md) — Core model API reference
- [Core/Fields](Fields.md) — Field type reference
- [Core/API](API.md) — Decorator reference

---

## Architecture and Framework Changes

### OWL Framework Advancements

Odoo Web Library (OWL) continues to mature in Odoo 19, powering both the web client and the POS self-order interface. Key OWL improvements:

- **Reactive state management**: The `useState` and `useStore` hooks provide fine-grained reactivity with minimal re-renders
- **Improved component lifecycle**: Better `onWillStart`, `onWillUpdateProps`, and `onWillDestroy` hooks
- **Context system**: Full context provider/consumer pattern for deep prop drilling
- **Portals**: Native modal/dropdown rendering outside component DOM hierarchy
- **t-set vs useRef**: New reactive ref pattern for DOM access

### Bootstrap 5 Integration

Odoo 19 fully integrates Bootstrap 5 (replacing Bootstrap 4 from earlier versions):

- CSS custom properties (variables) replace SASS variable overrides
- Offcanvas component replaces old sidebar pattern
- Enhanced dark mode support
- Improved RTL (right-to-left) language support

### Python 3.10+ Requirement

Odoo 19 requires Python 3.10 or higher. Key Python features utilized:

- `str.removeprefix()` / `str.removesuffix()` for path manipulation
- `typing` module enhancements: `Self`, `Never`, `Required`, `NotRequired`
- `functools.cache` for memoization
- `graphlib.TopologicalSorter` for dependency resolution

### PostgreSQL Compatibility

Odoo 19 is compatible with PostgreSQL 13 through 16. New PostgreSQL features leveraged:

- `SKIP LOCKED` for non-blocking record picking in concurrent scenarios
- `INSERT ... ON CONFLICT` (upsert) for batch creation performance
- `FILTER (WHERE ...)` aggregate syntax for conditional aggregation
- Improved JSON path query support for `fields.Json` indexing

---

## Performance Improvements

### ORM Query Optimization

Odoo 19's ORM has several performance enhancements:

1. **Prefetch batching**: Related fields are prefetched in larger batches, reducing query count
2. **Lazy field loading**: Non-visible fields are not loaded until explicitly accessed
3. **Cached computed fields**: `compute_sudo=True` fields are cached across transactions when safe
4. **Optimized write()**: Batch field updates avoid redundant constraint checks
5. **Index advisor**: Built-in suggestion for frequently-searched but unindexed fields

### Web Client Performance

- **Lazy loading of views**: Form/list views load only required components
- **Optimistic UI updates**: Actions reflect immediately, server sync happens in background
- **Virtual scrolling**: Large list views render only visible rows
- **Asset optimization**: SCSS compiled to CSS once, cached aggressively

### Migration Path from Earlier Versions

| Odoo Version | Key Changes to Prepare For |
|-------------|--------------------------|
| Odoo 15 | Python 3.8+, remove `@api.one`/`@api.multi`, `<tree>` → `<list>` |
| Odoo 16 | Python 3.9+, view attrs cleanup, check `fields.Json` usage |
| Odoo 17 | Python 3.10+, verify computed field dependencies, new asset pipeline |
| Odoo 18 | Most changes already captured in this document |

---

## Key Metrics and Statistics

| Metric | Value |
|--------|-------|
| Total CE modules in Odoo 19 | ~330 |
| New modules (vs Odoo 17) | ~25 |
| Removed/merged modules | ~15 |
| Minimum Python version | 3.10 |
| Minimum PostgreSQL version | 13 |
| Asset bundles in html_editor | 9 |
| IoT tool modules | 5 |
| Cloud storage providers | 2 |

---

## Upgrade Notes

### Before Upgrading

1. **Audit `@api.one` and `@api.multi` usage** — these must be removed from all custom modules
2. **Review `<tree>` view tags** — ensure all are migrated to `<list>`
3. **Check Python version** — must be 3.10+ before upgrading
4. **Verify add-on compatibility** — especially payment providers and third-party integrations
5. **Test PEPPOL configuration** — re-validate endpoint rules for your country

### After Upgrading

1. **Enable Passkeys** — Consider enabling for admin accounts first, then rollout
2. **Review IoT devices** — re-pair devices after framework changes
3. **Test HTML fields** — verify sanitization settings are appropriate
4. **Validate cloud storage** — test attachment upload/retrieval after configuration

---

## References

- Odoo 19 Official Release Notes: https://www.odoo.com/page/odoo-19
- Odoo Documentation: https://www.odoo.com/documentation/19.0/
- WebAuthn Standard: https://www.w3.org/TR/webauthn-1/
- PEPPOL Network: https://peppol.eu/
- Odoo Enterprise: https://www.odoo.com/app/studio
