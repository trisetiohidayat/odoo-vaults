---
Module: account_peppol
Version: Odoo 18
Type: Integration
Tags: #odoo18 #peppol #e-invoicing #edi #ubl #bisl #e-fff
---

# account_peppol — Peppol Network (e-Invoicing via Access Point)

**Addon path:** `~/odoo/odoo18/odoo/addons/account_peppol/`
**Purpose:** Integrates Odoo with the Peppol e-invoicing network through Odoo's hosted Access Point (proxy). Handles participant registration, sending invoices to any Peppol participant, and receiving invoices from senders. Built entirely on top of `account_edi`.

## Architecture Overview

```
Your Company (Sender/Receiver)
    └─ res.company: peppol_eas, peppol_endpoint, account_peppol_proxy_state
            └─ account_edi_proxy_client.user (proxy_type='peppol')
                    └─ Odoo EDI Proxy (peppol.api.odoo.com)
                            └─ Peppol Network (SML/SMP lookup)
                                    └─ Recipient Company (Receiver/Sender)
```

Odoo acts as an Access Point. You register as a participant; Odoo relays your invoices to the Peppol network and receives incoming invoices on your behalf.

---

## Model: `res.company` (Extension)

### Peppol Fields on Company

| Field | Type | Notes |
|-------|------|-------|
| `peppol_eas` | Selection (related `partner_id.peppol_eas`) | ISO 6523 Electronic Address Scheme, e.g. `'0007'` (Sweden), `'0192'` (Norway), `'0208'` (Belgium) |
| `peppol_endpoint` | Char (related `partner_id.peppol_endpoint`) | Participant identifier within the EAS scheme |
| `account_peppol_proxy_state` | Selection | `'not_registered'`, `'in_verification'`, `'sender'`, `'smp_registration'`, `'receiver'`, `'rejected'` |
| `account_peppol_migration_key` | Char | Set when migrating AWAY from Odoo's SMP; cleared after migration is sent |
| `account_peppol_contact_email` | Char | Primary contact for Peppol communications; defaults to company email |
| `account_peppol_phone_number` | Char | Mobile number for identification; validated against phonenumbers library; must be European |
| `peppol_purchase_journal_id` | Many2one `account.journal` | Purchase journal for incoming Peppol documents; auto-set when state != `'not_registered'` |

### `account_peppol_proxy_state` — States

| State | Meaning |
|-------|---------|
| `not_registered` | Default. No Peppol participation. |
| `in_verification` | SMS/code verification in progress (deprecated flow) |
| `sender` | Registered as sender only. Can send; cannot receive (no SMP entry). |
| `smp_registration` | SMP registration pending. Already a sender; receiver registration in progress. |
| `receiver` | Fully registered. Can send AND receive via Peppol. |
| `rejected` | Registration rejected. Cannot send or receive. |

### Key Methods

#### `_check_phonenumbers_import()`
Validates the `phonenumbers` Python library is installed. Raises `ValidationError` if not.

#### `_sanitize_peppol_phone_number(phone_number=None)`
Normalizes to E.164 format (`+32123456789`). Validates the number is in a European country in `PEPPOL_LIST`. Raises `ValidationError` on bad format.

#### `_check_peppol_endpoint_number(warning=False)`
Performs EAS-scheme-specific validation of `peppol_endpoint`.

**Mandatory rules** (`warning=False`, blocks bad values):
```python
PEPPOL_ENDPOINT_RULES = {
    '0007': _cc_checker('se', 'orgnr'),       # Swedish orgnr (10 digits)
    '0088': ean.is_valid,                      # EAN-13
    '0184': _cc_checker('dk', 'cvr'),          # Danish CVR
    '0192': _cc_checker('no', 'orgnr'),        # Norwegian orgnr (9 digits)
    '0208': _cc_checker('be', 'vat'),          # Belgian VAT (10 digits)
}
```

