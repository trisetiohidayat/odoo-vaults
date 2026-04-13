---
tags:
  - survey_crm
  - survey
  - crm
  - lead-generation
  - bridge-module
---

# Survey CRM

## Overview

- **Technical Name**: `survey_crm`
- **Name**: Survey CRM
- **Category**: Marketing/Surveys
- **Summary**: Generate CRM leads from survey responses
- **Depends**: `survey`, `crm`
- **Auto-install**: `True` (installs automatically when both `survey` and `crm` are present)
- **License**: LGPL-3
- **Author**: Odoo S.A.

## Description

Bridge module between `survey` and `crm`. When participants select specific answers marked as "lead-generating" in a survey, a CRM opportunity is automatically created with the participant's contact details and a full HTML-formatted description of their survey responses.

## File Structure

```
survey_crm/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── crm_lead.py          # Extends crm.lead
│   ├── crm_team.py          # Extends crm.team
│   ├── survey_question.py   # Extends survey.question
│   ├── survey_question_answer.py  # Extends survey.question.answer
│   ├── survey_survey.py     # Extends survey.survey
│   └── survey_user_input.py # Extends survey.user_input
├── views/
│   ├── survey_question_views.xml
│   ├── survey_survey_views.xml
│   └── survey_user_views.xml
└── demo/
    ├── lead_qualification_survey_demo.xml
    └── lead_qualification_answer_demo.xml
```

## Architecture

`survey_crm` uses **classic extension** (`_inherit`) across five models. It is a **pure bridge module** — it adds fields and methods but no new business logic beyond lead creation. The module is **auto-install** (`True`), meaning it is installed automatically when both `survey` and `crm` are in the installed modules chain, with no manual intervention required.

## Data Files

### XML Data (views)
- `views/survey_question_views.xml` — Adds `generate_lead` boolean to the suggested answer form
- `views/survey_survey_views.xml` — Adds lead count stat button, team_id field, and lead indicator on survey list/kanban
- `views/survey_user_views.xml` — Adds "Lead" button on survey response form

### Demo Data
- `demo/lead_qualification_survey_demo.xml` — Creates the "Let's connect!" demo survey with 12 questions covering company info, sector, headcount, and matrix question. Three suggested answers have `generate_lead=True`: "Manufacturing/Industry" (sector question), "100 - 499" (headcount question), and the "Yes" column of the matrix question.
- `demo/lead_qualification_answer_demo.xml` — Creates a pre-completed `survey.user_input` with lines for all questions, linked to partner `base.res_partner_address_4` (Floyd Steward). This response does NOT trigger lead creation because none of the selected answers have `generate_lead=True`.

---

## Models

### `survey.survey` (Survey)

Extends `survey.survey` (defined in `survey` module). Adds CRM-specific fields and two action methods.

#### Fields Added

**`generate_lead`** — `Boolean`, **stored**, computed

```
compute='_compute_generate_lead'
depends: survey_type, question_ids
```

True when the survey `survey_type` is `'survey'`, `'live_session'`, or `'custom'` **and** at least one question has `generate_lead=True`. This field is stored, so the value is written to the DB and recomputed only when `survey_type` or any `question_ids.generate_lead` changes.

> **Why this field exists**: Provides a cheap O(1) check whether a survey can generate leads, used to conditionally render the `team_id` field and the lead stat button in views.

**`lead_count`** — `Integer`, **stored**, computed

```
compute='_compute_lead_count'
depends: lead_ids
```

Counts leads via a `_read_group` call with an explicit `has_access('read')` guard. If the current user lacks CRM read access (e.g., a survey administrator who is not in the Sales group), `lead_count` is set to 0 rather than raising an AccessError.

> **Why `has_access('read')` check**: Prevents AccessError when a user without CRM read permissions views the survey form (e.g., a marketer editing survey questions). The stat button would otherwise crash for unauthorized users.

**`lead_ids`** — `One2many('crm.lead', 'origin_survey_id')`

Inverse of `crm.lead.origin_survey_id`. Used for the stat button and for the `lead_count` compute.

**`team_id`** — `Many2one('crm.team')`, indexed `btree_not_null`

```
index='btree_not_null'
ondelete='set null'
invisible="not generate_lead"  (view)
```

