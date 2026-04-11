---
tags:
  - odoo
  - odoo19
  - modules
  - website
  - livechat
  - hr
  - recruitment
  - chatbot
description: >
  Bridge module that attaches a "Jobs Bot" chatbot to the /jobs page via im_livechat
  channel rules, guiding visitors through department selection, job recommendations,
  and HR agent handoff. Purely data-driven — zero Python code.
---

# website_hr_recruitment_livechat

## Overview

- **Name**: Website IM Livechat HR Recruitment
- **Technical Name**: `website_hr_recruitment_livechat`
- **Category**: Website/Live Chat
- **Version**: `1.0` (unchanged since Odoo 16+)
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Summary**: Attaches a "Jobs Bot" chatbot to the `/jobs` recruitment page via an `im_livechat.channel.rule`. Visitors are guided through department selection, shown matching job positions, offered live HR agent handoff, or invited to leave an email for follow-up.
- **Technical Type**: Purely data-driven module — **zero Python code files**. All behaviour is defined through one XML demo file (`noupdate="1"`) that creates records in the `im_livechat` and `chatbot` core models.
- **Demo Data**: `noupdate="1"` — protected from reinstall overwriting.

## Dependencies

```
depends = ['website_hr_recruitment', 'im_livechat']
```

| Dependency | Role |
|---|---|
| `website_hr_recruitment` | Provides the `/jobs` page, `hr.applicant`, `hr.job` models; must be installed for the URL regex `/jobs$` to match a real page |
| `im_livechat` | Provides the `chatbot.script`, `chatbot.script.step`, `chatbot.script.answer`, `im_livechat.channel`, `im_livechat.channel.rule` infrastructure |

There is no Python `__init__.py` import — no models, controllers, or wizard files exist. The module only seeds data on installation or demo data reset.

## Module Structure

```
website_hr_recruitment_livechat/
├── __init__.py           # Empty — no Python code
├── __manifest__.py       # Metadata + demo data declaration
└── data/
    └── website_hr_recruitment_livechat_chatbot_demo.xml   # All chatbot records (noupdate="1")
```

No `models/`, `controllers/`, `views/`, `security/`, `static/`, or `tests/` directories exist.

---

## L1: Business Flow — How Livechat Creates HR Conversations

### End-to-End Visitor Journey

```
1. Visitor opens /jobs on the website
2. im_livechat JS detects URL matches /jobs$
3. 2-second timer fires → livechat widget auto-opens
4. discuss.channel created → attached to "Jobs Bot" chatbot.script
5. Bot posts welcome message (sequence 1, free_input_single)
6. Bot asks department preference (sequence 2, question_selection)
   ├─ Sales
   ├─ Services
   └─ R&D
7. Visitor selects a department
8. Bot shows matching job description (text step) + HR chat offer
   ├─ "Yes please" → forward_operator step → HR agent forwarded
   │                     ├─ Operator available → live transfer
   │                     └─ No operator → email capture → thank you
   └─ "No, I'll discover" → redirect_link to job detail page
```

### What Gets Created in the Database

On module install (via demo data):

| Record Type | XML ID | Purpose |
|---|---|---|
| `chatbot.script` | `chatbot_script_website_hr_recruitment` | The "Jobs Bot" script definition |
| `chatbot.script.step` | 20+ records | All conversation steps (welcome, departments, jobs, HR handoff, email capture) |
| `chatbot.script.answer` | 8+ records | Selectable options (Sales, Services, R&D, Yes/No, etc.) |
| `im_livechat.channel.rule` | `website_hr_recruitmentlivechat_channel_rule_chatbot` | Trigger rule for `/jobs$` URL |
| `res.partner` (implicit) | auto-created by `chatbot.script#create()` | Bot operator partner (`active=False`) |

On each livechat session (runtime):

| Record Type | Purpose |
|---|---|
| `discuss.channel` | The livechat session between visitor and bot/HR |
| `discuss.channel.member` | Participant records for visitor, bot, and any HR agent |
| `mail.message` | Each chatbot message posted into the channel |
| `chatbot.message` | Per-step chatbot tracking, stores user raw answers |
| `mail.guest` | Anonymous visitor identity if not logged in |

