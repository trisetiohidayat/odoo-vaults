---
title: Performance Optimization Guide
date: 2026-04-14
tags: [odoo, odoo19, performance, optimization, n+1, batch, index, cache]
related_links:
  - "[[Core/BaseModel]]"
  - "[[Core/API]]"
  - "[[Tools/ORM Operations]]"
  - "[[Modules/Stock]]"
---

# Odoo 19 Performance Optimization Guide

## Table of Contents

1. [N+1 Query Problems](#1-n1-query-problems)
2. [Batch Operations](#2-batch-operations)
3. [Index Strategy](#3-index-strategy)
4. [Domain Operator Efficiency](#4-domain-operator-efficiency)
5. [Computed Field Optimization](#5-computed-field-optimization)
6. [Context & Sudo Performance](#6-context--sudo-performance)
7. [Query Optimization](#7-query-optimization)
8. [View Optimization](#8-view-optimization)
9. [Caching Strategies](#9-caching-strategies)
10. [Heavy Operations](#10-heavy-operations)
11. [Prefetching Control](#11-prefetching-control)
12. [Test Performance](#12-test-performance)

---

## Introduction

Performance optimization is critical for Odoo applications handling large datasets or complex workflows. This guide covers systematic techniques to identify and eliminate performance bottlenecks, based on analysis of Odoo 19's ORM internals (see `~/odoo/odoo19/odoo/odoo/orm/models.py`) and real-world patterns from modules like [[Modules/Stock]] (stock_quant.py) and [[Modules/Account]] (account_account.py).

**Key Constants in Odoo 19 ORM:**

```python
# From odoo/orm/models.py (line 115-118)
AUTOINIT_RECALCULATE_STORED_FIELDS = 1000
INSERT_BATCH_SIZE = 100          # Batch size for bulk INSERT
UPDATE_BATCH_SIZE = 100          # Batch size for bulk UPDATE

# PREFETCH_MAX controls iteration chunking
PREFETCH_MAX = ...              # Limits prefetch per query batch
```

---

## 1. N+1 Query Problems

N+1 is the most common performance issue in Odoo. It occurs when a loop triggers one query per record instead of batching.

### 1.1 Classic N+1 Pattern

```python
# BAD: N+1 - Query per iteration
for order in orders:
    print(order.partner_id.name)          # Triggers query for each order
    for line in order.order_line:
        print(line.product_id.name)       # Triggers query for each line

# GOOD: Prefetch related fields upfront
orders = self.env['sale.order'].search([])
orders.mapped('partner_id.name')          # Single query for all partners
orders.mapped('order_line.product_id.name')  # Single query for all products
```

### 1.2 Detecting N+1 via SQL Logs

Enable SQL logging in `odoo.conf`:

```ini
[options]
# Log all SQL queries (verbose, use only for debugging)
# log_sql = True

# Or use postgresql to analyze:
# SET log_statement = 'all';
# In pg_log or via performance.schema
```

Analyze with `EXPLAIN ANALYZE`:

```sql
-- Check if queries are sequential vs batched
EXPLAIN ANALYZE
SELECT * FROM sale_order_line
WHERE order_id IN (SELECT id FROM sale_order WHERE partner_id = 1);
```

### 1.3 read_group vs Multiple read()

`read_group()` is optimized for aggregation and avoids N+1 by performing GROUP BY at the SQL level:

```python
# BAD: Multiple queries
vouchers = self.search([])
for v in vouchers:
    partner = self.env['res.partner'].browse(v.partner_id.id)
    print(partner.name)

# GOOD: read_group with aggregation
summary = self.env['account.move'].read_group(
    domain=[('move_type', 'in', ['in_invoice', 'in_refund'])],
    fields=['partner_id', 'amount_total:sum', 'amount_residual:sum'],
    groupby=['partner_id'],
    orderby='amount_total:sum desc'
)
# Returns pre-aggregated data in ONE query
```

### 1.4 Real Example from stock_quant.py

Odoo's stock module uses `_read_group` with complex domain normalization (line 135-177 in `stock_quant.py`):

```python
# From stock_quant.py - _compute_last_count_date
groups = self.env['stock.move.line']._read_group(
    [
        ('state', '=', 'done'),
        ('is_inventory', '=', True),
        ('product_id', 'in', self.product_id.ids),
        # Complex domain with OR conditions
        '|', ('lot_id', 'in', self.lot_id.ids), ('lot_id', '=', False),
        # ...
    ],
    ['product_id', 'lot_id', 'package_id', 'owner_id'],
    ['date:max']
)
```

This replaces what would otherwise be thousands of individual queries.

---

## 2. Batch Operations

### 2.1 create_multi (Bulk Insert)

Odoo 19 uses `INSERT_BATCH_SIZE = 100` (line 117). The ORM automatically batches inserts:

```python
# BEST: Pass all values at once - Odoo handles batching internally
self.env['sale.order.line'].create([
    {'order_id': order_id, 'product_id': p.id, 'product_uom_qty': qty}
    for p, qty in products
])

# From odoo/orm/models.py (line 4852-4891) - The ORM chunks large creates
for data_sublist in split_every(INSERT_BATCH_SIZE, data_list):
    cr.execute(SQL(
        'INSERT INTO %s (%s) VALUES %s RETURNING "id"',
        SQL.identifier(self._table),
        SQL(', ').join(map(SQL.identifier, columns)),
        SQL(', ').join(tuple(row) for row in rows),
    ))
```

### 2.2 write() on Recordsets

```python
# GOOD: Write on entire recordset (batched by ORM)
orders.write({'state': 'done'})

# Avoid individual writes in loops
# BAD:
for order in orders:
    order.write({'state': 'done'})

# GOOD:
orders.write([{'state': 'done'}] * len(orders))
```

### 2.3 unlink() on Large Recordsets

The ORM batches deletes using `cr.IN_MAX` (line 4232):

```python
# From models.py - deletion is batched automatically
for sub_ids in split_every(cr.IN_MAX, self.ids):
    cr.execute(SQL(
        "DELETE FROM %s WHERE id IN %s",
        SQL.identifier(self._table), sub_ids,
    ))
```

For manual control:

```python
def unlink_large_set(self, recordset, batch_size=1000):
    """Safely delete large recordsets in chunks"""
    ids = recordset.ids
    for i in range(0, len(ids), batch_size):
        batch = recordset.browse(ids[i:i + batch_size])
        batch.unlink()
        self.env.cr.commit()  # Commit per batch for long operations
```

### 2.4 Chunking Strategy

```python
from odoo.tools import split_every

BATCH_SIZE = 500

def bulk_process(self, record_ids):
    """Process large datasets in chunks"""
    for batch in split_every(BATCH_SIZE, record_ids):
        records = self.browse(batch)
        # Process batch
        self._process_batch(records)
```

---

## 3. Index Strategy

### 3.1 When to Add index=True

**Always index Many2one fields** that are frequently searched or filtered:

```python
# GOOD: Index for common access patterns
partner_id = fields.Many2one('res.partner', index=True)    # Almost always
company_id = fields.Many2one('res.company', index=True)    # Multi-company
location_id = fields.Many2one('stock.location', index=True)  # Stock ops

# From stock_quant.py (line 45-48):
product_id = fields.Many2one(
    'product.product', 'Product',
    index=True,  # Frequent search/index
    ondelete='restrict', required=True, check_company=True)
```

**Consider indexing:**
- Foreign keys used in filters
- Date fields with range queries
- Boolean fields with high selectivity (e.g., `active`)
- Selection fields with many options

### 3.2 Composite Indexes via _indexes

For multi-column queries, define composite indexes:

```python
class SaleOrder(models.Model):
    _name = 'sale.order'

    # Composite index for common query pattern:
    # WHERE company_id = ? AND date_order > ?
    _indexes = [
        'CREATE INDEX sale_order_company_date_idx ON sale_order (company_id, date_order DESC)'
    ]
```

**Partial Index** (PostgreSQL-specific):

```python
_indexes = [
    'CREATE INDEX sale_order_draft_idx ON sale_order (date_order) WHERE state = \'draft\''
]
```

### 3.3 Trigram Index for Text Search

For `ilike` searches on names/descriptions:

```python
# From account_account.py (line 33):
name = fields.Char(string="Account Name", required=True, index='trigram', tracking=True, translate=True)
# index='trigram' creates a GIN trigram index for faster text matching
```

### 3.4 SQL CREATE INDEX

```python
def _auto_init(self):
    super()._auto_init()
    self.env.cr.execute("""
        CREATE INDEX IF NOT EXISTS sale_order_company_date_idx
        ON sale_order (company_id, date_order DESC)
        WHERE state IN ('sale', 'done')
    """)
```

---

## 4. Domain Operator Efficiency

### 4.1 `=id` vs `in`

```python
# FASTEST: Single ID
domain = [('partner_id', '=', partner_id)]

# FAST: Small list
domain = [('partner_id', 'in', [1, 2, 3])]

# SLOWER: Large list (consider subquery)
domain = [('partner_id', 'in', self.search([...]).ids)]
```

### 4.2 `ilike` vs `=`

```python
# FASTEST: Exact match
domain = [('code', '=', '110001')]

# FAST: Trigram index available (requires setup)
domain = [('name', '=ilike', 'Cash')]

# SLOWER: Leading wildcard prevents index usage
domain = [('name', 'ilike', '%cash%')]  # Avoid if possible

# FASTEST: Trailing wildcard allows index
domain = [('name', 'ilike', 'cash%')]
```

### 4.3 parent_of vs child_of

For hierarchical data (categories, locations), use `parent_of`/`child_of`:

```python
# BAD: Expensive recursive query in loop
for child in children:
    domain = [('parent_id', '=', child.id)]
    
# GOOD: Single query with hierarchy operator
domain = [('categ_id', 'child_of', parent_id)]
# Translates to: WHERE parent_path LIKE '{parent_id}/%'

# From stock_quant.py (line 91-93):
tracking = fields.Selection(related='product_id.tracking', readonly=True)
# Uses parent_path for hierarchical lookups
```

### 4.4 Avoiding `%` Prefix in Like

```python
# BAD: Forces full scan
[('name', 'ilike', '%partial%')]

# GOOD: Use =ilike for known patterns
[('name', '=ilike', 'partial%')]

# BETTER: Use separate field with trigram index
[('name', 'ilike', 'partial%')]  # Works if index='trigram'
```

---

## 5. Computed Field Optimization

### 5.1 store=True Importance

**Without `store=True`**: Field is computed on every access, causing repeated computation.

**With `store=True`**: Field is computed once (on dependency change) and stored in DB.

```python
# BAD: Non-stored computed (computed every access)
total_amount = fields.Float(
    compute='_compute_total',
    store=False  # Default - recalculates every read!
)

# GOOD: Stored computed (computed on change, stored in DB)
total_amount = fields.Float(
    compute='_compute_total',
    store=True,  # Recalculate only when dependencies change
    index=True  # Can also be indexed for fast filtering
)
```

From stock_quant.py (line 87-90):

```python
available_quantity = fields.Float(
    'Available Quantity',
    compute='_compute_available_quantity',  # Non-stored (derives from quantity - reserved)
    digits='Product Unit'
)
# Note: Not stored because it depends on quantity which changes frequently
```

### 5.2 search() in Computed Fields (Anti-Pattern)

```python
# BAD: Search inside compute (N+1 trigger!)
@api.depends('partner_id')
def _compute_order_count(self):
    for record in self:
        record.order_count = self.env['sale.order'].search_count([
            ('partner_id', '=', record.partner_id.id)
        ])

# GOOD: Use read_group or mapped
@api.depends('partner_id')
def _compute_order_count(self):
    for record in self:
        # This still causes N+1 - use _compute differently
        pass

# BETTER: Pre-compute with record rules respected
@api.depends('partner_id')
def _compute_order_count(self):
    # Batch compute
    partner_ids = self.mapped('partner_id').ids
    if not partner_ids:
        for record in self:
            record.order_count = 0
        return
    
    counts = dict(self.env['sale.order'].read_group(
        [('partner_id', 'in', partner_ids)],
        ['partner_id'],
        ['id:count']
    ))
    for record in self:
        record.order_count = counts.get(record.partner_id.id, 0)
```

### 5.3 @api.depends Specificity

```python
# BAD: Over-broad dependencies
@api.depends('line_ids', 'line_ids.product_id', 'line_ids.product_id.name')
def _compute_total(self):
    # Triggers on ANY change to lines
    pass

# GOOD: Minimal dependencies
@api.depends('order_line.price_subtotal')
def _compute_amount(self):
    # Only triggers when price_subtotal actually changes
    for order in self:
        order.amount_total = sum(order.order_line.mapped('price_subtotal'))
```

### 5.4 Multi-company Context Dependencies

From account_account.py (line 334-335):

```python
@api.depends_context('company')
@api.depends('code_store')
def _compute_code(self):
    for record, record_root in zip(self, self.with_company(self.env.company.root_id).sudo()):
        record.code = record_root.code_store
```

---

## 6. Context & Sudo Performance

### 6.1 Cost of sudo()

`sudo()` bypasses record rules, but has performance cost:

```python
# Cost: Creates new environment, bypasses cache optimization
records_sudo = records.sudo()

# If you just need to bypass access check for one field:
records.with_prefetch().read(['name'])  # Specify fields

# When sudo is actually needed:
# 1. Reading fields the user cannot access
# 2. Writing to restricted fields
# 3. Bypassing record rules for system operations
```

### 6.2 with_context() Optimization

```python
# GOOD: Batch context changes
records.with_context(tracking_disable=True).write(vals)

# BAD: Multiple context switches
r1 = records.with_context(lang='fr')
r2 = r1.with_context(tz='America/New_York')
r3 = r2.with_context(uid=1)

# GOOD: Single context
records.with_context(lang='fr', tz='America/New_York', uid=1)
```

### 6.3 when_to_avoid_full_sudo

```python
# BAD: Sudo for simple read operations
partner = self.env['res.partner'].sudo().browse(partner_id)

# GOOD: Use sudo only for operations that need it
# Read as normal user
partner = self.env['res.partner'].browse(partner_id)
name = partner.name  # If user has read access

# Only sudo when necessary
if not user_has_access:
    partner = partner.sudo()
    partner.write({'restricted_field': value})
```

### 6.4 Prefetch Disabling

```python
# Disable tracking during bulk operations (from stock_quant.py line 263-313)
quants = self.with_context(inventory_mode=True).create(vals_list)
# Creates are batched when inventory_mode is set

# Disable prefetch when loading many records
self.with_context(prefetch_fields=False).search([])
```

---

## 7. Query Optimization

### 7.1 When to Use raw() SQL

Use raw SQL only when ORM cannot achieve the same efficiently:

```python
# From account_account.py (line 427-442) - Complex multi-company query
results = self.env.execute_query(SQL(
    """ SELECT DISTINCT ON (account_code.code)
               account_code.code,
               agroup.id AS group_id
          FROM (VALUES %(account_code_values)s) AS account_code (code)
     LEFT JOIN account_group agroup
            ON agroup.code_prefix_start <= LEFT(account_code.code, char_length(agroup.code_prefix_start))
           AND agroup.code_prefix_end >= LEFT(account_code.code, char_length(agroup.code_prefix_end))
           AND agroup.company_id = %(root_company_id)s
     ORDER BY account_code.code, char_length(agroup.code_prefix_start) DESC, agroup.id
    """,
    account_code_values=account_code_values,
    root_company_id=self.env.company.root_id.id,
))
```

### 7.2 cr.execute vs env.execute_query

Odoo 19 provides safe SQL execution:

```python
# OLD (still works but deprecated):
self.env.cr.execute(query)

# NEW (Odoo 19 - safer):
self.env.execute_query(SQL(...))  # Auto-parameterization
```

### 7.3 EXPLAIN ANALYZE Pattern

```python
def diagnose_query(self):
    """Analyze query performance"""
    query = """
        EXPLAIN ANALYZE
        SELECT * FROM sale_order
        WHERE partner_id IN (SELECT id FROM res_partner WHERE active = True)
        AND date_order > %s
    """
    self.env.cr.execute(query, (date_from,))
    for row in self.env.cr.fetchall():
        print(row)
```

### 7.4 When raw SQL is Appropriate

| Use Case | ORM Alternative | Raw SQL Benefit |
|----------|---------------|-----------------|
| Complex aggregation with window functions | `read_group` | Complex GROUP BY, PARTITION |
| Bulk update with complex formulas | `write` | SQL math operations |
| CTE (Common Table Expressions) | Nested search | Recursive queries |
| JSON/Array operations | Limited | Full PostgreSQL features |

---

## 8. View Optimization

### 8.1 limit on fields

**List View**: Only load fields you display:

```xml
<!-- BAD: Load all fields including heavy computed fields -->
<list>
    <field name="name"/>
    <field name="heavy_computed_field"/>  <!-- Full computation -->
</list>

<!-- GOOD: Use view_fields to limit, or use store=True -->
<list>
    <field name="name"/>
    <field name="total_amount" sum="Total"/>  <!-- Stored, pre-aggregated -->
</list>
```

### 8.2 load="" to Disable Auto-read

For fields that shouldn't load on view open:

```xml
<field name="description" load=""/>  <!-- Don't load until user scrolls -->
```

### 8.3 Lazy Values

```python
# In Python model - defer expensive computation
@api.depends('heavy_field')
def _compute_lazy_value(self):
    for record in self:
        if self.env.context.get('compute_now'):
            record.lazy_value = self._expensive_calculation(record)
        else:
            # Leave as None, compute on demand
            record.lazy_value = None
```

### 8.4 List View with Aggregation

```xml
<list string="Orders">
    <field name="partner_id"/>
    <field name="amount_total" sum="Total"/>
    <field name="order_line" widget="one2many_list"/>  <!-- Heavy - consider removing -->
</list>

<!-- Better: Use computed stored field for totals -->
<field name="amount_total" sum="Total"/>  <!-- Already aggregated in SQL -->
```

---

## 9. Caching Strategies

### 9.1 ir.config_parameter for Persistent Cache

```python
# Long-term cache (survives restarts)
config_param = self.env['ir.config_parameter'].sudo()

# Cache API keys, external service configs
cached_value = config_param.get_param('my_module.cache_key')
if not cached_value:
    cached_value = self._fetch_from_external_service()
    config_param.set_param('my_module.cache_key', cached_value)
    # Optional: set expiry with another param
```

### 9.2 LRU Cache (In-Memory)

```python
from odoo.tools import ormcache
from odoo.fields import Datetime

class MyModel(models.Model):
    _name = 'my.model'

    @api.model
    @ormcache('self.env.company.id')
    def _get_company_config(self):
        """Cache per company - cleared on module update"""
        return self.env['res.company'].browse(self.env.company.id)

    # Cache with TTL (using depends_context)
    @api.depends_context('lang')
    @api.model
    @ormcache('self.env.company.id', 'self.env.context.get("lang")')
    def _get_localized_config(self):
        return self._compute_config()
```

### 9.3 TTL Cache with Time Check

```python
from datetime import datetime, timedelta

class RateLimiter:
    _cache = {}
    _ttl = timedelta(minutes=5)
    
    @classmethod
    def get_cached_value(cls, key):
        if key in cls._cache:
            if datetime.now() - cls._cache[key]['time'] < cls._ttl:
                return cls._cache[key]['value']
        return None
    
    @classmethod
    def set_cached_value(cls, key, value):
        cls._cache[key] = {'value': value, 'time': datetime.now()}
```

### 9.4 Cache Invalidation

```python
# Invalidate on specific field changes
@api.constrains('state')
def _invalidate_config_cache(self):
    if self.state == 'done':
        # Clear related caches
        self.env['ir.config_parameter'].set_param('cached_value', '')
```

---

## 10. Heavy Operations

### 10.1 Chunking into Batches

```python
from odoo.tools import split_every

def process_large_import(self, records, batch_size=1000):
    """Process large import in chunks"""
    total = len(records)
    for i, batch in enumerate(split_every(batch_size, records)):
        self._process_batch(batch)
        _logger.info(f"Processed {min((i+1)*batch_size, total)}/{total}")
        
def _process_batch(self, batch):
    """Override in subclass"""
    for record in batch:
        record.write({'state': 'processed'})
```

### 10.2 @job with max_retries

```python
from odoo.addons.queue_job.models.job import job

class SaleOrder(models.Model):
    _name = 'sale.order'

    @job
    def process_heavy_export(self):
        """Heavy operation as background job"""
        orders = self.search([('state', '=', 'done')])
        for batch in split_every(500, orders.ids):
            # Process chunk
            self._export_batch(batch)
            # Delay between chunks to avoid memory issues
```

### 10.3 retrying Pattern

```python
from odoo.exceptions import RetryableJobError

class StockPicking(models.Model):
    _name = 'stock.picking'

    def process_with_retry(self):
        try:
            # Heavy operation
            self._heavy_operation()
        except OperationalError as e:
            # PostgreSQL connection error - retry
            raise RetryableJobError(
                "Database connection lost, will retry",
                requeue=True,
            )
        except UserError as e:
            # Business error - don't retry, fail immediately
            raise e
```

### 10.4 Scheduled Actions for Heavy Ops

```python
class StockScheduler(models.Model):
    _name = 'stock.scheduler'

    @api.model
    def _cron_recompute_quants(self):
        """Scheduled job for recomputation"""
        # Only recompute records modified since last run
        last_run = self.env['ir.config_parameter'].get_param(
            'stock.last_quant_recompute', '2000-01-01'
        )
        
        domain = [
            ('write_date', '>', last_run),
            ('inventory_quantity_set', '=', True),
        ]
        
        quants = self.env['stock.quant'].search(domain, limit=1000)
        if quants:
            quants._compute_is_outdated()
            
        # Update last run time
        self.env['ir.config_parameter'].set_param(
            'stock.last_quant_recompute',
            fields.Datetime.to_string(fields.Datetime.now())
        )
```

---

## 11. Prefetching Control

### 11.1 Understanding Prefetch

From models.py (line 361-362):

```python
__slots__ = ['env', '_ids', '_prefetch_ids']
# _prefetch_ids controls which records are loaded together
```

Odoo prefetches: when you access a field on one record, it loads that field for all records in the same prefetch set.

### 11.2 with_prefetch()

```python
# Create custom prefetch set
prefetch_ids = (1, 5, 10, 15, 20)
orders = self.env['sale.order'].browse([1, 5, 10, 15, 20]).with_prefetch(prefetch_ids)

# When you iterate, all 5 will be loaded together
for order in orders:
    print(order.partner_id.name)  # Single query loads all partners
```

### 11.3 read() with Specific Fields

```python
# BAD: Triggers full record load
orders = self.search([('state', '=', 'done')])
for order in orders:
    print(order.partner_id.name)

# GOOD: Read only needed fields
orders = self.search([('state', '=', 'done')])
data = orders.read(['partner_id'])  # One query with just partner_id
for d in data:
    print(d['partner_id'])  # No additional queries

# Combine with prefetch
orders.with_prefetch().read(['name', 'partner_id'])
```

### 11.4 Prefetch Group Control

```python
# From models.py (line 3759-3763):
# Fields with same prefetch group are loaded together
if self.env.context.get('prefetch_fields', True) and field.prefetch:
    # select fields with the same prefetch group
    if f.prefetch == field.prefetch
```

Customize prefetch behavior:

```python
# Split large recordset into smaller prefetch chunks
for batch in split_every(100, large_recordset):
    # Each batch has independent prefetch
    for record in batch:
        record.some_field  # Loads 100 at a time
```

---

## 12. Test Performance

### 12.1 setUpClass for Common Fixtures

```python
from odoo.tests import TransactionCase

class TestSalePerformance(TransactionCase):
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create once, reuse in all tests
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
        })
        
    def test_order_creation(self):
        # Uses cls.partner, cls.product from setUpClass
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 5,
            })]
        })
```

### 12.2 cold_start vs warm_start

```python
class TestLoadPerformance(TransactionCase):
    
    def test_cold_start(self):
        """First operation after server start"""
        # Measure: Initial DB connection, registry load
        start = time.time()
        orders = self.env['sale.order'].search([])
        elapsed = time.time() - start
        
    def test_warm_start(self):
        """Operation after cache is populated"""
        # First, warm up the cache
        self.env['sale.order'].search([], limit=1)
        
        # Now measure
        start = time.time()
        orders = self.env['sale.order'].search([])
        elapsed = time.time() - start
```

### 12.3 Test Isolation

```python
class TestIsolated(TransactionCase):
    
    def setUp(self):
        super().setUp()
        # Each test gets fresh transaction
        self.order = self.env['sale.order'].create({...})
        
    def test_1(self):
        # Changes here don't affect test_2
        self.order.write({'state': 'done'})
        
    def test_2(self):
        # Gets fresh order from setUp - not affected by test_1
        pass
```

### 12.4 Performance Benchmarking

```python
import time
from odoo.tests import TransactionCase

class TestBenchmark(TransactionCase):
    
    def test_benchmark_search(self):
        """Benchmark search with different approaches"""
        iterations = 100
        
        # Approach 1: Simple search
        start = time.time()
        for _ in range(iterations):
            self.env['sale.order'].search([('state', '=', 'sale')])
        simple_time = time.time() - start
        
        # Approach 2: Search with limit
        start = time.time()
        for _ in range(iterations):
            self.env['sale.order'].search([('state', '=', 'sale')], limit=100)
        limited_time = time.time() - start
        
        # Log comparison
        _logger.info(f"Simple: {simple_time:.3f}s, Limited: {limited_time:.3f}s")
        
        # Assertions
        self.assertLess(limited_time, simple_time)
```

---

## Quick Reference

### Performance Checklist

- [ ] All Many2one fields have `index=True`
- [ ] Computed fields use `store=True` when frequently accessed
- [ ] Bulk operations use batch methods (`create_multi`, `write` on recordset)
- [ ] N+1 avoided via `read_group`, `mapped`, or `read()`
- [ ] Domain operators optimized (`=` before `in`, trailing `%` in `like`)
- [ ] Trigram indexes on frequently searched text fields
- [ ] `sudo()` only when access rights need bypassing
- [ ] Heavy operations chunked in batches
- [ ] `tracking_disable=True` for bulk operations
- [ ] Tests use `setUpClass` for shared fixtures

### Key Constants (from Odoo 19 ORM)

| Constant | Value | Purpose |
|----------|-------|---------|
| `INSERT_BATCH_SIZE` | 100 | Bulk insert chunk size |
| `UPDATE_BATCH_SIZE` | 100 | Bulk update chunk size |
| `AUTOINIT_RECALCULATE_STORED_FIELDS` | 1000 | Threshold for recompute batching |
| `PREFETCH_MAX` | varies | Recordset iteration chunking |

### Related Documentation

- [[Core/BaseModel]] - ORM foundation
- [[Core/API]] - decorators for computed fields
- [[Tools/ORM Operations]] - CRUD operations guide
- [[Modules/Stock]] - stock_quant.py performance patterns
- [[Modules/Account]] - account_account.py indexing examples

---

*Document generated: 2026-04-14*
*Source: Analysis of Odoo 19 ORM internals and practical optimization patterns*
