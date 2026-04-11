# AutoResearch System Design

**Date:** 2026-04-10
**Status:** FOCUSED - 2 approaches selected
**Type:** Vault Enhancement / Autonomous Research System
**Selected Approaches:** Code vs Doc Tension + Depth Escalation (Parallel)

---

## 1. Concept & Vision

Sistem autoresearch adalah agen AI otonom yang bekerja secara terus-menerus untuk:

1. **Men Challenging existing documentation** di vault - memastikan catatan tidak outdated, tidak salah, dan selalu ground-truth dari code
2. **Mengeksplorasi codebase Odoo secara mendalam** - menggali edge cases, cross-module relationships, dan hal-hal yang tidak terdokumentasi di official docs
3. **Self-correcting** - sistem mendeteksi contradictions, gaps, dan inaccuracies, lalu mengupdate atau men-flag catatan yang relevan
4. **Progressive depth** - tidak hanya "document this", tapi terus push "kenapa bisa begitu? apa edge case-nya? bagaimana dengan modul lain?"

**Guiding Principles:**
- **Code is source of truth** - semua dokumentasi harus verifiable dari code Odoo
- **Continuous challenge** - tidak ada yang diasumsikan benar tanpa diverifikasi
- **Parallel verification + exploration** - verifikasi code dan eksplorasi depth berjalan bersamaan
- **Stoppable** - user bisa pause/stop kapan saja, dan sistem bisa resume dari checkpoint

---

## 2. Core Architecture

### 2.1 System Components

```
AutoResearch System
├── Skill Trigger (/autorestart)
│   └── Entry point - user invoke untuk start/stop research
├── Research Agent (Primary)
│   ├── Gap Detector - auto-detect modules/fields/methods yang belum terdokumentasi
│   ├── Code Analyzer - deep dive ke source code Odoo
│   ├── Verification Engine - Code vs Doc Tension (parallel)
│   └── Depth Explorer - Depth Escalation (parallel)
├── Checkpoint Manager
│   ├── Progress Tracker - save state setiap selesai unit kerja
│   ├── Resume Capability - bisa resume dari checkpoint terakhir
│   └── Activity Log - tracking semua aktivitas
└── Documentation Writer
    └── Updates vault dengan verified + deep information
```

### 2.2 Research Log Directory Structure

```
Odoo 19/
└── Research-Log/
    ├── backlog.md                      # Gaps found, priority queue
    ├── verified-status.md             # List of verified vs unverified docs
    ├── active-run/
    │   ├── checkpoint-stock.md         # Progress stock module
    │   ├── checkpoint-sale.md          # Progress sale module
    │   ├── checkpoint-purchase.md       # Progress purchase module
    │   └── ...
    ├── completed-runs/
    │   ├── run-2026-04-10/
    │   │   ├── status.json             # Final state
    │   │   ├── log.md                  # Activity log
    │   │   ├── depth-escalations.md     # Deep dive results
    │   │   └── edge-cases.md            # Edge cases documented
    │   └── run-2026-04-11/
    └── insights/
        ├── depth-escalations.md        # All deep dive results
        ├── edge-cases.md               # All edge cases discovered
        └── versioning-changes.md        # Version-specific behaviors
```

---

## 3. Selected Challenge Approaches

## 3.1 Code vs Doc Tension (Verification Layer)

### Concept

AI secara deliberate menulis catatan dalam format yang membedakan verified vs assumption. Setiap catatan memiliki confidence level dan date verifikasi. AI juga rutin men-challenge catatan lama: "Apakah code masih match dengan ini?"

**Core principle:** Every piece of information in the vault must be traceable to actual code.

### Documentation Format

Every documented entry uses this structured format:

```markdown
---
type: model
module: stock
model: stock.quant
verification_status: verified  # verified | partial | outdated | assumption
verified_at: 2026-04-10
confidence: high  # high | medium | low | unknown
source: ~/odoo/odoo19/odoo/addons/stock/models/stock_quant.py:387-412
---

# stock.quant

## Overview
[One paragraph summary - verified]

## Field: quantity

### Verification
**Status:** ✅ Verified
**Location:** stock_quant.py line 142
**Type:** `fields.Float()`

### Verified Behavior
- Default value: 0.0
- Digits: (10, 3)
- Acts as primary inventory quantity tracking

### Edge Cases (⚠️ Unverified)
- [ ] What happens when set to negative? (ValidationError? Silent?)
- [ ] Decimal precision behavior at boundaries?
- [ ] Rounding behavior on write?

## Field: available_quantity

### Verification
**Status:** ✅ Verified - Computed field
**Location:** stock_quant.py line 156
**Compute method:** `_compute_available_quantity()`

### Verified Behavior
- Formula: `quantity - reserved_quantity`
- Recomputed on: write to quantity or reserved_quantity

### Unverified Questions
- [ ] Does modification trigger onchange in picking UI?
- [ ] Performance impact of recomputation on large quants?

## Method: _update_available_quantity()

### Verification
**Status:** ✅ Verified
**Location:** stock_quant.py:387-412

### Behavior (Verified)
- Signature: `def _update_available_quantity(product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None, strict=False)`
- Returns: `float` delta applied
- Side effects:
  - Updates `quantity` field
  - Triggers `_on_quantity_updated()` if override exists
  - Calls `_merge_quants()` at end

### Edge Cases (⚠️ Unverified)
- [ ] Thread safety in concurrent operations
- [ ] Behavior when location is view type
- [ ] Interaction with package hierarchy

### Calls To (Verified)
- `_merge_quants()` at line 401

### Called By (Verified)
- `stock_move._action_done()` at line 1523 (via `sudo()`)
- `stock_picking.action_done()` at line 892

### Assumptions (⚠️ Unverified)
- [ ] Assumption: Runs in elevated privilege context (no ACL check)
  - Reason: Called from stock.move which uses `sudo()` internally
  - Need: Verify by reading stock_move._action_done() context
```

### Verification Status Meanings

| Status | Description |
|--------|-------------|
| `verified` | Source code read, behavior confirmed, line numbers cited |
| `partial` | Partially verified - core behavior confirmed, edge cases unknown |
| `outdated` | Documentation contradicts current code |
| `assumption` | Written from deduction, not direct code verification |
| `unknown` | Never been verified |

### Verification Triggers

1. **Initial documentation** - semua info yang ditulis harus verified langsung dari code
2. **Re-verification** - ketika碰到 existing docs, verify if still accurate
3. **Challenge cycle** - periodic review of "unverified" items
4. **On-demand** - user bisa request "verify this section"
5. **On conflict** - jika ditemukan contradiction, both sides verified

---

## 3.2 Depth Escalation (Exploration Layer)

### Concept

Setiap kali AI menemukan sesuatu yang sudah terdokumentasi, ia tidak berhenti - ia push lebih dalam. Ada 4 level kedalaman. **Parallel dengan Code vs Doc - saat verifikasi code, AI sekaligus melakukan depth exploration.**

### Four Levels

```
Level 1 (Surface) - "Does this exist?"
├── What is this?
├── Where is it defined?
└── What is the basic signature?

Level 2 (Context) - "Why does this exist?"
├── What problem does it solve?
├── What triggers this?
├── What calls this?
└── What is the lifecycle?

Level 3 (Edge Cases) - "What are the boundaries?"
├── What happens at edge cases?
├── What are the failure modes?
├── What are the security implications?
├── What happens with concurrent access?
└── What are the performance implications?

Level 4 (Historical) - "How did this evolve?"
├── How did this behave in v15, v16, v17, v18?
├── What changed in v19?
├── What is deprecated?
├── What will change in future versions?
└── Are there migration implications?
```

### Escalation Mechanism

**Parallel with Verification:**

Setiap kali AI mem-verifikasi sesuatu, ia juga menjalankan escalation questions.

```
When documenting: stock.quant._update_available_quantity()

Step 1: VERIFY (Code vs Doc)
├── Read source: stock_quant.py:387-412 ✅
├── Confirm behavior ✅
├── Record line numbers ✅
└── Mark as verified ✅

Step 2: ESCALATE (Depth)
├── Level 1: "Method exists, signature confirmed" ✅
├── Level 2: "Why exists?"
│   └── Answer: "To provide atomic quantity updates for stock operations"
│   └── Question: "What triggers this?" → "stock_move._action_done()"
│   └── Question: "What calls this?" → "stock_move, stock_picking, stock_scrap"
├── Level 3: "Edge cases?"
│   └── Question: "What if quantity goes negative?" → "Need to verify - code review"
│   └── Question: "Concurrency?" → "No explicit lock found - potential race condition"
│   └── Question: "Security?" → "Runs in sudo context - ACL bypass possible?"
├── Level 4: "Historical?"
│   └── Question: "Changed in v19?" → "Pre-19 had direct write, v19 added _merge_quants"
│   └── Question: "Migration impact?" → "Old data may have orphaned quants after upgrade"
```

