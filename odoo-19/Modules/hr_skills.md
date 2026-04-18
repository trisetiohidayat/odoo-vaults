---
type: module
module: hr_skills
tags: [odoo, odoo19, hr, modules, skills, certification, resume]
created: 2026-04-06
updated: 2026-04-11
updated_details: |
  2026-04-11 — Upgraded version_change section (L4: Odoo 18→19) from brief
  summary to comprehensive 10-item breakdown verified against Odoo 19 CE source.
  Added items: Domain API migration, command transformation pipeline,
  technical_is_new_default pattern, PropertiesDefinition, formatted_read_grouping_sets
  override, dynamic date interpolation in certification report SQL view.
depth: L4
---

# Module: hr_skills

**Tags:** #odoo19 #hr #modules #skills #certification #resume

## Overview

The `hr_skills` module provides comprehensive skills management for employees in Odoo 19. It allows organizations to catalog skills, proficiency levels, certifications, and professional resume entries for employees. The module also integrates with job positions to define required skills for roles and can automatically create activities when certifications are missing or expiring.

**Technical Name:** `hr_skills`
**Category:** Human Resources/Employees
**Sequence:** 270
**Depends:** `hr`
**Auto Install:** True
**Application:** True
**License:** LGPL-3

## Module Structure

```
hr_skills/
├── models/
│   ├── hr_skill.py                      # hr.skill - Individual skill definition
│   ├── hr_skill_type.py                 # hr.skill.type - Skill category/type
│   ├── hr_skill_level.py                # hr.skill.level - Proficiency levels
│   ├── hr_individual_skill_mixin.py     # Abstract mixin - Core skill logic
│   ├── hr_employee_skill.py             # hr.employee.skill - Employee skill record
│   ├── hr_job_skill.py                  # hr.job.skill - Job required skills
│   ├── hr_employee.py                   # hr.employee extension
│   ├── hr_employee_public.py            # hr.employee.public extension
│   ├── hr_job.py                        # hr.job extension
│   ├── hr_resume_line.py                # hr.resume.line - Professional entries
│   ├── hr_resume_line_type.py           # hr.resume.line.type - Entry types
│   └── resource_resource.py             # resource.resource extension
├── report/
│   ├── hr_employee_skill_report.py      # SQL view: skill analytics
│   ├── hr_employee_certification_report.py  # SQL view: certification tracking
│   ├── hr_employee_skill_history_report.py  # SQL view: historical changes
│   └── hr_employee_cv_report.py         # QWeb report for CV PDF
├── wizard/
│   └── hr_employee_cv_wizard.py         # CV print configuration wizard
├── controllers/
│   └── main.py                          # /print/cv HTTP endpoint
└── tests/
    ├── test_employee_skill.py            # Skill creation/editing/archival tests
    ├── test_certification_activities.py  # Automatic activity creation tests
    ├── test_resource.py                  # Resource integration tests
    └── test_ui.py                        # UI tests
```

---

## Core Models

### 1. hr.skill.type (`hr.skill.type`)

**File:** `models/hr_skill_type.py`
**Description:** Represents a category or type of skill (e.g., "Programming Languages", "Certifications", "Soft Skills")

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | Char | Yes | - | Name of the skill type (translatable) |
| `active` | Boolean | No | True | Whether the skill type is active |
| `sequence` | Integer | No | 10 | Display order |
| `color` | Integer | No | Random(1-11) | Color code for UI display |
| `skill_ids` | One2many | - | - | Skills belonging to this type |
| `skill_level_ids` | One2many | - | - | Proficiency levels for this type |
| `levels_count` | Integer | - | - | Computed count of levels |
| `is_certification` | Boolean | No | False | Whether this type is a certification |

#### Key Behaviors

**Skill Type vs Certification:**
- Regular skill types (`is_certification=False`): Allow only ONE active skill per `skill_id` per employee at any time
- Certification types (`is_certification=True`): Allow MULTIPLE certifications with the same `skill_id` if they have different validity periods

#### Computed Fields

```python
@api.depends('skill_level_ids')
def _compute_levels_count(self):
    level_count_by_skill_type = dict(self.env['hr.skill.level']._read_group(
        domain=[('skill_type_id', 'in', self.ids)],
        groupby=['skill_type_id'],
        aggregates=['__count']
    ))
    for skill_type in self:
        skill_type.levels_count = level_count_by_skill_type.get(skill_type, 0)
```

**display_name computation:**
```python
def _compute_display_name(self):
    for skill_type in self:
        if skill_type.is_certification:
            skill_type.display_name = skill_type.name + "\U0001F396"  # Military Medal unicode
        else:
            skill_type.display_name = skill_type.name
```

#### Constraints

```python
@api.constrains('skill_ids', 'skill_level_ids')
def _check_no_null_skill_or_skill_level(self):
    incorrect_skill_type = self.env['hr.skill.type']
    for skill_type in self:
        if not skill_type.skill_ids or not skill_type.skill_level_ids:
            incorrect_skill_type |= skill_type
    if incorrect_skill_type:
        raise ValidationError(
            _("The following skills type must contain at least one skill and one level: %s",
              "\n".join(skill_type.name for skill_type in incorrect_skill_type)))
```

#### Onchange Methods

```python
@api.onchange('skill_level_ids')
def _onchange_skill_level_ids(self):
    for level in self.skill_level_ids:
        if level.technical_is_new_default:
            # When a level is set as default, unset all others
            (self.skill_level_ids - level).write({'default_level': False})
            level.technical_is_new_default = False
            break
```

#### Copy Method

```python
def copy_data(self, default=None):
    vals_list = super().copy_data(default=default)
    return [
        {
            **vals,
            "name": self.env._("%(skill_type_name)s (copy)", skill_type_name=skill_type.name),
            "color": 0,
            "skill_ids": [Command.create({"name": skill.name}) for skill in skill_type.skill_ids],
        }
        for skill_type, vals in zip(self, vals_list)
    ]
```

**When duplicating a skill type:**
- Name gets " (copy)" suffix
- Color resets to 0
- Skills are copied (new Command.create)
- Levels are NOT copied (user must redefine)

#### L3: Skill Type Configuration

**Configuring Proficiency Levels:**
1. Navigate to Settings > Skills > Skill Types
2. Click Create
3. Enter name and optionally check "Certification"
4. In the Skills tab, add individual skills (e.g., "Python", "JavaScript")
5. In the Levels tab, add proficiency levels with `level_progress` values:
   - Example for languages: A1 (10), A2 (30), B1 (50), B2 (70), C1 (90), C2 (100)
6. Mark one level as "Default Level" for auto-selection

**Setting Up Certification Types:**
1. Create skill type with `is_certification=True`
2. Add skills (e.g., "AWS Solutions Architect")
3. Add levels (e.g., "Associate", "Professional", "Specialty")
4. When creating employee certifications, multiple entries with the same skill but different validity dates are allowed

#### L4: Performance and Edge Cases

- `levels_count` is computed via `_read_group()` which is efficient for large datasets
- The `technical_is_new_default` field is non-stored and computed on-the-fly, preventing database writes for this UI state
- The random color assignment on creation provides visual variety without user configuration
- Copying skills but not levels forces the user to reconsider level configuration, which is intentional design

---

### 2. hr.skill.level (`hr.skill.level`)

**File:** `models/hr_skill_level.py`
**Description:** Represents a proficiency level within a skill type (e.g., "A2" for languages, "Expert" for programming)

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `skill_type_id` | Many2one | No | - | Parent skill type (index btree_not_null, cascade) |
| `name` | Char | Yes | - | Level name (e.g., "Beginner", "Intermediate") |
| `level_progress` | Integer | No | - | Progress percentage (0-100) |
| `default_level` | Boolean | No | False | Is this the default selection? |
| `technical_is_new_default` | Boolean | - | - | Technical field for frontend interaction |

#### Constraints

```python
_check_level_progress = models.Constraint(
    'CHECK(level_progress BETWEEN 0 AND 100)',
    'Progress should be a number between 0 and 100.',
)
```

**Constraint Failure Example:**
```python
# This would raise ValidationError:
level = env['hr.skill.level'].create({
    'skill_type_id': cert_type.id,
    'name': 'Invalid',
    'level_progress': 150  # Invalid - exceeds 100
})
# Error: "Progress should be a number between 0 and 100."
```

#### Key Behaviors

**Single Default Level Rule:**
- Only ONE level per skill type can have `default_level=True`
- When creating a new level with `default_level=True`, existing default levels are unset
- When updating an existing level to set `default_level=True`, other levels are automatically unset

#### Methods

**create() override:**
```python
@api.model_create_multi
def create(self, vals_list):
    skill_levels = super().create(vals_list)
    for level in skill_levels:
        if level.default_level:
            level.skill_type_id.skill_level_ids.filtered(
                lambda r: r.id != level.id
            ).default_level = False
    return skill_levels
```

**write() override:**
```python
def write(self, vals):
    res = super().write(vals)
    if vals.get('default_level'):
        self.skill_type_id.skill_level_ids.filtered(
            lambda r: r.id != self.id
        ).default_level = False
    return res
```

