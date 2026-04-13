# hr_recruitment_skills

> Recruitment - Skills Management | Odoo S.A. | LGPL-3 | Category: Human Resources/Recruitment

Bridges the [Modules/hr_skills](modules/hr_skills.md) skills taxonomy with the [Modules/hr_recruitment](modules/hr_recruitment.md) applicant pipeline. Allows recruiters to record skills and certifications on applicants, score applicants against job skill requirements, find matching candidates, and automatically provision `hr.employee.skill` records upon hiring.

**Auto-installs** when both `hr_skills` and `hr_recruitment` are present.

---

## Module Hierarchy

```
hr_skills          ← dependency (skills taxonomy: hr.skill, hr.skill.type, hr.skill.level, hr.job.skill)
hr_recruitment     ← dependency (hr.applicant, hr.job, hr.recruitment.degree)
└── hr_recruitment_skills   ← this module (skills on applicants, matching engine)
```

---

## Manifest

```python
{
    'name': 'Recruitment - Skills Management',
    'category': 'Human Resources/Recruitment',
    'sequence': 270,
    'version': '1.0',
    'summary': 'Manage skills of your employees',   # misleading — actually manages applicant skills
    'depends': ['hr_skills', 'hr_recruitment'],
    'data': [
        'security/hr_recruitment_skills_security.xml',
        'views/hr_applicant_views.xml',
        'views/hr_applicant_skill_views.xml',
        'views/hr_job_views.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_recruitment_skills/static/src/**/*',
        ],
    },
    'demo': [
        'data/hr_recruitment_skills_demo.xml',   # seeds skills on existing hr_recruitment demo applicants
    ],
    'installable': True,
    'auto_install': True,   # fires when hr_skills AND hr_recruitment are both installed
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

---

## Dependency Chain (Key Models Consumed)

| Model | Module | Role |
|---|---|---|
| `hr.skill` | [Modules/hr_skills](modules/hr_skills.md) | Skill ontology (name, type, active) |
| `hr.skill.type` | [Modules/hr_skills](modules/hr_skills.md) | Skill categories (Languages, Technical, Soft Skills, Certifications) |
| `hr.skill.level` | [Modules/hr_skills](modules/hr_skills.md) | Proficiency levels with `level_progress` (integer 0-100) |
| `hr.job.skill` | [Modules/hr_skills](modules/hr_skills.md) | Job required skills with required `level_progress` |
| `hr.applicant` | [Modules/hr_recruitment](modules/hr_recruitment.md) | Applicant record (extended) |
| `hr.job` | [Modules/hr_recruitment](modules/hr_recruitment.md) | Job position (extended) |
| `hr.recruitment.degree` | [Modules/hr_recruitment](modules/hr_recruitment.md) | Education level with `score` (float) |
| `hr.talent.pool` | `hr_recruitment_extended` | Talent pool applicant (linked via `pool_applicant_id`) |
| `hr.employee.skill` | [Modules/hr_skills](modules/hr_skills.md) | Employee skill (target when hiring) |

---

## Models

### `hr.applicant.skill` (New Model)

**`_name = 'hr.applicant.skill'`**
Inherits `hr.individual.skill.mixin` — the same abstract mixin used by `hr.employee.skill`. Shares all mixin fields and behaviors (versioning, archiving, deduplication). Adds only one own field.

#### Own Fields

| Field | Type | Attributes | Description |
|---|---|---|---|
| `applicant_id` | `Many2one(hr.applicant)` | `required=True`, `index=True`, `ondelete='cascade'` | Link back to the applicant. Cascade deletes child skills when applicant is deleted. |

#### Inherited Fields (from `hr.individual.skill.mixin`)

| Field | Type | Default | Description |
|---|---|---|---|
| `skill_id` | `Many2one(hr.skill)` | compute | Auto-set based on `skill_type_id`. Domain filters to that type. Required, `ondelete='cascade'` |
| `skill_level_id` | `Many2one(hr.skill.level)` | compute | Auto-set to `default_level` flag or first level for the type. Required |
| `skill_type_id` | `Many2one(hr.skill.type)` | `_default_skill_type_id()` | Defaults to first skill type in DB (or first certification type if `certificate_skill` context is set) |
| `level_progress` | `Integer` | `related='skill_level_id.level_progress'` | Read-only integer 0-100. Primary weighting in matching algorithms |
| `color` | `Integer` | `related='skill_type_id.color'` | Inherited from skill type for UI coloring |
| `valid_from` | `Date` | `fields.Date.today()` | Start of validity window |
| `valid_to` | `Date` | `False` | End of validity window. `False` = indefinite |
| `levels_count` | `Integer` | `related='skill_type_id.levels_count'` | How many levels this skill type has (controls badge visibility) |
| `is_certification` | `Boolean` | `related='skill_type_id.is_certification'` | `True` for certification-type skill types. Drives archiving vs. deletion behavior |
| `display_warning_message` | `Boolean` | compute | `True` when `valid_to < valid_from` — triggers UI warning banner |

#### Mixin Behavior: Skill Versioning

The mixin implements a **versioning-by-archiving** pattern rather than in-place updates:

- **Regular skills** (`is_certification=False`): Only one active skill per `skill_id` per applicant. Editing any field on an active skill archives it (`valid_to = yesterday`) and creates a new version with the new values. Adding a second entry for the same skill archives the first.
- **Certifications** (`is_certification=True`): Multiple concurrent certifications for the same `skill_id` are allowed as long as their `(skill_level_id, valid_from, valid_to)` tuples differ. Editing a certification preserves its original `valid_from`/`valid_to` dates rather than resetting them to today/`False`.
- **Deduplication**: Multiple identical CREATE commands in a single batch (same `(applicant_id, skill_id, valid_from, valid_to)`) collapse to a single record.
- **Delete vs. Archive**: Skills created within the last 24 hours are physically deleted on removal. Older skills are archived (`valid_to = yesterday`), never deleted — preserving audit history.

#### `_get_current_skills_by_applicant()`

```python
def _get_current_skills_by_applicant(self) -> dict[int, hr.applicant.skill]
```

Groups all records by `(applicant_id, skill_id)`, filters to currently valid records (no `valid_to` or `valid_to >= today`), then for certifications that have no valid entry, picks the most recently expired one (`max(valid_to)`).

Returns a dict mapping `applicant.id` -> `hr.applicant.skill` recordset (the current/active skills for that applicant).

**Called by** `hr.applicant._compute_current_applicant_skill_ids()` to populate the editable `current_applicant_skill_ids` one2many.

#### `_linked_field_name()`

```python
def _linked_field_name(self) -> str  # returns "applicant_id"
```

Mixin hook. Used by `_get_transformed_commands()`, `_create_individual_skills()`, and `_write_individual_skills()` to know which field links this skill record to its parent individual.

---

### `hr.applicant` (Extended)

**Inherits: `hr.applicant`** (from `hr_recruitment`)

Adds a **Skills** notebook tab, skill matching fields, and talent-pool synchronization hooks.

#### Fields Added

| Field | Type | Compute | Description |
|---|---|---|---|
| `applicant_skill_ids` | `One2many(hr.applicant.skill, 'applicant_id')` | — | Full history of all skill records (active + archived). `copy=True` so skills carry over on applicant duplication |
| `current_applicant_skill_ids` | `One2many(hr.applicant.skill)` | `_compute_current_applicant_skill_ids`, `readonly=False` | Active skills only. This is the editable one2many in the Skills tab UI. Write operations on this field are intercepted and transformed by `_get_transformed_commands()` |
| `skill_ids` | `Many2many(hr.skill)` | `_compute_skill_ids`, `store=True` | Denormalized set of `hr.skill` records linked to this applicant. Stored for efficient domain filtering in `action_search_matching_applicants` |
| `matching_skill_ids` | `Many2many(hr.skill)` | `_compute_matching_skill_ids` | Skills the applicant has that are also required by the matched job |
| `missing_skill_ids` | `Many2many(hr.skill)` | `_compute_matching_skill_ids` | Skills required by the matched job that the applicant does not have |
| `matching_score` | `Integer` | `_compute_matching_skill_ids` | Percentage 0-100 of job requirements met (rounded). Displayed as a gauge widget on the Skills tab and as a progress bar in applicant list views |

#### `_compute_current_applicant_skill_ids()`

```python
@api.depends("applicant_skill_ids")
def _compute_current_applicant_skill_ids(self):
```

Reads all `applicant_skill_ids` for the current batch of applicants and calls `_get_current_skills_by_applicant()` in bulk (one query), then assigns results per applicant.

**L3**: `applicant_skill_ids` must be in the depends because `_get_transformed_commands` modifies `applicant_skill_ids` directly — recomputation must fire to reflect those changes in the editable `current_applicant_skill_ids`.

#### `_compute_skill_ids()`

```python
@api.depends("applicant_skill_ids.skill_id")
def _compute_skill_ids(self):
```

Flattens `applicant_skill_ids` to a unique set of `hr.skill` records. Stored for use in the domain of `action_search_matching_applicants`:

```python
('skill_ids', 'in', self.job_skill_ids.skill_id.ids)
```

#### `_compute_matching_skill_ids()`

```python
@api.depends_context("matching_job_id")
@api.depends("current_applicant_skill_ids", "type_id", "job_id",
             "job_id.job_skill_ids", "job_id.expected_degree")