**Warning-only rules** (`warning=True`, advisory only):
```python
PEPPOL_ENDPOINT_WARNINGS = {
    '0151': _cc_checker('au', 'abn'),         # Australian ABN
    '0201': lambda x: bool(re.match('[0-9a-zA-Z]{6}$')),  # Italian CUU
    '0210': _cc_checker('it', 'codicefiscale'), # Italian Codice Fiscale
    '0211': _cc_checker('it', 'iva'),          # Italian Partita IVA
    '9906': _cc_checker('it', 'iva'),
    '9907': _cc_checker('it', 'codicefiscale'),
}
```

#### `_sanitize_peppol_endpoint_in_values(vals)`
Strips/reshapes endpoint values on write/create for known EAS codes:
```python
PEPPOL_ENDPOINT_SANITIZERS = {
    '0007': _re_sanitizer(r'\d{10}'),   # extract 10 digits
    '0184': _re_sanitizer(r'\d{8}'),    # extract 8 digits
    '0192': _re_sanitizer(r'\d{9}'),    # extract 9 digits
    '0208': _re_sanitizer(r'\d{10}'),   # extract 10 digits
}
```

### Constraints

```python
@api.constrains('account_peppol_phone_number')
def _check_account_peppol_phone_number(self):
    for company in self:
        if company.account_peppol_phone_number:
            company._sanitize_peppol_phone_number()

@api.constrains('peppol_endpoint')
def _check_peppol_endpoint(self):
    # uses PEPPOL_ENDPOINT_RULES (mandatory)
    if not company._check_peppol_endpoint_number(PEPPOL_ENDPOINT_RULES):
        raise ValidationError("The Peppol endpoint identification number is not correct.")

@api.constrains('peppol_purchase_journal_id')
def _check_peppol_purchase_journal_id(self):
    if company.peppol_purchase_journal_id.type != 'purchase':
        raise ValidationError("A purchase journal must be used to receive Peppol documents.")
```

### Peppol Document Types

#### `_peppol_modules_document_types() -> dict`
Returns document types supported by each module. Base implementation in `res.company`:

```python
{
    'default': {
        "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1":
            "Peppol BIS Billing UBL Invoice V3",
        "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2::CreditNote##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1":
            "Peppol BIS Billing UBL CreditNote V3",
        "urn:...nen.nl:nlcius:v1.0::2.1": "SI-UBL 2.0 Invoice / CreditNote",
        "urn:...xeinkauf.de:kosit:xrechnung_3.0::2.1": "XRechnung UBL Invoice/CreditNote V2.0",
        "urn:...sg:3.0::2.1": "SG Peppol BIS Billing 3.0",
        "urn:...aunz:3.0::2.1": "AU-NZ Peppol BIS Billing 3.0",
    }
}
```

Country-specific modules (e.g., `l10n_nl`) add their own document types via the same method pattern.

#### `_peppol_supported_document_types() -> dict`
Flattens all modules' document types into a single dict `{identifier: document_name}`.

#### `_get_peppol_edi_mode() -> str`
Returns `'demo'`, `'test'`, or `'prod'` based on:
1. Demo mode if `peppol_eas == 'odemo'` (Odoo Demo ID)
2. User's `edi_mode` on the proxy user
3. `ir.config_parameter` `account_peppol.edi.mode`
4. Default: `'prod'`

---

## Model: `account_edi_proxy_client.user` (Extension)

Lives in `account_edi_proxy_client` module; `account_peppol` extends it with Peppol-specific behavior.

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `proxy_type` | Selection | Extended with `('peppol', 'PEPPOL')` option |
| `peppol_verification_code` | Char | **Deprecated** — SMS verification code (removed in master) |

### Proxy URLs

```python
{
    'peppol': {
        'prod': 'https://peppol.api.odoo.com',
        'test': 'https://peppol.test.odoo.com',
        'demo': 'demo',
    }
}
```

### `_call_peppol_proxy(endpoint, params=None) -> dict`

Central method for all Peppol API calls. Wraps `_make_request()`. Handles error codes:

```python
'code_incorrect'   → "The verification code is not correct"
'code_expired'     → "This verification code has expired..."
'too_many_attempts' → "Too many attempts to request an SMS code..."
'no_such_user'     → If inactive and no other peppol user: resets company state to 'not_registered'
```

### Cron Jobs

| Cron | Trigger Condition | Method |
|------|-------------------|--------|
| `_cron_peppol_get_new_documents` | `proxy_state='receiver'` | `_peppol_get_new_documents()` |
| `_cron_peppol_get_message_status` | `proxy_state in ('sender', 'smp_registration', 'receiver')` | `_peppol_get_message_status()` |
| `_cron_peppol_get_participant_status` | Always active | `_peppol_get_participant_status()` |

During `smp_registration`, `_cron_peppol_get_participant_status` retriggers itself hourly to pick up the registration completion.

### Receiving: `_peppol_get_new_documents()`

```
1. POST /api/peppol/1/get_all_documents
       domain: {direction: 'incoming', errors: False}
2. Receive list of message UUIDs
3. If len > BATCH_SIZE (50): retrigger cron
4. POST /api/peppol/1/get_document  (body: {message_uuids: [...]})
5. For each message:
       - Decrypt with _decrypt_data(enc_key, document_content)
       - Create ir.attachment with decoded XML
       - Create account.move (move_type='in_invoice') in peppol_purchase_journal_id
       - Call _extend_with_attachments() to populate from XML
       - Link attachment to move
6. POST /api/peppol/1/ack  (acknowledge receipt)
7. Commit after each batch
```

### Sending: `_call_web_service_after_invoice_pdf_render()` (in `account.move.send`)

Documents are sent to Peppol **after** the PDF is rendered. The Peppol payload is built from UBL XML attachments:

```python
params['documents'].append({
    'filename': filename,
    'receiver': f"{partner.peppol_eas}:{partner.peppol_endpoint}",
    'ubl': b64encode(xml_file).decode(),
})
POST /api/peppol/1/send_document  (body: {documents: [...]})
Response: {messages: [{message_uuid: '...'}, ...]}
```

Each invoice gets a `peppol_message_uuid` and its `peppol_move_state` becomes `'processing'`. The `_cron_peppol_get_message_status` poll is triggered 5 minutes later.

### `_peppol_get_message_status()`

```
1. Find moves with peppol_move_state='processing'
2. POST /api/peppol/1/get_document  (fetch status for each message_uuid)
3. For each message:
       - 'error' key in response → peppol_move_state='error'
       - error code 702 ('not ready yet') → skip (IAP still processing)
       - Otherwise: update peppol_move_state from response['state']
4. Acknowledge to proxy
```

### Participant Registration: `_peppol_register_sender()`

Called during onboarding. Sends company details to the proxy:
```python
POST /api/peppol/1/register_sender
    {company_details: {peppol_company_name, peppol_company_vat, peppol_country_code, ...}}
Sets: company.account_peppol_proxy_state = 'sender'
```

### Participant Registration (Receiver): `_peppol_register_sender_as_receiver()`

```
1. Check participant doesn't already exist on another SMP
2. POST /api/peppol/1/register_sender_as_receiver
       {migration_key: ..., supported_identifiers: [...]}
3. Clear migration_key from company
4. Set state='smp_registration'
5. Retrigger participant status cron in 1 hour
```

### Deregistration: `_peppol_deregister_participant()`

```
1. If receiver: fetch all pending documents first (acknowledge them)
2. POST /api/peppol/1/cancel_peppol_registration
3. Set company state='not_registered', clear migration_key
4. Delete the proxy user record
```

### Auto-Register Services: `_peppol_auto_register_services(module)`

Called in `_post_init_hook` when a country-specific l10n module is installed. Registers new document types with the IAP for all receiver users.

---

