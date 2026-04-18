---
type: module
module: web_hierarchy
tags: [odoo, odoo19, web, hierarchy, tree, parent_field, org_chart, view]
created: 2026-04-14
related_links:
  - "[Core/BaseModel](BaseModel.md)"
  - "[Core/Fields](Fields.md)"
---

# Web Hierarchy

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `web_hierarchy` |
| **Category** | Hidden |
| **Depends** | `web` |
| **Auto-install** | False |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Purpose

`web_hierarchy` adds a new view type called **Hierarchy** to Odoo's web client. Unlike the standard list (table) view, which renders records as flat rows, the hierarchy view displays records as an expandable **tree** or **org-chart** structure, revealing parent-child relationships visually.

This is not a dedicated model viewer -- it is a **view layer module** that works with any model that has a parent-child relationship defined. Common use cases include:

- **Employee org chart**: `hr.employee` with `parent_id` field.
- **Product categories**: `product.category` with `parent_id` (self-referential).
- **Account charts**: `account.account` with `parent_id`.
- **Project hierarchy**: `project.project` with `parent_id`.
- **Geographic regions**: `res.country` with `parent_path` for nested regions.

The hierarchy view is a QWeb-based view that uses JavaScript on the client side to render the tree, handle expand/collapse, drag-and-drop reordering, and inline editing.

## Architecture Overview

The module has three model extensions:

1. **`ir.ui.view`**: Registers `hierarchy` as a new view type and validates `<hierarchy>` XML nodes.
2. **`ir.actions.act_window.view`**: Adds `hierarchy` to the allowed `view_mode` selection.
3. **`base` (mixin on `models.Model`)**: Provides the `hierarchy_read()` method for fetching hierarchical data.

No new database tables are created. All hierarchy data comes from existing models that already have parent-child relationships.

## Model Extensions

### `ir.ui.view` (Extended)

#### `type` (Selection, extended)

```python
type = fields.Selection(selection_add=[('hierarchy', "Hierarchy")])
```

Registers the `hierarchy` view type. When a view with `type="hierarchy"` is defined in an XML `arch` field, Odoo's view system routes it to this module's rendering logic.

#### `_is_qweb_based_view(view_type)`

```python
def _is_qweb_based_view(self, view_type):
    return super()._is_qweb_based_view(view_type) or view_type == "hierarchy"
```

Hierarchy views are QWeb-based (unlike list and form views which use non-QWeb rendering in Odoo 17+). This method tells the view system to use the QWeb engine for hierarchy views.

#### `_validate_tag_hierarchy(node, name_manager, node_info)`

This is the core validation method for `<hierarchy>` XML nodes. It enforces two rules:

1. **Single `<templates>` child**: The `<hierarchy>` node must contain exactly one `<templates>` child element, which holds the QWeb templates for rendering each node. Multiple `<templates>` elements are not allowed.

```python
if child.tag == 'templates':
    if not templates_count:
        templates_count += 1
    else:
        msg = _('Hierarchy view can contain only one templates tag')
        self._raise_view_error(msg, child)
```

2. **Valid attributes only**: Any attributes on `<hierarchy>` that are not in the whitelist are rejected:

```python
HIERARCHY_VALID_ATTRIBUTES = {
    '__validate__',   # ir.ui.view internal validation flag
    'class',          # CSS classes
    'js_class',       # JavaScript widget class
    'string',         # View title (from ir.ui.view)
    'create',         # Enable inline record creation
    'edit',           # Enable inline record editing
    'delete',         # Enable inline record deletion
    'parent_field',  # Name of the parent field (default: 'parent_id')
    'child_field',    # Name of child field (optional)
    'icon',           # Default icon for nodes
    'draggable',      # Enable drag-and-drop reordering
    'default_order'   # Default sort order
}
```

If an invalid attribute is found, an error is raised listing all invalid attributes.

#### `_get_view_info()`

```python
def _get_view_info(self):
    return {'hierarchy': {'icon': 'fa fa-share-alt fa-rotate-90'}} | super()._get_view_info()
```

Returns view metadata: the hierarchy view is associated with the `fa-share-alt fa-rotate-90` (rotated share icon) in the view selector toolbar.

### `ir.actions.act_window.view` (Extended)

```python
view_mode = fields.Selection(
    selection_add=[('hierarchy', 'Hierarchy')],
    ondelete={'hierarchy': 'cascade'}
)
```

Adds `hierarchy` to the list of available view modes for window actions. The `ondelete='cascade'` means that when the parent action is deleted, the hierarchy view record is also deleted.