def _compute_matching_skill_ids(self):
```

**Context variable**: `matching_job_id` (int) — allows computing matching scores for a *different* job than `applicant.job_id`. Used when viewing applicants from the "Matching Applicants" action where `active_id` is a job, not an applicant.

**Algorithm**:

```
job_total = sum(job.job_skill_ids.mapped("level_progress")) + (job.expected_degree.score * 100)
job_skill_map = {js.skill_id: js.level_progress}  # required skill -> required progress

applicant_total = sum(
    min(skill.level_progress, job_skill_map[skill.skill_id] * 2)
    for skill in matching_applicant_skills
) + (applicant.type_id.score * 100 if job.expected_degree.score > 1 else 0)

matching_score = round(applicant_total / job_total * 100) if job_total else 0
```

**Key observations**:
- Each matched skill contributes `min(applicant_progress, 2 * required_progress)`. The `*2` cap means an applicant with double the required level gets full credit for that skill — prevents over-weighting ultra-qualified candidates.
- Degree score is included in `applicant_total` only if `job.expected_degree.score > 1` — if the job's required degree has a score of 0 or 1, degree is ignored in matching. Covered by test `test_job_with_no_skills_and_degree_with_score_zero`.
- `matching_skill_ids` = job skills that appear in `current_applicant_skill_ids`.
- `missing_skill_ids` = job skill IDs minus `matching_skill_ids`.

**L4 Performance**: This compute method calls `filtered()` on `current_applicant_skill_ids` and multiple `mapped()` calls. On large applicant batches (displaying 200+ rows), `matching_job_id` context forces re-computation per applicant row against a single `matching_job`. Consider batching the job skill map lookup if performance issues arise.

#### `_get_employee_create_vals()`

```python
def _get_employee_create_vals(self):
    vals = super()._get_employee_create_vals()
    vals["employee_skill_ids"] = [
        (0, 0, {
            "skill_id": applicant_skill.skill_id.id,
            "skill_level_id": applicant_skill.skill_level_id.id,
            "skill_type_id": applicant_skill.skill_type_id.id,
        })
        for applicant_skill in self.applicant_skill_ids
    ]
    return vals