#### L3: Skill Level Validation

**Level Progress Semantics:**
- `level_progress` represents a percentage from 0% (no knowledge) to 100% (fully mastered)
- Used in reports for aggregation and visualization
- The `level_progress / 100.0` is used in the SQL view for reports

**Default Level Auto-Selection:**
- When a user selects a skill type in the employee skill form, the default level is auto-populated
- The `technical_is_new_default` flag (set by frontend) triggers the onchange to unset other defaults

**Creating Levels for New Skill Types:**
1. Navigate to the skill type form
2. Go to Levels tab
3. Add levels in ascending order of proficiency
4. Set `level_progress` for each (e.g., Beginner=25, Intermediate=50, Advanced=75, Expert=100)
5. Check "Default Level" on the intended starting level

**Example: Language Levels**
```
| Level | Progress | Description                          |
|-------|----------|--------------------------------------|
| A1    | 10       | Beginner - Basic expressions         |
| A2    | 30       | Elementary - Simple conversations    |
| B1    | 50       | Intermediate - Routine tasks          |
| B2    | 70       | Upper Intermediate - Complex topics  |
| C1    | 90       | Advanced - Complex abstract topics   |
| C2    | 100      | Mastery - Near-native proficiency     |
```

#### L4: Performance Implications

- The `index='btree_not_null'` on `skill_type_id` ensures efficient joins when filtering by skill type
- The `default_level` update on create/write requires a filtered search within the same skill type, which is efficient due to the index
- The `technical_is_new_default` computed field avoids database writes for transient UI state
- Using `filtered()` instead of search in the loop is efficient for small recordset sizes

---

### 3. hr.skill (`hr.skill`)

**File:** `models/hr_skill.py`
**Description:** Individual skill definitions (e.g., "Python", "Project Management")

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | Char | Yes | - | Skill name (translatable) |
| `sequence` | Integer | No | 10 | Display order within type |
| `skill_type_id` | Many2one | Yes | - | Parent skill type (index, cascade) |
| `color` | Integer | - | - | Related from skill_type_id.color |

#### Computed Methods

```python
@api.depends('skill_type_id')
@api.depends_context('from_skill_dropdown')
def _compute_display_name(self):
    if not self.env.context.get('from_skill_dropdown'):
        return super()._compute_display_name()
    for record in self:
        record.display_name = f"{record.name} ({record.skill_type_id.name})"
```

**Context-Based Display Name:**
- When `from_skill_dropdown` context is set, display name becomes `"Python (Languages)"` format
- Otherwise, uses default `name` field as display name
- This context is typically set in the skill selection dropdown widget

#### L3: Skill Definition

**Creating Skills:**
1. Navigate to Settings > Skills > Skills
2. Click Create
3. Select Skill Type
4. Enter Skill Name
5. Set Sequence for ordering
6. Save

**Skill Organization:**
- Skills are organized by Skill Type (category)
- Each skill belongs to exactly one type
- Skills within a type are ordered by `sequence`

#### L4: Performance Notes

- The `color` field is a related field, not stored, computed on-the-fly
- No performance concern as it's only computed when accessed
- The `index=True` on `skill_type_id` ensures efficient filtering by skill type
- The `_order = "sequence, name"` provides consistent ordering without requiring explicit sorting

---

### 4. hr.individual.skill.mixin (`hr.individual.skill.mixin`)

**File:** `models/hr_individual_skill_mixin.py`
**Description:** Abstract mixin providing the core skill management logic. Both `hr.employee.skill` and `hr.job.skill` inherit from this mixin.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `skill_id` | Many2one | Yes | - | The skill (cascade, domain by skill_type_id) |
| `skill_level_id` | Many2one | Yes | - | Proficiency level (domain by skill_type_id) |
| `skill_type_id` | Many2one | Yes | Default | Parent skill type |
| `level_progress` | Integer | - | - | Related from skill_level_id |
| `color` | Integer | - | - | Related from skill_type_id |
| `valid_from` | Date | No | Today | Validity start date |
| `valid_to` | Date | No | - | Validity end date (null = indefinite) |
| `levels_count` | Integer | - | - | Related from skill_type_id |
| `is_certification` | Boolean | - | - | Related from skill_type_id |
| `display_warning_message` | Boolean | - | - | Date validation warning |
| `certification_skill_type_count` | Integer | - | - | Count of cert skill types |

#### Computed Fields

```python
@api.depends('skill_type_id')
def _compute_skill_id(self):
    for record in self:
        if record.skill_type_id:
            record.skill_id = record.skill_type_id.skill_ids[0] if record.skill_type_id.skill_ids else False
        else:
            record.skill_id = False

@api.depends('skill_id')
def _compute_skill_level_id(self):
    for record in self:
        if not record.skill_id:
            record.skill_level_id = False
        else:
            skill_levels = record.skill_type_id.skill_level_ids
            record.skill_level_id = skill_levels.filtered('default_level') or skill_levels[0] if skill_levels else False
```

**Auto-selection Logic:**
1. When skill_type is set, the first skill in that type is auto-selected
2. When skill_id is set/changed, the default level (or first level) is auto-selected
3. This provides sensible defaults when creating skill records via the UI

#### L3: Skill vs Certification Behavior

This is the core business logic distinction in the module:

**Regular Skills:**
1. Only ONE active skill per `skill_id` is allowed at any time
2. When adding a new skill with the same `skill_id`, the previous one is ARCHIVED (valid_to set to yesterday)
3. Skills should NOT be deleted unless created within the last 24 hours
4. Skills should NOT be written to in-place; instead, archive and create new

**Certifications:**
1. MULTIPLE certifications with the same `skill_id` and `level_id` are allowed if their validity periods differ
2. Certifications can be deleted at any time
3. When updating a certification, it is ARCHIVED and a new one is created

**Active Skill/Certification Definition:**
- Active if `valid_to` is unset (NULL) OR `valid_to >= today`

#### Constraints

**Non-Overlapping Check:**
```python
@api.constrains(lambda self: ['valid_from', 'valid_to', 'skill_id', 'skill_type_id',
                              'skill_level_id', self._linked_field_name()])
def _check_not_overlapping_regular_skill(self):
```

This constraint validates that:
- For regular skills: No two active skills with the same `skill_id` can exist
- For certifications: No two certifications with identical `skill_id`, `skill_level_id`, `valid_from`, and `valid_to` can exist

**Date Validation:**
```python
@api.constrains('valid_from', 'valid_to')
def _check_date(self):
    if valid_to and valid_from > valid_to:
        raise ValidationError("valid_to cannot be before valid_from")
```

**Skill-Type Matching:**
```python
@api.constrains('skill_id', 'skill_type_id')
def _check_skill_type(self):
    # skill_id must belong to skill_type_id
```

**Skill-Level Matching:**
```python
@api.constrains('skill_type_id', 'skill_level_id')
def _check_skill_level(self):
    # skill_level_id must belong to skill_type_id
```

#### L4: Core Business Logic Methods

**`_get_overlapping_individual_skill()`:**

This method builds a domain to find overlapping skills and returns a dictionary mapping existing skills to conflicting new skills.

Key logic:
1. For certifications (if `_can_edit_certification_validity_period()` is True): Overlap is checked by exact `skill_id`, `skill_level_id`, `valid_from`, `valid_to`
2. For regular skills: Overlap is checked by `skill_id` AND date range intersection

```python
def _get_overlapping_individual_skill(self, vals_list):
    # Returns dict: {existing_skill: [conflicting_new_skills]}
```

**Overlap Detection Algorithm:**
```python
# For regular skills: Check if date ranges overlap
if (matching_ind_skill.valid_from <= new_ind_skill['valid_from'] and
    (not matching_ind_skill.valid_to or
     matching_ind_skill.valid_to >= new_ind_skill['valid_from']
    )) or (matching_ind_skill.valid_from <= new_ind_skill['valid_to'] and
           (not matching_ind_skill.valid_to or
            matching_ind_skill.valid_to >= new_ind_skill['valid_to']
           )):
    # Overlap detected
```

**`_expire_individual_skills()`:**

Archives skills by setting `valid_to` to yesterday, or deletes if recently created.

```python
def _expire_individual_skills(self):
    yesterday = fields.Date.today() - relativedelta(days=1)
    to_remove = self.env[self._name]
    to_archive = self.env[self._name]
    for individual_skill in self:
        if individual_skill.valid_from >= yesterday or (individual_skill.valid_to and individual_skill.valid_to <= yesterday):
            to_remove += individual_skill
        else:
            to_archive += individual_skill
    # Returns: [[2, id] for skills to delete] + [[1, id, {'valid_to': yesterday}] for skills to archive]
```

**Deletion vs Archival Logic:**
| Condition | Action |
|----------|--------|
| `valid_from >= yesterday` | DELETE (created in last 24 hours) |
| `valid_to <= yesterday` | DELETE (expired more than 24 hours ago) |
| Otherwise | ARCHIVE (set valid_to to yesterday) |

**`_create_individual_skills()`:**

