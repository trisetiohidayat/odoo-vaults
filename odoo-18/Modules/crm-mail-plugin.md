---
Module: crm_mail_plugin
Version: Odoo 18
Type: Integration
Tags: #odoo, #odoo18, #crm, #mail-plugin, #outlook, #gmail, #rpc
---

# crm_mail_plugin — CRM Mail Plugin Integration

## Overview

| Property | Value |
|---|---|
| Category | Sales/CRM |
| Depends | `crm`, `mail_plugin` |
| Auto-install | `True` |
| Version | 1.0 |
| License | LGPL-3 |
| Source | `addons/crm_mail_plugin/` |

**Purpose:** Extends the Outlook/Gmail sidebar plugin (the "mail plugin") with CRM capabilities. Enables sales people to view existing leads linked to a contact, create new leads from emails, and log email content as internal notes — all without leaving their email client.

The plugin communicates with Odoo exclusively via JSON-RPC over HTTPS. All routes are authenticated via `auth="outlook"` (OAuth 2.0 bearer token handled by the `mail_plugin` base module).

---

## Dependencies

```
crm_mail_plugin
    ├── crm          (crm.lead model)
    └── mail_plugin  (base plugin controller, auth middleware, res.partner enrichment)
```

The `mail_plugin` base module (`addons/mail_plugin/`) provides:
- `MailPluginController` — base controller with all partner/company enrichment routes
- `auth="outlook"` auth decorator — validates OAuth 2.0 tokens against Odoo's OAuth provider
- `res.partner` enrichment routes (`/mail_plugin/partner/get`, `/mail_plugin/partner/create`, etc.)
- `res.partner.iap` model for IAP-cached company data

---

## Architecture

```
Outlook / Gmail Plugin (JS sidebar)
        |
        | JSON-RPC (HTTPS)
        v
crm_mail_plugin.controllers.mail_plugin.MailPluginController
    ├── _fetch_partner_leads()        → list leads for partner
    ├── _get_contact_data()            → adds "leads" key to contact response
    ├── _mail_content_logging_models_whitelist() → adds crm.lead
    └── _translation_modules_whitelist() → adds crm_mail_plugin

crm_mail_plugin.controllers.crm_client.CrmClient
    ├── /mail_plugin/lead/create       → create lead from email
    └── (legacy routes for older plugin versions)
```

---

## Model Extensions

### `crm.lead` — Extended by `crm_mail_plugin`

**File:** `models/crm_lead.py`

This model extension is minimal — one deprecated method for backward compatibility:

```python
class Lead(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def _form_view_auto_fill(self):
        # Deprecated since saas-14.3
        # Needed for supporting older mail plugin versions
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'crm.lead',
            'context': {
                'default_partner_id': self.env.context.get('params', {}).get('partner_id'),
            }
        }
```

No new fields are added. No constraints. No overrides of core lead behavior.

**Purpose:** This method existed in older plugin versions to pre-fill the lead form with a partner. It is no longer used in Odoo 18 but is preserved so databases upgraded from older versions with custom plugin integrations still function.

---

## Controller: `mail_plugin.py`

### `MailPluginController` (extends `mail_plugin.controllers.mail_plugin.MailPluginController`)

**File:** `controllers/mail_plugin.py`

#### `_fetch_partner_leads(partner, limit=5, offset=0)`

Returns an array of lead summaries for the given partner:

```python
def _fetch_partner_leads(self, partner, limit=5, offset=0):
    partner_leads = request.env['crm.lead'].search(
        [('partner_id', '=', partner.id)], offset=offset, limit=limit)
    recurring_revenues = request.env.user.has_group('crm.group_use_recurring_revenues')

    leads = []
    for lead in partner_leads:
        lead_values = {
            'lead_id': lead.id,
            'name': lead.name,
            'expected_revenue': formatLang(request.env, lead.expected_revenue,
                                           currency_obj=lead.company_currency),
            'probability': lead.probability,
        }
        if recurring_revenues:
            lead_values.update({
                'recurring_revenue': formatLang(request.env, lead.recurring_revenue,
                                                currency_obj=lead.company_currency),
                'recurring_plan': lead.recurring_plan.name,
            })
        leads.append(lead_values)
    return leads
```