## Model: `res.partner` (Extension)

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `invoice_sending_method` | Selection | Extended with `('peppol', 'by Peppol')` |
| `peppol_eas` | Selection | Extended with `('odemo', 'Odoo Demo ID')` for test mode |
| `peppol_verification_state` | Selection (company_dependent) | `'not_verified'`, `'not_valid'`, `'not_valid_format'`, `'valid'` |
| `available_peppol_sending_methods` | Json (compute) | Filters `'peppol'` if company country not in `PEPPOL_LIST` |
| `available_peppol_edi_formats` | Json (compute) | Peppol formats if sending via Peppol, else standard formats |

### SML/SMP Lookup

The Peppol network uses a two-tier lookup:
1. **SML** (Service Metadata Locator): DNS-based. Given `EAS:ENDPOINT`, computes: `B-{md5(lowercase(identification))}.iso6523-actorid-upis.{edelivery|acc.edelivery}.tech.ec.europa.eu/{encoded_identification}`
2. **SMP** (Service Metadata Publisher): HTTP server at that DNS name. Returns an XML document listing which document types (e.g., Invoice 3.0) the participant can receive.

```python
def _get_participant_info(edi_identification):
    hash_participant = md5(edi_identification.lower().encode()).hexdigest()
    endpoint_participant = parse.quote_plus(f"iso6523-actorid-upis::{edi_identification}")
    sml_zone = 'acc.edelivery' if edi_mode == 'test' else 'edelivery'
    smp_url = f"http://B-{hash_participant}.iso6523-actorid-upis.{sml_zone}.tech.ec.europa.eu/{endpoint_participant}"
    # GET smp_url → returns XML service metadata
    # Returns None if unreachable (participant not on network)
```

Belgium special case: Belgian companies are pre-registered on Hermes Belgium. The `hermes-belgium` access point URL is filtered out — Belgian companies without a real Peppol setup should not be flagged as participants.

### Verification States

| State | Meaning |
|-------|---------|
| `not_verified` | No EAS/endpoint, or format not in Peppol formats |
| `not_valid` | SML/SMP lookup returned nothing — partner not on Peppol |
| `not_valid_format` | Partner is on Peppol but cannot receive the specific document type (UBL format) |
| `valid` | Partner is on Peppol and can receive the document type |

### `_get_peppol_verification_state(endpoint, eas, invoice_edi_format) -> str`

```python
def _get_peppol_verification_state(self, peppol_endpoint, peppol_eas, invoice_edi_format):
    if not (peppol_eas and peppol_endpoint) or invoice_edi_format not in self._get_peppol_formats():
        return 'not_verified'
    edi_identification = f"{peppol_eas}:{peppol_endpoint}".lower()
    participant_info = self._get_participant_info(edi_identification)
    if participant_info is None:
        return 'not_valid'
    # ... checks service metadata for document type support
```

### Belgian Endpoint Auto-Swap

Belgium has two EAS codes that map to the same entity. If a Belgian partner is not found with EAS `0208`, the code checks EAS `9925` (BE + VAT without BE prefix):
```python
inverse_eas = '9925' if self_partner.peppol_eas == '0208' else '0208'
inverse_endpoint = f'BE{endpoint}' if peppol_eas == '0208' else endpoint[2:]
```

### `_update_peppol_state_per_company(vals=None)`

Called on `write()` and `create()` for partners. For each partner that has EAS, endpoint, is UBL format, and in a Peppol country, it triggers `button_account_peppol_check_partner_endpoint(company)` to update the verification state.

---

## Model: `account.move` (Extension)

### Added Fields

| Field | Type | Notes |
|-------|------|-------|
| `peppol_message_uuid` | Char | UUID assigned by the Peppol proxy when sent |
| `peppol_move_state` | Selection (store, compute) | `'ready'`, `'to_send'`, `'processing'`, `'done'`, `'error'` (and deprecated `'skipped'`) |

### `peppol_move_state` — States

| State | Meaning |
|-------|---------|
| `ready` | Posted sale invoice; company is sender/receiver; partner is valid Peppol participant; not yet sent |
| `to_send` | Queued for sending; Peppol checkbox checked in send wizard |
| `processing` | Sent to Peppol proxy; awaiting delivery confirmation |
| `done` | Recipient confirmed receipt |
| `error` | Failed; see error message |
| `skipped` | Deprecated — now treated as regular error |

