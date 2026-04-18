---
type: module
module: crm_mail_plugin
tags: [odoo, odoo19, crm, mail, outlook, plugin, email, lead, conversion]
created: 2026-04-14
uuid: b8d4f7a3-2c9e-5f1b-8a3d-4e6f8b1c5d7e
---

# CRM Mail Plugin (`crm_mail_plugin`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | CRM Mail Plugin |
| **Technical** | `crm_mail_plugin` |
| **Category** | Sales / CRM |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 19.0 |
| **Depends** | `crm`, `mail_plugin` |
| **Auto-install** | `True` |

The `crm_mail_plugin` module integrates Odoo's CRM application with the Outlook and Gmail mail plugin. It enables sales teams to convert emails received in their mailbox into CRM leads without leaving their email client, and to log email content as internal notes on existing leads. The module extends the base `mail_plugin` infrastructure to add CRM-specific actions to the email client's sidebar panel.

This is the CRM counterpart to [Modules/project_mail_plugin](Modules/project_mail_plugin.md), which provides the same integration for the Project application. Both modules share the same architectural pattern: extending `MailPluginController` from `mail_plugin` to add model-specific data and actions to the contact panel.

## Architecture

### Design Philosophy

The module is intentionally minimal. The CRM integration with the mail plugin is simpler than the project integration because the primary use case — creating a lead from an email — does not require complex search or selection flows. A lead can be created directly from the email's sender address, with the email body becoming the lead's description. The module focuses on this single high-value workflow rather than trying to replicate the full CRM interface in the email client.

### Module Structure

```
crm_mail_plugin/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── crm_lead.py     # CrmLead extension with _form_view_auto_fill
├── controllers/
│   └── crm_plugin.py   # (if any CRM-specific HTTP endpoints needed)
└── tests/
    └── test_crm_mail_plugin.py
```

### Dependency Chain

```
crm_mail_plugin
├── crm               (crm.lead model, lead creation, pipeline management)
└── mail_plugin       (MailPluginController, _get_contact_data, auth mechanisms)
        └── auth_outlook  (Outlook OAuth for authentication)
```

## Models

### `crm.lead` (Extended)

**File:** `crm_mail_plugin/models/crm_lead.py`

The `crm.lead` model is the central CRM entity representing a sales lead or opportunity. The module adds a single method to support backward compatibility with older versions of the mail plugin.

#### `_form_view_auto_fill()` — Deprecated Compatibility Method

```python
@api.model
def _form_view_auto_fill(self):
    """
    Deprecated as of saas-14.3, not needed for newer versions of the mail plugin
    but necessary for supporting older versions.
    """
    return {
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_model': 'crm.lead',
        'context': {
            'default_partner_id': self.env.context.get('params', {}).get('partner_id'),
        }
    }
```

**Purpose and context:**

This method exists solely for backward compatibility with older versions of the mail plugin (prior to saas-14.3). In those older versions, the Outlook add-in used a server-side form action to open the lead creation form. The method returns a window action that opens a lead form pre-filled with the sender's partner ID.

For current versions of the mail plugin, this method is no longer used. The modern mail plugin uses JSON-RPC calls directly to create leads without needing a separate form view action. However, the method is retained because:

1. **Older plugin versions may still be deployed**: Enterprise customers with long upgrade cycles may have older mail plugin versions installed alongside a newer Odoo backend.
2. **API stability**: Third-party integrations that reference `_form_view_auto_fill` continue to work without modification.

**Why it's deprecated:**

The method is considered deprecated because:
- It opens a form in Odoo (requiring context-switching to the browser).
- It does not provide direct feedback in the email client.
- Modern JSON-RPC-based workflows are more efficient and provide a better user experience.
- The `partner_id` extraction from `params` is fragile and depends on how the mail plugin passes context.

The deprecation notice (`deprecated as of saas-14.3`) signals that developers should not build new integrations on this method.

#### Standard `crm.lead` Fields (Relevant to Mail Plugin)

