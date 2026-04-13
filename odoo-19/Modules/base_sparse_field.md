# Sparse Fields (`base_sparse_field`)

> **Purpose**: Implementation of "sparse" fields — fields that are mostly null — stored compactly in a JSON serialized field, bypassing PostgreSQL's 1000-column-per-table limit.

```yaml
module: base_sparse_field
category: Hidden
license: LGPL-3
author: Odoo S.A.
version: "1.0"
depends: [base]
```

---

## Module Overview

The `base_sparse_field` module solves a structural limitation of PostgreSQL: tables cannot have more than ~1000 columns. When a model needs many optional attributes that are null for most records, each column wastes schema space.

**Core solution**: multiple "sparse" fields are collapsed into a single `Serialized` field holding a JSON dict. The serialized field acts as a key-value store. Sparse fields are never stored as real PostgreSQL columns — they are computed/inverse-linked against the JSON dict at runtime.

**Dependency chain**: `base` → `base_sparse_field` → any module defining sparse fields.

---

## Architecture

### Three-Layer Model

```
Model Table (PostgreSQL)
├── id                     -- row ID
├── data                   -- fields.Serialized()  →  text column, holds JSON dict
└── (no individual columns for sparse fields)

Runtime Record (Odoo ORM)
├── record.data            →  dict read from JSON column
├── record.some_sparse     →  record.data.get('some_sparse')
└── record.some_sparse = v →  record.data['some_sparse'] = v  then  record.data = record.data
```

### Serialization Granularity

A single `Serialized` field can hold **any number** of sparse field values. All sparse fields pointing to the same serialization field share one JSON blob.

```python
class MyModel(models.Model):
    _name = 'my.model'

    data = fields.Serialized()          # one JSON column for all sparse fields below

    flag    = fields.Boolean(sparse='data')    # "data" key = "flag"
    qty     = fields.Integer(sparse='data')   # "data" key = "qty"
    note    = fields.Char(sparse='data')       # "data" key = "note"
    partner = fields.Many2one('res.partner', sparse='data')  # stored as id integer
```

JSON stored in DB (for example):

```json
{
    "flag": true,
    "qty": 42,
    "note": "Special handling",
    "partner": 7
}
```

### Test Model: `sparse_fields.test`

`models/models.py` defines a `sparse_fields.test` TransientModel used for testing. This model exercises all sparse field types:

| Field | Type | Sparse target |
|-------|------|---------------|
| `data` | `Serialized` | — |
| `boolean` | `Boolean` | `sparse='data'` |
| `integer` | `Integer` | `sparse='data'` |
| `float` | `Float` | `sparse='data'` |
| `char` | `Char` | `sparse='data'` |
| `selection` | `Selection` | `sparse='data'` |
| `partner` | `Many2one` | `sparse='data'` |

---

## `fields.py` — Core Field Implementation

### `monkey_patch` Decorator

```python
def monkey_patch(cls):
    def decorate(func):
        name = func.__name__
        func.super = getattr(cls, name, None)   # save original as func.super
        setattr(cls, name, func)
        return func
    return decorate
```

**Purpose**: Attach a replacement method to any `fields.Field` class method while preserving the original as `.super`. All three patches below call `func.super(...)` to preserve any prior patches (e.g., from other modules).

### Patch 1: `fields.Field._get_attrs`

**File**: `models/fields.py`, line 37

```python
@monkey_patch(fields.Field)
def _get_attrs(self, model_class, name):
    attrs = _get_attrs.super(self, model_class, name)   # call parent _get_attrs first
    if attrs.get('sparse'):
        # by default, sparse fields are not stored and not copied
        attrs['store'] = False              # NEVER stored in a PostgreSQL column
        attrs['copy'] = attrs.get('copy', False)   # defaults False, can be overridden
        attrs['compute'] = self._compute_sparse    # always a compute, never stored
        if not attrs.get('readonly'):
            attrs['inverse'] = self._inverse_sparse  # only if not readonly
    return attrs
```

**Key behaviors enforced for every sparse field**:

| Attribute | Value | Reason |
|-----------|-------|--------|
| `store` | `False` | Never a real PostgreSQL column |
| `copy` | `False` | Copying JSON blob by reference is unsafe |
| `compute` | `_compute_sparse` | Mandatory; reads from serialization field |
| `inverse` | `_inverse_sparse` (if not readonly) | Mandatory for writable fields |