### Computed: `_compute_peppol_move_state()`

```python
@api.depends('state')
def _compute_peppol_move_state(self):
    can_send = self.env['account_edi_proxy_client.user']._get_can_send_domain()
    for move in self:
        if all([
            move.company_id.account_peppol_proxy_state in can_send,
            move.commercial_partner_id.peppol_verification_state == 'valid',
            move.state == 'posted',
            move.is_sale_document(include_receipts=True),
            not move.peppol_move_state,        # not already processed
        ]):
            move.peppol_move_state = 'ready'
        elif (move.state == 'draft' and move.is_sale_document() and
              move.peppol_move_state not in ('processing', 'done')):
            move.peppol_move_state = False
```

### `action_cancel_peppol_documents()`

Cancels Peppol-specific sending state. **Cannot cancel** if `peppol_move_state in ('processing', 'done')` — the document has already been delivered to the network.

```python
def action_cancel_peppol_documents(self):
    if any(move.peppol_move_state in {'processing', 'done'} for move in self):
        raise UserError("Cannot cancel an entry that has already been sent to PEPPOL")
    self.peppol_move_state = False
    self.sending_data = False
```

---

## Model: `account.journal` (Extension)

| Field | Type | Notes |
|-------|------|-------|
| `account_peppol_proxy_state` | Selection (related `company_id.account_peppol_proxy_state`) | Convenience |
| `is_peppol_journal` | Boolean | Flags the journal as the designated Peppol purchase journal |

### Journal Methods

```python
def peppol_get_new_documents(self):
    # Called from journal button
    edi_users = self.env['account_edi_proxy_client.user'].search([
        ('company_id.account_peppol_proxy_state', '=', 'receiver'),
        ('company_id', 'in', self.company_id.ids),
        ('proxy_type', '=', 'peppol')
    ])
    edi_users._peppol_get_new_documents()

def action_peppol_ready_moves(self):
    # Opens a filtered list view of moves with peppol_move_state='ready'
    return {
        'name': "Peppol Ready invoices",
        'res_model': 'account.move',
        'context': {'search_default_peppol_ready': 1},
    }
```

---

## Wizard: `peppol.registration`

Main onboarding/configuration wizard for Peppol participation. A `TransientModel`.

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `company_id` | Many2one `res.company` | Required |
| `contact_email` | Char (related, required) | From `account_peppol_contact_email` |
| `edi_mode` | Selection | `'demo'`, `'test'`, `'prod'` |
| `edi_mode_constraint` | Selection (compute) | Restricted by `ir.config_parameter` or trial mode |
| `phone_number` | Char (related) | From `account_peppol_phone_number` |
| `peppol_eas` | Selection (related, required) | |
| `peppol_endpoint` | Char (related, required) | Alphanumeric-only onchange sanitiser |
| `smp_registration` | Boolean | Register as receiver; defaults to `True` if no existing SMP registration found |
| `peppol_warnings` | Json (compute) | Advisory warnings: wrong endpoint format, already on another SMP |
| `edi_user_id` | Many2one `account_edi_proxy_client.user` (compute) | Existing proxy user for this company |

### Onchange: Endpoint Sanitiser

```python
@api.onchange('peppol_endpoint')
def _onchange_peppol_endpoint(self):
    # Strips all non-alphanumeric characters
    wizard.peppol_endpoint = ''.join(char for char in wizard.peppol_endpoint if char.isalnum())
```

### Onchange: Phone Number Normalization

Parses and reformats to E.164 using the country code from `company_id.country_code`.

### Onchange: `_compute_smp_registration`

Attempts to check if the company is already on another SMP. If `_check_company_on_peppol()` raises a `UserError`, the company is already registered elsewhere, so `smp_registration = False` (sender-only mode).

### Registration Action: `button_register_peppol_participant()`

