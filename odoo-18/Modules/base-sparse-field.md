---
Module: base_sparse_field
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #fields, #modules, #performance
---

# base_sparse_field

Sparse fields allow many rarely-used fields to be stored compactly in a serialized (`text`) database column instead of each having their own column. Implemented via monkey-patching of `fields.Field`.

## Module Overview

- **Field type introduced:** `Serialized` — a `text` column storing JSON-serialized dicts
- **Sparse attribute:** `sparse='field_name'` on any field type
- **Model extended:** `base` (abstract, for `_valid_field_parameter`)
- **Model extended:** `ir.model.fields` (for field reflection)
- **Dependency:** `base`
- **Pattern:** Monkey-patching `fields.Field` class methods

---

## Core Concept

A **sparse field** has a very small probability of being non-null. Rather than allocating a full database column per field, all sparse fields that share the same `sparse` serialization field are stored together as key-value pairs in a JSON dict inside a `text` column.

Example field definition:
```python
data = fields.Serialized()           # the container
boolean = fields.Boolean(sparse='data')
integer = fields.Integer(sparse='data')
```

The `data` field stores: `{"boolean": true, "integer": 42}` as JSON text. The `boolean` and `integer` fields are not stored as their own columns.

---

## Implementation

### Monkey-Patching Pattern

```python
def monkey_patch(cls):
    """ Return a method decorator to monkey-patch the given class. """
    def decorate(func):
        name = func.__name__
        func.super = getattr(cls, name, None)
        setattr(cls, name, func)
        return func
    return decorate
```

Stores the original method as `.super` on the patched method for chaining.

---

### `_get_attrs()` patch

```python
@monkey_patch(fields.Field)
def _get_attrs(self, model_class, name):
    attrs = _get_attrs.super(self, model_class, name)
    if attrs.get('sparse'):
        attrs['store'] = False          # sparse fields are NOT stored as their own column
        attrs['copy'] = attrs.get('copy', False)
        attrs['compute'] = self._compute_sparse
        if not attrs.get('readonly'):
            attrs['inverse'] = self._inverse_sparse
    return attrs
```

When a field with `sparse=...` attribute is defined:
- `store=False` (unless explicitly set True — but normally sparse fields are not stored independently)
- `copy=False` (sparse fields are not copied by default)
- `compute` is set to `_compute_sparse`
- `inverse` is set to `_inverse_sparse` (unless readonly)

---

### `_compute_sparse()` patch

```python
@monkey_patch(fields.Field)
def _compute_sparse(self, records):
    for record in records:
        values = record[self.sparse]
        record[self.name] = values.get(self.name)
    if self.relational:
        for record in records:
            record[self.name] = record[self.name].exists()
```

Reads the serialized container, extracts the field's value by key, assigns it to each record. For relational fields (Many2one), calls `.exists()` to ensure the linked record is still valid.

---

### `_inverse_sparse()` patch

```python
@monkey_patch(fields.Field)
def _inverse_sparse(self, records):
    for record in records:
        values = record[self.sparse]
        value = self.convert_to_read(record[self.name], record, use_display_name=False)
        if value:
            if values.get(self.name) != value:
                values[self.name] = value
                record[self.sparse] = values
        else:
            if self.name in values:
                values.pop(self.name)
                record[self.sparse] = values
```

Writes the field value back into the serialized container. If the value is falsy, removes the key from the dict (lazy cleanup).

---

## `Serialized` Field Class

```python
class Serialized(fields.Field):
    """ Serialized fields provide the storage for sparse fields. """
    type = 'serialized'
    column_type = ('text', 'text')

    prefetch = False  # not prefetched by default

    def convert_to_column_insert(self, value, record, values=None, validate=True):
        return self.convert_to_cache(value, record, validate=validate)

    def convert_to_cache(self, value, record, validate=True):
        return json.dumps(value) if isinstance(value, dict) else (value or None)

    def convert_to_record(self, value, record):
        return json.loads(value or "{}")
```

- **Type:** `'serialized'`
- **DB column:** `text` (no length limit)
- **Cache format:** JSON string (what goes into the DB)
- **Record format:** Python dict (what is used in ORM operations)
- **prefetch=False:** Sparse fields are NOT prefetched with the main query — they are loaded lazily per-record

---

## Model Extensions

### `base` (abstract extension)

```python
class Base(models.AbstractModel):
    _inherit = 'base'

    def _valid_field_parameter(self, field, name):
        return name == 'sparse' or super()._valid_field_parameter(field, name)
```

Registers `'sparse'` as a valid field parameter on all models.

---

### `ir.model.fields` (extension)

```python
class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    ttype = fields.Selection(selection_add=[
        ('serialized', 'serialized'),
    ], ondelete={'serialized': 'cascade'})
    serialization_field_id = fields.Many2one('ir.model.fields',
        string='Serialization Field',
        ondelete='cascade',
        domain="[('ttype','=','serialized'), ('model_id', '=', model_id)]")
```

- Adds `'serialized'` as a field type in the technical model
- Links sparse fields to their container `serialization_field_id`

**`_reflect_fields()` override:**

After calling `super()._reflect_fields()`, it queries the database for fields with a `serialization_field_id`, then updates `serialization_field_id` on any field that has a `sparse` attribute but the link is missing. This ensures the ORM reflection is complete after module installation.

**`_instanciate_attrs()` override:**

When reloading field definitions from `ir.model.fields`, re-applies the `sparse` attribute from `serialization_field_id`.

**`write()` constraint:**

Disallows changing `serialization_field_id` or renaming a sparse field after creation.

---

## Test Model

```python
class TestSparse(models.TransientModel):
    _name = 'sparse_fields.test'
    _description = 'Sparse fields Test'

    data = fields.Serialized()
    boolean = fields.Boolean(sparse='data')
    integer = fields.Integer(sparse='data')
    float = fields.Float(sparse='data')
    char = fields.Char(sparse='data')
    selection = fields.Selection([('one', 'One'), ('two', 'Two')], sparse='data')
    partner = fields.Many2one('res.partner', sparse='data')
```

Demonstrates all supported sparse field types.

---

## L4 Notes

- **Performance tradeoff:** Sparse fields avoid schema bloat (many columns) but trade it for:
  - Each access requires deserializing the JSON dict (CPU cost)
  - Updates require writing the entire container back (write amplification)
  - They cannot be indexed or used in `order=` clauses
- **When to use:** Sparse fields are appropriate when you have many optional properties on a record that are rarely populated (e.g., custom fields, per-record metadata, feature flags).
- **`prefetch=False`:** The serialized field itself is not prefetched. Accessing any sparse field on a recordset will trigger a separate read of the serialized container. For sparse fields, this means reading the JSON text from disk.
- **Relational sparse fields:** Many2one sparse fields call `.exists()` on the browsed record to handle deleted linked records gracefully.
- **`copy=False`:** Sparse fields are not copied by default on `copy()` operations. This is intentional — sparse values are typically ephemeral state, not canonical data.
- **No search:** Because sparse fields are not stored as their own column with an index, they cannot be used in domain filters or SQL `WHERE` clauses efficiently. The search would require a full table scan + JSON parsing.
- **`store=True` with sparse:** While technically possible to set `store=True` on a sparse field, this would allocate a real column AND serialize the value — defeating the purpose. The `_get_attrs` patch sets `store=False` as default, but allows override.
- **Inverse order matters:** The inverse writes back to the container. If two sparse fields on the same record are modified in the same `write()` call, the last one wins because each inverse writes the full container. This is generally safe but means the order of field definition matters for conflict resolution.