Transforms CREATE commands to handle the archiving logic. When creating a new skill for an employee who already has an active skill with the same `skill_id`:
1. Archives the existing skill (sets valid_to to yesterday)
2. Creates the new skill with the provided values

```python
def _create_individual_skills(self, vals_list):
    # Input: [{linked_field, skill_id, skill_type_id, skill_level_id, ...}]
    # Output: [WRITE commands to archive] + [CREATE commands for new skills]
```

**`_write_individual_skills()`:**

Transforms WRITE commands:
- If core fields (skill_type_id, skill_id, skill_level_id, linked_field) are being modified, archives the current record and creates a new one
- Otherwise, behaves like standard write

```python
def _write_individual_skills(self, commands):
    # For CREATE (0): Calls _create_individual_skills
    # For WRITE (1): Calls _write_individual_skills (archives if core fields change)
    # For UNLINK (2): Calls _expire_individual_skills
```

**`_get_transformed_commands()`:**

Main entry point that orchestrates command transformation:
1. Separates CREATE, WRITE, and UNLINK commands
2. Handles mixed commands (same ID in both update and delete) by resetting updates
3. Returns unified list of transformed commands

```python
def _get_transformed_commands(self, commands, individuals):
    # Returns: [UNLINK commands] + [WRITE commands] + [CREATE commands]
```

#### L4: Performance Considerations

- All methods use efficient Domain API (Domain.AND, Domain.OR) for complex searches
- The `_can_edit_certification_validity_period()` check is done once at method entry
- Grouped lookups use `.grouped()` for efficient dictionary creation
- The `skills_to_archive._expire_individual_skills()` is called only once for all skills to archive

---

### 5. hr.employee.skill (`hr.employee.skill`)

**File:** `models/hr_employee_skill.py`
**Description:** Concrete implementation of `hr.individual.skill.mixin` for employees. Links individual skills to employees.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `employee_id` | Many2one | Yes | - | Employee record (index, cascade) |

#### Methods

```python
def _linked_field_name(self):
    return 'employee_id'

def get_current_skills_by_employee(self):
    # Returns dict: {employee_id: hr.employee.skill recordset}
    # Filters to only active skills (valid_to >= today OR valid_to is NULL)
    # For certifications without valid ones, returns the latest expired certification
```

**`get_current_skills_by_employee()` Logic:**
```python
def get_current_skills_by_employee(self):
    emp_skill_grouped = dict(self.grouped(lambda emp_skill: (emp_skill.employee_id, emp_skill.skill_id)))
    result_dict = defaultdict(lambda: self.env['hr.employee.skill'])
    for (employee, skill), emp_skills in emp_skill_grouped.items():
        # Filter to active skills
        filtered_emp_skill = emp_skills.filtered(
            lambda es: not es.valid_to or es.valid_to >= fields.Date.today()
        )
        if skill.skill_type_id.is_certification and not filtered_emp_skill:
            # No valid certification exists - return latest expired one
            expired_skills = (emp_skills - filtered_emp_skill)
            expired_skills_group_by_valid_to = expired_skills.grouped('valid_to')
            max_valid_to = max(expired_skills.mapped('valid_to'))
            result_dict[employee.id] += expired_skills_group_by_valid_to[max_valid_to]
            continue
        result_dict[employee.id] += filtered_emp_skill
    return result_dict
```

**Modal Actions:**
```python
def open_hr_employee_skill_modal(self):
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'hr.employee.skill',
        'res_id': self.id if self else False,
        'target': 'new',
        'context': {
            'show_employee': True,
            'default_skill_type_id': self.env['hr.skill.type'].search(
                [('is_certification', '=', True)], limit=1
            ).id
        },
        'views': [(self.env.ref('hr_skills.employee_skill_view_inherit_certificate_form').id, 'form')],
    }

def action_save(self):
    return {'type': 'ir.actions.act_window_close'}
```

#### L3: Employee Skill Rating

The `skill_level_id` field represents the proficiency rating. The `level_progress` (related to `skill_level_id.level_progress`) indicates the proficiency percentage.

**Adding Skills via Form:**
1. Open Employee form
2. Go to "Skills" page (or "Certifications" page)
3. Click Add
4. Select Skill Type
5. Select Skill
6. Select Level (proficiency rating)
7. Set validity dates (for certifications)
8. Save

**Rating Change Flow:**
When changing a skill's level:
1. The original skill record is archived (valid_to = yesterday)
2. A new skill record is created with the new level
3. Both records are preserved in history

#### L3: Skill Matching for Recruitment

The employee skill records can be used for:
- **Gap Analysis:** Compare employee skills against job-required skills
- **Candidate Matching:** Match job applicants against job requirements
- **Career Development:** Identify skill gaps for training plans

The `_add_certification_activity_to_employees()` method on `hr.employee` automatically creates activities when:
- Employee is assigned to a job with required certifications
- Employee lacks the required certification
- Employee's certification is expired or expiring within 3 months

#### L4: Edge Cases

**Expired Certifications with Valid Ones:**
If an employee has both a valid and expired certification for the same skill:
- Only the valid one appears in `current_employee_skill_ids`
- The expired one is preserved in `employee_skill_ids` for historical tracking

**Certification with Same Validity Period:**
If two certifications have identical `skill_id`, `skill_level_id`, `valid_from`, and `valid_to`:
- The constraint prevents creation of the second one
- Error message shows the conflicting record

**Multiple Expired Certifications:**
If there are multiple expired certifications for the same skill:
- The one with the most recent `valid_to` date is shown in current skills
- This ensures users see the most relevant certification history

---

### 6. hr.job.skill (`hr.job.skill`)

**File:** `models/hr_job_skill.py`
**Description:** Links required skills to job positions. Inherits from `hr.individual.skill.mixin`.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `job_id` | Many2one | Yes | - | Job position (index, cascade) |

#### Key Override

```python
def _can_edit_certification_validity_period(self):
    return False  # Job skills cannot edit certification validity
```

This means job skills behave like regular skills even if their skill type is marked as certification:
- Only one active skill per `skill_id` is allowed
- No overlapping certifications

#### L3: Job Skill Requirements

**Defining Job Skills:**
1. Open Job Position form
2. Go to "Skills" page
3. Add required skills with expected proficiency levels
4. Set validity requirements if needed

**Skill Requirements vs Employee Skills:**
- Job skills define what is NEEDED for the role
- Employee skills define what an employee HAS
- The `_add_certification_activity_to_employees()` method on `hr.employee` compares these to identify gaps

#### L4: Job Skill Behavior

Job skills do NOT use the certification validity logic because:
- Job requirements are about the proficiency level needed, not validity periods
- Multiple certification entries with different validity periods don't make sense for job requirements
- The `is_certification` flag on the skill type is ignored for job skills

---

### 7. hr.employee Extension

**File:** `models/hr_employee.py`
**Description:** Adds skill management capabilities to the HR employee model.

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `resume_line_ids` | One2many | Professional resume entries |
| `employee_skill_ids` | One2many | All employee skills |
| `current_employee_skill_ids` | One2many | Active skills only (computed) |
| `skill_ids` | Many2many | Skills summary (computed, stored) |
| `certification_ids` | One2many | Certification skills only (computed) |
| `display_certification_page` | Boolean | Whether to show certification tab (computed) |

#### Computed Fields

```python
@api.depends('employee_skill_ids')
def _compute_current_employee_skill_ids(self):
    current_employee_skill_by_employee = self.employee_skill_ids.get_current_skills_by_employee()
    for employee in self:
        employee.current_employee_skill_ids = current_employee_skill_by_employee[employee.id]

@api.depends('employee_skill_ids.skill_id')
def _compute_skill_ids(self):
    for employee in self:
        employee.skill_ids = employee.employee_skill_ids.skill_id

@api.depends('employee_skill_ids')
def _compute_certification_ids(self):
    for employee in self:
        employee.certification_ids = employee.employee_skill_ids.filtered('is_certification')

def _compute_display_certification_page(self):
    # True if at least one certification skill type exists
    self.display_certification_page = bool(self.env['hr.skill.type'].search_count(
        [('is_certification', '=', True)], limit=1
    ))
```

#### Create/Write Override

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        # Combine current_employee_skill_ids, certification_ids, and employee_skill_ids
        vals_emp_skill = vals.pop('current_employee_skill_ids', [])\
            + vals.pop('certification_ids', []) + vals.get('employee_skill_ids', [])
        vals['employee_skill_ids'] = self.env['hr.employee.skill']._get_transformed_commands(
            vals_emp_skill, self
        )
    return super().create(vals_list)

def write(self, vals):
    if 'current_employee_skill_ids' in vals or 'certification_ids' in vals or 'employee_skill_ids' in vals:
        vals_emp_skill = vals.pop('current_employee_skill_ids', []) + vals.pop('certification_ids', [])\
            + vals.get('employee_skill_ids', [])
        vals['employee_skill_ids'] = self.env['hr.employee.skill']._get_transformed_commands(
            vals_emp_skill, self
        )
    return super().write(vals)
