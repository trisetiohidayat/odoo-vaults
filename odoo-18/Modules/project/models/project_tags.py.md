# Project Tags - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_tags.py`
**Lines:** ~95

---

## Model Overview

`project.tags` is a tagging system for tasks and projects. It supports project-specific tag filtering for performance optimization in large projects.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; tag name; `translate=True` |
| `color` | Integer | Kanban color (1-11); random default |
| `project_ids` | Many2many | `project.project`; projects that can use this tag |
| `task_ids` | Many2many | `project.task`; tasks with this tag |

---

## SQL Constraints

```python
SQL_CONSTRAINT: unique(name)
```
Tag names must be unique globally (not per project).

---

## Key Methods

### `read_group(domain, fields, groupby, ...)`
**Special behavior:** If `project_id` is in context, filters tags to those available in that project via `name_search()`.
**Logic:**
1. Get tag IDs available in the project via `name_search()`.
2. Add `('id', 'in', tag_ids)` to domain.
3. Proceed with standard `read_group`.

### `search_read(domain, fields, offset, limit, order)`
**Special behavior:** Same project-specific filtering as `read_group`.
**Additional logic:** Calls `arrange_tag_list_by_id()` to reorder results to match `name_search()` order.

### `name_search(name, args, operator, limit)`
**Optimized path when `project_id` in context:**
1. **Step 1 (Top):** Find tags from the last 1000 tasks of the project, matching the search criteria. Limit = `limit`.
2. **Step 2 (Fill):** If fewer results than `limit`, fill with tags matching the criteria but NOT in step 1 results.
3. **Fallback:** If `project_id` NOT in context, falls back to standard `name_search`.

**SQL optimization:**
```sql
SELECT DISTINCT project_tags_tags.id FROM (
    SELECT rel.project_tags_id AS id
    FROM project_tags_project_task_rel AS rel
    JOIN project_task AS task ON task.id=rel.project_task_id
        AND task.project_id=%(project_id)s
    ORDER BY task.id DESC
    LIMIT 1000
) AS project_tags_tags
```
**Rationale:** Only tags used in the most recent tasks are shown first, giving users the most relevant tags.

### `name_create(name)`
**Special behavior:** Case-insensitive duplicate detection.
**Logic:**
1. Search for existing tag with `name = ileike name.strip()`.
2. If found: return existing tag (id, display_name).
3. If not found: create a new tag via `super()`.

### `arrange_tag_list_by_id(tag_list, id_order)`
**Purpose:** Reorder a list of tag records to match a given ID sequence.
**Algorithm:** O(n) using hash map:
```python
tags_by_id = {tag['id']: tag for tag in tag_list}
return [tags_by_id[id] for id in id_order if id in tags_by_id]
```

---

## Edge Cases & Failure Modes

1. **Tag name uniqueness across projects:** The `unique(name)` constraint is global. Two projects cannot have tags with the same name. This can be confusing when different project teams expect independent tag sets.
2. **Tag search with no `project_id` context:** Falls back to unfiltered `name_search`. For large databases, this could be slow.
3. **`limit=None`:** When `limit=None` is passed to `name_search`, it falls back to `super().name_search()` which may return all matching tags without the project optimization.
4. **Tag used in deleted tasks:** Tags remain even if all tasks using them are deleted or archived.
5. **Tag color randomization:** Each new tag gets a random color 1-11. Multiple tags can have the same color by chance.
6. **`project_ids` and tag visibility:** A tag with `project_ids` set is only available in those projects. However, the `read_group` and `search_read` optimizations require the `project_id` to be in the context — if not, the tag won't be filtered even if it only belongs to certain projects.
7. **Translation:** `name` is `translate=True`. The same tag can have different names in different languages. The `unique(name)` constraint may behave unexpectedly in multi-language environments.
8. **Performance of project-specific search:** The 1000-task limit for finding recent tags is a hardcoded constant. Very large projects (with millions of tasks) will have the same limit regardless.