### `base` (Mixin on `models.Model`)

This is the most architecturally significant extension. It adds `hierarchy_read()`, which is the data fetching engine for the hierarchy view.

#### `hierarchy_read(domain, specification, parent_field, child_field=None, order=None)`

```python
@api.model
def hierarchy_read(self, domain, specification, parent_field, child_field=None, order=None):
    if parent_field not in specification:
        specification[parent_field] = {"fields": {"display_name": {}}}
    records = self.search(domain, order=order)
    fetch_child_ids_for_all_records = False

    if not records:
        return []
    elif len(records) == 1:
        # Single record: expand its subtree and the parent's subtree
        domain = [(parent_field, '=', records.id), ('id', '!=', records.id)]
        if records[parent_field]:
            records += records[parent_field]
            domain = [('id', 'not in', records.ids), (parent_field, 'in', records.ids)]
        records += self.search(domain, order=order)
    else:
        fetch_child_ids_for_all_records = True

    children_ids_per_record_id = {}
    if not child_field:
        # Use _read_group to get child counts per parent
        children_ids_per_record_id = {
            record.id: child_ids
            for record, child_ids in self._read_group(
                [(parent_field, 'in',
                  records.ids if fetch_child_ids_for_all_records
                  else (records - records[parent_field]).ids)],
                (parent_field,),
                ('id:array_agg',),
                order=order
            )
        }

    result = records.web_read(specification)

    if children_ids_per_record_id:
        for record_data in result:
            if record_data['id'] in children_ids_per_record_id:
                record_data['__child_ids__'] = children_ids_per_record_id[
                    record_data['id']
                ]

    return result
```

**How it works:**

1. **Domain search**: Finds all records matching the provided domain.
2. **Smart subtree loading**:
   - If only one record is found, it also loads that record's children AND its parent (and siblings). This ensures the single-record view shows context.
   - If multiple records are found, it loads all their children recursively.
3. **Child resolution**: If `child_field` is not provided, uses `_read_group` to compute child IDs per parent ID. This is efficient because it uses a single SQL `GROUP BY` query rather than N queries for N records.
4. **`__child_ids__`**: Each record in the result includes a `__child_ids__` array listing the IDs of its direct children. The frontend uses this to render the expand/collapse nodes.
5. **`web_read`**: Delegates to `web_read()` (from `base`) for actual field value fetching with the provided specification.

**The `specification` parameter**: This is a dict mapping field names to sub-specifications, following the Odoo web API format:

```python
spec = {
    'name': {},                          # Read 'name' field
    'parent_id': {'fields': {'name': {}}},  # Read 'parent_id' and its display_name
    'child_ids': {'fields': {'name': {}}},  # Read children
}
```

## Hierarchy View XML Configuration

A hierarchy view is defined in XML using the `<hierarchy>` tag:

```xml
<record id="view_employee_hierarchy" model="ir.ui.view">
    <field name="name">employee.hierarchy</field>
    <field name="model">hr.employee</field>
    <field name="arch" type="xml">
        <hierarchy parent_field="parent_id"
                   child_field="child_ids"
                   draggable="true"
                   create="true"
                   edit="true"
                   delete="true"
                   icon="fa fa-users"
                   default_order="name asc">
            <templates>
                <t t-name="hierarchy-body">
                    <div class="o_hierarchy_node_content d-flex align-items-center">
                        <field name="name"/>
                    </div>
                </t>
            </templates>
        </hierarchy>
    </field>
</record>
```

### Attribute Reference

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `parent_field` | string | `'parent_id'` | Name of the Many2one field pointing to the parent record |
| `child_field` | string | auto | Name of the One2many field pointing to children. If omitted, children are computed from `parent_field` via `hierarchy_read` |
| `draggable` | boolean | `false` | Enable drag-and-drop to change parent |
| `create` | boolean | `true` | Enable inline record creation |
| `edit` | boolean | `true` | Enable inline record editing |
| `delete` | boolean | `true` | Enable inline record deletion |
| `icon` | string | `'fa fa-share-alt fa-rotate-90'` | Default icon for nodes |
| `default_order` | string | model default | Sort order for records |

### Templates

The `<templates>` section inside `<hierarchy>` uses QWeb syntax to define how each node is rendered. The standard template name is `hierarchy-body`:

```xml
<templates>
    <t t-name="hierarchy-body">
        <div class="o_hierarchy_node">
            <div class="o_hierarchy_node_header">
                <field name="name" class="fw-bold"/>
                <span class="badge bg-info ms-2">
                    <field name="department_id"/>
                </span>
            </div>
            <div class="o_hierarchy_node_body text-muted">
                <field name="job_id"/>
            </div>
        </div>
    </t>
</templates>
```