The sales team to which leads generated from this survey will be assigned. Only visible when `generate_lead=True` in the form view. The `btree_not_null` index is used because Odoo's ORM generates a partial index only on non-null values for `Many2one` fields with this index type — this optimizes the `_compute_lead_count` read-group query which filters on `origin_survey_id IN (...)`.

#### Methods

**`@api.depends('survey_type', 'question_ids')` `_compute_generate_lead()`**

```python
def _compute_generate_lead(self):
    for survey in self:
        survey.generate_lead = (
            survey.survey_type in ['survey', 'live_session', 'custom']
            and any(q.generate_lead for q in survey.question_ids)
        )
```

Explicitly depends on `survey_type` and `question_ids` (not `question_ids.generate_lead`) because Odoo's ORM invalidation on `suggested_answer_ids.generate_lead` already triggers recomputation through the question chain. This is the standard Odoo pattern for computed fields that depend on inverse chains.

**`@api.depends('lead_ids')` `_compute_lead_count()`**

```python
def _compute_lead_count(self):
    for survey in self:
        if self.ids and self.env['crm.lead'].has_access('read'):
            leads = self.env['crm.lead']._read_group(
                [('origin_survey_id', 'in', self.ids)],
                ['origin_survey_id'],
                ['__count']
            )
            # maps to survey.lead_count
        else:
            survey.lead_count = 0
```