```python
def button_register_peppol_participant(self):
    edi_user = self.edi_user_id or self.env['account_edi_proxy_client.user'] \
        ._register_proxy_user(self.company_id, 'peppol', self.edi_mode)
    edi_user._peppol_register_sender()           # always needed
    if self.smp_registration:
        edi_user._peppol_register_sender_as_receiver()  # may fail; rolls back if so
    # On success: company.account_peppol_proxy_state = 'sender' or 'smp_registration'
```

### Deregistration: `button_deregister_peppol_participant()`

```python
def button_deregister_peppol_participant(self):
    if self.edi_user_id:
        self.edi_user_id._peppol_deregister_participant()
```

---

## Wizard: `account_peppol.service.wizard`

Allows receiver participants to configure which Peppol document types (Invoice vs CreditNote vs XRechnung vs SI-UBL, etc.) they can receive.

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `edi_user_id` | Many2one `account_edi_proxy_client.user` | |
| `service_json` | Json | Raw services from IAP (`{identifier: {document_name, ...}}`) |
| `service_ids` | One2many `account_peppol.service` | Per-document-type lines |
| `service_info` | Html (compute) | Warning about non-configurable services from other providers |

### Flow

```
1. confirm() reads service_ids changes
2. Differs service_json (current on IAP) vs service_ids (desired)
3. to_add = identifiers in service_ids.enabled but not in service_json
4. to_remove = identifiers in service_json but not in service_ids.enabled
5. POST /api/peppol/2/add_services    (if to_add)
6. POST /api/peppol/2/remove_services (if to_remove)
```

---

## Wizard: `account.move.send.wizard` (Extension)

### `_compute_sending_method_checkboxes()` (Override)

Adds Peppol-specific logic to the send wizard:
- Disables Peppol checkbox if partner `peppol_verification_state in ('not_valid', 'not_verified')`
- Adds `'(Test)'` or `'(Demo)'` suffix to label in non-prod modes
- Adds `'(Customer not on Peppol)'` or `'(no VAT)'` suffix when disabled
- Calls `button_account_peppol_check_partner_endpoint(company)` to refresh partner's verification state before computing

### `action_send_and_print()` (Override)

```python
def action_send_and_print(self):
    if 'peppol' in self.sending_methods:
        if move.partner_id.commercial_partner_id.peppol_verification_state != 'valid':
            raise UserError("Partner doesn't have a valid Peppol configuration.")
        if registration_action := self._do_peppol_pre_send(move):
            return registration_action  # redirect to registration wizard
    return super().action_send_and_print()
```

---

## Wizard: `account.move.send.batch.wizard` (Extension)

### `_compute_summary_data()` (Override)

Refreshes partner Peppol verification state for all Peppol-eligible moves before computing the batch summary.

---

## Res Config Settings

All fields are related from `res.company` or `account_edi_proxy_client.user`:

| Field | Source | Notes |
|-------|--------|-------|
| `account_peppol_edi_user` | compute | Proxy user for this company |
| `account_peppol_edi_mode` | related `user.edi_mode` | |
| `account_peppol_contact_email` | related `company_id` | |
| `account_peppol_eas` | related `company_id` | |
| `account_peppol_endpoint` | related `company_id` | |
| `account_peppol_migration_key` | related `company_id` | |
| `account_peppol_phone_number` | related `company_id` | |
| `account_peppol_proxy_state` | related `company_id` | |
| `account_peppol_purchase_journal_id` | related `company_id` | |

### Buttons

- `action_open_peppol_form()` → opens `peppol.registration` wizard
- `button_update_peppol_user_data()` → `PATCH /api/peppol/1/update_user`
- `button_peppol_smp_registration()` → registers as receiver
- `button_deregister_peppol_participant()` → deregisters from network
- `button_migrate_peppol_registration()` → **deprecated**, raises `UserError`
- `button_account_peppol_configure_services()` → opens `account_peppol.service.wizard`

---

## L4: Peppol Participant Identifier Format