**No `hr.applicant` record is auto-created.** The email captured via `question_email` is stored in `chatbot.message.user_raw_answer`. A separate bridge module (e.g., `hr_recruitment_livechat`, if it existed) would need to wire this to `hr.applicant#create()`.

---

## L2: Field Types, Defaults, Constraints

### `chatbot.script` Fields (from `im_livechat`)

The demo XML sets only two explicit fields on the script record. All others use `chatbot.script` defaults.

| Field | Value Set in Demo | Default (if not set) | Notes |
|---|---|---|---|
| `title` | `"Jobs Bot"` | required Char | Displayed in channel header |
| `image_1920` | `odoobot.png` | `False` | Bot avatar in chat widget |
| `active` | not set | `True` | Script is active |
| `first_step_id` | not set | auto-assigned to lowest sequence step | Entry point of script |
| `operator_partner_id` | not set | auto-created `res.partner` | The bot's identity |
| `script_step_ids` | not set directly | populated by step records via `chatbot_script_id` | Inverse of `chatbot.script.step.chatbot_script_id` |

### `im_livechat.channel.rule` Fields

```
id:              website_hr_recruitmentlivechat_channel_rule_chatbot
regex_url:       "/jobs$"
action:          "auto_popup"
auto_popup_timer: 2
chatbot_script_id: chatbot_script_website_hr_recruitment
channel_id:      im_livechat.im_livechat_channel_data
country_ids:     False (not set → applies globally)
sequence:        10  (default)
chatbot_enabled_condition: not set → defaults to "always"
```

| Field | Type | Default | Constraint |
|---|---|---|---|
| `regex_url` | Char | required | PostgreSQL `LIKE` pattern matched against `request.httprequest.path` |
| `action` | Selection | required | `"display_button"` \| `"auto_popup"` \| `"open_window"` |
| `auto_popup_timer` | Integer | `0` | Seconds before auto popup fires |
| `chatbot_script_id` | Many2one | required if `action` involves chatbot | Points to `chatbot.script` |
| `channel_id` | Many2one | required | The livechat channel to use |
| `country_ids` | Many2many | empty → all countries | Country filter for rule matching |
| `sequence` | Integer | `10` | Rules evaluated in ascending order |
| `chatbot_enabled_condition` | Selection | `"always"` | `"always"` \| `"only_if_no_operator"` \| `"only_if_operator"` |

### `chatbot.script.step` Step Types Used

| `step_type` | Demo Field Set | Behaviour |
|---|---|---|
| `free_input_single` | `message` | Accepts any single-line text input; no validation |
| `question_selection` | `message`, `answer_ids` | Presents `chatbot.script.answer` buttons; visitor selects one |
| `text` | `message` | Bot displays text; no input collected |
| `question_email` | `message` | Validates email via `email_normalize()`; stores in `user_raw_answer` |
| `forward_operator` | `message` | Transfers to a live HR agent; falls to next step if no agent available |

### `chatbot.script.answer` Fields

| Field | Demo Value | Notes |
|---|---|---|
| `name` | "Sales", "Services", "R&D", "Yes please!", "No I will discover by myself!" | Button label |
| `script_step_id` | parent step | The question this answer belongs to |
| `sequence` | 1, 2, 3 | Order among siblings |
| `redirect_link` | `/jobs/marketing-and-community-manager-6` etc. | For self-discovery paths; opens URL after step message |

---

## L3: Cross-Model Integration, Override Patterns, Workflow Triggers

### Cross-Model Relationship Diagram

```
im_livechat.channel.rule
    channel_id ──────────────► im_livechat.channel  (the livechat channel)
    chatbot_script_id ─────────► chatbot.script       (the Jobs Bot)
    regex_url ─────────────────► matched on page request

chatbot.script
    operator_partner_id ───────► res.partner         (auto-created, active=False)
    script_step_ids (1:N) ─────► chatbot.script.step (cascade delete)

chatbot.script.step
    chatbot_script_id ──────────► chatbot.script
    answer_ids (1:N) ───────────► chatbot.script.answer
    triggering_answer_ids (M:N) ► chatbot.script.answer (domain: sequence < current)

chatbot.script.answer
    script_step_id ─────────────► chatbot.script.step

Runtime records (created per session):
    discuss.channel ────────────► chatbot.script (via script_step_id on first message)
    discuss.channel.member ──────► discuss.channel + res.partner/mail.guest
    mail.message ────────────────► discuss.channel (each bot message)
    chatbot.message ─────────────► discuss.channel + chatbot.script.step
```

