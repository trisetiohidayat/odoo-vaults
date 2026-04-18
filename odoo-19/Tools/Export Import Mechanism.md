---
type: reference
module: base (ir.model.data)
tags: [odoo, odoo19, export, import, external-id, ir_model_data, load, export_data]
created: 2026-04-13
related_skills:
  - odoo19-export-import
  - odoo-orm-sync
---

# External ID & Export/Import Mechanism

## Overview

Dokumentasi ini menjelaskan bagaimana Odoo menghasilkan external ID (`__export__.*`), bagaimana `export_data()` dan `load()` ORM bekerja, dan workflow yang benar untuk export-then-import.

---

## External ID Format

### Format

```
module.name
__export__.tableName_dbID_hash
base.main_partner
```

**Komponen:**
| Komponen | Contoh | Penjelasan |
|----------|--------|------------|
| `module` | `__export__`, `base`, `__import__` | Module name (string sebelum `.`) |
| `name` | `res_partner_bank_2_5d96b266` | Format: `{table}_{dbID}_{hash}` |
| `dbID` | `2` | Primary key integer record |
| `hash` | `5d96b266` | 8 karakter pertama UUID v4 hex |

### Source Code: `__ensure_xml_id()`

**Location:** `~/odoo/odoo19/odoo/odoo/orm/models.py:599-676`

```python
def __ensure_xml_id(self, skip=False):
    """Create missing external ids for records in self"""
    modname = '__export__'

    # Check existing ir_model_data entries
    cr.execute("""
        SELECT res_id, module, name
        FROM ir_model_data
        WHERE model = %s AND res_id IN %s
    """, self._name, tuple(self.ids))
    xids = {res_id: (module, name) for res_id, module, name in cr.fetchall()}

    def to_xid(record_id):
        module, name = xids.get(record_id, (None, None))
        if module:
            return '%s.%s' % (module, name)
        missing.add(record_id)

    missing = set(self.ids) - set(xids.keys())
    if missing:
        xids.update(
            (r.id, (modname, '%s_%s_%s' % (
                r._table,      # e.g., res_partner_bank
                r.id,          # e.g., 2
                uuid.uuid4().hex[:8]  # RANDOM per call, e.g., 5d96b266
            )))
            for r in self.browse(missing)
        )
```

---

## ⚠️ CRITICAL: Hash is RANDOM Per Call

**`uuid.uuid4().hex[:8]` — ini adalah UUID v4 RANDOM, bukan deterministic!**

### Behavior Chart

| Call | Action | Hash Created | ir_model_data |
|------|--------|-------------|----------------|
| **Call 1** | `export_data(['id'])` | INSERT with **RANDOM** hash | 60 new entries created |
| **Call 2** | `export_data(fields)` | REUSE existing entry | Same hash (stable) |
| **Call 3+** | `export_data(...)` | REUSE existing entry | Same hash (stable) |

**⚠️ IMPORTANT:** Always call `export_data(['id'])` FIRST before exporting the actual data. This creates `ir_model_data` entries so subsequent calls produce STABLE IDs.

### Two-Call Export Pattern

```python
# ❌ WRONG: Single call gives RANDOM hash each time
result = records.export_data(['id', 'field1'])
# Each new export will have DIFFERENT hash!

# ✅ CORRECT: Two-call pattern for STABLE IDs
records.export_data(['id'])  # Step 1: creates ir_model_data entries
result = records.export_data(['id', 'field1'])  # Step 2: reuses entries, STABLE
```

**Implikasi:**
- **First export ever** → hash RANDOM → all 60 IDs are new
- **Subsequent exports** → same hash → stable
- **Different DB** → no entries → hash will be new but unresolvable

---

## `export_data()` ORM Method

**Location:** `odoo/orm/models.py:880-892`

```python
def export_data(self, fields_to_export):
    """Export fields for selected objects"""
    if not (self.env.is_admin() or self.env.user.has_group('base.group_allow_export')):
        raise UserError(_("You don't have the rights to export data..."))
    fields_to_export = [fix_import_export_id_paths(f) for f in fields_to_export]
    return {'datas': self._export_rows(fields_to_export)}
```

**Output:** `{'datas': [[row1], [row2], ...]}`
- NO header row in `datas`
- `id` column → external ID string (e.g., `__export__.res_partner_bank_2_5d96b266`)
- Many2one dengan `/id` suffix → external ID string related record
- Many2one tanpa `/id` → display name (string)