```

#### L4: `_add_certification_activity_to_employees()`

This scheduled method creates `mail.activity` records for employees who need certifications for their jobs.

**Domain for Eligible Employees:**
```python
employee_domain = Domain.AND([
    Domain("job_id", "in", jobs_with_certification.ids),
    Domain.OR([
        Domain("user_id", "!=", False),
        Domain("parent_id.user_id", "!=", False),
        Domain("job_id.user_id", "!=", False),
    ]),
])
```

An employee is eligible if:
1. They are assigned to a job with required certifications
2. AND they have a responsible user (either themselves, their manager, or the job's responsible user)

**Activity Creation Logic:**
```python
for skill_level_key, summary in job_skill_level_mapping[job_id].items():
    if (employee.id, summary) in existing_activity_keys:
        continue  # Skip if activity already exists

    valid_to_date = employee_cert_data.get(employee, {}).get(skill_level_key)
    if valid_to_date is not None and (valid_to_date is False or valid_to_date > three_months_later):
        continue  # Skip if certification is valid and not expiring soon

    activity = employee.activity_schedule(
        act_type_xmlid="hr_skills.mail_activity_data_upload_certification",
        summary=summary,
        note="Certification missing or expiring soon",
        date_deadline=valid_to_date or today,
        user_id=responsible.id,
    )
```

**Triggered By:**
- Scheduled action running periodically (e.g., daily)
- Activity type: `hr_skills.mail_activity_data_upload_certification`

**Three Month Threshold:**
- Certifications expiring within 3 months trigger reminder activities
- `three_months_later = today + relativedelta(months=3)`
- This gives employees time to renew before expiry

#### L3: Resume Line History

The `get_internal_resume_lines()` method returns historical job titles for employees by querying `hr.employee.version_ids` (employee versioning system).

This is used in the CV report to show career progression with dates.

**Access Control:**
```python
if not self.env['hr.employee.public'].browse(res_id).has_access('read'):
    raise AccessError(self.env._("You cannot access the resume of this employee."))
```

---

### 8. hr.resume.line (`hr.resume.line`)

**File:** `models/hr_resume_line.py`
**Description:** Professional resume entries for employees (education, work experience, courses, etc.)

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `employee_id` | Many2one | Yes | - | Employee (cascade) |
| `name` | Char | Yes | - | Entry title (translatable) |
| `date_start` | Date | Yes | Today | Start date |
| `date_end` | Date | No | - | End date (null = current) |
| `duration` | Integer | No | - | Duration in days |
| `description` | Html | No | - | Detailed description |
| `line_type_id` | Many2one | No | - | Type of resume line |
| `is_course` | Boolean | No | - | Related from line_type_id |
| `course_type` | Selection | No | 'external' | Course delivery type |
| `color` | Char | No | '#000000' | Display color |
| `external_url` | Char | No | - | URL to course/certificate |
| `certificate_filename` | Char | No | - | Certificate file name |
| `certificate_file` | Binary | No | - | Certificate attachment |
| `resume_line_properties` | Properties | No | - | Custom properties |
| `avatar_128` | Image | - | - | Related from employee |
| `company_id` | Many2one | - | - | Related from employee |
| `department_id` | Many2one | - | - | Related from employee |

#### Constraints

```python
_date_check = models.Constraint(
    'CHECK ((date_start <= date_end OR date_end IS NULL))',
    'The start date must be anterior to the end date.',
)
```

#### Onchange Methods

**`_onchange_external_url()`:**
Auto-extracts website name from URL to set the `name` field:
```python
def _onchange_external_url(self):
    if not self.name and self.external_url:
        website_name_match = re.search(r'((https|http):\/\/)?(www\.)?(.*)\.', self.external_url)
        if website_name_match:
            self.name = website_name_match.group(4).capitalize()
```

**Example URL extraction:**
| Input URL | Extracted Name |
|-----------|----------------|
| `https://www.coursera.org/learn/python` | Coursera |
| `https://www.udemy.com/course/aws` | Udemy |

**Computed Fields:**
```python
@api.depends('course_type')
def _compute_external_url(self):
    for resume_line in self:
        if resume_line.course_type != 'external':
            resume_line.external_url = ''

@api.depends('course_type')
def _compute_color(self):
    for resume_line in self:
        if resume_line.course_type == 'external':
            resume_line.color = '#a2a2a2'
```

#### L3: Resume Entry Types

**Standard Types (from data/hr_resume_data.xml):**
- Education
- Work Experience
- Certifications
- Projects
- Trainings
- Mis

**Course Tracking:**
- When `line_type_id.is_course=True`, the entry is treated as a course
- External courses can have URLs and certificate file attachments
- Certificate files are stored as binary attachments

#### L4: Properties Definition

The `resume_line_properties` field uses a `PropertiesDefinition` from the line type:
```python
resume_line_type_properties_definition = fields.PropertiesDefinition('Sections Properties')
```

This allows different resume line types to have different custom property fields. For example:
- Education type might have: "University Name", "Degree", "GPA"
- Work Experience might have: "Company Name", "Manager Name"

---

### 9. hr.resume.line.type (`hr.resume.line.type`)

**File:** `models/hr_resume_line_type.py`
**Description:** Categorizes resume line entries.

#### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | Char | Yes | - | Type name (translatable) |
| `sequence` | Integer | No | 10 | Display order |
| `is_course` | Boolean | No | False | Is this a course type? |
| `resume_line_type_properties_definition` | PropertiesDefinition | No | - | Custom properties |

#### L3: Custom Resume Sections

Organizations can define custom resume line types with specific properties:
1. Create a new resume line type
2. Define custom properties (e.g., "University Name", "Degree")
3. When creating resume lines, these properties are available

---

## Reporting Models

### 10. hr.employee.skill.report (`hr.employee.skill.report`)

**File:** `report/hr_employee_skill_report.py`
**Description:** SQL view for skill analytics. Auto-generated table via `init()`.

**Inherits:** `hr.manager.department.report` (mixin for manager-based access)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Employee |
| `company_id` | Many2one | Company |
| `department_id` | Many2one | Department |
| `job_id` | Many2one | Job position |
| `skill_id` | Many2one | Skill |
| `skill_type_id` | Many2one | Skill type |
| `skill_level` | Char | Level name |
| `level_progress` | Float | Progress (0-1) |
| `active` | Boolean | Related from employee |

#### SQL View Definition

```sql
CREATE OR REPLACE VIEW hr_employee_skill_report AS (
    SELECT
        row_number() OVER () AS id,
        e.id AS employee_id,
        e.company_id AS company_id,
        v.department_id AS department_id,
        v.job_id AS job_id,
        s.skill_id AS skill_id,
        s.skill_type_id AS skill_type_id,
        sl.level_progress / 100.0 AS level_progress,
        sl.name AS skill_level
    FROM hr_employee e
    LEFT JOIN hr_version v ON e.current_version_id = v.id
    LEFT OUTER JOIN hr_employee_skill s ON e.id = s.employee_id
    LEFT OUTER JOIN hr_skill_level sl ON sl.id = s.skill_level_id
    LEFT OUTER JOIN hr_skill_type st ON st.id = sl.skill_type_id
    WHERE st.active IS True
      AND st.is_certification IS NOT TRUE
      AND s.valid_to IS NULL  -- Only active skills
)
```

#### L3: Using Skill Reports

**In Pivot View:**
The `formatted_read_grouping_sets()` method with `hierarchical_naming=False` provides flat department names for grouping.

**Available Aggregations:**
- `level_progress`: Average proficiency across employees/skills
- Group by: department, job, skill type, skill, level

---

### 11. hr.employee.certification.report (`hr.employee.certification.report`)

**File:** `report/hr_employee_certification_report.py`
**Description:** SQL view for certification tracking and expiry.

#### SQL View Definition

```sql
CREATE OR REPLACE VIEW hr_employee_certification_report AS (
    SELECT
        row_number() OVER () AS id,
        e.id AS employee_id,
        e.company_id AS company_id,
        v.department_id AS department_id,
        s.skill_id AS skill_id,
        s.skill_type_id AS skill_type_id,
        sl.level_progress / 100.0 AS level_progress,
        sl.name AS skill_level,
        (s.valid_to IS NULL OR s.valid_to >= today) AND s.valid_from <= today AS active
    FROM hr_employee e
    LEFT JOIN hr_version v ON e.current_version_id = v.id
    LEFT OUTER JOIN hr_employee_skill s ON e.id = s.employee_id
    LEFT OUTER JOIN hr_skill_level sl ON sl.id = s.skill_level_id
    LEFT OUTER JOIN hr_skill_type st ON st.id = sl.skill_type_id
    WHERE e.active AND st.active IS True AND st.is_certification IS TRUE
)
```

**Key Difference from Skill Report:**
- Includes ALL certifications (not just active ones)
- Has `active` boolean computed based on current date

#### L3: Expiry Tracking

Use this report to:
- Identify employees with expired certifications
- Plan recertification campaigns
- Track certification distribution by department

---

### 12. hr.employee.skill.history.report (`hr.employee.skill.history.report`)

