---
title: "ORM Internals Deep Dive"
date: 2026-04-14
tags: [odoo, odoo19, orm, internals, core, deep-dive]
sources: 
  - "/Users/tri-mac/odoo/odoo19/odoo/odoo/orm/models.py (7127 lines)"
  - "/Users/tri-mac/odoo/odoo19/odoo/odoo/orm/fields.py"
  - "/Users/tri-mac/odoo/odoo19/odoo/odoo/orm/environments.py"
  - "/Users/tri-mac/odoo/odoo19/odoo/odoo/osv/fields.py"
version: "1.0"
type: core
module: orm
---

# ORM Internals Deep Dive

## Overview

Dokumentasi ini menjelaskan internal ORM Odoo 19 secara mendalam — bagaimana recordset bekerja, mekanisme caching, environment management, dan flow control. Berbeda dengan [[Core/BaseModel]] yang fokus pada penggunaan API, dokumen ini mengekspos mekanisme internal yang jarang ter文档化.

**Source Location:** `odoo/odoo/orm/models.py` (7,127 lines), `orm/fields.py`, `orm/environments.py`

**Architecture at a Glance:**

```
┌─────────────────────────────────────────────────────────────┐
│                        BaseModel                            │
│  __slots__ = ['env', '_ids', '_prefetch_ids']               │
├─────────────────────────────────────────────────────────────┤
│  Recordset Operations: search(), browse(), create(), write() │
│  Prefetching: _prefetch_ids controls batch reads            │
│  Modified Triggers: modified() → invalidate → recompute       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Environment                              │
│  cr (cursor) + uid (user) + context + su (superuser)         │
│  Provides: cache, tocompute, protected, transaction         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Transaction                             │
│  field_data, field_dirty, tocompute, protected, cache         │
│  Manages: flush, commit, rollback lifecycle                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. Recordset Lazy Evaluation

### 1.1 How `self` Works

Setiap method di Odoo model menerima `self` sebagai recordset — bukan single record. Recordset adalah ordered collection dari records dengan karakteristik lazy evaluation.

**Source: `orm/models.py` — BaseModel definition:**
```python
class BaseModel(metaclass=MetaModel):
    """..."""
    __slots__ = ['env', '_ids', '_prefetch_ids']

    # _ids: tuple of record IDs (empty for new records)
    # _prefetch_ids: IDs for prefetching optimization
```

**Recordset Structure:**
```python
# Simplified recordset internal representation
class BaseModel:
    def __init__(self, env, ids, prefetch_ids):
        self.env = env           # Environment (cr, uid, context, su)
        self._ids = ids or ()    # Tuple of record IDs
        self._prefetch_ids = prefetch_ids or ids  # Prefetch batch
```

**When is Database Actually Hit?**

| Operation | DB Hit Point | Trigger |
|-----------|-------------|---------|
| `search()` | **Immediately** | SQL query executes |
| `browse()` | **Never** (lazy) | Only when fields accessed |
| `read()` | **On field access** | Triggers prefetch batch |
| `write()` | **On field assignment** | Cache marked dirty, flush triggers |
| `create()` | **On create() call** | INSERT executed |

### 1.2 ensure_one()

`ensure_one()` adalah guard yang memastikan recordset hanya berisi tepat satu record.

**Implementation:**
```python
# From models.py - modified() and related pattern
def ensure_one(self):
    """Raise if ``self`` is not a single-record recordset."""
    if len(self) != 1:
        raise ValueError("Expected singleton: %s" % self)
```

**Usage Pattern:**
```python
def action_confirm(self):
    self.ensure_one()  # Guard - single record only
    if self.state != 'draft':
        raise UserError("Can only confirm draft orders")
    self.write({'state': 'sale'})
    return True
```

**Behind the scenes:**
```python
# When you do self.ensure_one()
# ORM checks len(self._ids)
# If len != 1, raises ValueError with record info

# Common mistake:
orders = self.env['sale.order'].search([('state', '=', 'draft')])
orders.action_confirm()  # ValueError: Expected singleton: sale.order(1, 5, 8, 12)

# Correct pattern - loop:
for order in orders:
    order.action_confirm()  # Each iteration = single record
```

### 1.3 Recordsets are Sets (Not Lists)

Recordset behavior mirrors Python sets, not lists:

**Set-like Properties:**
```python
# Records are unique - no duplicates
partners = self.env['res.partner'].search([])
partner_1 = partners[0]
partner_2 = partners[0]  # Same object, not a copy

# Union/intersection operations
a = self.env['res.partner'].search([('country_id', '=', 1)])
b = self.env['res.partner'].search([('customer_rank', '>', 0)])

combined = a | b        # Union
common = a & b          # Intersection
only_in_a = a - b       # Difference