**Note on `store=False`**: Even if a developer passes `store=True` to a sparse field, `_get_attrs` overwrites it to `False`. There is no way to store a sparse field as a real column.

### Patch 2: `fields.Field._compute_sparse`

**File**: `models/fields.py`, line 49

```python
@monkey_patch(fields.Field)
def _compute_sparse(self, records):
    for record in records:
        values = record[self.sparse]          # read full JSON dict from serialization field
        record[self.name] = values.get(self.name)   # extract value by field name as key
    if self.relational:
        for record in records:
            record[self.name] = record[self.name].exists()  # safety: filter deleted IDs
```

**Computed value extraction**: `record.data.get('boolean')` → `None` if absent, value if present.

**Relational field safety (`exists()`)**: For `Many2one` sparse fields, after reading the raw integer ID from JSON, `record[self.name].exists()` replaces the browse record with only the subset whose ID still resolves to an unlinked record. This prevents stale references (deleted partners, products, etc.) from crashing reads.

**Performance implication**: `_compute_sparse` iterates records in Python. For large recordsets, this is less efficient than a SQL JOIN. Sparse fields are designed for occasional reads, not bulk querying.

### Patch 3: `fields.Field._inverse_sparse`

**File**: `models/fields.py`, line 58

```python
@monkey_patch(fields.Field)
def _inverse_sparse(self, records):
    for record in records:
        values = record[self.sparse]           # read current JSON dict
        value = self.convert_to_read(record[self.name], record, use_display_name=False)
        if value:
            if values.get(self.name) != value:
                values[self.name] = value       # write into dict
                record[self.sparse] = values    # trigger ORM write of serialization field
        else:
            if self.name in values:
                values.pop(self.name)           # remove null entries from dict
                record[self.sparse] = values
```

**Bidirectional sync logic**:

