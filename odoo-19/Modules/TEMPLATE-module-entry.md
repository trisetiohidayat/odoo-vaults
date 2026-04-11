---
type: module-template
title: "Module Documentation Template"
description: "Standard template for documenting Odoo modules with 3-layer structure"
usage: Copy to new module file and fill in the blanks
created: YYYY-MM-DD
updated: 2026-04-06
version: "1.1"
---

# Module Documentation Template

This template provides a **standard structure** for documenting any Odoo module. Follow this template when creating or updating module documentation.

## When to Use

| Module Status | Action |
|---------------|--------|
| New module being documented | Use this template as the base |
| Existing module being enhanced | Add missing sections incrementally |
| Existing detailed module (300+ lines) | Already complete — just add Quick Access |

---

## Quick Access (Add to ALL modules)

Every module documentation file should start with a **Quick Access** block:

```markdown
## Quick Access

### 📖 Reference
→ Model & Field tables below

### 🔀 Flows (Technical — AI & Developer)
→ [[Flows/ModuleName/flow-name]] — Flow description
→ [[Flows/ModuleName/flow-name-2]] — Flow description

### 📋 How-To Guides (Functional — Business)
→ [[Business/Category/guide-name]] — Guide description
→ [[Business/Category/guide-name-2]] — Guide description

### 🔗 Related Modules
→ [[Modules/RelatedModule]] — Brief relationship
→ [[Modules/AnotherModule]] — Brief relationship
→ [[Patterns/Workflow Patterns]] — Pattern reference
```

---

## Full Module Template Structure

Below is the complete template for a detailed module documentation file.

### Section 1: Module Info

```markdown
---
type: module
module: module_name
tags: [odoo, odoo19, module-name]
updated: YYYY-MM-DD
version: "1.0"
---

 Module Info (`__manifest__.py`)

**File:** `/path/to/addons/module_name/__manifest__.py`

| Property | Value |
|----------|-------|
| Name | Module Title |
| Version | 1.0 |
| Category | Category Name |
| Summary | Brief description |
| Author | Odoo S.A. |
| License | LGPL-3 / Proprietary |
| Application | True / False |
| Installable | True |

**Dependencies:**
- dependency_1
- dependency_2
```

---

### Section 2: Model Documentation

For each model in the module, document:

```markdown
## N. Model Name (`model.name`)

**File:** `path/to/models/model_name.py`

### Basic Info
| Property | Value |
|----------|-------|
| `_name` | `model.name` |
| `_description` | Model Description |
| `_inherit` | parent.model |
| `_order` | field_name |
| `_rec_name` | name_field |

### Key Fields
| Field | Type | Description |
|-------|------|-------------|
| `field_name` | Char | Brief description |
| `field_name` | Many2one (model) | Brief description |
| `field_name` | Selection | option_a, option_b |

### Key Methods
- `_compute_field()` — `@api.depends` description
- `_onchange_field()` — Onchange description
- `action_*()` — Action description
- `create()` / `write()` — Override description

### Constraints
```python
_sql_constraints = [
    ('unique_name', 'unique(name)', 'Name must be unique'),
]
```

### Model Relationships
```
model.name
    |-- belongs to --> related.model (field_id)
    |-- has many --> child.model (child_ids)
    |-- inherits from --> parent.model (field_id)
```

---

### Section 3: Method Chains (Level 1)

Add for important models:

```markdown
## Flows (Level 1 — Method Chains)

### [Action] Method Chain

```
model.method(vals)
  │
  ├─► [A] IF condition:
  │      └─► sub_method() → effect
  │
  ├─► [B] related_model.create() [cross-module]
  │      └─► inverse_field_set()
  │
  └─► [C] side_effect()
        └─► notification / activity
```

### Error Scenarios
| Trigger | Error | Reason |
|---------|-------|--------|
| Duplicate | `ValidationError` | constraint |
| Missing field | `ValidationError` | required |
| Invalid state | `UserError` | business rule |
```

---

### Section 4: Business Flows (Cross-Module)

Link to Flows/ directory:

```markdown
## Related Flows

> **For complete method chain documentation, see:**
> - [[Flows/ModuleName/flow-1]] — Description
> - [[Flows/ModuleName/flow-2]] — Description
```

---

### Section 5: Integration Points

Document how this module interacts with others:

```markdown
## Integration Points

| Module | Interaction Type | Description |
|--------|----------------|-------------|
| `sale` | Depends on | Sale order integration |
| `stock` | Extends | Stock move creation |
| `account` | Creates records | Invoice generation |

```

---

### Section 6: File Structure

```markdown
## File Structure

```
module_name/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── model_1.py
│   └── model_2.py
├── views/
│   ├── model_1_views.xml
│   └── model_2_views.xml
├── security/
│   └── ir.model.access.csv
├── data/
│   └── sequence_data.xml
└── wizards/
    ├── __init__.py
    └── wizard_model.py
```
```

---

## Checklist for New Module Documentation

When documenting a new module, ensure:

### Essentials
- [ ] Module Info (__manifest__.py)
- [ ] All models documented with Basic Info
- [ ] Key fields listed with types
- [ ] Key methods listed with descriptions
- [ ] Constraints documented

### Level 1 Enhancement
- [ ] Quick Access block at top
- [ ] At least one Method Chain section
- [ ] Error Scenarios table
- [ ] Integration Points section

### Level 2 Enhancement
- [ ] Related Flows linked to Flows/ directory
- [ ] Business Guides linked to Business/ directory
- [ ] File Structure documented

### Quality
- [ ] All wikilinks verified (point to existing files)
- [ ] Frontmatter complete (type, module, tags)
- [ ] Code examples tested (if applicable)

---

## Related Templates

- [[Flows/TEMPLATE-flow]] — Flow document template
- [[Business/TEMPLATE-guide]] — Business guide template
- [[Snippets/method-chain-example]] — Method chain notation reference
- [[Patterns/Workflow Patterns]] — Workflow patterns
- [[Patterns/Security Patterns]] — Security patterns