**L4 Notes:**
- Always limited to 5 leads with pagination (`offset`/`limit`) — the plugin UI only shows a summary list.
- `expected_revenue` is formatted with the lead's company currency via `formatLang`.
- `recurring_revenue` fields are gated by `crm.group_use_recurring_revenues` — users without this group see no recurring revenue data.
- Returns only `lead_id`, `name`, `expected_revenue`, `probability`, `recurring_revenue`, `recurring_plan` — no email body, no description.

#### `_get_contact_data(partner)`

**Overrides parent (`mail_plugin.MailPluginController`).** Adds a `"leads"` key to the contact data returned by the base plugin.

```python
def _get_contact_data(self, partner):
    contact_values = super(MailPluginController, self)._get_contact_data(partner)

    if not request.env['crm.lead'].has_access('create'):
        return contact_values  # no "leads" key added

    if not partner:
        contact_values['leads'] = []
    else:
        contact_values['leads'] = self._fetch_partner_leads(partner)
    return contact_values
```

**L4 — Access Control Pattern:**

The method checks `crm.lead.has_access('create')` to decide whether to show the CRM section. This means:
- If the current user **cannot create leads**, the CRM section is completely hidden in the plugin UI.
- If the user **can create leads**, the full lead list is shown.

This is a UX pattern: instead of showing an empty section or an error, the entire CRM feature is invisible to users without CRM create rights.

#### `_mail_content_logging_models_whitelist()`

**Overrides parent.** Adds `crm.lead` to the models that can receive logged emails.

```python
def _mail_content_logging_models_whitelist(self):
    models_whitelist = super()._mail_content_logging_models_whitelist()
    if not request.env['crm.lead'].has_access('create'):
        return models_whitelist
    return models_whitelist + ['crm.lead']
```

Combined with the base `log_mail_content(model, res_id, message, attachments)` route, this allows the plugin to post email bodies as internal notes on `crm.lead` records.

#### `_translation_modules_whitelist()`

**Overrides parent.** Adds `crm_mail_plugin` to the translation module list so plugin UI strings are translated for the current user's lang.

---

## Controller: `crm_client.py`

### `CrmClient` (extends `MailPluginController`)

**File:** `controllers/crm_client.py`

#### `/mail_plugin/lead/create`

**Route:** `POST /mail_plugin/lead/create`
**Auth:** `auth="outlook"`
**Type:** JSON

```python
@http.route('/mail_plugin/lead/create', type='json', auth='outlook', cors="*")
def crm_lead_create(self, partner_id, email_body, email_subject):
    partner = request.env['res.partner'].browse(partner_id).exists()
    if not partner:
        return {'error': 'partner_not_found'}

    record = request.env['crm.lead'].with_company(partner.company_id).create({
        'name': html2plaintext(email_subject),
        'partner_id': partner_id,
        'description': email_body,
    })
    return {'lead_id': record.id}
```

**Behavior:**
- Creates a lead with `name` = email subject (HTML stripped via `html2plaintext`)
- `partner_id` = the contact selected in the plugin
- `description` = full email body (HTML preserved as Markup)
- Uses `with_company(partner.company_id)` to set the correct company context
- Returns `{'lead_id': id}` on success, `{'error': 'partner_not_found'}` if partner doesn't exist