```

Overrides the `hr.applicant` hook to provision `hr.employee.skill` records when an employee is created from an applicant. Called by `action_create_employee()` / `create_employee_from_applicant()`.

**L3**: Iterates `applicant_skill_ids` (all history, including expired skills), not `current_applicant_skill_ids`. Expired skills are transferred to the employee — preserves full history. Confirmed by test `test_create_employee_from_skilled_applicant`.

#### `_map_applicant_skill_ids_to_talent_skill_ids(vals)`

```python
def _map_applicant_skill_ids_to_talent_skill_ids(self, vals):
```

Handles **one-way applicant -> talent pool synchronization**. When `hr_recruitment_extended` is installed, applicants can have a `pool_applicant_id` pointing to a `hr.talent.pool` applicant. This method remaps ORM commands from the real applicant's `applicant_skill_ids` to the talent's `applicant_skill_ids`.

The core challenge: skill record IDs are **unique per applicant**. `arabic` skill on applicant A has a different DB ID from `arabic` skill on the talent. Direct `write()` would fail. The method instead:
- `Command.UPDATE` on applicant -> `Command.UPDATE` on talent using `talent_skills[applicant_skill_id]` lookup
- `Command.UPDATE` (new skill on applicant, not on talent) -> `Command.create` with correct `skill_id`/`skill_type_id`
- `Command.DELETE` -> `Command.delete` on talent
- `Command.CREATE` -> passed through unchanged

Tested in 14 test cases in `TestRecruitmentSkills`: add, update, delete, and one-way isolation in both directions.

#### `action_add_to_job()`

```python
def action_add_to_job(self):
```

Moves the current applicant to the job identified by `context.get('matching_job_id')` and sets them to stage `hr_recruitment.stage_job0` (New stage). Returns the standard applicant list action re-scoped to the new job.

Called from the "Move to this Job Position" button in the Matching Applicants list view.

#### `create(vals_list)` — Override

```python
@api.model_create_multi
def create(self, vals_list):
    if not self:
        for vals in vals_list:
            vals["applicant_skill_ids"] = (
                vals.pop("current_applicant_skill_ids", [])
                + vals.get("applicant_skill_ids", [])
            )
    return super().create(vals_list)