1. Read current JSON dict from serialization field (e.g., `record.data`)
2. Convert the sparse field's value using `convert_to_read` (strips display names, converts to canonical form)
3. If new value is truthy → set `dict[field_name] = converted_value`, then write dict back
4. If new value is falsy → pop `field_name` from dict (nulls don't occupy space in JSON)
5. Writing `record[self.sparse] = values` triggers the ORM to write the serialized field, which in turn triggers `_compute_sparse` to re-read — but ORM batching prevents infinite loops

**Null pruning**: Sparse fields that are `False` / `None` / `0` / `''` are removed from the JSON dict rather than stored as explicit nulls. This keeps JSON payloads small.

**Inverse batching**: The outer loop over `records` means one `record[self.sparse] = values` per record. If all records in a `write()` call share the same sparse field name, each record triggers its own JSON write. Large batches (e.g., `env['model'].search([]).write({field: val})`) can cause N individual writes.

---

## `models.py` — ORM Integration

### `Base` Extension

```python
class Base(models.AbstractModel):
    _inherit = 'base'

    def _valid_field_parameter(self, field, name):
        return name == 'sparse' or super()._valid_field_parameter(field, name)
```

**Purpose**: Register `'sparse'` as a valid field parameter. Without this, the ORM raises a validation error when it encounters `sparse='data'` on any field definition.

This is a **monkey-patch at framework level** — it extends `Base` (which every Odoo model inherits from) so that the parameter is globally accepted across all models.

### `IrModelFields` Extension

```python
class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    ttype = fields.Selection(selection_add=[
        ('serialized', 'serialized'),
    ], ondelete={'serialized': 'cascade'})
```

**Adds `'serialized'` to the field type dropdown** in Technical Settings → Database Structure → Models → Fields. This allows developers to declare a field type as `serialized` in the UI.

#### `serialization_field_id` Field

```python
serialization_field_id = fields.Many2one(
    'ir.model.fields',
    string='Serialization Field',
    ondelete='cascade',
    domain="[('ttype','=','serialized'), ('model_id', '=', model_id)]",
    help="If set, this field will be stored in the sparse structure of the "
         "serialization field, instead of having its own database column. "
         "This cannot be changed after creation.",
)
```

**Purpose**: Links a sparse field to its owning serialized field. The domain restricts the Many2one to only show serialized-type fields on the same model.

**Cascade delete**: If the serialization field is deleted, all sparse fields that reference it are cascade-deleted (they cannot survive without their storage container).

#### `write()` Override — Immutability of Serialization

```python
def write(self, vals):
    if 'serialization_field_id' in vals or 'name' in vals:
        for field in self:
            if 'serialization_field_id' in vals and field.serialization_field_id.id != vals['serialization_field_id']:
                raise UserError(_('Changing the storing system for field "%s" is not allowed.', field.name))
            if field.serialization_field_id and (field.name != vals['name']):
                raise UserError(_('Renaming sparse field "%s" is not allowed', field.name))
    return super().write(vals)
```

**Two hard constraints enforced**:

1. **Cannot change the serialization field**: If a sparse field already has a `serialization_field_id`, it cannot be reassigned to a different serialized field.
2. **Cannot rename a sparse field**: If a field has a `serialization_field_id`, its `name` cannot change. Renaming would break the key in the JSON dict — the old key would be orphaned in all existing rows with no migration path.

These constraints are **irreversible in production**. Attempting either raises `UserError`.

#### `_reflect_fields()` Override — Wire Serialization Links

**File**: `models/models.py`, line 41

```python
def _reflect_fields(self, model_names):
    super()._reflect_fields(model_names)   # persist field metadata to ir.model.fields first

    cr = self.env.cr

    # Step 1: Query existing ir.model.fields rows for all models
    query = """
        SELECT model, name, id, serialization_field_id
        FROM ir_model_fields
        WHERE model IN %s
    """
    cr.execute(query, [tuple(model_names)])
    existing = {row[:2]: row[2:] for row in cr.fetchall()}   # {(model, name): (id, serialization_field_id)}

    # Step 2: Determine serialization_field_id for each sparse field by inspecting _fields
    updates = defaultdict(list)
    for model_name in model_names:
        for field_name, field in self.env[model_name]._fields.items():
            field_id, current_value = existing[(model_name, field_name)]
            try:
                value = existing[(model_name, field.sparse)][0] if field.sparse else None
            except KeyError:
                raise UserError(_(
                    'Serialization field "%(serialization_field)s" not found for sparse field %(sparse_field)s!',
                    serialization_field=field.sparse,
                    sparse_field=field,
                ))
            if current_value != value:
                updates[value].append(field_id)

    if not updates:
        return

    # Step 3: Batch-update serialization_field_id on ir.model.fields rows
    query = "UPDATE ir_model_fields SET serialization_field_id=%s WHERE id IN %s"
    for value, ids in updates.items():
        cr.execute(query, [value, tuple(ids)])

    # Step 4: Trigger ORM invalidation so cached field metadata is refreshed
    records = self.browse(id_ for ids in updates.values() for id_ in ids)
    self.pool.post_init(records.modified, ['serialization_field_id'])
```

**Flow**: After the ORM writes field definitions to `ir.model.fields`, this override queries those newly-written rows, looks up the `_fields` dict on each model class, finds which field is named in `sparse='...'`, resolves that to an `ir.model.fields` ID, and batch-updates `serialization_field_id` on all changed fields.

**Important**: `self.pool.post_init` registers a callback to fire after the transaction commits, calling `records.modified` to invalidate the field cache. This ensures subsequent reads see the updated `serialization_field_id`.

**Error handling**: If `field.sparse` references a field name that has no corresponding entry in `ir.model.fields` (e.g., a typo or the serialized field was never persisted), a `UserError` is raised during module load.

#### `_instanciate_attrs()` Override — Restore Sparse from Metadata

```python
def _instanciate_attrs(self, field_data):
    attrs = super()._instanciate_attrs(field_data)
    if attrs and field_data.get('serialization_field_id'):
        serialization_record = self.browse(field_data['serialization_field_id'])
        attrs['sparse'] = serialization_record.name
    return attrs
```

**Purpose**: When Odoo loads a model from `ir.model.fields` (e.g., after a module upgrade or from the registry cache), it needs to reconstruct the field with `sparse='...'` from the stored metadata. This method reads `serialization_field_id` from the field row and sets `attrs['sparse']` to the serialization field's name string.

**Reverse of `_reflect_fields`**: Together, `_reflect_fields` (write model → metadata) and `_instanciate_attrs` (metadata → model) form a round-trip pair.

---

## `Serialized` Field

**File**: `models/fields.py`, line 77

```python
class Serialized(fields.Field):
    """ Serialized fields provide the storage for sparse fields. """
    type = 'serialized'
    column_type = ('text', 'text')      # VARCHAR/TEXT in PostgreSQL

    prefetch = False                   # not prefetched by default

    def convert_to_column_insert(self, value, record, values=None, validate=True):
        return self.convert_to_cache(value, record, validate=validate)

    def convert_to_cache(self, value, record, validate=True):
        # cache format: json.dumps(value) or None
        return json.dumps(value) if isinstance(value, dict) else (value or None)

    def convert_to_record(self, value, record):
        return json.loads(value or "{}")
```

### Storage Chain

| Stage | Format | Method |
|-------|--------|--------|
| DB column (PostgreSQL) | TEXT (JSON string) | `column_type = ('text', 'text')` |
| ORM cache | JSON string or `None` | `convert_to_cache` → `json.dumps` |
| Record attribute | Python `dict` | `convert_to_record` → `json.loads` |

### `prefetch = False`

The serialized field is **not prefetched** automatically. This is a deliberate performance decision: the JSON blob for a table with many sparse fields could be megabytes per row if many sparse values are populated. Prefetching all serialized fields for all records would be prohibitively expensive.

**Consequence**: Reading a sparse field always incurs at least one JSON read from the database (unless the cache is already warm from a prior access to a different sparse field on the same record). Batching of sparse field reads within the same record works because all sparse fields on the same model share one serialized field — reading any sparse field on a record also caches the entire `data` dict.

### `convert_to_cache`

```python
def convert_to_cache(self, value, record, validate=True):
    return json.dumps(value) if isinstance(value, dict) else (value or None)
```

- Accepts a Python `dict` → serializes to JSON string
- Accepts a pre-serialized JSON string (e.g., already JSON) → passes through
- Accepts `None` / falsy → returns `None`

**Idempotent writes**: Calling `record.data = record.data` (a no-op at the Python level) still goes through `convert_to_cache` and can re-serialize if the value is already a dict. This is safe due to ORM batching.

### `convert_to_record`

```python
def convert_to_record(self, value, record):
    return json.loads(value or "{}")
```

- DB TEXT `NULL` → `json.loads("{}")` → `{}`
- DB TEXT `'{"key": 5}'` → `json.loads(...)` → `{'key': 5}`

**Default to empty dict**: `or "{}"` ensures the result is always a dict, never `None`. This eliminates `None`-type errors when accessing sparse fields on records that have never had any sparse values written.

---

## View Integration (`views/views.xml`)

### Model Form View Extension

```xml
<record model="ir.ui.view" id="model_form_view">
    <field name="model">ir.model</field>
    <field name="inherit_id" ref="base.view_model_form"/>
    <field name="arch" type="xml">
        <field name="related" position="before">
            <field name="serialization_field_id"
                domain="[('ttype','=','serialized'), ('model_id','=',parent.model)]"
                readonly="state == 'base'"
                options="{'no_create': True}"/>
        </field>
    </field>
</record>
```

In the Model form (Technical Settings → Models → select a model), the **Serialization Field** dropdown appears before **Related Field**. It is readonly for base/system fields (`state == 'base'`).

### Field Form View Extension

```xml
<record model="ir.ui.view" id="field_form_view">
    <field name="model">ir.model.fields</field>
    <field name="inherit_id" ref="base.view_model_fields_form"/>
    <field name="arch" type="xml">
        <field name="related" position="before">
            <field name="serialization_field_id"
                context="{'default_model_id': model_id, 'default_ttype': 'serialized'}"
                readonly="state == 'base'"
                options="{'no_create': True}"/>
        </field>
    </field>
</record>
```

In the Field form (Technical Settings → Models → Fields → select a field), the **Serialization Field** dropdown appears before **Related Field**. The context sets defaults so creating a new field from this view pre-fills `model_id` and `ttype='serialized'`.

Both fields use `options="{'no_create': True}"` — users must select an existing serialized field; they cannot create one inline from the field form.

---

## Security (`security/ir.model.access.csv`)

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sparse_fields_test,access.sparse_fields_test,model_sparse_fields_test,base.group_system,1,1,1,0
```

**Model**: `sparse_fields.test` (the test TransientModel)

| Permission | Value | Who |
|------------|-------|-----|
| Read | Yes | `base.group_system` (Administrator) |
| Write | Yes | `base.group_system` |
| Create | Yes | `base.group_system` |
| Unlink | No | TransientModels auto-deleted; unlink meaningless |

Only users in the Administrator group can interact with the test model. The actual `Serialized` and sparse fields on real models inherit the security model of their parent model — there is no separate security layer for sparse storage itself.

---

## Test Coverage (`tests/test_sparse_fields.py`)

```python
def test_sparse(self):
    record = self.env['sparse_fields.test'].create({})
    self.assertFalse(record.data)          # empty dict on new record

    partner = self.env.ref('base.main_partner')
    values = [
        ('boolean', True),
        ('integer', 42),
        ('float', 3.14),
        ('char', 'John'),
        ('selection', 'two'),
        ('partner', partner.id),
    ]
    # Sequential write: each field write appends to JSON dict
    for n, (key, val) in enumerate(values):
        record.write({key: val})
        self.assertEqual(record.data, dict(values[:n+1]))

    # Verify reads return correct values (including Many2one resolution)
    for key, val in values[:-1]:
        self.assertEqual(record[key], val)
    self.assertEqual(record.partner, partner)

    # Sequential nulling: setting to False removes key from JSON
    for n, (key, _val) in enumerate(values):
        record.write({key: False})
        self.assertEqual(record.data, dict(values[n+1:]))

    # Reflection: ir.model.fields has serialization_field_id set to 'data'
    names = [name for name, _ in values]
    domain = [('model', '=', 'sparse_fields.test'), ('name', 'in', names)]
    fields = self.env['ir.model.fields'].search(domain)
    self.assertEqual(len(fields), len(names))
    for field in fields:
        self.assertEqual(field.serialization_field_id.name, 'data')
```

The test validates: empty initialization, sequential value writes, value reads (including Many2one), sequential nulling (key removal), and `ir.model.fields` reflection linking all sparse fields to their `serialization_field_id`.

---

## L4: Performance, Edge Cases, and Gotchas

### Performance Considerations

1. **No SQL index on sparse field values**: Because sparse values live inside a JSON TEXT column, PostgreSQL cannot use B-tree indexes on individual keys. Searching/filtering by sparse field value requires a full table scan or a GIN index on the serialized column (not configured by default). Use `domain` filters on sparse fields only for small datasets.

2. **`prefetch = False`**: The serialized field is not prefetched. Every sparse field read that is not already in the ORM cache triggers a DB read. However, since all sparse fields on a model share the same serialization field, the first sparse field access on a record warms the cache for all other sparse fields on that record.

3. **Inverse write amplification**: Writing to N sparse fields on the same record triggers N writes to the serialization field (each `_inverse_sparse` does `record[self.sparse] = values`). The ORM batches these within a single `write()` call, but each field still causes a JSON serialization round-trip.

4. **JSON payload size**: If many sparse fields on a model are populated, the JSON blob can grow large. Odoo reads/writes the entire blob on every access. Models with dozens of heavily-populated sparse fields may experience I/O overhead.

### Edge Cases

1. **Stale Many2one IDs**: If a `res.partner` record referenced by a sparse `Many2one` field is deleted, `convert_to_record` stores the integer ID, and `_compute_sparse` returns a browse record with `.exists() == False`. The value reads as `False`, not as an error. The stale ID is cleaned on next inverse write.

2. **Concurrent writes to same record's serialized field**: If two transactions write different sparse fields on the same record simultaneously, the second write reads a stale `data` dict (missing the first transaction's change). The ORM's optimistic locking does not cover JSON sub-field conflicts. This is a **design-level race condition** — serialize access to sparse fields on high-concurrency models.

3. **Rename immutability**: Attempting to rename a sparse field after it has rows with data raises `UserError`. The JSON keys in existing rows would become orphaned. There is no automated migration.

4. **Serialization field change immutability**: A sparse field's `serialization_field_id` cannot be changed after creation. The JSON values are keyed by field name, not by position — reassigning to a different serialized field would lose context.

5. **Copy behavior**: `copy=False` (default) means duplicating a record via `copy()` does not copy sparse field values. This is usually the desired behavior — the new record starts with an empty `data` dict.

6. **`convert_to_read` and `use_display_name=False`**: In `_inverse_sparse`, the `convert_to_read` call with `use_display_name=False` ensures that Many2one sparse fields store the integer ID, not the name. This makes the JSON portable and avoids name-resolution overhead.

### Odoo 18 → 19 Changes

The `base_sparse_field` module has **no significant behavioral changes** from Odoo 18 to Odoo 19. The module's implementation (monkey-patching `fields.Field`, the `Serialized` class, the `ir.model.fields` extensions) was stable before Odoo 19 and remains unchanged.

Key stable aspects:
- `Serialized` field type and JSON storage mechanism: unchanged
- `_valid_field_parameter` extension on `Base`: unchanged
- `IrModelFields` serialization field linking: unchanged
- `_reflect_fields` round-trip: unchanged

The main area of evolution is around the `fields.Field` base class — any future changes to `_get_attrs`, `_compute_sparse`, or `_inverse_sparse` in the framework would affect sparse field behavior.

### Security Considerations

1. **No column-level ACL on JSON keys**: PostgreSQL row-level security and field access rules in Odoo apply at the column level. Since sparse fields have no PostgreSQL column, they bypass column-level `perm_read` / `perm_write` restrictions on the table. **A user with read access to the model can read all sparse fields**, even if the CSV security file specifies `perm_read=0` on individual fields (which is not possible for sparse fields anyway since they have no column). The model's `perm_read` / `perm_write` governs access.

2. **JSON injection**: Sparse field values are serialized via `json.dumps`. The `convert_to_cache` method passes dict values through `json.dumps` and non-dict values through unchanged. Malicious JSON content in a serialized field is not a vector because the JSON dict is always written as a whole, never concatenated from user input.

3. **Audit trail**: Since sparse field changes are writes to the serialized field, `mail.message` tracking on the model captures the serialized field as a whole, not individual sparse field changes. If you need per-field audit, implement explicit log fields or override `_inverse_sparse` to post tracking messages.

---

## Related Models and Cross-Module Integration

| Model | Relationship | Purpose |
|-------|-------------|---------|
| `ir.model.fields` | Extended by `IrModelFields` | Tracks `ttype='serialized'` and `serialization_field_id` |
| `ir.model` | Extended (view only) | UI for serialization field assignment |
| `base` | Extended (`_valid_field_parameter`) | Accepts `sparse` parameter globally |
| `fields.Field` | Monkey-patched | `_get_attrs`, `_compute_sparse`, `_inverse_sparse` |
| `fields.Serialized` | Added to `fields` module | The storage field class |

**Consumed by**: Any module that defines a `sparse='...'` parameter on a field. Core examples include `fetchmail` (fetchmail.server fields), `payment` (payment.transaction extra data), and various enterprise modules that attach metadata to records without bloating tables.

---

## Complete Field Signature Reference

### `Serialized` (class, `models/fields.py:77`)

```python
class Serialized(fields.Field):
    type = 'serialized'
    column_type = ('text', 'text')
    prefetch = False

    def convert_to_column_insert(self, value, record, values=None, validate=True)
    def convert_to_cache(self, value, record, validate=True)
    def convert_to_record(self, value, record)
```

### `fields.Field._get_attrs` (patched, `models/fields.py:38`)

When `sparse` parameter is present:
```python
attrs['store'] = False
attrs['copy'] = attrs.get('copy', False)
attrs['compute'] = self._compute_sparse
if not attrs.get('readonly'):
    attrs['inverse'] = self._inverse_sparse
```

### `fields.Field._compute_sparse` (patched, `models/fields.py:50`)

```python
def _compute_sparse(self, records)  # void, mutates records in-place
# relational: calls .exists() on each browse record
```

### `fields.Field._inverse_sparse` (patched, `models/fields.py:59`)

```python
def _inverse_sparse(self, records)  # void, writes to serialization field
# null values are pruned (popped) from JSON dict
```

### `Base._valid_field_parameter` (extended, `models/models.py:12`)

```python
def _valid_field_parameter(self, field, name) -> bool
# returns True for name == 'sparse', else delegates to super()
```

### `IrModelFields.write` (overridden, `models/models.py:29`)

- Blocks changes to `serialization_field_id` if already set
- Blocks rename of any field that has `serialization_field_id`

### `IrModelFields._reflect_fields` (overridden, `models/models.py:41`)

After standard field reflection, queries `ir.model.fields` rows and sets `serialization_field_id` for sparse fields by resolving `field.sparse` to its field ID. Raises `UserError` if the referenced serialization field does not exist in `ir.model.fields`.

### `IrModelFields._instanciate_attrs` (overridden, `models/models.py:84`)

Reads `serialization_field_id` from field metadata row and sets `attrs['sparse']` to the serialization field's name string. Used when loading models from the registry after a module upgrade.

---

## Related

- [Core/Fields](Core/Fields.md) — Field types reference (Char, Integer, Many2one, Serialized)
- [Core/API](Core/API.md) — `@api.depends` and computed field patterns
- [Core/BaseModel](Core/BaseModel.md) — ORM foundation, `_inherit`, recordset behavior
- [Tools/ORM Operations](Tools/ORM-Operations.md) — `search()`, `write()`, domain operators