### Trigger Mechanism — How the Rule Fires

The entire automation lives in `im_livechat.channel.rule#match_rule()`:

```python
# im_livechat/models/im_livechat_channel.py (conceptual)
def match_rule(self, channel, url, country_id):
    domain = [
        ('channel_id', '=', channel.id),
        '|', ('country_ids', '=', False),  # global rules
             ('country_ids', 'in', country_id.ids),
        ('regex_url', '=', url),            # or '=like' depending on config
    ]
    return self.search(domain, order='sequence', limit=1)
```

1. `website_sale` controller renders the `/jobs` page with the livechat widget JS embedded.
2. JS reads the page URL (`/jobs`), fetches channel rules from `/im_livechat/channel_rule`.
3. The rule with `regex_url="/jobs$"` matches. The `$` anchor means exact match — `/jobs/marketing-and-community-manager-6` does **not** match.
4. `action="auto_popup"` + `auto_popup_timer=2` → JS opens the widget after 2 seconds.
5. `discuss.channel` created, linked to `channel_id` (the livechat channel).
6. `chatbot.script#_post_welcome_steps()` posts the welcome message as `mail.message` from the bot partner.

### `triggering_answer_ids` — The Answer Graph

```python
# chatbot.script.step — triggering_answer_ids field
triggering_answer_ids = fields.Many2many(
    'chatbot.script.answer',
    'chatbot_script_step_answer_rel',
    string='Triggers',
    domain="[('script_step_id.sequence', '<', sequence)]",
)
```

**Evaluation logic** in `chatbot.script.step#_fetch_next_step()`:
- Collects all `triggering_answer_ids` for the candidate step.
- If the visitor's selected answer is in that set → step is reachable.
- Multiple answers from the **same parent** → OR logic (any match suffices).
- The demo always sets single answers → simple one-to-one routing.

### `forward_operator` — The Handoff Flow

When the bot reaches a step with `step_type = "forward_operator"`:

1. `chatbot.script.step#_process_step()` calls `_forward_human_operator()` on the `discuss.channel`.
2. `discuss.channel` looks up an available operator on `channel_id` matching language/expertise.
3. **If available**: Creates a `discuss.channel.member` of type `"agent"` for the HR operator; bot member transitions from `"bot"` to history.
4. **If no operator available**: The `forward_operator` step does nothing (silent), and execution falls through to the next step in the XML order — which is the "no operator available" text message.
5. Email capture follows regardless.

---

## L4: Version Changes, Security, Extension Points

### Odoo 18 → 19 Changes

This module had **no Python code changes** between Odoo 18 and 19. It remains at version `1.0` with identical XML across both major versions.

However, the `im_livechat` and `chatbot` core framework received significant internal changes in Odoo 18 that affect this module's behaviour:

| Change | Odoo Version | Impact on This Module |
|---|---|---|
| `im_livechat.channel.rule` gained `chatbot_enabled_condition` field | Odoo 18 | Demo rule relies on default `"always"` — still correct. If a site sets `"only_if_no_operator"`, the chatbot would only fire when no HR agent is online. |
| `discuss.channel` now tracks `livechat_member_type` per member (`visitor`, `agent`, `bot`) | Odoo 18 | Enables clearer handoff states. The `forward_operator` step transitions bot → agent correctly. |
| `question_email` gained server-side email normalisation validation | Odoo 17 | Email capture always validated server-side in Odoo 19. |
| `operator_expertise_ids` added on `im_livechat.channel` for smart routing | Odoo 18 | Not used in demo, but could enable routing by job domain (e.g., R&D question → developer-skilled operator). |
| `chatbot.script.step` `triggering_answer_ids` domain changed from implicit to explicit `domain` attribute | Odoo 18 | No XML change needed — the demo answers all satisfy the domain `< sequence`. |
| `free_input_single` step type behaviour refined | Odoo 16 → 17 | Accepts free text; the demo uses it only for welcome (no answer processing). |

### Security Analysis