```

Merges `current_applicant_skill_ids` into `applicant_skill_ids` before calling `super()`. Required because the UI writes to `current_applicant_skill_ids` (editable computed field) but the actual stored one2many is `applicant_skill_ids`. The `if not self:` guard prevents infinite recursion on the ORM batch dispatch.

#### `write(vals)` — Override

```python
def write(self, vals):
    if "current_applicant_skill_ids" in vals or "applicant_skill_ids" in vals:
        skills = vals.pop("current_applicant_skill_ids", []) + vals.get("applicant_skill_ids", [])
        original_vals = vals.copy()
        original_vals["applicant_skill_ids"] = skills
        vals["applicant_skill_ids"] = self.env["hr.applicant.skill"]._get_transformed_commands(
            skills, self
        )
        for applicant in self:
            if applicant.pool_applicant_id and (not applicant.is_pool_applicant):
                mapped_skills = applicant._map_applicant_skill_ids_to_talent_skill_ids(original_vals)
                applicant.pool_applicant_id.write({"applicant_skill_ids": mapped_skills})
    return super().write(vals)
```

Intercepts any write to either `current_applicant_skill_ids` or `applicant_skill_ids`, calls `_get_transformed_commands()` to apply the mixin's versioning/archiving logic, then triggers talent pool sync if applicable.

---

### `hr.job` (Extended)

**Inherits: `hr.job`** (from `hr_skills` which already extends `hr.job` from `hr_recruitment`)

#### Fields Added

| Field | Type | Compute | Group | Description |
|---|---|---|---|---|
| `applicant_matching_score` | `Float` | `_compute_applicant_matching_score` | `hr_recruitment.group_hr_recruitment_interviewer` | Score 0-100 of the applicant currently active in the form context. Hidden when no `active_applicant_id` in context |

#### `_compute_applicant_matching_score()`

```python
@api.depends_context("active_applicant_id")
def _compute_applicant_matching_score(self):
```

Reads the single applicant from `context['active_applicant_id']` (populated by the "Matching Positions" action on the applicant form) and computes the same matching algorithm as `hr.applicant._compute_matching_skill_ids()`, writing the result onto each `hr.job` record in the set.

This is the reverse computation — displayed on the Job form to show how well the *currently viewed applicant* matches this job.

#### `action_search_matching_applicants()`

```python
def action_search_matching_applicants(self):
```

Returns a scoped `ir.actions.act_window` that opens the applicant list view filtered to applicants with matching skills from *other* jobs:

```python
domain = [
    ('job_id', '!=', self.id),                           # exclude current job's own applicants
    ('skill_ids', 'in', self.job_skill_ids.skill_id.ids), # has at least one matching skill
]
context = {'matching_job_id': self.id}                   # triggers _compute_matching_skill_ids
```

**UI**: Uses a custom list view (`crm_case_tree_view_inherit_hr_recruitment_skills`) that adds a "Move to this Job Position" button per row, displays `matching_skill_ids` and `missing_skill_ids` as tag widgets, and shows `matching_score` as a progress bar.

**L3**: The domain uses `skill_ids` (stored `Many2many`) for the initial broad filter. The `matching_score` and `matching_skill_ids`/`missing_skill_ids` are then computed in the view via `matching_job_id` context.

**Registered as** a `ir.actions.server` bound to the `hr.job` form via `action_applicant_search_applicant` in `hr_applicant_views.xml`.

---

## Skill Matching Algorithm

```
matching_score = round(applicant_total / job_total * 100)