**File:** `report/hr_employee_skill_history_report.py`
**Description:** Tracks skill changes over time, useful for skill trend analysis.

#### SQL View Definition

Uses a CTE-based approach with:
1. `individual_skill` CTE: Extracts skill validity data
2. `date_table` CTE: Collects all valid_from and valid_to dates
3. Main query: CROSS JOINs date_table with employee skills to show what skill was active at each date

**Key Insight:**
The `DISTINCT ON` clause ensures only the most recent skill entry is shown for each (date, employee, skill) combination.

#### L3: Historical Analysis

**Use Cases:**
- Track skill acquisition over time
- Identify skill trends in the organization
- Analyze skill development paths

---

## Supporting Models

### 13. hr.job Extension (`hr.job`)

**File:** `models/hr_job.py`
**Description:** Adds skill requirements to job positions.

#### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `job_skill_ids` | One2many | Required skills for the job |
| `current_job_skill_ids` | One2many | Active skills only (computed, searchable) |
| `skill_ids` | Many2many | Skills summary (computed, stored) |

#### Search Method

```python
def _search_current_job_skill_ids(self, operator, value):
    # Supports: 'in', 'not in', 'any' operators
    # For 'any': Allows domain filtering on skill attributes
```

**Example Usage in Domain:**
```python
# Find jobs requiring "Python" skill
[('current_job_skill_ids.skill_id', '=', python_skill_id)]

# Find jobs requiring skill level >= B1
[('current_job_skill_ids.skill_level_id.level_progress', '>=', 50)]
```

#### Create/Write Override

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        vals_job_skill = vals.pop("current_job_skill_ids", []) + vals.get("job_skill_ids", [])
        vals["job_skill_ids"] = self.env["hr.job.skill"]._get_transformed_commands(vals_job_skill, self)
    return super().create(vals_list)

def write(self, vals):
    if "current_job_skill_ids" in vals or "job_skill_ids" in vals:
        vals_job_skill = vals.pop("current_job_skill_ids", []) + vals.get("job_skill_ids", [])
        vals["job_skill_ids"] = self.env["hr.job.skill"]._get_transformed_commands(vals_job_skill, self)
    return super().write(vals)
```

---

### 14. hr.employee.public Extension

**File:** `models/hr_employee_public.py`
**Description:** Public-facing employee view with skill information (for portal users).

All skill fields are related from `employee_id`:
- `resume_line_ids`
- `employee_skill_ids`
- `current_employee_skill_ids`
- `certification_ids`
- `display_certification_page`

**Purpose:**
This model is used for portal access where users should see their own employee skill information without requiring full HR access.

---

### 15. resource.resource Extension

**File:** `models/resource_resource.py`
**Description:** Links employee skills to resource records.

```python
employee_skill_ids = fields.One2many(related='employee_id.employee_skill_ids')
```

---

## Wizard and Controller

### 16. hr.employee.cv.wizard (`hr.employee.cv.wizard`)

**File:** `wizard/hr_employee_cv_wizard.py`
**Description:** Wizard for configuring and printing employee CVs.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `employee_ids` | Many2many | - | Employees to include |
| `color_primary` | Char | Company primary_color | Primary theme color |
| `color_secondary` | Char | Company secondary_color | Secondary theme color |
| `show_skills` | Boolean | True | Include skills section |
| `show_contact` | Boolean | True | Include contact info |
| `show_others` | Boolean | True | Include uncategorized resume lines |
| `can_show_others` | Boolean | - | Computed: are there uncategorized lines? |
| `can_show_skills` | Boolean | - | Computed: do employees have skills? |

#### Computed Fields

```python
@api.depends('employee_ids')
def _compute_can_show_others(self):
    for wizard in self:
        wizard.can_show_others = wizard.employee_ids.resume_line_ids.filtered(lambda l: not l.line_type_id)
        wizard.can_show_skills = wizard.employee_ids.skill_ids
```

#### Action

```python
def action_validate(self):
    self.ensure_one()
    return {
        'name': _('Print Resume'),
        'type': 'ir.actions.act_url',
        'url': '/print/cv?' + url_encode({
            'employee_ids': ','.join(str(x) for x in self.employee_ids.ids),
            'color_primary': self.color_primary,
            'color_secondary': self.color_secondary,
            'show_skills': 1 if self.show_skills else None,
            'show_contact': 1 if self.show_contact else None,
            'show_others': 1 if self.show_others else None,
        })
    }
```

---

### 17. HrEmployeeCV Controller

**File:** `controllers/main.py`
**Description:** HTTP endpoint for printing CVs as PDF.

#### Route

```
/print/cv
```

**Parameters:**
- `employee_ids`: Comma-separated employee IDs
- `color_primary`: Primary color (hex)
- `color_secondary`: Secondary color (hex)
- `show_skills`: Include skills
- `show_contact`: Include contact
- `show_others`: Include others

#### Security

```python
@route(["/print/cv"], type='http', auth='user')
def print_employee_cv(self, employee_ids='', color_primary='#666666', color_secondary='#666666', **post):
    if not request.env.user._is_internal() or not employee_ids or re.search("[^0-9|,]", employee_ids):
        return request.not_found()

    if not request.env.user.has_group('hr.group_hr_user') and employees.ids != request.env.user.employee_id.ids:
        return request.not_found()
```

**Security Rules:**
1. User must be internal (not portal/public)
2. User must have valid employee_ids parameter (no SQL injection)
3. HR users can print any employee's CV
4. Non-HR users can only print their own CV

---

## L4: Odoo 18 to Odoo 19 Changes

This section documents every structural, API, and behavioral change between Odoo 18 and Odoo 19 for the `hr_skills` module. All items are verified against the Odoo 19 CE source at `odoo/addons/hr_skills/`.

### 1. `hr.manager.department.report` Mixin Added to Report Models

**Files changed:** `report/hr_employee_skill_report.py`, `report/hr_employee_certification_report.py`

In Odoo 18, both report models were plain `models.BaseModel` subclasses. In Odoo 19, they inherit from `hr.manager.department.report`:

```python
# Odoo 18
class HrEmployeeSkillReport(models.BaseModel):
    _name = 'hr.employee.skill.report'

# Odoo 19
class HrEmployeeSkillReport(models.BaseModel):
    _name = 'hr.employee.skill.report'
    _inherit = ["hr.manager.department.report"]
```

This mixin adds:
- `has_department_manager_access` computed field — True if the current user manages the employee's department
- Department-level ACL via record rule `hr_employee_skill_report_manager`
- Automatic read-group filtering so department managers only see their team's skill data

### 2. Domain API (Domain.AND, Domain.OR) Replaces Raw List Domains

**Files changed:** `models/hr_employee.py`, `models/hr_job.py`, `models/hr_individual_skill_mixin.py`

Every complex domain in Odoo 19 uses the `Domain` class instead of raw Python list syntax. This is a code-quality improvement — the ORM converts `Domain` objects back to list domains internally — but it makes intent explicit and avoids bracket-matching errors in deeply nested AND/OR clauses.

**Odoo 18 pattern (raw list):**
```python
domain = ['&',
    ('job_id', 'in', jobs.ids),
    '|',
    ('user_id', '!=', False),
    ('parent_id.user_id', '!=', False),
]
```

**Odoo 19 pattern (Domain API):**
```python
from odoo.fields import Domain

domain = Domain.AND([
    Domain("job_id", "in", jobs.ids),
    Domain.OR([
        Domain("user_id", "!=", False),
        Domain("parent_id.user_id", "!=", False),
    ]),
])
```

The `Domain` class provides `Domain(field, operator, value)` leaf nodes, `Domain.AND`/`Domain.OR` combinators, and `Domain.FALSE`/`Domain.TRUE` sentinels.

### 3. Scheduled Certification Activities: `_add_certification_activity_to_employees()`

**File added:** `data/ir_cron_data.xml`; method in `models/hr_employee.py`

A daily cron job automatically creates `mail.activity` records for employees who are missing required certifications for their job position, or whose certifications are expiring within 3 months.

**Cron registration:**
```xml
<record id="hr_job_skills_cron_add_certification_activity_to_employees" model="ir.cron">
    <field name="name"> hr: Add certification activity to employees</field>
    <field name="model_id" ref="model_hr_employee"/>
    <field name="state">code</field>
    <field name="code">model._add_certification_activity_to_employees()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
</record>
```

The method finds all jobs with `is_certification=True` skill requirements, finds employees in those jobs who have a responsible user, checks existing activities to avoid duplicates, and schedules a 5-day reminder with type `hr_skills.mail_activity_data_upload_certification`.

### 4. Employee Versioning: `hr_version` Join in SQL Views

**Files changed:** `report/hr_employee_skill_report.py`, `report/hr_employee_certification_report.py`

Odoo 19 introduced the employee versioning system (`hr.employee.version_ids`) for tracking career history. The skill report SQL views were updated to join through `current_version_id`:

```sql
-- Odoo 18: direct join to hr_department
LEFT JOIN hr_department d ON d.id = e.department_id