The template has access to all fields specified in the view's active field list. Standard QWeb directives (`t-esc`, `t-if`, `t-foreach`) are available.

## `_parent_name` Pattern

Many Odoo models use a convention where the parent field is explicitly named `_parent_name`. For example, `res.country` has:

```python
_parent_name = 'parent_id'
```

This is used by `hierarchy_read` internally when `child_field` is not provided -- it looks for a field matching the parent field name to build the tree.

Models that support the `_parent_name` convention include:
- `product.category`
- `account.account`
- `res.country`
- `res.country.state`
- `stock.location`
- `project.project` (via `parent_id`)

## `_parent_store` Pattern

The `_parent_store` pattern is a database-level optimization for tree-structured data. It stores a materialized path (like `/1/5/23/`) in a `parent_path` Char field:

```python
_parent_name = 'parent_id'
parent_path = fields.Char(index=True)
```

When a record's parent is changed, the `parent_path` is automatically updated for the record and all its descendants by Odoo's ORM. This enables:

1. **Efficient subtree queries**: Finding all descendants of record 23 can be done with `parent_path LIKE '23/%'`, which is a single indexed query.
2. **Breadcrumb trails**: The path can be split to show ancestors.
3. **Depth calculation**: The number of `/` separators gives the depth level.

The `hierarchy_read` method in `web_hierarchy` does NOT automatically use `_parent_store` -- it uses `hierarchy_read` from the base mixin which uses `_read_group`. However, the combination of `_parent_store` + hierarchy view is a powerful pattern for deep tree structures.

## Drag-and-Drop: `draggable="true"`

When `draggable="true"`, users can drag nodes to change their parent. This requires:

1. The `parent_field` to be editable inline (not `readonly`).
2. An `onchange` handler on the model that validates the new parent (prevents circular references).
3. The `write()` method on the model to update the `parent_id` field.

A typical circular reference check:

```python
@api.onchange('parent_id')
def _check_parent_not_child(self):
    if self.parent_id:
        # Get all ancestor IDs
        ancestors = self._get_ancestors()
        if self.parent_id.id in ancestors:
            raise UserError(_("A record cannot be its own ancestor."))
```

## Security Considerations

Hierarchy views respect standard Odoo access control:
- Record rules apply to the hierarchy data (users only see records they have access to).
- The tree structure may appear incomplete if a user's ACLs hide some records -- this is expected behavior.
- The `__child_ids__` in `hierarchy_read` results are filtered by access rights.

## Relationship to Tree Views

The hierarchy view and the standard list (tree) view both show multiple records, but with key differences:

| Aspect | List View | Hierarchy View |
|--------|-----------|--------------|
| Display | Flat table rows | Expandable tree nodes |
| Parent-child | Not visualized | Explicitly shown |
| Expand/collapse | Not available | Core interaction |
| Drag-and-drop | Not available | Available (`draggable`) |
| Sorting | Column headers | `default_order` attribute |
| Inline editing | Per-cell | Per-node (full record) |
| Best for | Tabular data, reports | Org charts, category trees |

## Common Configuration Mistakes

**Missing `parent_field`**: If omitted, defaults to `parent_id`. If the model uses a different parent field name (e.g., `category_id` on `product.template`), you must specify it explicitly.

**Circular reference**: The model should have a constraint preventing a record from being its own ancestor. Without this, drag-and-drop can create infinite recursion.

**Missing field access**: If a field in the template is not in the active field list or the user lacks read access, the node renders with an error. Ensure all displayed fields have proper ACLs.

**Wrong view type**: The `type` field on the view record must be `hierarchy`, not `tree`. The old `<tree>` view type still exists in Odoo 19 (it renders as a list/table), but `<hierarchy>` is the new widget for tree structures.

## Related Models

| Model | Role |
|-------|------|
| `ir.ui.view` | Registers `hierarchy` as a view type |
| `ir.actions.act_window.view` | Adds hierarchy to view mode options |
| `base` (mixin) | Provides `hierarchy_read()` data fetching |
| `hr.employee` | Common use case (org chart) |
| `product.category` | Category tree |
| `account.account` | Chart of accounts |

## Related

- [Core/BaseModel](BaseModel.md) -- ORM foundation, `_parent_name`, `_parent_store`
- [Core/Fields](Fields.md) -- Char, Many2one, One2many field types
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) -- How `base` mixin works