The `crm.lead` model provides many fields that are relevant to the mail plugin integration:

| Field | Type | Description |
|-------|------|-------------|
| `partner_id` | Many2one | The contact (res.partner) associated with this lead |
| `name` | Char | Lead title/subject |
| `contact_name` | Char | Contact person's name |
| `email_from` | Char | Primary email address |
| `phone` | Char | Phone number |
| `description` | Html | Lead notes and email content |
| `team_id` | Many2one | Sales team responsible |
| `user_id` | Many2one | Salesperson assigned |
| `stage_id` | Many2one | Pipeline stage |
| `company_id` | Many2one | Company |
| `priority` | Selection | Low/Medium/High priority |

## Mail Plugin Integration

### How Email-to-Lead Conversion Works

The mail plugin (installed as an Outlook add-in or browser extension) provides a "Create Lead" action in the email context menu. The complete flow:

```
Sales rep opens email in Outlook
    ↓
Mail plugin reads email: sender, subject, body
    ↓
Plugin calls Odoo JSON-RPC endpoint
    (crm.lead.create via mail_plugin.generic_thread_message)
    ↓
Odoo creates crm.lead:
    - name = email subject
    - email_from = sender email
    - description = email body
    - partner_id = matched contact (if found)
    ↓
Lead appears in CRM pipeline
    ↓
Sales rep follows up from within Odoo
```

### Partner Matching

When the mail plugin creates a lead, it attempts to match the email sender to an existing contact in Odoo:

1. The plugin calls `mail_plugin.contact/search_read` to find a `res.partner` with a matching email.
2. If a match is found, the `partner_id` is passed to the lead creation endpoint.
3. If no match is found, the lead is created without a `partner_id`, and the email address is stored in `email_from`.

The `partner_id` matching is powerful because it links the lead to the full contact record, including:
- Company information (`partner_id.parent_id`)
- Previous lead and opportunity history
- Contact address and phone numbers
- Sales team assignment rules (via `partner_id.team_id`)

### Email Content Logging

Beyond lead creation, the mail plugin supports logging email content as internal notes on existing leads. This is enabled through the `mail.content.log` mechanism:

1. User selects a lead in the CRM view.
2. User clicks "Log Email" in the mail plugin.
3. The plugin sends the email body to Odoo's `mail.message` endpoint.
4. A `mail.message` record is created with `model='crm.lead'` and `res_id=<lead_id>`.
5. The message appears in the lead's chatter as an internal note.

The `crm_mail_plugin` module does not implement this directly — it relies on the base `mail_plugin` infrastructure. However, the `description` field on `crm.lead` can also be used for storing email content, as the `generic_thread_message` method appends email body to this field.

## Mail Plugin Base Architecture

To understand `crm_mail_plugin`, it helps to understand the `mail_plugin` base module that it extends.

### `MailPluginController`

The base controller (`mail_plugin.controllers.mail_plugin.MailPluginController`) provides:

- **`_get_contact_data(partner)`**: Returns contact information for the sidebar panel.
- **`_mail_content_logging_models_whitelist()`**: Returns models that support mail content logging.
- **`_translation_modules_whitelist()`**: Returns modules whose terms are loaded for the plugin's translation interface.
- **`_handle_partner_thread(partner, thread_model, thread_id, message)**`: Handles email logging to a partner's thread.
- **`generic_thread_message()`**: Generic handler for logging messages to any model.

### Extension Pattern Used by `crm_mail_plugin`

Unlike `project_mail_plugin` (which extends all three `_get_*` methods), `crm_mail_plugin` does not extend the controller at all. Instead, it extends the `crm.lead` model with the deprecated `_form_view_auto_fill` method. This is because:

1. **CRM lead creation is handled differently**: The mail plugin's generic `generic_thread_message()` endpoint is used for CRM lead creation, not a custom controller method.
2. **No contact panel data needed**: Unlike projects (where you want to see existing tasks in the sidebar), CRM leads do not have a natural "list of related leads per contact" that needs to appear in the email sidebar. The workflow is primarily one-directional: email -> lead.
3. **Minimal module design**: The module only needs to provide the backward-compatible form action, which it does through the model extension.

## Compatibility Notes

### Odoo Version Compatibility

The `_form_view_auto_fill()` method is marked as deprecated **as of saas-14.3**. In Odoo 19, this method is retained but should not be used for new development. The preferred approach for Odoo 19+ is:

```python
# Modern approach: Use the mail plugin's JSON-RPC directly
# No server-side method needed; the plugin handles lead creation via:
# env['crm.lead'].create({
#     'name': email_subject,
#     'email_from': email_from,
#     'description': email_body,
#     'partner_id': partner_id,  # optional
# })
```

### Outlook vs. Gmail Plugin

Both the Outlook add-in and the Gmail extension use the same `mail_plugin` base controller. The `crm_mail_plugin` module works with both plugins without modification because they share the same API contract.

## Business Impact

### Sales Response Time

The primary business benefit is dramatically faster lead capture. Sales representatives who receive inbound emails can create a lead in seconds without switching to the Odoo CRM interface. Studies consistently show that faster lead response time correlates with higher conversion rates in B2B sales.

### No Lead Loss

By embedding lead creation directly in the email workflow, the module eliminates the "I'll add it to Odoo later" pattern that results in lost leads. The email and the lead are created in one action.

### Contact History Linkage

When the email sender is matched to an existing Odoo contact (`partner_id`), the new lead automatically connects to the contact's existing history in Odoo. This gives sales reps immediate context: has this contact interacted with us before? What opportunities exist? This 360-degree view is a significant advantage over standalone email marketing tools.

### Pipeline Accuracy

Because leads are created from actual email correspondence, the CRM pipeline more accurately reflects real business activity than leads entered manually. Marketing and sales management can trust the pipeline data for forecasting and reporting.

## Configuration

### Enabling the Mail Plugin

1. Install `crm_mail_plugin` (and its dependencies: `crm`, `mail_plugin`).
2. Configure the Outlook add-in: go to **Settings > Integrations > Outlook Add-in** and follow the OAuth setup instructions.
3. Configure the Gmail extension: go to **Settings > Integrations > Gmail Add-in** and follow the setup instructions.
4. Assign the `mail_plugin` group to users who need access: **Settings > Users > Access Rights**.

### Lead Assignment Rules

To automatically assign newly created leads to the right salesperson:

1. Go to **CRM > Configuration > Lead Assignment**.
2. Create or edit assignment rules based on territory, product line, or contact company.
3. The mail plugin respects these rules when creating leads — the assignment is computed at creation time based on the contact's attributes.

## Related

- [Modules/crm](Modules/CRM.md) — CRM base module: lead, opportunity, pipeline, team
- [Modules/mail_plugin](Modules/mail_plugin.md) — Mail plugin base: Outlook/Gmail add-in infrastructure
- [Modules/project_mail_plugin](Modules/project_mail_plugin.md) — Project equivalent: email-to-task conversion
- [Modules/crm_livechat](Modules/crm_livechat.md) — CRM + Livechat integration
- [Modules/crm_helpdesk](crm_helpdesk.md) — CRM + Helpdesk integration

## Real-World Scenarios

### Scenario 1: Inbound Inquiry Conversion

A sales rep receives an email from a new prospect (no existing Odoo contact):
1. In Outlook, they click "Create Lead" in the mail plugin sidebar.
2. The plugin extracts the sender's email and creates a `crm.lead` with:
   - `email_from`: prospect's email
   - `name`: email subject
   - `description`: email body
3. The lead appears in the CRM pipeline as "New" stage.
4. The sales rep follows up from Odoo, converting the lead to an opportunity when qualified.

### Scenario 2: Existing Contact Follow-Up