where:
  job_total        = sum(job_skill.level_progress) + (job.expected_degree.score * 100)
  job_skill_map    = {skill_id -> job_skill.level_progress}

  applicant_total  = sum(min(applicant_skill.level_progress, job_skill_map[skill_id] * 2))
                   + (applicant.type_id.score * 100)   [only if job.expected_degree.score > 1]
```

**Score cap per skill**: `min(applicant_progress, 2 * required_progress)`. An applicant with 80 progress against a 40-required skill scores 40, not 80. Prevents over-qualified candidates from dominating the score.

**Degree weighting**: Degree contributes `type_id.score * 100`. For a degree with `score=0.5`, this adds up to 50 points to the job total and applicant total. If `expected_degree.score <= 1`, degree is excluded entirely.

---

## Skill Versioning and Archiving Logic (Mixin)

Located in `hr.individual.skill.mixin` (from `hr_skills`, reused by `hr.applicant.skill`).

### `_create_individual_skills(vals_list)`

Transforms a list of CREATE command values into a combination of CREATE, WRITE (archive), and UNLINK commands:
1. Searches for existing active skills for the same `(linked_field, skill_id)`.
2. For **regular skills**: if an active skill for the same `skill_id` exists, archives it (`valid_to = yesterday`) before creating the new one.
3. For **certifications**: checks for identical `(skill_id, skill_level_id, valid_from, valid_to)` to prevent exact duplicates. Different date ranges are allowed.
4. Deduplicates identical CREATE commands within the same batch.
5. Returns: `[archive_commands...] + [[0, 0, new_vals]...]`

### `_write_individual_skills(commands)`

Transforms WRITE commands on individual skill records:
- If only "passive" fields are modified (`valid_from`/`valid_to`) -> standard write.
- If `skill_type_id`, `skill_id`, `skill_level_id`, or the linked field are modified -> archives the old record and creates a new one.
- For certifications: `valid_from`/`valid_to` are preserved from the original; for regular skills: `valid_from = today`, `valid_to = False`.

### `_expire_individual_skills()`

Called for UNLINK commands or when archiving:
- Skills with `valid_from >= yesterday` (created in last 24h) -> **deleted** (`[2, id]`).
- Older skills -> **archived** with `valid_to = yesterday` (`[1, id, {'valid_to': yesterday}]`).
- Handles overlapping constraint check before archiving: if archiving would create an overlap with another existing skill, the conflicting record is deleted instead.

### `_get_transformed_commands(commands, individuals)`

Top-level orchestrator called from `hr.applicant.write()`. Separates commands into updated, unlinked, and created groups, calls the three methods above, and concatenates results.

---

## Security

### Record Rules

| Rule | Model | Group | Domain |
|---|---|---|---|
| `hr_applicant_skill_interviewer_rule` | `hr.applicant.skill` | `hr_recruitment.group_hr_recruitment_interviewer` | Applicant is in user's `interviewer_ids` (via `job_id.interviewer_ids` OR `applicant_id.interviewer_ids`) |
| `hr_applicant_skill_officer_rule` | `hr.applicant.skill` | `hr_recruitment.group_hr_recruitment_user` | `(1, '=', 1)` — full access |

**Interviewer scoping**: Interviewers see skills only for applicants they are assigned to interview. This requires a join through `hr.applicant` -> `job_id.interviewer_ids` or `applicant_id.interviewer_ids`. `hr_recruitment.group_hr_recruitment_interviewer` has full CRUD via the CSV `perm_write: 1`.

### Access Control (CSV)

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
hr_recruitment_skills.access_hr_applicant_skill_interviewer,
  access_hr_applicant_skill_interviewer,
  hr_recruitment_skills.model_hr_applicant_skill,
  hr_recruitment.group_hr_recruitment_interviewer,
  1,1,1,1                                           # full CRUD for interviewers

access_hr_job_skill_recruitment_user,
  hr.job.skill.recruitment.user,
  hr_skills.model_hr_job_skill,
  hr_recruitment.group_hr_recruitment_user,
  1,1,1,1                                           # recruitment users manage job skills
```