**IMPORTANT:** `export_data()` calls `__ensure_xml_id()` which **INSERT** into `ir_model_data` on first export!

---

## `load()` ORM Method

**Location:** `odoo/orm/models.py:894-1073`

```python
@api.model
def load(self, fields, data):
    """Import data matrix, returns {ids, messages, nextrow}"""
    mode = self.env.context.get('mode', 'init')
    current_module = self.env.context.get('module', '__import__')
    noupdate = self.env.context.get('noupdate', False)
```

### Import Resolution Logic

```
Excel id column
  │
  ├─ id EMPTY / None
  │     └─► CREATE new record
  │
  ├─ id = "__export__.table_N_hash"
  │     └─► Resolve via ir_model_data
  │            ├─ Found → UPDATE existing record
  │            └─ Not found → CREATE new record (module='__import__')
  │
  ├─ id = "module.name" (proper external ID)
  │     └─► Resolve via ir_model_data
  │            ├─ Found → UPDATE existing record
  │            └─ Not found → CREATE new record
  │
  └─ id = integer (DB ID)
        └─► UPDATE record by DB ID
```

### Source Code: Resolution

```python
# models.py:5136-5151
for data in data_list:
    xml_id = data.get('xml_id')
    if not xml_id:
        # No xml_id → check for 'id' field in values
        if vals.get('id'):
            data['record'] = self.browse(vals['id'])
            to_update.append(data)  # UPDATE by DB ID
        elif not update:
            to_create.append(data)  # CREATE new
        continue

    # Has xml_id → look up in ir_model_data
    row = existing.get(xml_id)
    if not row:
        to_create.append(data)  # Not found → CREATE
        continue

    # Found → check if record is valid
    d_id, d_module, d_name, d_model, d_res_id, d_noupdate, r_id = row
    record = self.browse(d_res_id)
    if r_id:
        data['record'] = record
        to_update.append(data)  # UPDATE existing
```

---

## Workflow: Correct Export → Import

### ⚠️ CRITICAL: The Two-Call Pattern

A **single** `export_data()` call produces **RANDOM** hashes because `__ensure_xml_id()` uses `uuid.uuid4().hex[:8]` on first creation. The IDs in the Excel are correct, but if you export again, you get **DIFFERENT** IDs!

**The Solution: Two-Call Export**

```python
# STEP 1: First export → creates ir_model_data entries (hash=RANDOM)
records.export_data(['id'])

# STEP 2: Second export → REUSES entries, hash is STABLE
fields = ['id', 'acc_number', 'partner_id/id']
result = records.export_data(fields)
# IDs are now STABLE and match ir_model_data
```

**Why it works:**
- Step 1 inserts 60 entries into `ir_model_data` (one-time RANDOM hash per entry)
- Step 2 finds existing entries → reuses same hash → **STABLE**
- All subsequent exports produce the same IDs

### ✅ Same Database (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: First export_data(['id']) → creates ir_model_data entries│
│  → __ensure_xml_id() INSERT into ir_model_data                   │
│  → hash is RANDOM on first call → stored in DB                   │
│                                                                  │
│  STEP 2: Second export_data(fields) → REUSES entries, STABLE    │
│  → Export to Excel with STABLE external IDs                     │
│                                                                  │
│  STEP 3: Edit Excel (change values, keep id column)             │
│  → External IDs are in ir_model_data, will resolve              │
│                                                                  │
│  STEP 4: Import (resolves IDs via ir_model_data)                │
│  → id column → lookup → found → UPDATE record                   │
│  → Many2one fields resolve via their own ir_model_data entries  │
└─────────────────────────────────────────────────────────────────┘
```

### ❌ Cross-Database (Will Fail)

```
┌─────────────────────────────────────────────────────────────────┐
│  DB-A: Export                                                    │
│  → export_data() creates __export__ entries in DB-A             │
│  → hash = RANDOM (e.g., __export__.res_partner_bank_2_abc123)  │
│                                                                  │
│  DB-B: Import                                                   │
│  → load() tries to resolve __export__.res_partner_bank_2_abc123│
│  → Query ir_model_data in DB-B → NOT FOUND                      │
│  → Result: "No matching record found for external id"           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Cross-Module: Many2one Field Resolution