| Area | Analysis | Risk Level |
|---|---|---|
| **Data ownership** | Chatbot conversations are `discuss.channel` + `mail.message` records. Access controlled by `im_livechat` ACLs — `base.group_user` (internal) vs. public (livechat). Public visitors get a `mail.guest` session with limited access. | Low |
| **Email capture** | `question_email` stores the visitor's raw answer in `chatbot.message.user_raw_answer`. This is plain text. GDPR requires: (1) informing the visitor at step 1 that data is collected, (2) a privacy policy link, (3) the ability to request deletion. | Medium |
| **Bot partner** | `chatbot.script#create()` auto-creates a `res.partner` with `active=False` for the bot. This prevents it from appearing in `res.partner` searches or reports. | Low |
| **`noupdate="1"`** | All demo data is protected from reinstall overwriting. To reset: (1) manually delete records, or (2) upgrade module with `--demo-data`. | N/A |
| **URL regex** | The `regex_url="/jobs$"` pattern is matched server-side in `im_livechat.channel.rule#match_rule()`. Malformed regex could cause matching failures but not code injection. | Low |
| **Redirect links** | `redirect_link` fields point to hardcoded internal URLs (`/jobs/marketing-and-community-manager-6`). No user-supplied URL is used. | Low |
| **Image field** | `image_1920` loaded from `mail/static/src/img/odoobot.png` — internal asset path, not user-supplied. | Low |

### ACL Dependencies

The module itself creates no new models requiring ACL. However, the records it creates depend on access rights for:

| Model | ACL Required | Note |
|---|---|---|
| `chatbot.script` | Read | Created via demo data |
| `chatbot.script.step` | Read | Created via demo data |
| `chatbot.script.answer` | Read | Created via demo data |
| `im_livechat.channel.rule` | Write | Created via demo data |
| `discuss.channel` (runtime) | Read/Write | Runtime session records |
| `mail.message` (runtime) | Read/Write | Messages in livechat |
| `chatbot.message` (runtime) | Read/Write | Step tracking |

Public users need `im_livechat` public access (`base.group_public`). Authenticated website users inherit `base.group_user` ACL.

### Extension Points

#### Adding a New Department Branch

Duplicate the Services branch XML, replacing:
- `chatbot_script_website_hr_recruitment_department_<dept>` answer record
- All downstream steps, updating `triggering_answer_ids` to the new answer
- `redirect_link` in the "No" answer to point to the correct job page

#### Auto-Creating an HR Applicant from Email Capture

The demo does **not** link captured emails to `hr.applicant`. To implement:

```python
# Override in a new module: hr_recruitment_livechat
from odoo import models
from odoo.addons.im_livechat.models.chatbot_script_step import ChatbotScriptStep

class ChatbotScriptStepHr(models.Model):
    _inherit = 'chatbot.script.step'

    def _process_step(self, channel, message):
        super()._process_step(channel, message)
        if self.step_type == 'question_email':
            # Extract email and create applicant
            email = channel._chatbot_prepare_customer_values().get('email')
            if email:
                self.env['hr.applicant'].create({
                    'partner_name': channel._chatbot_prepare_customer_values().get('name', 'Unknown'),
                    'email_from': email,
                    'job_id': self._find_matching_job_id(),  # custom logic
                })
```

#### Changing the Trigger URL

| Pattern | Matches |
|---|---|
| `/jobs$` (current) | Exactly `/jobs` only |
| `/jobs/.+$` | `/jobs/marketing-and-community-manager-6` (job detail pages) |
| `/jobs.*` | All URLs starting with `/jobs` including sub-pages |

Modify `regex_url` in the `im_livechat.channel.rule` record to change trigger scope.

#### Smart Routing by Expertise (Odoo 18+)

After Odoo 18, `im_livechat.channel` supports `operator_expertise_ids`. To route R&D chatbot visitors to developers:

1. Add expertise records for each department.
2. Add `expertise_ids` to operators in the livechat channel.
3. The `forward_operator` step will automatically prefer operators with matching expertise.

---

## Related Modules

- [[Modules/im_livechat]] — Core livechat framework; `chatbot.script`, `discuss.channel`
- [[Modules/website_hr_recruitment]] — Website job board; provides `/jobs` page and `hr.applicant` model
- [[Modules/hr_recruitment]] — Backend recruitment; `hr.applicant`, `hr.job`, `hr.department`
- `crm_livechat` — Bridges chatbot email capture to CRM lead creation
- `helpdesk_livechat` — Bridges chatbot email/phone to helpdesk ticket creation