# Membership test
if partner in partners:  # Uses __contains__
    print("Found!")
```

**Key Difference from Lists:**
```python
# List behavior
lst = [1, 2, 3, 1, 2]  # Duplicates allowed
lst[0] = 999            # Modifies index 0 only

# Recordset behavior
records = self.env['model'].browse([1, 2, 1, 2])  # Duplicates removed
# records._ids = (1, 2) - automatically deduplicated!

# Implications:
# 1. Can't have same ID twice
# 2. Ordering matters (tuple), but duplicates don't
# 3. Set operations work: |, &, -, +, etc.
```

**Empty Recordset Pattern:**
```python
# Empty recordset is falsy
if not records:
    return []  # No records to process

# But empty recordset has model info
empty = self.env['sale.order']
print(empty._name)  # 'sale.order'
print(len(empty))   # 0

# Can chain operations on empty (returns empty)
empty.search_count()  # Returns 0
empty.read(['name'])  # Returns []
```

### 1.4 Lazy Evaluation Mechanics

**Flow: Lazy Evaluation to Actual DB Hit**

```python
# Step 1: search() creates recordset (NO DB hit for data)
orders = self.env['sale.order'].search([
    ('state', '=', 'draft')
])
# SQL: SELECT id FROM sale_order WHERE state = 'draft'
# Result: orders._ids = (1, 5, 9, 23, ...)

# Step 2: Access field - triggers fetch
print(orders[0].name)  # DB HIT HERE
# ORM:
# 1. Check if 'name' is in cache for ids (1,5,9,23,...)
# 2. If not, execute batch fetch for prefetch_ids
# 3. Return value for id=1

# Step 3: Access another field on same recordset
print(orders[0].amount_total)  # May hit DB if not prefetched
# Prefetch logic: if 'name' was fetched, also fetch 'amount_total'
# for all records in orders._ids (batched)

# Step 4: Another record's field
print(orders[1].name)  # No DB hit - already prefetched
```

---

## 2. Prefetching Mechanism

### 2.1 How Prefetching Works

Prefetching adalah optimization mechanism yang batch-reads field values untuk menghindari N+1 queries.

**Source: `orm/models.py` — fetch() and _fetch_field():**
```python
def _fetch_field(self, field: Field) -> None:
    """ Read from the database in order to fetch ``field`` 
        for ``self`` in cache. """
    # determine which fields can be prefetched
    if self.env.context.get('prefetch_fields', True) and field.prefetch:
        fnames = [
            name
            for name, f in self._fields.items()
            # select fields with the same prefetch group
            if f.prefetch == field.prefetch
            # discard fields with groups that the user may not access
            if self._has_field_access(f, 'read')
        ]
        if field.name not in fnames:
            fnames.append(field.name)
    else:
        fnames = [field.name]
    self.fetch(fnames)  # Execute batch fetch

def fetch(self, field_names: Collection[str] | None = None) -> None:
    """ Make sure the given fields are in memory for the records in ``self``,
        by fetching what is necessary from the database. """
    self = self._origin
    if not self or not (field_names is None or field_names):
        return

    fields_to_fetch = self._determine_fields_to_fetch(
        field_names, ignore_when_in_cache=True
    )
    
    # ... fetch implementation
    fetched = self._fetch_query(query, fields_to_fetch)
```

### 2.2 Prefetch Groups

Fields are grouped by `prefetch` attribute for batching:

**Prefetch in Field Definition:**
```python
# From fields_misc.py - Id field
class Id(PrimitiveField):
    name = 'ID'
    store = True
    readonly = True
    prefetch = False  # Id is NEVER prefetched (always explicit)

# From fields_properties.py
class Properties(Field):
    type = 'properties'
    prefetch = False  # Properties can't be prefetched

# Default prefetch = True for regular fields
class Char(Field):
    prefetch = True  # Default - batch read with other True fields
```

**How Prefetch Batching Works:**
```python
# Scenario: Reading many partners
partners = self.env['res.partner'].search([])  # 100 records

# Without prefetch: 100 queries for 'name'
for p in partners:
    print(p.name)  # Each = 1 query? NO!

# With prefetch: 1 query for ALL names
# 1. Access partners[0].name
#    - Check cache: not found
#    - Fetch ALL partners' names in one query
# 2. Access partners[1].name ... partners[99].name
#    - All served from cache, no DB hit
```

### 2.3 Prefetch IDs Structure

```python
class BaseModel:
    __slots__ = ['env', '_ids', '_prefetch_ids']
    
    def __init__(self, env, ids, prefetch_ids):
        self.env = env
        self._ids = ids or ()           # Actual record IDs
        self._prefetch_ids = prefetch_ids or ids  # Batch for prefetch
```

**Prefetch ID Usage:**
```python
# When you create a subset recordset
orders = self.env['sale.order'].search([])
subset = orders[:5]  # First 5 records