A sales rep receives an email from a contact that already exists in Odoo:
1. The mail plugin recognizes the email address and matches it to `res.partner`.
2. The lead is created with `partner_id` pre-populated.
3. The lead inherits the contact's company, sales team, and assigned salesperson.
4. The CRM's assignment rules apply automatically.

### Scenario 3: Email Thread Logging

An existing opportunity is being negotiated. The prospect sends an email with updated requirements. The sales rep:
1. Opens the lead in Odoo.
2. Uses the mail plugin to "Log Email" on the lead.
3. The email body is appended to the lead's `description` field and a `mail.message` is created.
4. The full email history is visible in the lead's chatter, providing a complete audit trail.

## How Mail Logging Works (Deep Dive)

The mail content logging feature (enabled by the whitelist mechanism) works as follows:

```
Email received in Outlook
    ↓
User selects lead in CRM and clicks "Log Email" in mail plugin
    ↓
Mail plugin sends POST to /mail_plugin/message_post
    ↓
mail_plugin.generic_thread_message() called
    ↓
Creates mail.message record:
    - model = 'crm.lead'
    - res_id = lead_id
    - body = email body (HTML sanitized)
    - message_type = 'email'
    ↓
Chatter updated in real-time
    ↓
Lead description field optionally updated
```

The `description` field on `crm.lead` is an HTML field and can store formatted email content. However, most implementations prefer to keep the description clean and rely on the `mail.message` records in chatter for the full email history.

## Performance Considerations

### Lead Creation from Email

Creating a lead from an email is a lightweight operation — it creates a single `crm.lead` record. The mail plugin batches multiple operations in a single request to minimize round trips.

### Contact Matching

The contact matching process in the mail plugin (which resolves email addresses to `res.partner` records) uses a standard Odoo `search()` query on `email_from`. For organizations with large contact databases, this query should be fast because `email_from` is indexed in the standard `res.partner` model.

### Caching

The mail plugin caches contact data in the Outlook session to avoid re-fetching on every email. The cache is invalidated when:
- A new contact is created in Odoo.
- A contact's data is updated.
- The user switches to a different email thread.

## Testing the Integration

When testing `crm_mail_plugin` and its integration with the mail plugin, validate:

1. **Lead creation from email**: Create a lead from an email, verify fields are populated correctly.
2. **Partner matching**: Send an email from a known contact, verify `partner_id` is correctly linked.
3. **Email logging**: Log an email on an existing lead, verify it appears in chatter.
4. **Backward compatibility**: Verify `_form_view_auto_fill()` still works for older plugin versions.
5. **Access control**: Verify users without CRM access cannot create leads via the plugin.

## Comparison with Other Mail-Plugin Modules

| Feature | `crm_mail_plugin` | `project_mail_plugin` |
|---------|-------------------|----------------------|
| Create records from email | Lead | Task |
| View related records in sidebar | No | Yes (task list) |
| Search for existing records | No | Yes (project search) |
| Create related records | No | Yes (project creation) |
| Log email as note | Yes (via mail_plugin) | Yes (via description) |
| Controller override | No | Yes (3 methods) |
| Backward compatibility method | `_form_view_auto_fill()` | None |

The project plugin is architecturally richer because tasks have a natural list-per-contact pattern (multiple tasks per partner), while leads are fundamentally individual records without a natural "list per partner" aggregation.

## Related

- [Modules/crm](Modules/CRM.md) — CRM base: lead, opportunity, stage, team, assignment rules
- [Modules/mail_plugin](Modules/mail_plugin.md) — Mail plugin base: Outlook/Gmail add-in, generic thread messaging
- [Modules/project_mail_plugin](Modules/project_mail_plugin.md) — Project equivalent: task creation and project search
- [Modules/crm_iap_lead](crm_iap_lead.md) — IAP-based lead generation from website forms
- [Modules/crm_helpdesk](crm_helpdesk.md) — CRM + Helpdesk: ticket-to-lead conversion