-- Odoo 19: indirect join through hr_version
LEFT JOIN hr_version v ON e.current_version_id = v.id
LEFT OUTER JOIN hr_department d ON d.id = v.department_id
```

The department in the skill report now reflects the employee's current job assignment via the versioning system, not a frozen field.

### 5. CV Report SCSS Styling via `web.report_assets_pdf`

**File changed:** `__manifest__.py` (assets section)

The CV PDF report uses SCSS for styling, loaded via the `web.report_assets_pdf` bundle:

```python
'assets': {
    'web.report_assets_pdf': [
        '/hr_skills/static/src/scss/report_employee_cv.scss',
    ],
}
```

Custom `primary_color` and `secondary_color` from company settings are passed through the wizard and applied as CSS variables in the QWeb template.

### 6. `resume_line_properties`: PropertiesDefinition Field

**File changed:** `models/hr_resume_line.py`, `models/hr_resume_line_type.py`

The `hr.resume.line` model gains a `resume_line_properties` field using Odoo's `PropertiesDefinition`:

```python
# In hr.resume.line.type
resume_line_type_properties_definition = fields.PropertiesDefinition('Sections Properties')

# In hr.resume.line
resume_line_properties = fields.Properties(
    'Properties',
    definition='line_type_id.resume_line_type_properties_definition',
)
```

This enables per-type custom fields on resume entries. For example, "Education" type could have "University Name" and "Degree", while "Work Experience" has "Company Name" and "Manager Name".

### 7. `technical_is_new_default`: Non-Stored Computed Field Pattern

**File changed:** `models/hr_skill_level.py`

A new pattern for frontend-to-backend communication without database writes:

```python
technical_is_new_default = fields.Boolean(
    compute="_compute_technical_is_new_default",
    readonly=False,  # writable but not stored
)

def _compute_technical_is_new_default(self):
    self.technical_is_new_default = False
```

The frontend sets this to `True` when a user clicks to make a level the new default. The `_onchange_skill_level_ids` on `hr.skill.type` detects this flag, unsets other defaults, and resets the flag — all without a database write.

### 8. `active` Field in Certification Report: Dynamic Date Interpolation

**File changed:** `report/hr_employee_certification_report.py`

The `active` boolean is computed directly in the SQL view using the server date:

```sql
(s.valid_to IS NULL OR s.valid_to >= '%(date)s') AND s.valid_from <= '%(date)s' AS active
```

The date is passed via `fields.Date.context_today(self)` through the `init()` method's formatting dict, keeping the `active` column current without requiring view recomputation.

### 9. Command Transformation Pipeline: `_get_transformed_commands()`

**File changed:** `models/hr_individual_skill_mixin.py` — entirely rewritten

The skill create/write/expire pipeline in this form is new in Odoo 19:

- Regular skill updates archive the old record and create a new one (never in-place write)
- Certifications allow overlapping date ranges when `_can_edit_certification_validity_period()` is `True`
- Deletion is deferred: only recently-created or already-expired skills are deleted; others are archived
- Mixed commands (same ID in both UPDATE and UNLINK) are detected and the UPDATE is discarded

This pipeline is called from both `hr.employee.create()`/`write()` and `hr.job.create()`/`write()`.

### 10. `formatted_read_grouping_sets` Override for Flat Department Names

**File changed:** `report/hr_employee_skill_report.py`

```python
@api.model
def formatted_read_grouping_sets(self, domain, grouping_sets, aggregates=(), *, order=None):
    self_contexted = self.with_context(hierarchical_naming=False)
    return super().formatted_read_grouping_sets(
        domain, grouping_sets, aggregates, order=order,
    )
```

Passes `hierarchical_naming=False` to the pivot renderer, preventing Odoo from displaying department names as "Company / Division / Sub-division" in the skills inventory pivot view.

---

## L4: Performance Considerations

### 1. SQL Views vs Computed Fields

The reporting models use SQL views (`_auto = False`, `init()` method) instead of computed fields because:
- They aggregate data across many records
- They support pivot/graph views efficiently
- They can be indexed and optimized by PostgreSQL

### 2. Domain API Efficiency

The extensive use of `Domain` class:
- Avoids string parsing overhead
- Provides type-safe domain construction
- Is optimized for complex domains

### 3. One2many with Domains

```python
employee_skill_ids = fields.One2many(
    'hr.employee.skill',
    'employee_id',
    domain=[('skill_type_id.active', '=', True)]
)
```

This domain filter is applied at the database level, improving performance when filtering inactive skill types.

### 4. Grouped Lookups

```python
def get_current_skills_by_employee(self):
    emp_skill_grouped = dict(self.grouped(lambda emp_skill: (emp_skill.employee_id, emp_skill.skill_id)))
```

The `.grouped()` method efficiently creates dictionaries from recordsets for O(n) complexity.

### 5. Indexing Strategy

| Field | Index Type | Purpose |
|-------|------------|---------|
| `skill_type_id` on hr_skill | btree | Fast skill type filtering |
| `employee_id` on hr_employee_skill | btree | Fast employee skill lookup |
| `skill_level_id.level_progress` | btree | Level-based filtering |

---

## L4: Security Concerns

### 1. Field-Level Security

```python
skill_ids = fields.Many2many(
    compute='_compute_skill_ids',
    store=True,
    groups="hr.group_hr_user"  # Only HR users can see all skills
)
```

Non-HR users cannot access the `skill_ids` field. This prevents regular employees from seeing the full skills list.

### 2. CV Access Control

```python
if not request.env.user.has_group('hr.group_hr_user'):
    if employees.ids != request.env.user.employee_id.ids:
        return request.not_found()
```

Employees can only print their own CV unless they have HR access. This prevents unauthorized CV viewing.

### 3. Resume Access Control

```python
def get_internal_resume_lines(self, res_id, res_model):
    if not self.env['hr.employee.public'].browse(res_id).has_access('read'):
        raise AccessError(...)
```

Prevents unauthorized access to employee resume information.

### 4. Input Validation

The controller validates employee_ids to prevent injection:
```python
if re.search("[^0-9|,]", employee_ids):
    return request.not_found()
```

---

## L4: Edge Cases and Failure Modes

### Skill Level Mismatch

**Scenario:** User selects a skill type, then manually changes skill_level_id to a level from a different skill type.

**Constraint:** `_check_skill_level()` catches this mismatch:
```python
if record.skill_level_id not in record.skill_type_id.skill_level_ids:
    raise ValidationError("The skill level is not valid for skill type")
```

### Skill-Skill Type Mismatch

**Scenario:** User tries to set skill_id to a skill from a different skill type than skill_type_id.

**Constraint:** `_check_skill_type()` catches this:
```python
if record.skill_id not in record.skill_type_id.skill_ids:
    raise ValidationError("The skill and skill type don't match")
```

### Date Validation

**Scenario:** User sets valid_to before valid_from.

**Onchange:** `display_warning_message` shows warning
**Constraint:** `_check_date()` prevents saving:
```python
if ind_skill.valid_from > ind_skill.valid_to:
    raise ValidationError("The start date must be anterior to the end date")
```

### Circular Default Level Update

**Scenario:** User sets level A as default, then sets level B as default.

**Protection:** Both create() and write() handle this:
- On create: Filters out self.id before unsetting
- On write: Uses same pattern

---

## Test Coverage

### test_employee_skill.py

Comprehensive tests covering:
- Adding new skills
- Editing skill levels (archives old, creates new)
- Overlap detection for skills and certifications
- Date range management
- Archiving vs deletion rules
- Deduplication of duplicate entries
- RPC call behavior

**Note:** Tests are currently skipped (`cls.skipTest(cls, "To be reintroduced post 18.4 freeze")`)

**Test Structure:**
```
Test: Add English B1
  --> Previous: 5 skills
  --> New skill created with valid_from = today
  --> Old English A2 archived (valid_to = yesterday)
  --> Total: 6 skills

Test: Edit English A2 to English B1
  --> Same behavior as add, but editing existing record

Test: Archive vs Delete Regular Skill
  --> Skill created >24h ago: archived when removed
  --> Skill created <24h ago: deleted when removed

Test: Same Certification Different Levels Can Coexist
  --> Odoo 50% (2024-01-01 to 2024-12-31) + Odoo 50% (2024-06-01 to 2025-05-31) = ALLOWED
```

### test_certification_activities.py

Tests for the automatic certification activity feature:
- Activity creation for missing certifications
- No activity for valid certifications
- Activity for wrong level certifications
- Activity for expiring certifications
- Activity deduplication
- Multi-employee scenarios

**Test Structure:**
```
Test: Employee with no certifications gets activity
  --> Job requires: Cert1 (level 50%), Cert2 (level 100%)
  --> Employee has: none
  --> Result: 2 activities created

Test: Employee with correct certifications gets no activity
  --> Job requires: Cert1 (50%), Cert2 (100%)
  --> Employee has: Cert1 (50%), Cert2 (100%)
  --> Result: No activities

Test: Activities are only created once
  --> First run: activities created
  --> Second run: no new activities (already exist)