# subset._ids = (1,2,3,4,5)
# subset._prefetch_ids = orders._ids (all 100 records!)

# This means: when fetching a field for subset,
# ORM can fetch for ALL orders, not just the 5

# Subsequent field access on 'orders' benefits from prefetch
```

### 2.4 _prefetch_ids in _fetch_query

**Source pattern:**
```python
# From models.py _fetch_query
def _fetch_query(self, query: Query, fields: Sequence[Field]) -> Self:
    """ Fetch the given fields from the given query,
        put them in cache, and return the fetched records. """
    
    # column_fields vs other_fields distinction
    column_fields: OrderedSet[Field] = OrderedSet()
    other_fields: OrderedSet[Field] = OrderedSet()
    
    for field in fields:
        if field.name == 'id':
            continue
        assert field.store
        (column_fields if field.column_type else other_fields).add(field)
    
    # Fetch column fields in single SQL query
    if column_fields:
        # The SQL JOINs include prefetch_ids optimization
        # Query uses self._prefetch_ids for batching
```

### 2.5 Prefetch Context Control

**Context flags to control prefetching:**
```python
# Disable prefetch entirely
records.with_context(prefetch_fields=False).read(['name'])

# Selective prefetch
records.with_context(prefetch_langs=True)  # For translated fields

# Prefetch all accessible fields
records.fetch()  # Fetches all prefetch=True fields

# Fetch specific fields only
records.fetch(['name', 'email', 'phone'])  # Specific batch
```

---

## 3. Registry & Environment

### 3.1 Environment Construction

**Source: `orm/environments.py` — Environment class:**
```python
class Environment(Mapping[str, "BaseModel"]):
    """ The environment stores various contextual data used by the ORM:

    - :attr:`cr`: the current database cursor (for database queries);
    - :attr:`uid`: the current user id (for access rights checks);
    - :attr:`context`: the current context dictionary (arbitrary metadata);
    - :attr:`su`: whether in superuser mode.
    """

    cr: BaseCursor
    uid: int
    context: frozendict
    su: bool
    transaction: Transaction

    def __new__(cls, cr: BaseCursor, uid: int, context: dict, su: bool = False):
        assert isinstance(cr, BaseCursor)
        if uid == SUPERUSER_ID:
            su = True

        # determine transaction object
        transaction = cr.transaction
        if transaction is None:
            transaction = cr.transaction = Transaction(Registry(cr.dbname))

        # if env already exists, return it (memoization!)
        for env in transaction.envs:
            if env.cr is cr and env.uid == uid and env.su == su and env.context == context:
                return env

        # otherwise create environment, and add it in the set
        self = object.__new__(cls)
        self.cr, self.uid, self.su = cr, uid, su
        self.context = frozendict(context)
        self.transaction = transaction

        transaction.envs.add(self)
        # the default transaction's environment is the first one with a valid uid
        if transaction.default_env is None and uid and isinstance(uid, int):
            transaction.default_env = self
        return self
```

### 3.2 Environment.__call__ (Environment Switching)

**Source:**
```python
def __call__(
    self,
    cr: BaseCursor | None = None,
    user: IdType | BaseModel | None = None,
    context: dict | None = None,
    su: bool | None = None,
) -> Environment:
    """ Return an environment based on ``self`` with modified parameters. """
    cr = self.cr if cr is None else cr
    uid = self.uid if user is None else int(user)
    if context is None:
        context = clean_context(self.context) if su and not self.su else self.context
    su = (user is None and self.su) if su is None else su
    return Environment(cr, uid, context, su)
```

**Usage patterns:**
```python
# sudo() - switch to superuser
env = self.env.sudo()  # or self.env(su=True)

# with_user() - switch user
env = self.env.with_user(user_id)
env = self.env.with_user(some_user_record)

# with_context() - modify context
env = self.env.with_context(lang='en_US')
env = self.env.with_context(tracking_disable=True)
env = self.env.with_context(force_company=company_id)