Uses `_read_group` (which bypasses the `search` method's access rights checks) combined with an explicit `has_access('read')` guard. This is a performance optimization for batch reading multiple surveys at once (e.g., kanban view) — a single grouped query instead of N individual counts.

**`action_end_session()`** — overrides `survey.survey.action_end_session()`

```python
def action_end_session(self):
    super().action_end_session()
    user_inputs = self.user_input_ids.filtered(
        lambda ui: ui.create_date >= self.session_start_time)
    user_inputs._create_leads_from_generative_answers()
```

For live session surveys, called when a session ends (distinct from `_mark_done` which fires on every individual submission). Filters user inputs created since `session_start_time` and generates leads only for those new responses. This prevents re-creating leads for responses already processed during an earlier partial session.

> **Live session distinction**: `_mark_done()` is **not** called when a live session is in progress — only when the session is explicitly ended. This method bridges that gap.

**`action_survey_see_leads()`**

```python
def action_survey_see_leads(self):
    self.ensure_one()
    action = self.env['ir.actions.actions']._for_xml_id('crm.crm_lead_all_leads')
    action['context'] = dict(ast.literal_eval(action['context'] ...), create=False)
    action['domain'] = [('origin_survey_id', 'in', self.ids)]
    return action
```

Returns the CRM leads action filtered to this survey's leads. `create=False` in the context prevents users from manually creating leads from the list view (leads can only come from survey submissions). Uses `ast.literal_eval` with `.strip()` to safely parse the existing context string.

---

### `survey.question` (Survey Question)

Extends `survey.question`. Adds a computed `generate_lead` field that propagates up from suggested answers.

#### Fields Added

**`survey_type`** — `Selection`, **related** (not stored)

```python
survey_type = fields.Selection(related='survey_id.survey_type')
```

A related field mirroring `survey_id.survey_type`. Used in the view's `column_invisible` attribute on `generate_lead` in `survey.question.answer` — the "Create Leads" checkbox is only visible when the survey type is `'survey'`, `'live_session'`, or `'custom'`. Defined here (rather than directly in `survey_question_answer.py`) because the view `column_invisible` expression evaluates in the context of the current model.

**`generate_lead`** — `Boolean`, **stored**, computed

```
compute='_compute_generate_lead'
depends: question_type, suggested_answer_ids
```

True when the question type is `'simple_choice'`, `'multiple_choice'`, or `'matrix'` **and** at least one suggested answer has `generate_lead=True`. Non-choice question types (char_box, text_box, numerical_box, date, etc.) can never generate leads because there are no suggested answers to flag.

```python
@api.depends('question_type', 'suggested_answer_ids')
def _compute_generate_lead(self):
    for question in self:
        question.generate_lead = (
            question.question_type in ['simple_choice', 'multiple_choice', 'matrix']
            and any(answer.generate_lead for answer in question.suggested_answer_ids)
        )
```

> **Performance note**: The `depends` includes `suggested_answer_ids` (the full recordset), not `suggested_answer_ids.generate_lead`. Odoo recomputes whenever the suggested answers change at all (add/remove/modify), which is correct since `generate_lead` is a stored field.

---

### `survey.question.answer` (Suggested Answer)

Extends `survey.question.answer`. This is the **primary user-facing toggle** for lead generation.

#### Fields Added

**`generate_lead`** — `Boolean`, **not stored**

```python
fields.Boolean('Lead creation', help='Creates a lead when participants choose this answer')
```

When True, any survey submission containing this answer triggers lead creation. This field is **not stored** because it is not directly computed — the computation happens at the question level (`survey.question.generate_lead`) and at the response level (checking `answer.generate_lead` on each selected answer).

> **UX note**: The "Create Leads" column in the question form is hidden via `column_invisible` when `parent.survey_type not in ['survey', 'live_session', 'custom']`. This prevents confusion in quiz-mode surveys where lead generation is not applicable.

---

### `survey.user_input` (Survey Response)

Extends `survey.user_input`. The core model where submission triggers are handled and lead creation occurs.

#### Fields Added

**`lead_id`** — `Many2one('crm.lead')`

```
ondelete='set null'
```

Links a survey response to at most one CRM lead. `ondelete='set null'` means if the lead is deleted, the survey response record remains intact with a null `lead_id`. This is a **unidirectional one-to-one** relationship (a lead has `origin_survey_id` pointing back, but `crm.lead` has no `lead_ids` field).

#### Methods

**`_mark_done()`** — overrides `survey.user_input._mark_done()`

```python
def _mark_done(self):
    super()._mark_done()
    user_inputs = self.filtered(lambda ui:
        ui.survey_id.survey_type in ['survey', 'live_session', 'custom'])
    user_inputs._create_leads_from_generative_answers()
```

Called when a survey response is submitted and marked as done. Filters to only the survey types that support lead generation, then calls `_create_leads_from_generative_answers()`. The filter prevents unnecessary queries for quiz-type surveys.

> **Important distinction**: `_mark_done()` is **not** called during live sessions while they are in progress — only when a session is explicitly ended via `action_end_session()`. This is why `survey_survey.action_end_session()` also calls `_create_leads_from_generative_answers()` for live sessions.

**`_create_leads_from_generative_answers()`** — core lead creation logic

```python
def _create_leads_from_generative_answers(self):
    user_inputs_generating_leads = self.filtered(lambda ui:
        any(answer.generate_lead for answer in ui.user_input_line_ids.suggested_answer_id))
    user_inputs_grouped_by_survey = user_inputs_generating_leads.grouped('survey_id')

    lead_create_vals = {}
    for survey, user_inputs in user_inputs_grouped_by_survey.items():
        survey_lead_values = self._prepare_common_survey_lead_values(survey)
        for user_input in user_inputs:
            lead_create_vals[user_input] = (
                user_input._prepare_user_input_lead_values()
                | survey_lead_values  # dict merge
            )

    if lead_create_vals:
        leads = self.env['crm.lead'].sudo().create(list(lead_create_vals.values()))
        for user_input, lead in zip(lead_create_vals.keys(), leads):
            user_input.lead_id = lead
```

Key design decisions:
- **Batch creation**: Leads are created in a single `sudo().create()` call, then assigned to each `user_input.lead_id` in a post-processing loop. This is far more efficient than creating one lead at a time per response.
- **`sudo()` usage**: Required because the user completing the survey may not have CRM create permissions (e.g., a public/anonymous user or a survey admin). The CRM access rights are enforced at the survey configuration level, not at the submission level.
- **Pre-computed survey values**: `_prepare_common_survey_lead_values(survey)` is called once per survey, then merged with each user's individual values. This avoids repeating the UTM medium/source lookups for every response.
- **`grouped()` method**: Python 3.7+ dict insertion-order-preserving `dict.groupby`. Groups all responses by survey for batch processing across multiple surveys in a single call.

**`_prepare_common_survey_lead_values(survey)`**

```python
def _prepare_common_survey_lead_values(self, survey):
    salesperson = self.env['res.users']
    sales_team = survey.team_id or self.env['crm.team']
    if sales_team:
        salesperson = (
            self.survey_id.user_id
            if survey.team_id in self.survey_id.user_id.sudo().crm_team_ids
            else self.env['res.users']
        )
        if not salesperson:
            salesperson = survey.team_id.user_id or self.env['res.users']

    return {
        'medium_id': self.env['utm.medium']._fetch_or_create_utm_medium('Survey').id,
        'origin_survey_id': survey.id,
        'source_id': self.env['utm.mixin']._find_or_create_record('utm.source', survey.title).id,
        'team_id': sales_team.id,
        'type': 'opportunity',
        'user_id': salesperson.id,
    }
```

Salesperson assignment priority:
1. If `survey.team_id` is set and the survey's responsible user (`survey.user_id`) belongs to that team → assign that user
2. Else if `survey.team_id` is set → assign the team leader (`survey.team_id.user_id`)
3. Else → no user assigned (empty `res.users` record)

> **Security note**: Uses `.sudo()` when checking `crm_team_ids` because the survey responsible may not have CRM read access. The resulting `user_id` may be empty, which is valid — Odoo allows leads with no assigned salesperson.

UTM fields set:
- `medium_id`: Fetches or creates a UTM medium named "Survey" via `_fetch_or_create_utm_medium('Survey')` — ensures consistent tracking across all survey-generated leads.
- `source_id`: Creates a UTM source named after the survey title via `_find_or_create_record('utm.source', survey.title)`.

**`_prepare_user_input_lead_values()`**

```python
def _prepare_user_input_lead_values(self):
    self.ensure_one()
    input_lead_values = self._prepare_lead_values_from_user_input_lines()
    username = participant_name = self.partner_id.name or self.partner_id.email
    if not username:
        participant_name = input_lead_values['user_nickname'] or \
                          input_lead_values['public_user_mail'] or _('New')
    lead_contact_name = username or input_lead_values['user_nickname']
    lead_title = _('%(participant_name)s %(category_name)s results', ...)

    lead_values = {
        'contact_name': lead_contact_name,
        'description': input_lead_values['description'],
        'name': lead_title,
    }
    if self.partner_id.active:
        lead_values['partner_id'] = self.partner_id.id
    elif input_lead_values['public_user_mail']:
        lead_values['email_from'] = input_lead_values['public_user_mail']

    return lead_values
```

Lead title format: `"Floyd Steward survey results"` or `"New live session results"` for anonymous users.

Contact priority:
1. Authenticated partner name → `partner_id` set (links to existing CRM partner)
2. Authenticated partner email only → `partner_id` not set, but `email_from` populated
3. Public/anonymous user with email field in survey → `email_from` populated from char_box answer
4. Fully anonymous → `contact_name` from nickname or "New"

> **Active partner check**: `partner_id.active` guards against assigning leads to `odoobot` or `public` partner records. These system partners exist in the DB but should not be linked to CRM leads.

**`_prepare_lead_values_from_user_input_lines()`** — HTML description generation

```python
def _prepare_lead_values_from_user_input_lines(self):
    answers_by_question = self.user_input_line_ids.grouped('question_id')
    # Returns dict with 'description', 'user_nickname', 'public_user_mail'
```

Formats the full survey response as HTML for the lead description. Handles all question types:

| Question Type | Output Format |
|---|---|
| `simple_choice` | `<li>Question — Answer</li>` (with comma-separated for multiple) |
| `multiple_choice` | `<li>Question — Answer 1, Answer 2, Answer 3</li>` |
| `matrix` | `<li>Question<br/>&emsp;Row 1 — Col A<br/>&emsp;Row 2 — Col B</li>` |
| `char_box` | `<li>Question — Value</li>` (also extracts nickname/email) |
| `numerical_box` | `<li>Question — 42</li>` |
| `scale` | `<li>Question — 3</li>` |
| `date` | `<li>Question — 2026-01-15</li>` |
| `datetime` | `<li>Question — 2026-01-15 14:30:00</li>` |
| `text_box` | `<li>Question<br/>&emsp;Line 1<br/>&emsp;Line 2</li>` |
| Skipped | `<li>Question — <i>Skipped</i></li>` |

Special handling for `char_box`:
- If `save_as_nickname=True` on the question → value extracted as `user_nickname`
- If `validation_email=True` on the question → value extracted as `public_user_mail`

Markup/HTML safety:
- Uses `markupsafe.Markup` for all HTML construction
- Uses `markupsafe.escape()` on all user-provided values (question titles, answer values, text inputs) to prevent XSS
- Placeholder values (like `%(question_title)s`) are kept outside the `Markup()` constructor to ensure they are escaped

**`action_redirect_lead()`**

```python
def action_redirect_lead(self):
    self.ensure_one()
    action = self.env['ir.actions.act_window']._for_xml_id('crm.crm_lead_opportunities')
    action['views'] = [((self.env.ref('crm.crm_lead_view_form').id), 'form')]
    action['res_id'] = self.lead_id.id
    return action
```

Redirects to the CRM lead form view associated with this response. The button is only shown when `lead_id` is set (invisible when null). Uses `ensure_one()` to guard against being called on a recordset.

---

### `crm.lead` (Lead/Opportunity)

Extends `crm.lead`. The target model for survey-generated leads.

#### Fields Added

**`origin_survey_id`** — `Many2one('survey.survey')`, indexed `btree_not_null`

```
index='btree_not_null'
ondelete='set null'
```

Links the lead back to the source survey. The `btree_not_null` index optimizes reverse lookups from `survey.survey.lead_ids` and the `_compute_lead_count` read-group query. When a survey is deleted, leads retain their `origin_survey_id` as null rather than cascading delete.

> **Security consideration**: Because this field is added via `_inherit` (classic extension), any module can add or modify survey origin data on leads. Third-party integrations that create leads from surveys should populate `origin_survey_id` for consistency.

---

### `crm.team` (Sales Team)

Extends `crm.team`. Provides a reverse lookup of surveys assigned to each team.

#### Fields Added

**`origin_survey_ids`** — `One2many('survey.survey', 'team_id')`

Inverse of `survey.survey.team_id`. This is primarily for display/UI purposes — it allows viewing all surveys whose leads are routed to a given sales team from the team form view.

---

## Lead Creation Flow

```
Survey Response Submitted (survey.user_input._mark_done)
    │
    ├─► super()._mark_done()          [marks response as 'done']
    │
    ├─► Filter: survey_type in ['survey', 'live_session', 'custom']
    │
    └─► _create_leads_from_generative_answers()
            │
            ├─► Filter: any answer.generate_lead for any line
            │
            ├─► Group by survey_id
            │
            ├─► Per survey: _prepare_common_survey_lead_values()
            │       ├─► utm.medium 'Survey' (fetch_or_create)
            │       ├─► utm.source '<survey_title>' (find_or_create)
            │       └─► team_id + user_id assignment
            │
            ├─► Per response: _prepare_user_input_lead_values()
            │       ├─► contact_name (partner.nickname, char_box, or 'New')
            │       ├─► name ('<name> survey results')
            │       ├─► partner_id OR email_from
            │       └─► description (HTML from all answer lines)
            │
            ├─► Batch: env['crm.lead'].sudo().create([...])
            │
            └─► Post: user_input.lead_id = lead
```

**Live session variant**: When `survey_survey.action_end_session()` is called (instead of `_mark_done`):

```
Live Session Ended (survey.survey.action_end_session)
    │
    ├─► super().action_end_session()   [closes the session]
    │
    ├─► Filter: user_input.create_date >= session_start_time
    │
    └─► _create_leads_from_generative_answers()   [same as above]
```

This prevents re-processing responses that were already handled in a previous session end event.

---

## Cross-Module Integration

### UTM (UTM Tracking)
`survey_crm` integrates with `utm` (via the `survey` and `crm` dependencies):
- `utm.medium`: "Survey" medium is fetched/created for all survey leads, enabling consistent medium-level reporting in UTM dashboards.
- `utm.source`: A source record is created per survey title, allowing per-survey source attribution.

### CRM Lead Assignment
Leads are always created as `type='opportunity'` (never as raw leads). This reflects the assumption that a survey participant who explicitly selected a lead-generating answer has demonstrated sufficient intent to be treated as a qualified opportunity rather than an unqualified lead.

### Survey Types and Lead Generation

| Survey Type | Leads on Submit | Leads on Session End |
|---|---|---|
| `survey` | Yes | N/A (not a session) |
| `live_session` | No (session in progress) | Yes |
| `custom` | Yes | Yes (if shared as a link) |
| `quiz` | No | No |

---

## Performance Considerations

### Batch Operations
The `_create_leads_from_generative_answers()` method is designed for bulk processing. When multiple responses are submitted at once (e.g., batch survey invites), all leads are created in a single `sudo().create()` call. The `grouped()` call ensures O(n) grouping rather than nested O(n*m) loops.

### Stored Computed Fields
`generate_lead` on `survey.survey` and `survey.question`, and `lead_count` on `survey.survey`, are all stored (`store=True`). This avoids recomputing on every read and makes the kanban view load fast for surveys with many leads.

### Read Group for Lead Count
`_compute_lead_count` uses `_read_group` instead of `search_count` to avoid the access rights overhead of `search()` for every survey in a list view. The `has_access('read')` guard ensures no AccessError for non-CRM users viewing surveys.

### Database Indexes
Two fields carry explicit `index='btree_not_null'`:
- `survey.survey.team_id` — optimizes the lead count group-by and team-based lead routing queries
- `crm.lead.origin_survey_id` — optimizes the reverse lookup from survey → leads

---

## Security Considerations

### Lead Creation Permissions
`crm.lead.sudo().create()` bypasses CRM access rights. This is **intentional and correct**: survey respondents (who may be public users, portal users, or authenticated employees without CRM create rights) should be able to submit surveys that generate leads. Access control is enforced at the survey configuration level, not at the submission level.

### Partner Linking
The `partner_id.active` check prevents linking leads to system partner records:
```python
if self.partner_id.active:  # blocks odoobot, public partners
    lead_values['partner_id'] = self.partner_id.id
```
This prevents survey responses from being associated with internal system accounts.

### XSS Prevention
`_prepare_lead_values_from_user_input_lines()` uses `markupsafe.escape()` on all user-supplied values (question titles, answer text, text box content) before inserting them into the HTML description. This prevents stored XSS attacks where a malicious survey question or answer text could execute JavaScript in the CRM user's browser.

### Access Control on Views
The lead stat button on the survey form view uses `invisible="not (survey_type in [...] and lead_count != 0)"` — the button is hidden entirely if there are no leads, avoiding the need for a click-to-crash pattern.

---

## Edge Cases and Failure Modes

### Duplicate Lead Prevention
A single `survey.user_input` can have multiple answer lines with `generate_lead=True` (e.g., selecting multiple lead-generating options in a multiple_choice question). However, `_create_leads_from_generative_answers()` creates **exactly one lead per response** — it checks `any(answer.generate_lead ...)` (boolean OR), not a count of triggering answers. All triggering answers in the same response contribute to a single lead's description.

### Re-submission
If a survey allows multiple attempts (`is_attempts_limited=False` or `attempts_limit > 1`), each completed submission creates its own `survey.user_input` record. Each can independently trigger lead creation. There is no deduplication between attempts — a user who re-takes the survey and triggers lead-generating answers will generate a second lead.

### Session Restart
If `session_start_time` is modified (e.g., a new session starts after an old one), the `action_end_session` filter `create_date >= session_start_time` may miss or double-count responses. This is a known limitation — the session start time should be treated as an immutable marker.

### Survey Deletion After Lead Creation
When a `survey.survey` record is deleted, `crm.lead.origin_survey_id` is set to null (due to `ondelete='set null'` on the Many2one). The leads themselves are not deleted. The `survey.survey` table entry is removed, but the `lead_ids` one2many on any surviving copy of the survey would be null.

### Empty Team / No Salesperson
If `survey.team_id` is not set and neither the survey responsible nor the team leader can be assigned, `user_id` is set to `False` (empty res.users record). This results in a lead with no assigned salesperson, which is valid in CRM — unassigned leads can be routed later via assignment rules.

### Matrix Question with Multiple Selections
When a matrix question allows multiple selections per row and a user selects multiple columns, the code handles this by appending to the last answer entry with a comma separator:
```python
elif question.question_type == 'matrix' and row:  # multiple col selections
    answers[-1] += Markup(', %(col_value)s') % {'col_value': col_value}
```

---

## Related Models and Modules

- [Modules/survey](survey.md) — Base survey module (defines `survey.survey`, `survey.question`, `survey.user_input`)
- [Modules/CRM](CRM.md) — CRM lead management (defines `crm.lead`, `crm.team`)
- [Modules/website_crm](website_crm.md) — Website lead capture via contact form
- `utm` — UTM tracking mixin for `medium_id` and `source_id` on leads