**L4 Notes:**
- No UTM source/medium is set — leads created from email are not UTM-tracked by default.
- No default team or user assignment — falls back to CRM's standard assignment logic.
- The `description` field stores raw HTML — no sanitization is applied (email body is trusted content from the user's own mailbox).
- The `partner_id` write triggers the standard partner-assignment cascade (creating a contact if needed via `_handle_partner_assignment`).

#### Legacy Routes (Deprecated)

All routes in `CrmClient` prefixed with `/mail_client_extension/` are deprecated since saas-14.3 but preserved for backward compatibility with older plugin versions:

| Route | Purpose |
|---|---|
| `/mail_client_extension/log_single_mail_content` | Log email body as note on lead |
| `/mail_client_extension/lead/get_by_partner_id` | Get leads by partner (replaced by `_fetch_partner_leads`) |
| `/mail_client_extension/lead/create_from_partner` | Redirect to prefilled lead form |
| `/mail_client_extension/lead/open` | Open lead in edit mode |
| `/mail_client_extension/modules/get` | Return installed modules (contacts + crm) |

---

## Views

### Lead Form Extension

**File:** `views/crm_lead_views.xml`

Inherits `crm.crm_lead_view_form` — no UI changes in Odoo 18 (the view extension exists for structural compatibility).

### Plugin Lead Template

**File:** `views/crm_mail_plugin_lead.xml`

Contains the `lead_creation_prefilled_action` server action (deprecated, for backward compat):

```xml
<record id="lead_creation_prefilled_action" model="ir.actions.server">
  <field name="name">Redirection to the lead creation form with prefilled info</field>
  <field name="model_id" ref="model_crm_lead"/>
  <field name="state">code</field>
  <field name="code">action = model._form_view_auto_fill()</field>
</record>
```

---

## Auth Mechanism

All routes use `auth="outlook"` which is provided by `mail_plugin.controllers.authenticate`. This:

1. Extracts the OAuth 2.0 bearer token from the `Authorization` header.
2. Validates the token against Odoo's OAuth provider.
3. Sets `request.uid` to the authenticated user.
4. Raises `403 Forbidden` if token is invalid or expired.

**CORS:** All routes have `cors="*"` since the plugin runs in the email client's iframe (Outlook Web / Gmail) and needs to call Odoo's API from a different origin.

---

## How Email-to-Lead Flow Works (L4)

```
1. User reads email in Outlook/Gmail
2. Plugin sidebar shows contact info
   → calls GET /mail_plugin/partner/get (partner found by email)
   → _get_contact_data() adds "leads" array
   → Plugin displays existing leads for that contact

3. User clicks "Create Lead" in plugin
   → Plugin calls POST /mail_plugin/lead/create
   → crm_lead_create() creates lead with:
       name = email subject
       partner_id = selected contact
       description = email body
   → Returns lead_id

4. User clicks "Log Email" on existing lead
   → Plugin calls POST /mail_plugin/log_mail_content
       model='crm.lead', res_id=lead_id, message=body
   → _mail_content_logging_models_whitelist() allows crm.lead
   → message_post(body=Markup(body)) creates internal note

5. Lead appears in Odoo CRM with email as description/note
```

---

## Key L4 Insights

1. **No `iap_enrich` on leads created via plugin** — Enrichment is triggered separately via `crm_iap_enrich` (IAP credits consumed). The plugin only creates leads from emails, it does not enrich them.
2. **Access-gated CRM section** — The `has_access('create')` check in `_get_contact_data` means the plugin's CRM panel is completely invisible to users without lead creation rights. This is cleaner than showing an empty panel.
3. **`with_company` on lead creation** — Uses the partner's company as the lead's company, ensuring multi-company isolation.
4. **Email body stored as `description`** — Not as a `mail.message` (chatter post), but as the lead's description field. This makes it searchable and visible in the lead form header without opening the chatter.
5. **Translation support** — `_translation_modules_whitelist` ensures all plugin UI labels for CRM (lead names, button text) are returned in the user's language.
6. **`recurring_revenue` gated by group** — The recurring revenue fields are only returned to users in the `crm.group_use_recurring_revenues` group. Without the group, those fields are omitted entirely.
7. **Legacy route preservation** — The deprecated `/mail_client_extension/` routes use `auth="user"` (full session auth) while newer `/mail_plugin/` routes use `auth="outlook"` (OAuth token). Both mechanisms coexist.