### Escalation Questions Per Type

**For Fields:**
```
Level 1: Name, type, default value, location
Level 2: Why this field exists, who sets it, what depends on it
Level 3: Edge values, validation, constraints, performance at scale
Level 4: When was it introduced, deprecated in favor of what, migration notes
```

**For Methods:**
```
Level 1: Name, signature, parameters, return value
Level 2: Purpose, callers, callees, transaction context
Level 3: Exception paths, side effects, concurrency, security
Level 4: Version changes, deprecation, backwards compatibility
```

**For Relationships:**
```
Level 1: Related model, field type (Many2one, One2many, etc.)
Level 2: Why related, cascade behavior, ondelete
Level 3: Orphan records, circular dependencies, performance
Level 4: When introduced, changes across versions
```

**For States/Workflows:**
```
Level 1: All possible states, initial state
Level 2: Valid transitions, trigger conditions, guards
Level 3: Invalid transition handling, deadlock possibilities
Level 4: State model changes across versions
```

### Stopping Criteria

Depth escalation stops when:
1. **All 4 levels answered** - no more unanswered questions
2. **No more code to explore** - source thoroughly analyzed
3. **User stops** - explicit stop signal or timeout
4. **Checkpoint reached** - time/milestone based save
5. **Diminishing returns** - next level would be speculation, not verification

**Practical stopping rules:**
- Level 4 is optional - only explore if version-specific info is relevant
- Stop Level 3 if edge case is theoretical (no code evidence)
- Document "needs deeper investigation" for questions that can't be answered from code

### Depth Output Format

```markdown
## Escalation: stock.picking.action_done()

### Level 1: Surface
- **Method:** `action_done()` at stock_picking.py:1234
- **Signature:** `self → stock.picking`
- **Purpose:** Validate and complete transfer

### Level 2: Context
- **Problem solved:** Completes transfer, updates moves, creates accounting entries
- **Triggers:** Called by UI "Validate" button or by wizard
- **Called by:**
  - `button_validate()` at line 1200
  - `stock_backorder_confirmation.confirm()` at line 2345
- **Calls:**
  - `self.move_ids.action_done()` - cascade to moves
  - `_autoconfirm_picking()` - if auto mode
  - `_trigger_assign()` - if user_id set

### Level 3: Edge Cases
- **Empty picking:** If no moves, still returns True (no-op)
- **Partial quantity:** Creates backorder if picking_type.create_backorder != 'never'
- **Concurrent validate:** Uses `self.env.cr.commit()` internally - potential issue if nested transaction
- **Security:** Runs as user with picking write rights (not sudo)

### Level 4: Historical
- **v18:** Called `_create_lot()` inline
- **v19:** Extracted to `_create_lot()` method - cleaner, override-able
- **Deprecation:** None
- **Migration:** No special handling needed

### Deeper Questions (Unanswered)
- [ ] Behavior when picking partner has specific address requirements?
- [ ] Interaction with delivery routing rules?
- [ ] Performance on large picking (>100 lines)?
```

---

## 4. Parallel Integration: Verification + Depth

### The Workflow