```

---

## Related Modules

- [Modules/HR](Modules/HR.md) - Core HR module (dependency)
- [Modules/Resource](Modules/resource.md) - Resource scheduling
- [Modules/Mail](Modules/mail.md) - Activity and notification system
- [Modules/documents](Modules/documents.md) - Document management for certificates
- [Modules/hr_recruitment](Modules/hr_recruitment.md) - Applicant tracking (skill matching)
- [Modules/hr_recruitment_skills](Modules/hr_recruitment_skills.md) - Skills assessment for recruitment
- [Modules/hr_skills](Modules/hr_skills.md) - Skills assessment in events
- [Modules/hr_skills](Modules/hr_skills.md) - Skills from e-learning (integrates with slides)
- [Modules/hr_skills](Modules/hr_skills.md) - Skills from surveys/certifications

---

## See Also

- [Core/Fields](Core/Fields.md) - Field types used in skills
- [Core/API](Core/API.md) - @api.depends, @api.constrains decorators
- [Core/BaseModel](Core/BaseModel.md) - Model foundation and inheritance
- [Patterns/Security Patterns](Patterns/Security Patterns.md) - Access control implementation
- [Modules/HR](Modules/HR.md) - Employee model extension
- [Modules/hr_recruitment](Modules/hr_recruitment.md) - Job position model

---

## L4: XML Views and UI Architecture

### Custom Widgets

The module defines two custom JavaScript widgets loaded via `web.assets_backend`:

- **`skills_one2many`** (`static/src/fields/skills_one2many/`): Renders the employee skills list with inline editing, color-coded expiry indicators, and progress bars. Supports decoration classes for visual state (muted=expired, danger=expiring within 7 days, warning=expiring within 3 months).
- **`resume_one2many`** (`static/src/views/skills_list_renderer.js`): Renders resume lines with custom card layout and handles the `internal_resume_lines` widget for displaying historical job titles from `hr.employee.version_ids`.

### Key View IDs and Inheritance

| View ID | Model | Type | Purpose |
|---------|-------|------|---------|
| `hr_skills.hr_employee_view_form` | hr.employee | form | Adds Resume section (left) and Skills section (right) to employee form |
| `hr_skills.hr_employee_public_view_form_inherit_resume` | hr.employee.public | form | Public-facing employee with resume + skills (readonly) |
| `hr_skills.view_employee_filter` (inherited) | hr.employee | search | Adds `employee_skill_ids` and `resume_line_ids` filter fields |
| `hr_skills.resume_line_view_form` | hr.resume.line | form | Base form for resume lines (priority=1) |
| `hr_skills.resume_line_view_form_inherit` | hr.resume.line | form | Adds employee_id visibility based on is_course (priority=100) |
| `hr_skills.employee_skill_view_form` | hr.employee.skill | form | Skill entry dialog with category/skill/level badges |
| `hr_skills.employee_skill_view_inherit_certificate_form` | hr.employee.skill | form | Certification dialog — limits skill_type to is_certification=True types |
| `hr_skills.hr_skill_type_view_form` | hr.skill.type | form | Skill type form with inline skill and level editors |
| `hr_skills.hr_job_skill_view_form` | hr.job.skill | form | Job skill dialog form |

### Form Behavior Notes

- **Employee skill form**: `skill_level_id` is hidden when `levels_count <= 1` (only one level exists for the type).
- **Certification validity**: `valid_from`/`valid_to` fields are only visible when `is_certification=True`; `valid_from` is required in that case.
- **Date warning**: A Bootstrap alert warns if `valid_to < valid_from` via `display_warning_message`.
- **Resume line form**: For course-type lines, the employee field is visible; for non-course, employee is shown on the left side of the date group.

### Search Views

- **`hr_skills.view_resume_lines_filter`**: Search panel with company and department filters (icon-enabled).
- **`hr_skills.hr_employee_skill_view_search`**: Certification search with filters: Valid certification, group by skill/type/employee.
- **`hr_skills.hr_resume_line_kanban_view`**: Kanban view colored by `course_type` badge.

### Report Views

- **`hr_employee_skill_report_view_pivot`**: Rows=skill_type+skill, columns=department+employee, measure=level_progress (percentage widget).
- **`hr_employee_certification_report_view_pivot`**: Rows=employee, columns=skill_type+skill, measure=level_progress.
- **`hr_employee_skill_history_report_views.xml`** (graph view): Used for the department action `action_hr_employee_skill_log_department` — temporal=0, grouped by skill_type then skill.

---

## L4: Security Model

### Access Control List (ir.model.access.csv)

| Model | Group | R | W | C | D |
|-------|-------|---|---|---|---|
| `hr.resume.line` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.resume.line` | base.group_user (employee) | 1 | 1 | 1 | 1 |
| `hr.resume.line.type` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.resume.line.type` | base.group_user | 1 | 0 | 0 | 0 |
| `hr.skill.type` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.skill.type` | base.group_user | 1 | 0 | 0 | 0 |
| `hr.skill.level` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.skill.level` | base.group_user | 1 | 0 | 0 | 0 |
| `hr.skill` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.skill` | base.group_user | 1 | 0 | 1 | 0 |
| `hr.employee.skill` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.employee.skill` | base.group_user | 1 | 1 | 1 | 1 |
| `hr.job.skill` | hr.group_hr_user | 1 | 1 | 1 | 1 |
| `hr.job.skill` | base.group_user | 1 | 0 | 0 | 0 |
| `hr.employee.skill.report` | hr.group_hr_user | 1 | 0 | 0 | 0 |
| `hr.employee.skill.report` | base.group_user | 1 | 0 | 0 | 0 |
| `hr.employee.certification.report` | base.group_user | 1 | 0 | 0 | 0 |
| `hr.employee.skill.history.report` | hr.group_hr_user | 1 | 0 | 0 | 0 |
| `hr.employee.skill.history.report` | base.group_user | 1 | 0 | 0 | 0 |

### Record Rules (hr_skills_security.xml)

**`hr_resume_rule_employee`** (`base.group_user`): Full read access for all resume lines; no create/write/unlink.

**`hr_resume_rule_employee_hr_user`** (`hr.group_hr_user`): Full CRUD access.

**`hr_skills_rule_employee_update`** (`base.group_user`): Employees can only create/write/unlink their own resume lines via `[('employee_id.user_id','=',user.id)]`. Notably, `perm_read=False` here but the base rule gives full read — the base `hr_resume_rule_employee` takes precedence.

**`hr_skill_rule_employee`** (`base.group_user`): Full read for all employee skills; no create/write/unlink.

**`hr_skill_rule_hr_user`** (`hr.group_hr_user`): Full access.

**`hr_skill_rule_employee_update`** (`base.group_user`): Employees can CRUD their own skills via `[('employee_id.user_id','=',user.id)]`, with `perm_read=False` (same pattern as resume).

**`hr_employee_skill_report_hr_user`** (`hr.group_hr_user`): Full access to skill report (domain `[(1,'=',1)]`).

**`hr_employee_skill_report_manager`** (`base.group_user`): Access if `has_department_manager_access=True` — uses the `hr.manager.department.report` mixin for department-level filtering.

**`hr_employee_skill_report_multicompany`**: No group — applies to all users. Domain `[('company_id', 'in', company_ids + [False])]` enforces multi-company record rules.

### Field-Level Groups

- `hr.employee.skill_ids` (Many2many, computed+stored): `groups="hr.group_hr_user"` — only HR users see the skill summary field.
- Resume lines and employee skills are visible to all employees via `base.group_user` read access.

---

## L4: Automation and Scheduled Actions

### Cron: `_add_certification_activity_to_employees`

**Technical Details:**

| Property | Value |
|----------|-------|
| Model | `hr.employee` |
| Method | `_add_certification_activity_to_employees()` |
| Frequency | Daily (`interval_number=1`, `interval_type=days`) |
| XML ID | `hr_skills.hr_job_skills_cron_add_certification_activity_to_employees` |

**Execution Flow:**

1. Query all jobs that have at least one `hr.job.skill` where `skill_type_id.is_certification=True`.
2. Build a mapping `{(job, (skill_id, skill_level_id)): summary}` for required certifications per job.
3. Query employees assigned to those jobs who also have a responsible user (employee, manager, or job responsible).
4. For each employee, check existing `mail.activity` records with `activity_category='upload_file'` and `res_model='hr.employee'` to avoid duplicates.
5. Compare employee certifications against job requirements — skip if certification is active and valid beyond 3 months.
6. Schedule a `mail.activity` with:
   - Type: `hr_skills.mail_activity_data_upload_certification` (icon: `fa-upload`, delay: 5 days)
   - Summary: `"<skill_name>: <level_name>"`
   - Note: `"Certification missing or expiring soon"`
   - Deadline: certification `valid_to` date, or today if no end date
   - Responsible: the resolved user (employee > manager > job responsible)

**Performance Characteristics:**
- Uses `Domain` API for efficient, type-safe domain construction.
- Processes all eligible employees in a single pass — no per-employee search.
- Existing activity check `(res_id, summary)` prevents duplicate activities on re-runs.
- Returns the cumulative recordset of created activities for logging/testing.

---

## L4: Seeded Reference Data

### Skill Types (hr_skill_data.xml)

| Skill Type | Sequence | Default Levels |
|------------|----------|----------------|
| Languages (`hr_skill_type_lang`) | 1 | A1(A2,B1,B2,C1,C2) — 10/40/60/75/85/100% |
| Soft Skills (`hr_skill_type_softskill`) | 2 | Beginner/Elementary/Intermediate/Advanced/Expert — 15/25/50/80/100% |

### Default Skills (38 total)

**Languages (20):** French, Spanish, English, German, Filipino, Arabic, Bengali, Mandarin Chinese, Wu Chinese, Hindi, Russian, Portuguese, Indonesian, Urdu, Japanese, Punjabi, Javanese, Telugu, Turkish, Korean, Marathi.

**Soft Skills (13):** Communication, Teamwork, Problem-Solving, Time Management, Critical Thinking, Decision-Making, Organizational, Stress management, Adaptability, Conflict Management, Leadership, Creativity, Resourcefulness, Persuasion, Openness to criticism.

### Resume Line Types (hr_resume_data.xml)

| XML ID | Name | Sequence | is_course |
|--------|------|----------|-----------|
| `hr_skills.resume_type_experience` | Other Experience | 1 | False |
| `hr_skills.resume_type_education` | Education | 2 | False |
| `hr_skills.resume_type_training` | Training | 3 | True |

### Mail Activity Type

| Property | Value |
|----------|-------|
| XML ID | `hr_skills.mail_activity_data_upload_certification` |
| Name | Certifications |
| Summary | Upload a certification |
| Model | hr.employee |
| Icon | fa-upload |
| Delay | 5 days |
| Category | upload_file |
| Sequence | 25 |

---

## L4: CV Report QWeb Template

**Report Name:** `hr_skills.report_employee_cv`
**Report Action:** `hr_skills.action_report_employee_cv`
**Paper Format:** `hr_skills.paperformat_resume` (custom paperformat in data)
**SCSS Asset:** `hr_skills/static/src/scss/report_employee_cv.scss` loaded via `web.report_assets_pdf`

**Controller Endpoint:** `GET /print/cv`

**Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `employee_ids` | CSV string | required | Comma-separated employee IDs |
| `color_primary` | hex string | `#666666` | Primary theme color |
| `color_secondary` | hex string | `#666666` | Secondary theme color |
| `show_skills` | flag | True | Include skills section |
| `show_contact` | flag | True | Include contact information |
| `show_others` | flag | True | Include resume lines without type |