### Field-Level Groups

| Field | Group Required | Reason |
|---|---|---|
| `hr.job.applicant_matching_score` | `hr_recruitment.group_hr_recruitment_interviewer` | Sensitive matching analytics |
| `hr.job.current_job_skill_ids` (inherited) | `!hr.group_hr_user, !hr_recruitment.group_hr_recruitment_interviewer` | Hidden from plain users and interviewers; shown to recruitment officers |

### `matching_score` Visibility

Displayed to all authenticated users in the applicant list view via the progress bar widget. No explicit group restriction. This may be a privacy consideration for roles without recruitment access.

---

## UI Integration

### Applicant Form View

- Inherits `hr_recruitment.hr_applicant_view_form` and adds a **Skills** notebook page.
- Uses the `skills_one2many` widget (from `hr_skills` web component) bound to `current_applicant_skill_ids`.
- List rows show `skill_type_id`, `skill_id`, `skill_level_id`, and `level_progress` as a progress bar.
- Row decorations: muted (expired), danger (expiring within 7 days), warning (expiring within 1 month).
- Right column: `matching_score` gauge widget (`skill_match_gauge_field`) showing percentage match to `job_id`.
- Gauge hidden for talent pool applicants (`invisible="is_pool_applicant"`).

### Applicant List View (Standard)

- Inherits `hr_recruitment.crm_case_tree_view_job`.
- Adds `matching_score` as a progress bar column (invisible when falsy).

### Matching Applicants List View

- Custom view `crm_case_tree_view_inherit_hr_recruitment_skills` (primary extension).
- "Move to this Job Position" button in the list header.
- Columns: `partner_name`, `matching_score`, `matching_skill_ids` (many2many_tags), `missing_skill_ids` (many2many_tags).
- Hides: `application_status`, `priority`, `partner_phone`, `categ_ids`.
- Search panel: `applicant_skill_ids` added as a filterable field.
- Group by filter: `groupby_skills` groups applicants by their skill set.

### Job Form View

- Inherits `hr_skills.view_hr_job_form`.
- `current_job_skill_ids` field visibility restricted: hidden from plain `base.group_user` and `hr_recruitment.group_hr_recruitment_interviewer` — only recruitment officers (`hr_recruitment.group_hr_recruitment_user`) see it.