```
When AI starts documenting a model/field/method:

┌─────────────────────────────────────────────────────────┐
│  PHASE 1: DISCOVER                                       │
│  - Scan code structure                                   │
│  - List all fields, methods, relationships               │
│  - Identify gap vs existing docs                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  PHASE 2: VERIFY + DEPTH (Parallel)                      │
│                                                         │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │ Code vs Doc      │    │ Depth Escalation │          │
│  │ (Verification)   │    │ (Exploration)    │          │
│  │                  │    │                  │          │
│  │ • Read source    │    │ • Level 1: What? │          │
│  │ • Confirm        │    │ • Level 2: Why? │          │
│  │ • Record line    │    │ • Level 3: Edge?│          │
│  │ • Mark status    │    │ • Level 4: Hist? │          │
│  │                  │    │                  │          │
│  │ [SYNCHRONOUS]   │    │ [SYNCHRONOUS]   │          │
│  └──────────────────┘    └──────────────────┘          │
│                                                         │
│  Both run in parallel, results merged                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  PHASE 3: DOCUMENT                                       │
│  - Write verified + deep doc                            │
│  - Mark confidence levels                               │
│  - Flag unverified items for future research            │
│  - Record "deeper questions" for escalation             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  PHASE 4: UPDATE TRACKING                                │
│  - Update verified-status.md                            │
│  - Add to backlog if gaps found                         │
│  - Log to activity                                      │
│  - Check checkpoint interval                            │
└─────────────────────────────────────────────────────────┘
```

### Example: Documenting stock.quant

**Phase 1 (Discover):**
```
Found: stock.quant model has 15 fields, 8 methods
Existing doc: 7 fields documented, 3 methods documented
Gaps: 8 fields, 5 methods not documented
```

**Phase 2 (Verify + Depth in parallel):**

For field `quantity`:
```
Verification:
- Read stock_quant.py line 142
- Confirmed: Float field, default 0.0
- Status: verified ✅

Depth:
- Level 1: "Exists, Float type, default 0" ✅
- Level 2: "Primary tracking field, used by _update_available_quantity" ✅
- Level 3: "Edge case - negative value? Rounding?" → Need to verify
- Level 4: "No version changes in v19"
```

For method `_update_available_quantity()`:
```
Verification:
- Read stock_quant.py line 387-412
- Confirmed: signature, behavior, callers
- Status: verified ✅

Depth:
- Level 1: "Method exists with specific signature" ✅
- Level 2: "Atomic quantity update, called by stock_move._action_done()" ✅
- Level 3: "Concurrency? Security? Edge cases?" → Found potential issue: no locking
- Level 4: "Changed in v19 - _merge_quants added"
```

**Phase 3 (Document):**
```markdown
## Field: quantity

### Verification ✅
- Line: 142
- Type: fields.Float(), default=0.0

### Depth L1: Primary inventory quantity
### Depth L2: Used by _update_available_quantity() for tracking
### Depth L3 ⚠️: Negative value handling - unverified
### Depth L4: No version changes

## Method: _update_available_quantity()

### Verification ✅
- Lines: 387-412
- Signature confirmed

### Depth L1: Method exists
### Depth L2: Atomic quantity update for stock operations
### Depth L3 ⚠️:
  - Concurrency: No explicit lock found ⚠️
  - Security: Runs in sudo context ⚠️
### Depth L4: v19 added _merge_quants() call
```

**Phase 4 (Track):**
```markdown
# Verified Status Update

Entry: stock.quant.quantity
Status: verified
Verified_at: 2026-04-10
Notes: Level 3 edge case (negative value) needs further investigation

Entry: stock.quant._update_available_quantity
Status: verified
Verified_at: 2026-04-10
Notes: Potential concurrency issue flagged, security context flagged
```

---

## 5. Operation Model

### 5.1 Trigger Mechanism

**Entry Point:** Skill `/autorestart`

```markdown
/autorestart [options]

Options:
  --modules=stock,sale,purchase   # Specific modules to research
  --mode=deep                      # deep (Level 4) | medium (Level 3) | quick (Level 2)
  --limit=60m                      # Time limit (m=minutes, h=hours)
  --checkpoint=10m                 # Save checkpoint every N minutes

Commands:
  /autorestart                     # Start with defaults (deep mode, 60m)
  /autorestart --modules=stock     # Focus on stock only
  /autorestart --mode=quick        # Quick verification (Level 2)
  /autorestop                      # Stop current research (graceful)
  /autorestatus                    # Show current status
  /autorelog                       # Show recent activity log
  /autoverify module=stock         # Verify specific module docs
  /autorestop --force              # Immediate stop (may lose progress)
```

### 5.2 Checkpoint-Based Operation

**Checkpoint Trigger:**
- Time-based: Every N minutes (default 10m)
- Milestone-based: After each module/model completion
- Manual: On `/autocheckpoint` command

