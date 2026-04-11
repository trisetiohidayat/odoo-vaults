# web_hierarchy

**Category:** Hidden
**Depends:** `web`
**Author:** Odoo S.A.
**License:** LGPL-3

Adds a Hierarchy view type to Odoo, allowing records to be displayed in an expandable tree/organization-chart structure.

## Models

### `ir.ui.view`
Inherits `base` view; registers the `hierarchy` view type.

- `type`: Selection field extended with `[('hierarchy', "Hierarchy")]`
- `_is_qweb_based_view()`: Returns `True` for `hierarchy` views
- `_validate_tag_hierarchy()`: Validates the `<hierarchy>` XML node — requires a single `<templates>` child, and only valid attributes (see below)
- `_get_view_info()`: Returns `{'hierarchy': {'icon': 'fa fa-share-alt fa-rotate-90'}}`

**Valid XML attributes for `<hierarchy>` tag:**
`__validate__`, `class`, `js_class`, `string`, `create`, `edit`, `delete`, `parent_field`, `child_field`, `icon`, `draggable`, `default_order`

### `ir.actions.act_window.view`
Extends `view_mode` selection with `hierarchy` (cascade delete).

### `base` (mixin on `models.Model`)
Provides `hierarchy_read()` for fetching hierarchical record data:

```python
base.hierarchy_read(domain, specification, parent_field, child_field=None, order=None)
```

- Searches records matching domain
- Fetches child IDs via `_read_group` for each record
- Returns list of dicts with `__child_ids__` for each record

## Key Features
- Hierarchical tree/org-chart display of any model with a parent field
- Configurable `parent_field` and `child_field` attributes
- Drag-and-drop reordering via `draggable="True"`
- Custom icons per record
- Default sort order configuration
- Full inline create/edit/delete actions