Peppol uses ISO 6523 for participant identification: `EAS:ENDPOINT`.

| EAS Code | Country/Scheme | Example Endpoint | Validation |
|----------|---------------|------------------|------------|
| `0007` | Sweden (Organisationsnummer) | `1234567890` (10 digits) | Swedish orgnr |
| `0088` | EAN-13 (Global) | `5012345678901` (13 digits) | EAN checksum |
| `0184` | Denmark (CVR) | `12345678` (8 digits) | Danish CVR |
| `0192` | Norway (Organisasjonsnummer) | `123456789` (9 digits) | Norwegian orgnr |
| `0208` | Belgium (VAT) | `0123456789` (10 digits) | Belgian VAT |
| `0151` | Australia (ABN) | — | ABN checksum |
| `0210` | Italy (Codice Fiscale) | — | Italian CF |
| `0211` | Italy (Partita IVA) | — | Italian P.IVA |
| `9925` | Belgium alternate (BE+VAT) | `0123456789` | Belgian VAT |
| `odemo` | Odoo Demo | — | Test only |

Full proxy identification string sent to API: `f'{company.peppol_eas}:{company.peppol_endpoint}'`

---

## L4: When Participant Not Found

```
1. Partner has no peppol_eas or peppol_endpoint
   → button_account_peppol_check_partner_endpoint() returns False early
   → peppol_verification_state = 'not_verified'
   → Peppol checkbox is readonly (disabled) in send wizard

2. SML lookup fails (participant_info is None)
   → _get_participant_info() returns None
   → peppol_verification_state = 'not_valid'
   → "Customer is on Peppol but did not enable receiving documents." alert shown

3. Participant found on SMP but not contactable
   → _check_peppol_participant_exists() returns False
   → peppol_verification_state = 'not_valid'

4. Participant found but cannot receive this format
   → _check_document_type_support() returns False
   → peppol_verification_state = 'not_valid_format'
   → Peppol checkbox disabled; warning shown

5. Send attempted to invalid partner
   → _call_web_service_after_invoice_pdf_render() sets peppol_move_state='error'
   → error = "Partner is missing Peppol EAS and/or Endpoint identifier."
       or "Please verify partner configuration in partner settings."
```

The send wizard will not let Peppol be checked for invalid partners. The "Customer not on Peppol" alert appears in the wizard if the partner is verified but Peppol is not selected.

---

## Peppol Send Flow (End-to-End)

```
1. User clicks "Send & Print" on posted invoice
2. account.move.send wizard opens
   └─> _compute_sending_method_checkboxes()
           └─> button_account_peppol_check_partner_endpoint() refreshes partner state
           └─> Peppol checkbox enabled if partner.peppol_verification_state == 'valid'
3. User checks Peppol, clicks Send
   └─> account.move.send.wizard.action_send_and_print()
           └─> _do_peppol_pre_send(moves)
                   └─> Sets peppol_move_state = 'to_send' (if not already)
4. PDF is rendered by _render_pdf_and_notify()
5. _call_web_service_after_invoice_pdf_render()
           └─> Builds params['documents'] with base64-encoded UBL XML
           └─> POST /api/peppol/1/send_document
           └─> Response: {messages: [{message_uuid, ...}, ...]}
           └─> For each invoice: peppol_message_uuid = uuid, peppol_move_state = 'processing'
           └─> _message_log: "Document sent to Peppol Access Point"
           └─> Trigger _cron_peppol_get_message_status in 5 minutes
6. Cron: _cron_peppol_get_message_status()
           └─> GET /api/peppol/1/get_document  (status check)
           └─> Updates peppol_move_state: 'done' when recipient confirms
```

---

## See Also

- [Modules/account-edi](odoo-18/Modules/account-edi.md) — Core EDI infrastructure (document lifecycle, crons, format registry)
- [Modules/Account](odoo-18/Modules/account.md) — `account.move` base model
- [Core/API](odoo-18/Core/API.md) — `@api.depends`, computed fields, constraints
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine pattern used throughout