**Checkpoint File Format:**
```json
{
  "run_id": "run-2026-04-10-001",
  "started_at": "2026-04-10T10:00:00Z",
  "last_checkpoint": "2026-04-10T10:10:00Z",
  "current_module": "stock",
  "current_model": "stock.quant",
  "current_task": "depth escalation on _update_available_quantity",
  "current_depth_level": 3,
  "modules_completed": ["base", "product"],
  "modules_in_progress": ["stock"],
  "modules_pending": ["sale", "purchase", "account", ...],
  "gaps_found_this_run": 15,
  "verified_entries": 42,
  "depth_escalations_done": 15,
  "unverified_items": 8,
  "status": "running",
  "stop_requested": false
}
```

### 5.3 Resume Capability

**On Stop:**
1. Complete current task gracefully
2. Save final checkpoint with `stop_requested: true`
3. Log all findings
4. Mark incomplete work as "partial"

**On Resume:**
1. Load last checkpoint
2. Continue from last task
3. Re-verify "partial" entries (code may have changed)
4. Skip fully completed modules

### 5.4 Stop Mechanism

**Graceful Stop (`/autorestop`):**
- Complete current task
- Final checkpoint
- Log "stopped by user"

**Force Stop (`/autorestop --force`):**
- Save immediately
- May lose current task progress
- Log "force stopped"

**Timeout Stop:**
- If `limit` reached
- Final checkpoint
- Log "timeout"

---

## 6. Gap Detection

### 6.1 Gap Types

| Type | Description | Priority |
|------|-------------|----------|
| Missing Module | Module not documented at all | Critical |
| Missing Model | Module exists but model not documented | High |
| Missing Fields | Model exists but field not documented | High |
| Missing Methods | Model exists but method not documented | High |
| Missing Edge Cases | Method exists but edge cases not explored | Medium |
| Missing Version Info | Feature exists but historical context not documented | Medium |
| Outdated Doc | Doc exists but code has changed | Critical |
| Low Confidence | Entry marked as "assumption" or "partial" | Medium |

### 6.2 Detection Algorithm

```
1. SCAN CODEBASE
   ├── List all modules in ~/odoo/odoo19/odoo/addons/
   ├── For each module: List all models (from __init__.py)
   ├── For each model: List all fields (from class definition)
   └── For each model: List all public methods (not starting with _)

2. COMPARE WITH VAULT
   ├── For each code model: Check if Modules/<module>.md exists
   ├── For each documented model: Cross-check fields
   ├── For each documented field: Verify attributes (type, default, required)
   ├── For each documented method: Check if source still exists
   └── For each method: Verify behavior from code

3. CLASSIFY GAPS
   ├── Parse gap type from comparison
   ├── Assign priority based on:
   │   - Is it a core module (base, product, stock, sale, purchase, account)?
   │   - Is it a commonly used model?
   │   - Is it blocking understanding of other modules?
   └── Generate gap entry for backlog

4. PRIORITIZE
   ├── Dependencies first: document base before dependent modules
   ├── Usage frequency: core modules first
   └── Gap severity: critical gaps first
```

---

## 7. Output Files

### 7.1 Backlog (`backlog.md`)

```markdown
# AutoResearch Backlog

**Last Updated:** 2026-04-10
**Total Gaps:** 47
**Critical:** 5 | **High:** 12 | **Medium:** 30

---

## Critical Priority

### [CRITICAL] stock.quant._update_available_quantity() - Concurrency Issue
**Module:** stock
**Type:** missing-depth-escalation
**Discovery Date:** 2026-04-10
**Issue:** Method has no explicit locking - potential race condition under concurrent operations
**Verification Needed:** Test concurrent access, verify if Odoo has implicit locking
**Status:** Pending

### [CRITICAL] sale.order._create_invoices() - Version Behavior Change
**Module:** sale
**Type:** missing-version-info
**Discovery Date:** 2026-04-10
**Issue:** Method behavior changed in v19 but not documented
**Verification Needed:** Compare v18 vs v19 implementation
**Status:** Pending

---

## High Priority

### [HIGH] stock.picking - Missing fields
**Module:** stock
**Type:** missing-fields
**Fields:** backorder_id, return_id, immediate_transfer
**Status:** Pending

...
```

### 7.2 Verified Status (`verified-status.md`)