# Combined
env = self.env.sudo().with_user(admin_id).with_context(lang='id_ID')
```

### 3.3 Transaction Object

**Source: `orm/environments.py` — Transaction class:**
```python
class Transaction:
    """ A object holding ORM data structures for a transaction. """
    __slots__ = (
        'cache',              # field_data: {field: {id: value}}
        'default_env',        # default Environment for flushing
        'envs',               # WeakSet of Environments
        'field_data',         # {field: {id: value}} cache
        'field_data_patches',  # {field: {id: [patch_ids]}}
        'field_dirty',         # {field: OrderedSet[ids]} dirty fields
        'protected',          # {field: ids} protected from invalidation
        'registry',           # Model registry
        'tocompute',           # {field: OrderedSet[ids]} pending computation
    )

    def __init__(self, registry: Registry):
        self.registry = registry
        self.envs = WeakSet[Environment]()
        # ... initialization
        
        self.field_data = defaultdict(dict)
        self.field_dirty = defaultdict["Field", OrderedSet["IdType"]](OrderedSet)
        self.field_data_patches = defaultdict["Field", defaultdict["IdType", list["IdType"]](lambda: defaultdict(list))
        self.protected = StackMap["Field", OrderedSet["IdType"]]()
        self.tocompute = defaultdict["Field", OrderedSet["IdType"]](OrderedSet)
        self.cache = Cache(self)
```

### 3.4 Model Registry

**Source: `orm/models.py` — MetaModel metaclass:**
```python
class MetaModel(type):
    """ The metaclass of all model classes.
        Its main purpose is to register the models per module.
    """
    _module_to_models__: defaultdict[str, list[MetaModel]] = defaultdict(list)
    pool: Registry | None

    def __new__(meta, name, bases, attrs):
        attrs.setdefault('__slots__', ())
        attrs.setdefault('_field_definitions', [])
        attrs.setdefault('_table_object_definitions', [])

        if attrs.get('_register', True):
            # determine '_module'
            if '_module' not in attrs:
                module = attrs['__module__']
                assert module.startswith('odoo.addons.')
                attrs['_module'] = module.split('.')[2]

            _inherit = attrs.get('_inherit')
            if _inherit and isinstance(_inherit, str):
                attrs.setdefault('_name', _inherit)
                attrs['_inherit'] = [_inherit]

            if not attrs.get('_name'):
                attrs['_name'] = re.sub(r"(?<=[^_])([A-Z])", r".\1", name).lower()

        return super().__new__(meta, name, bases, attrs)
```

### 3.5 Environment Properties (Cached)

```python
@functools.cached_property
def registry(self) -> Registry:
    """Return the registry associated with the transaction."""
    return self.transaction.registry

@functools.cached_property
def cache(self):
    """Return the cache object of the transaction."""
    return self.transaction.cache

@functools.cached_property
def user(self) -> BaseModel:
    """Return the current user (as an instance)."""
    return self(su=True)['res.users'].browse(self.uid)

@functools.cached_property
def company(self) -> BaseModel:
    """Return the current company."""
    company_ids = self.context.get('allowed_company_ids', [])
    if company_ids:
        if not self.su:
            user_company_ids = self.user._get_company_ids()
            if set(company_ids) - set(user_company_ids):
                raise AccessError(...)
        return self['res.company'].browse(company_ids[0])
    return self.user.company_id.with_env(self)

@functools.cached_property
def companies(self) -> BaseModel:
    """Return a recordset of the enabled companies by the user."""
    # Similar logic for multiple companies

@functools.cached_property
def tz(self) -> tzinfo:
    """Return the current timezone info, defaults to UTC."""

@functools.cached_property
def lang(self) -> str | None:
    """Return the current language code."""
```

---

## 4. Transaction Management

### 4.1 Flush Mechanism

**Source: `orm/environments.py` — flush_all():**
```python
def flush_all(self) -> None:
    """ Flush all pending computations and updates to the database. """
    for _ in range(MAX_FIXPOINT_ITERATIONS):
        self._recompute_all()
        model_names = OrderedSet(field.model_name for field in self._field_dirty)
        if not model_names:
            break
        for model_name in model_names:
            self[model_name].flush_model()
    else:
        _logger.warning("Too many iterations for flushing fields!")

def _recompute_all(self) -> None:
    """ Process all pending computations. """
    for _ in range(MAX_FIXPOINT_ITERATIONS):
        fields_ = [field for field, ids in self.transaction.tocompute.items() if any(ids)]
        if not fields_:
            break
        for field in fields_:
            self[field.model_name]._recompute_field(field)
    else:
        _logger.warning("Too many iterations for recomputing fields!")
```

### 4.2 When to Call flush()

**Automatic Flush Points:**
```python
# 1. Before any SQL query (search, read, write)
orders = self.search([('state', '=', 'draft')])  # Auto-flush first

# 2. Before commit
self.env.cr.commit()  # Triggers flush via pre-commit hooks

# 3. At transaction boundaries
self.env.flush_all()  # Manual when needed
```

**Manual Flush Scenarios:**
```python
# 1. After batch create, before external call
records = self.create(batch_values)
self.env.flush_all()  # Ensure all computed fields computed
external_api.process(records.ids)

# 2. Before search with complex computed field domain
# If domain uses computed field, flush first
self.env.flush_all()
results = self.search([('computed_field', '=', value)])

# 3. Reading data that depends on uncommitted changes
self.env.cr.execute("SELECT ...")  # Direct SQL
# Need flush for ORM cached values to be written first
```

### 4.3 flush_model() internals

**Source: `orm/models.py` — flush_model():**
```python
def flush_model(self, fnames: Iterable[str] | None = None) -> None:
    """ Flush pending updates for ``self``'s model. """
    if not self.env.field_dirty:
        return  # Nothing to flush

    # Collect fields to flush
    if fnames is None:
        fnames = self._fields
    dirty_fields = [
        field for field, ids in self.env.field_dirty.items()
        if field.model_name == self._name and field.name in fnames
    ]

    if not dirty_fields:
        return

    # Write dirty field values to database
    for field in dirty_fields:
        ids = self.env.field_dirty[field]
        records = self.browse(ids)
        
        # For each field, batch write dirty values
        self._write_field(records, field, tocompute=False)
        
        # Clear dirty status
        del self.env.field_dirty[field]

def _write_field(self, records, field, tocompute=False):
    """ Write the values of ``field`` for ``records`` to the database. """
    # Build UPDATE statement
    # Execute with batch size (UPDATE_BATCH_SIZE = 100)
    # Handle protected fields
    # Mark as not dirty after successful write
```

### 4.4 Commit/Rollback Integration

**Source: `sql_db.py` — Cursor:**
```python
# From sql_db.py transaction lifecycle
class Cursor:
    def commit(self):
        self.flush()  # Flush pending ORM changes
        self.precommit.clear()  # Run pre-commit hooks
        # ... actual PostgreSQL commit
        self.reset()  # Clear transaction state

    def rollback(self):
        self.clear()  # Clear ORM caches
        self.precommit.clear()
        # ... actual PostgreSQL rollback
        self.reset()

    def clear(self):
        """ Clear the caches of the transaction object. """
        if self.transaction is not None:
            self.transaction.clear()
        self.precommit.clear()
```

---

## 5. Field Delegation (_inherits)

### 5.1 _inherits Definition

**Source: `orm/models.py` — BaseModel attributes:**
```python
_inherits: frozendict[str, str] = frozendict()
"""dictionary {'parent_model': 'm2o_field'} mapping the _name of the parent business
objects to the names of the corresponding foreign key fields to use::

  _inherits = {
      'a.model': 'a_field_id',
      'b.model': 'b_field_id'
  }

implements composition-based inheritance: the new model exposes all
the fields of the inherited models but stores none of them:
the values themselves remain stored on the linked record.
"""
```

### 5.2 Delegation Internals

**How _inherits Works:**

```python
# Example: sale.order.line inherits from product.product
class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherits = {'product.product': 'product_id'}

# What this means:
# - sale_order_line table has:
#   - id (primary key)
#   - product_id (FK to product_product)
#   - other order line specific fields
# - BUT access to product.product fields (name, list_price, etc.)
#   is delegated through product_id FK

# When you read order_line.name:
# 1. Check if 'name' is in sale_order_line columns
# 2. No -> check _inherits
# 3. Found: 'product.product' via 'product_id'
# 4. SELECT name FROM product_product WHERE id = product_id
```

### 5.3 Delegation Field Access

**Source: Field inherited flag:**
```python
# From orm/fields.py
class Field(typing.Generic[T]):
    inherited: bool = False
    inherited_field: Field | None = None
    
    # During setup, if field comes from _inherits:
    if self.inherited:
        self.inherited_field = field  # Parent field
        if field.required:
            self.required = True
        delegate_field = model._fields[self.related.split('.')[0]]
        self._modules = tuple({*self._modules, *delegate_field._modules, *field._modules})
```

**Field Access Path:**
```python
# sale.order.line has _inherits = {'product.product': 'product_id'}

# When accessing order_line.name (Char field from product.product):
# 1. Field 'name' is inherited (field.inherited = True)
# 2. Field's related path = 'product_id.name'
# 3. Delegate field = product_id (Many2one)
# 4. ORM reads product.product record via product_id
# 5. Returns product.name
```

### 5.4 delegate=True vs _inherits

**Two delegation mechanisms:**

```python
# 1. _inherits (class-level delegation)
# Model exposes parent's fields but stores in separate table
class ChildModel(models.Model):
    _name = 'child.model'
    _inherits = {'parent.model': 'parent_id'}
    # Fields stored in parent.model table
    # Child just has FK + extra fields

# 2. delegate=True (field-level delegation)
# Field can delegate access to related model
class SomeModel(models.Model):
    partner_id = fields.Many2one('res.partner', delegate=True)
    # Now you can access partner_id.street directly
    # Even if not defined on SomeModel

# Key difference:
# - _inherits: automatic delegation for ALL parent fields
# - delegate=True: opt-in per field, allows arbitrary access
```

---

## 6. Cache Invalidation

### 6.1 Cache Structure

**Source: `orm/environments.py` — Transaction field_data:**
```python
class Transaction:
    # Main cache: {field: {id: value}}
    field_data = defaultdict["Field", typing.Any](dict)
    
    # Dirty fields: fields with uncommitted changes
    field_dirty = defaultdict["Field", OrderedSet["IdType"]](OrderedSet)
    
    # Protected fields: fields not to invalidate
    protected = StackMap["Field", OrderedSet["IdType"]]()
    
    # Backward-compatible cache view
    cache = Cache(self)
```

### 6.2 clean_cache() and invalidate_all()

**Source:**
```python
def clear(self) -> None:
    """ Clear all record caches, and discard all fields to recompute.
        This may be useful when recovering from a failed ORM operation. """
    reset_cached_properties(self)
    self.transaction.clear()

def invalidate_all(self, flush: bool = True) -> None:
    """ Invalidate the cache of all records.

    :param flush: whether pending updates should be flushed before invalidation.
        It is ``True`` by default, which ensures cache consistency.
        Do not use this parameter unless you know what you are doing.
    """
    if flush:
        self.flush_all()
    self.transaction.invalidate_field_data()
```

### 6.3 When Computed Field Cache is Invalidated

**Computed Field Cache Lifecycle:**

```python
# 1. Field definition
total_amount = fields.Float(
    compute='_compute_total',
    store=True  # Stored computed field
)

# 2. First access or dependency change triggers computation
# _compute_total runs and stores result in cache

# 3. Dependency field changes (e.g., price_unit modified)
@api.depends('price_unit', 'product_uom_qty')
def _compute_total(self):
    for record in self:
        record.total_amount = record.price_unit * record.product_uom_qty

# 4. On price_unit write:
# - ORM marks 'total_amount' as dirty (to-be-recomputed)
# - Stored in Transaction.tocompute[field]

# 5. Cache invalidation:
# - Either on flush (write to DB)
# - Or explicit invalidation
```

### 6.4 modified() Triggers

**Source: Field modification pattern:**
```python
# When a field value is modified on a record:
def __set__(self, records, value):
    # 1. Convert value to cache format
    value = self.convert_to_cache(value, records, validate=False)
    
    # 2. Mark field as dirty (for stored computed fields)
    if self.store and self.compute:
        records.env.transaction.tocompute[self].update(records._ids)
    
    # 3. Invalidate cache for this field
    records._invalidate_cache([self.name])
    
    # 4. Trigger dependent field recomputation
    # (handled by flush mechanism)
```

---

## 7. Modified Triggers

### 7.1 How Field Changes Propagate

**Propagation Chain:**

```python
# Scenario: Write on sale.order.line.price_unit

# 1. Direct effect:
# - price_unit field cache invalidated for the record
# - price_unit marked as dirty in field_dirty

# 2. Stored computed field dependency:
# @api.depends('price_unit', 'product_uom_qty')
# def _compute_total(self):
#     self.total_amount = self.price_unit * self.product_uom_qty

# - total_amount added to tocompute[total_amount_field]
# - Also invalidated from cache

# 3. Cascade to dependent fields:
# If total_amount is dependency for other fields,
# they are also marked for recomputation

# 4. On flush:
# - tocompute fields are processed
# - _recompute_field() called for each
# - Results written to cache and DB (if store=True)
```

### 7.2 modified() Call Chain

**Internal trigger mechanism:**
```python
# From models.py - field assignment flow
def write(self, vals):
    # 1. Validate fields
    self._validate_fields(list(vals.keys()))
    
    # 2. Write values (triggers field.__set__)
    for field_name, value in vals.items():
        self[field_name] = value  # This calls __set__
    
    # 3. Mark as modified for triggers
    self.modified(list(vals.keys()))
    
    # 4. Return True
    return True

def modified(self, field_names):
    """ Mark field as modified for trigger propagation. """
    # For each field:
    # - Invalidate cache for dependent fields
    # - Add to tocompute queue for stored computed
    # - Trigger field-specific behaviors
```

### 7.3 protected() Context Manager

**Protecting Fields from Invalidation:**
```python
# Source: environments.py
@contextmanager
def protecting(self, what, records=None) -> Iterator[None]:
    """ Prevent the invalidation or recomputation of fields on records.
    The parameters are either:
    - ``what`` a collection of fields and ``records`` a recordset, or
    - ``what`` a collection of pairs ``(fields, records)``.
    """
    protected = self._protected
    try:
        protected.pushmap()
        if records is not None:
            what = [(what, records)]
        ids_by_field = defaultdict(list)
        for fields, what_records in what:
            for field in fields:
                ids_by_field[field].extend(what_records._ids)

        for field, rec_ids in ids_by_field.items():
            ids = protected.get(field)
            protected[field] = ids.union(rec_ids) if ids else frozenset(rec_ids)
        yield
    finally:
        protected.popmap()

# Usage:
with self.env.protecting(fields_to_keep, records_to_protect):
    # During this block, field values won't be invalidated
    # Useful for computed field overrides
    pass
```

---

## 8. ORM Method Resolution

### 8.1 _inherited and Method Resolution Order

**Source: MetaModel and model class setup:**
```python
class MetaModel(type):
    """..."""
    def __init__(self, name, bases, attrs):
        super().__init__(name, bases, attrs)

        if not attrs.get('_register', True):
            return

        # Remember which models to instantiate for this module.
        if self._module:
            self._module_to_models__[self._module].append(self)

        if not self._abstract and self._name not in self._inherit:
            # this class defines a model: add magic fields
            def add_default(name, field):
                if name not in attrs:
                    setattr(self, name, field)
                    field.__set_name__(self, name)

            # Add create_uid, create_date, write_uid, write_date
            if attrs.get('_log_access', self._auto):
                # ...
```

### 8.2 _model_classes__ and resolve_mro

**Source: `orm/fields.py` — resolve_mro:**
```python
def resolve_mro(model: BaseModel, name: str, predicate) -> list[typing.Any]:
    """ Return the list of successively overridden values of attribute ``name``
        in mro order on ``model`` that satisfy ``predicate``.  Model registry
        classes are ignored.
    """
    result = []
    for cls in model._model_classes__:  # Model classes, not registry
        value = cls.__dict__.get(name, SENTINEL)
        if value is SENTINEL:
            continue
        if not predicate(value):
            break
        result.append(value)
    return result
```

### 8.3 How super() Resolution Works with _inherit

**Multiple _inherit Resolution:**

```python
# When you have:
# Module A: class SaleOrder(models.Model): _name = 'sale.order'
# Module B: class SaleOrderExtension(models.Model): _inherit = 'sale.order'

# Resolution order:
# 1. Class with _name = 'sale.order' is the PRIMARY
# 2. Classes with _inherit = 'sale.order' are EXTENSIONS
# 3. Method resolution follows Python MRO with extensions

# Example: action_confirm
# Module A defines action_confirm()
# Module B overrides action_confirm()

# When calling order.action_confirm():
# 1. Look in class B first (most recent override)
# 2. If not found, look in class A (inherited)
# 3. If not found, look in BaseModel

# super() in Module B's action_confirm:
# super() refers to Module A's action_confirm
# So B.action_confirm() can call A.action_confirm() via super()
```

### 8.4 Extension Patterns

```python
# Pattern 1: Simple override
class MyExtension(models.Model):
    _inherit = 'sale.order'
    
    def action_confirm(self):
        # Replace original
        # Call parent via super() if needed
        return super().action_confirm()

# Pattern 2: Multiple inheritance
class AdvancedSale(models.Model):
    _inherit = ['sale.order', 'mail.thread', 'mail.activity.mixin']
    # Gets fields/methods from ALL parents
    # MRO determined by Python

# Pattern 3: Adding new fields
class MyExtension(models.Model):
    _inherit = 'sale.order'
    
    x_custom_field = fields.Char('Custom Field')
    # Just adds field, doesn't override any method
```

---

## 9. Environment Switching

### 9.1 sudo()

**Source: Environment.__call__ with su parameter:**
```python
def sudo(self, flag=True):
    """ Return a new environment with superuser mode enabled. """
    return self(su=flag)

# Usage:
# Regular env
self.env.uid  # Current user ID
self.env.user  # Current user record

# Sudo env
self.env.sudo().uid  # Still same uid, but su=True
self.env.sudo().user  # Admin user (with_context like self(su=True))

# Common use:
record.sudo().write({'field': value})  # Bypass access rights
```

### 9.2 with_context()

**Source:**
```python
def with_context(self, *args, **kwargs):
    """ Return a new environment with modified context. """
    if args:
        # with_context(ctx) - replace entire context
        context = args[0]
    else:
        # with_context(key=value) - merge into current
        context = {**self.context, **kwargs}
    return self(context=context)

# Usage:
self.env.with_context(tracking_disable=True)  # Disable mail tracking
self.env.with_context(lang='fr_FR')  # Change language
self.env.with_context(force_company=company_id)  # Multi-company
self.env.with_context(binary_field_real_user=True)  # Binary field access
```

### 9.3 with_user()

**Source:**
```python
def with_user(self, user):
    """ Return a new environment with different user. """
    uid = int(user) if isinstance(user, int) else user.id
    return self(user=uid)

# Usage:
admin_env = self.env.with_user(admin_user)
admin_env['res.partner'].create({...})  # Creates as admin

# Common pattern for API/scheduled actions:
@api.model
def _some_cron_method(self):
    # Default: runs as superuser
    # Switch to specific user if needed
    user_env = self.with_user(uid)
    user_env['some.model'].process_data()
```

### 9.4 with_company()

**Multi-company context switching:**
```python
# Method 1: Context-based
env = self.env.with_context(allowed_company_ids=[company_id])

# Method 2: Using company property
env = self.env.company = company  # Sets allowed_company_ids

# Method 3: Combined with sudo
env = self.env.sudo().with_user(user_id).with_context(
    allowed_company_ids=[company_id]
)

# All three achieve company-aware environment
```

### 9.5 cr vs env

**Cursor vs Environment distinction:**
```python
# cr - raw database cursor
self.env.cr.execute("SELECT id FROM res_partner")
self.env.cr.fetchall()

# env - ORM abstraction layer
self.env['res.partner'].search([])

# When to use cr:
# - Direct SQL queries
# - Performance-critical batch operations
# - Complex queries not expressible in ORM

# When to use env:
# - Normal CRUD operations
# - When access rights matter
# - When you need field-level logic (compute, onchange)

# Mixing:
self.env.flush_all()  # First flush ORM changes
self.env.cr.execute("SELECT ...")  # Then raw SQL
# ORM doesn't know about raw SQL changes!
```

---

## 10. Bypass Mode

### 10.1 with_bypass() Pattern

**Understanding bypass mechanisms:**
```python
# Odoo doesn't have a public with_bypass() method
# But internal mechanisms exist for specific use cases

# 1. sudo() acts as access rights bypass
record.sudo().unlink()  # Bypass ACL, record rules

# 2. For specific field access, using NO_ACCESS trick
# From models.py:
NO_ACCESS = '.'  # Prevents field access via ORM (except sudo)

# 3. bypass_search_access on many2one fields
class SomeField(fields.Many2one):
    bypass_search_access = True  # Skip ir.rule on search

# 4. Direct SQL bypass
# For performance, direct SQL bypasses ORM entirely
# No access rights, no cache, no triggers
```

### 10.2 bypass_jobs (Queue Job internal)

```python
# In Odoo, certain operations bypass normal flow:

# 1. Immediate action execution
env['some.model'].with_context(
    skip_next_workflow=True  # Skip workflow triggers
).write({'state': 'done'})

# 2. Cron job bypassing record rules
# Using @api.model decorated methods run as superuser
@api.model
def _cron_something(self):
    # Runs as superuser, no record rule filtering
    pass

# 3. With_context bypass patterns:
# 'mail_create_nosubscribe': Don't subscribe followers
# 'mail_notify_noemail': No email notification
# 'tracking_disable': No message tracking
```

### 10.3 Security Considerations

**When bypassing is appropriate:**
```python
# DO:
# - System-level operations (ir.cron)
# - Data migration scripts
# - Admin functions

# DON'T:
# - User-facing business logic
# - When other users' data is at risk
# - In regular model methods

# Best practice:
@api.model
def _system_operation(self):
    """ System operation requiring bypass. """
    # Check if this is appropriate context
    if not self.env.is_admin():
        raise AccessError("Admin required")
    
    # Perform operation
    return self.sudo()._do_operation()
```

---

## Summary: Request/Response Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HTTP REQUEST / RPC CALL                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Environment Construction                              │
│  Environment(cr, uid, context, su)                                      │
│  - Attaches to Transaction (or creates new)                              │
│  - Memoizes environment for same parameters                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Model Registry                                    │
│  pool = Registry(dbname)                                               │
│  - Lazy loads model classes                                            │
│  - Resolves _inherit chain                                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Method Execution                                     │
│  def some_method(self):                                                │
│      self.ensure_one()           # Validate single record              │
│      self.check_access('write')  # ACL check                          │
│      self.write({'field': val})   # Triggers modified()                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Cache Invalidation / Recompute                         │
│  - Field dirty marking in Transaction                                  │
│  - tocompute queue for stored computed fields                          │
│  - On flush: _write_field() + _recompute_field()                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SQL Execution                                     │
│  - Batch writes (UPDATE_BATCH_SIZE = 100)                               │
│  - Prefetch reads (prefetch_ids batching)                              │
│  - Automatic transaction management                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Database COMMIT                                     │
│  - flush_all() called before commit                                    │
│  - precommit hooks executed                                            │
│  - Transaction cache cleared on commit/rollback                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [[Core/BaseModel]] - Base model usage and common methods
- [[Core/Fields]] - Field types and attributes
- [[Core/API]] - Decorators (@api.depends, @api.onchange, etc.)
- [[Patterns/Inheritance Patterns]] - _inherit, _inherits patterns
- [[Core/Exceptions]] - ORM exceptions (ValidationError, AccessError)

## Tags

#orm #internals #prefetching #cache #environment #transaction #bypass