When exporting `partner_id/id` (with `/id` suffix):
1. `export_data()` calls `__ensure_xml_id()` for `res.partner` records
2. External IDs for partners created/retrieved from `ir_model_data`
3. Excel shows `__export__.res_partner_2632_4fd62e48`

When importing:
1. `load()` resolves `partner_id/id` via `ir_model_data`
2. Looks up `__export__.res_partner_2632_4fd62e48`
3. Finds res_id → writes `partner_id = 2632`

**Requirement:** Both source and target must have the same external ID entry in `ir_model_data`.

---

## Stability Comparison

| ID Type | Example | Stable? | Cross-DB? | Notes |
|---------|---------|---------|-----------|-------|
| `__export__.*` | `__export__.res_partner_2_abc123` | ⚠️ After first creation | ❌ No | Random hash, created on export |
| `__import__.*` | `__import__.res_partner_2` | ✅ Yes | ❌ No | Created on import if not found |
| `module.name` | `base.main_partner`, `my_module.partner_1` | ✅ Yes | ✅ Yes | Stable, manually assigned |
| DB integer ID | `22` | ✅ Yes | ⚠️ Risky | Only if record ID is same in target |

---

## Common Error Messages

### "No matching record found for external id '__export__.*'"

**Cause:** External ID doesn't exist in target DB's `ir_model_data`

**Solutions:**
1. Export and import on the **same database** (IDs exist in same DB)
2. Use **DB integer ID** for many2one fields (partner_id = 2632, not partner_id/id)
3. Use **proper module.name external IDs** that exist in both DBs
4. Generate `__export__` IDs first in target DB by running export_data()

### "The combination Account Number/Partner must be unique"

**Cause:** Record exists, import tries to UPDATE but uniqueness constraint violated

**This is actually CORRECT behavior** when:
- id column IS populated with a valid external ID
- load() resolves it → finds existing record → tries to UPDATE
- The update would create a duplicate unique combination

**Check:** Is this a real duplicate in the DB, or is the external ID pointing to the wrong record?

---

## Best Practices

### 1. Always export from the database where you will import

```bash
# SAME DATABASE - will work
echo "
records = env['res.partner.bank'].search([])
result = records.export_data(['id', 'acc_number', 'partner_id/id'])
# export → edit → import back to same DB
" | python odoo-bin shell -c odoo.conf -d SAME_DB
```

### 2. For cross-DB, use DB integer IDs (not external IDs)

```bash
# Export with DB integer IDs
echo "
records = env['res.partner.bank'].search([])
result = records.export_data(['id', 'acc_number', 'partner_id'])  # no /id
# partner_id column = integer, always resolvable
" | python odoo-bin shell -c odoo.conf -d SOURCE_DB

# Import with integer IDs (no external ID resolution needed)
```

### 3. Create stable external IDs in a custom module

```python
# In your custom module's data file
<record id="my_bank_001" model="res.partner.bank">
    <field name="acc_number">001663384844</field>
    <field name="partner_id" ref="base.main_partner"/>
</record>
```

### 4. For bulk operations, stop Odoo service first

```bash
# Stop Odoo before bulk import via shell
sudo systemctl stop odoo

# Import
echo "
result = env['res.partner.bank'].with_context(tracking_disable=True).load(fields, rows)
print('Imported:', result.get('ids'))
" | python odoo-bin shell -c odoo.conf -d DATABASE

# Start Odoo
sudo systemctl start odoo
```

---

## Field Format Reference

| Field in export_fields | Excel Column | Output for res.partner.bank record 2 |
|------------------------|-------------|--------------------------------------|
| `id` | `id` | `__export__.res_partner_bank_2_5d96b266` |
| `acc_number` | `acc_number` | `001663384844` |
| `partner_id` | `partner_id` | `Markus Schlueter` (display name, no /id) |
| `partner_id/id` | `partner_id/id` | `__export__.res_partner_2632_4fd62e48` |
| `company_id` | `company_id` | `My Company` (display name) |
| `company_id/id` | `company_id/id` | `__export__.res_company_1_abc12345` |

---

## Summary

1. **`__export__` hash is RANDOM** per export call — first call creates entries, subsequent calls reuse
2. **Export and import must happen in SAME database** for `__export__` IDs to resolve
3. **For cross-DB:** use DB integer IDs or stable `module.name` external IDs
4. **Many2one resolution:** `field/id` → external ID lookup via `ir_model_data`
5. **`load()` behavior:** id populated → UPDATE if found, CREATE if not; id empty → always CREATE