```markdown
# Verification Status

**Last Updated:** 2026-04-10
**Total Entries:** 156
**Verified:** 142 | **Partial:** 8 | **Outdated:** 2 | **Unknown:** 4

---

## Verified Entries

| Module | Model | Field/Method | Verified At | Confidence |
|--------|-------|-------------|-------------|------------|
| stock | stock.quant | quantity | 2026-04-10 | high |
| stock | stock.quant | available_quantity | 2026-04-10 | high |
| stock | stock.quant | _update_available_quantity() | 2026-04-10 | high |
| sale | sale.order | name | 2026-04-10 | medium |
| ... | ... | ... | ... | ... |

---

## Entries Needing Attention

### Partial - May Need Deeper Verification

- `stock.picking.action_done()` - Edge cases not fully explored
- `account.move.post()` - Exception paths need verification

### Outdated - Needs Update

- `sale.order.line.product_id` - Onchange behavior changed in v19.2
- `stock.location.usage` - New 'transit' type added in v19.1

### Unknown - Never Verified

- `base.module.module.dependencies` - Complex dependency resolution not studied
- `ir.config_parameter.get()` - Caching behavior unclear

---

## Verification Schedule

- [ ] Re-verify `stock.quant` - Last verified 2026-04-10 (due: 2026-05-10)
- [ ] Re-verify `sale.order` - Last verified 2026-04-10 (due: 2026-05-10)
- [ ] Challenge all "assumption" entries - 4 remaining
```

### 7.3 Activity Log (`log.md`)

```markdown
# AutoResearch Activity Log

**Run ID:** run-2026-04-10-001
**Started:** 2026-04-10T10:00:00
**Status:** Running

---

## Activity Timeline

### 10:00 - Run Started
- Mode: deep
- Modules: all
- Checkpoint: 10m
- Time limit: 60m

### 10:10 - Checkpoint 1
- Modules scanned: base, product
- Models scanned: 24
- Gaps found: 12
- Verified: 35 entries
- Depth L3 reached: 8 items

### 10:20 - Checkpoint 2
- Modules scanned: stock
- Models scanned: 18
- Gaps found: 8
- Verified: 42 entries
- Depth L3 reached: 15 items
- **Critical finding:** stock.quant._update_available_quantity has no locking
- **Note:** Potential race condition - flagged for backlog

### 10:30 - Checkpoint 3
- Current: exploring stock.picking.action_done()
- Depth level: 3/4
- Finding: Method runs in sudo context - ACL bypass possible
```

---

## 8. Implementation Plan

### Phase 1: Core Infrastructure
- [ ] Create Research-Log directory structure
- [ ] Create backlog.md, verified-status.md templates
- [ ] Implement checkpoint manager (save/load JSON)
- [ ] Implement activity logger

### Phase 2: Skill Creation
- [ ] Create `/autorestart` skill
- [ ] Create `/autorestop` skill
- [ ] Create `/autorestatus` skill
- [ ] Create `/autoverify` skill

### Phase 3: Gap Detection
- [ ] Implement module scanner (list all addons)
- [ ] Implement model scanner (parse __init__.py)
- [ ] Implement field scanner (parse model classes)
- [ ] Implement gap classifier
- [ ] Integrate with backlog.md

### Phase 4: Parallel Verification + Depth
- [ ] Implement verification engine (read code, confirm behavior)
- [ ] Implement depth escalation system
- [ ] Implement parallel execution of both
- [ ] Implement structured doc output format

### Phase 5: Continuous Operation
- [ ] Implement continuous loop
- [ ] Implement stop/resume
- [ ] Implement periodic re-verification
- [ ] Create insights collection

---

## 9. Success Metrics

### Quantitative
- **Coverage:** X/304 modules with documentation
- **Verification Rate:** Y% of entries marked "verified"
- **Depth Coverage:** Z% of verified entries with Level 3+ exploration
- **Gaps Remaining:** N items in backlog

### Qualitative
- **Depth:** How comprehensive are the edge case explorations?
- **Accuracy:** How often does vault match actual code?
- **Insight:** How many discoveries go beyond official docs?

### Activity
- **Run Duration:** How long did research run?
- **Work Efficiency:** Checkpoints vs work done
- **Critical Findings:** Number of important discoveries

---

*Document created: 2026-04-10*
*Last updated: 2026-04-10*
*Status: Ready for implementation planning*