### Matching Positions Action

`action_find_matching_job` is a `ir.actions.act_window` bound to `hr.applicant` form that opens the job list with `context = {'active_applicant_id': active_id}`. This context populates `hr.job.applicant_matching_score` on each job record as the recruiter views them from within an applicant form.

---

## Talent Pool Synchronization

When `hr_recruitment_extended` is installed, each `hr.applicant` can have a `pool_applicant_id` pointing to a `hr.talent.pool` applicant (which shares the `hr.applicant` model).

**Direction**: One-way, applicant -> talent only. Changes on the talent do **not** propagate to the applicant.

**Behavior**:
- Adding a skill on the applicant creates the same skill on the linked talent.
- Updating a skill level on the applicant updates the talent's corresponding skill.
- Deleting a skill from the applicant deletes the talent's corresponding skill.
- Adding/editing/deleting on the talent has no effect on the applicant.
- When an applicant is created from a talent (`job.add.applicants` wizard), skills are **copied** from talent to new applicant, not moved — confirmed by `test_applicant_from_talent_preserve_skills`.

---

## Demo Data

Loaded from `data/hr_recruitment_skills_demo.xml` (`noupdate="1"`):

Seeds `hr.applicant.skill` records on pre-existing `hr_recruitment` demo applicants:

| Demo Applicant | Skills Added |
|---|---|
| `hr_case_mkt0` (Micheal) | English C2, French B2, Organizational (soft skill) |
| `hr_case_mkt1` (Micheal's child) | Organizational (soft skill) |
| `hr_case_salesman1` | French B1, English A1 |
| `hr_case_dev0` | Go Beginner, HTML Expert, CSS Expert |
| `hr_case_dev1` | Go Beginner, HTML Beginner, CSS Beginner |
| `hr_case_dev2` | Go Intermediate, Ruby Expert |

---

## Key Edge Cases and Failure Modes

### Overlap/Constraint Violations

`_check_not_overlapping_regular_skill()` fires on every `create`/`write`. Overlapping regular skills (same `(applicant_id, skill_id)` with intersecting validity windows) are rejected with a `ValidationError`. Also covers:
- Adding a skill that overlaps with an existing active skill.
- Adding a certification that has the exact same `(skill_id, skill_level_id, valid_from, valid_to)` as an existing certification.
- `valid_to < valid_from` rejected by `_check_date()`.

### Cascading Deletes

- Deleting an `hr.applicant` cascades to all `hr.applicant.skill` records.
- Deleting an `hr.skill` cascades to all `hr.applicant.skill` records referencing it.
- Deleting an `hr.skill.type` cascades to all skills of that type.
- Deleting an `hr.skill.level` cascades to all `hr.applicant.skill` records at that level.

### `matching_score = False` Conditions

Score is `False` (not 0) when:
- The job has neither `job_skill_ids` nor `expected_degree`.
- `job_total` is 0 (sum of `level_progress` + degree score is zero).
- The applicant has no `current_applicant_skill_ids`.

### `matching_job_id` Context Collisions

`_compute_matching_skill_ids` is called in two distinct contexts:
1. **Applicant form/list**: no `matching_job_id` -> matches against `applicant.job_id`.
2. **Matching Applicants action**: `matching_job_id` set in context -> matches against that job even if the applicant is linked to a different job.

Because `matching_job_id` is a context variable (not a stored field), the computation does not benefit from ORM invalidation tracking — it always recomputes when the context changes. This is acceptable since context is request-scoped.

### Talent Pool Applicant Flag

The `is_pool_applicant` check (`not applicant.is_pool_applicant`) prevents the write override from triggering talent sync when the record being written is *itself* the talent pool applicant. Only the "real" applicant propagates changes upward.

---

## Tags

#odoo #odoo19 #modules #recruitment #hr #skills