**Access Control (from `controllers/main.py`):**
1. `request.env.user._is_internal()` — rejects portal/guest users
2. Regex `[^0-9|,]` on `employee_ids` — blocks injection attempts
3. If `hr.group_hr_user`: allow all employee IDs
4. Else: only allow `employees.ids == request.env.user.employee_id.ids` (own CV only)

**Wizard Flow:** The `hr.employee.cv.wizard` builds a URL query string and redirects to `/print/cv` via `ir.actions.act_url`. The wizard's `can_show_others` and `can_show_skills` computed fields dynamically hide toggles when no relevant data exists.

---

## L4: Command Transformation Deep Dive

### `_get_transformed_commands()` — Full Flow

```
Incoming ORM commands (CREATE/WRITE/UNLINK)
    |
    v
Separate into:
  - CREATE [0, 0, {...}] commands
  - WRITE  [1, id, {...}] commands
  - UNLINK [2, id] commands
    |
    v
Handle mixed commands (same ID in both update and delete):
  - Reset those updates to avoid conflicting operations
    |
    v
UNLINK path:
  -> _expire_individual_skills()
  -> Returns [2, id] for recent skills, [1, id, {valid_to: yesterday}] for archive-eligible

WRITE path:
  -> _write_individual_skills()
  -> If core fields (skill_type/skill/skill_level/linked_field) changed:
       archive old record + create new
     Else:
       normal write

CREATE path:
  -> _create_individual_skills()
  -> For regular skills: archive existing active skill with same skill_id first
  -> For certifications: allow multiple with different validity periods
    |
    v
Final: UNLINK commands + WRITE commands + CREATE commands
```

### Passive Fields Pattern

`_get_passive_fields()` on the mixin returns `[]` by default. Subclasses can override to preserve additional fields (e.g., a description or notes field) when a skill record is archived and a new one is created. The `_write_individual_skills()` method extracts values for these fields from the old record if not provided in the new vals.

### Certification Validity Edit Mode

When `_can_edit_certification_validity_period()` returns `True` (employee skill):
- Overlap is checked by exact `(skill_id, skill_level_id, valid_from, valid_to)` tuple.
- This allows multiple certifications with same skill/level if dates differ.
- The `_onchange_is_certification()` resets validity dates when type changes.

When `_can_edit_certification_validity_period()` returns `False` (job skill):
- Job skills ignore the `is_certification` flag — treated as regular skills.
- Only one active skill per `skill_id` is allowed.

---

## L4: `get_internal_resume_lines()` Deep Dive

This method reconstructs an employee's career progression from `hr.employee.version_ids` (the employee versioning system in Odoo 19).

**Algorithm:**
1. Get the target employee (or resolve from `res.users`).
2. Verify read access via `hr.employee.public.has_access('read')`.
3. Sort `version_ids` by `date_version` ascending.
4. For each adjacent pair of versions:
   - If current version has no `job_title`: skip (wait for next version to close the gap).
   - If `job_title` differs OR there is a gap in dates between versions: emit a resume line for the current version.
   - If `job_title` matches and dates are continuous: merge (extend `interval_date_start`).
5. Handle the last version specially — emit if it has a job title, otherwise close the last open interval.

**Output:** List of `{id, job_title, date_start, date_end}` dicts (newest first).

**Access Control:** Raises `AccessError` if the user cannot read the employee via `hr.employee.public`. This is the only method in the module that explicitly checks access rights.

---

## L4: `formatted_read_grouping_sets` Override

The `hr.employee.skill.report` model overrides `formatted_read_grouping_sets()` to pass `hierarchical_naming=False` to the context:

```python
def formatted_read_grouping_sets(self, domain, grouping_sets, aggregates=(), *, order=None):
    self_contexted = self.with_context(hierarchical_naming=False)
    return super().formatted_read_grouping_sets(
        domain, grouping_sets, aggregates, order=order,
    )
```

**Why:** In the pivot view grouped by department, Odoo's default behavior is to show hierarchical names (e.g., "Parent / Child Department"). This override ensures flat department names are displayed, improving readability in the Skills Inventory report.

---

## L4: `_load_scenario()` Integration

The `hr.employee._load_scenario()` override in `models/hr_employee.py` integrates `hr_skills_scenario.xml` when loading the HR scenario data:

```python
def _load_scenario(self):
    super()._load_scenario()
    demo_tag = self.env.ref('hr_skills.employee_resume_line_emp_eg_1', raise_if_not_found=False)
    if demo_tag:
        return
    convert.convert_file(self.env, 'hr', 'data/scenarios/hr_scenario.xml', None, mode='init')
    convert.convert_file(self.env, 'hr_skills', 'data/scenarios/hr_skills_scenario.xml', None, mode='init')
```

**Logic:** If the demo tag `hr_skills.employee_resume_line_emp_eg_1` already exists (demo data already loaded), skip loading again. Otherwise, load the standard HR scenario first, then the hr_skills scenario.

This pattern ensures demo data for skills and resume lines is only loaded once, even if the module is reinstalled.

---

## L4: Multi-Company and Department Manager Access

### `hr.manager.department.report` Mixin

Both `hr.employee.skill.report` and `hr.employee.certification.report` inherit from `hr.manager.department.report`. This Odoo 19 mixin provides:

- **`has_department_manager_access`** (computed field): True if the current user manages the employee's department.
- **`employee_id`** read group aggregation with manager-based filtering.
- The record rule `hr_employee_skill_report_manager` uses this field to restrict access to managers of the employee's department.

### Multi-Company Record Rule

The `hr_employee_skill_report_multicompany` rule (no group — applies to all users):
```python
domain_force = [('company_id', 'in', company_ids + [False])]
```
This enforces that users only see skill report records for their allowed companies (or records with no company set).

---

## Data Flow Summary

```
hr.skill.type (1) ──< hr.skill (N) ──< hr.employee.skill / hr.job.skill
                         │
                         └──< hr.skill.level (N)

hr.employee (1) ──< hr.employee.skill (N)
          │
          ├──< hr.resume.line (N) ──< hr.resume.line.type (N)
          │
          └──< current_employee_skill_ids (computed)
          └──< certification_ids (computed)
          └──< skill_ids (computed, stored)

hr.job (1) ──< hr.job.skill (N)

Scheduled Action (daily):
  hr.employee._add_certification_activity_to_employees()
    → mail.activity (upload_file category, hr.employee model)
    → triggers notification to responsible user

CV Report:
  hr.employee.cv.wizard → /print/cv → hr.employee.cv.controller
    → report.hr_skills.report_employee_cv (QWeb PDF)
```
