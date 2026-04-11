# AutoResearch System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement an autonomous AI research system for the Odoo 19 vault that continuously verifies documentation against code and explores depth (edge cases, versioning) using parallel Code vs Doc Tension + Depth Escalation approaches.

**Architecture:**
- Skill-based trigger (`/autorestart`) initiates continuous research
- Research agent runs parallel verification + depth exploration on each code element
- Checkpoint-based progress tracking with resume capability
- Structured documentation output with confidence levels and depth levels

**Tech Stack:**
- Claude Code skills system
- Markdown-based tracking files (backlog, verified-status, activity log)
- Odoo 19 source code at `~/odoo/odoo19/odoo/addons/`

---

## Phase 1: Core Infrastructure

### Task 1: Create Research-Log Directory Structure

**Files:**
- Create: `Odoo 19/Research-Log/backlog.md`
- Create: `Odoo 19/Research-Log/verified-status.md`
- Create: `Odoo 19/Research-Log/active-run/placeholder.md`
- Create: `Odoo 19/Research-Log/completed-runs/placeholder.md`
- Create: `Odoo 19/Research-Log/insights/placeholder.md`

**Step 1: Create Research-Log directory**

Claude Code: Create the directory structure manually or via Bash.

**Step 2: Create backlog.md template**

```markdown
# AutoResearch Backlog

**Last Updated:** YYYY-MM-DD
**Total Gaps:** 0
**Critical:** 0 | **High:** 0 | **Medium:** 0

---

## Critical Priority

(No items)

---

## High Priority

(No items)

---

## Medium Priority

(No items)

---

## Gap Detection Log

| Date | Module | Model | Type | Description | Status |
|------|--------|-------|------|-------------|--------|
```

**Step 3: Create verified-status.md template**

```markdown
# Verification Status

**Last Updated:** YYYY-MM-DD
**Total Entries:** 0
**Verified:** 0 | **Partial:** 0 | **Outdated:** 0 | **Unknown:** 0

---

## Verified Entries

| Module | Model | Field/Method | Verified At | Confidence | Depth Level |
|--------|-------|-------------|-------------|-------------|--------------|
| (none yet) | | | | | |

---

## Entries Needing Attention

### Partial
- (none)

### Outdated
- (none)

### Unknown
- (none)

---

## Verification Schedule

- (none scheduled)
```

**Step 4: Create placeholder files**

Add minimal `.gitkeep` style files in active-run, completed-runs, insights directories.

---

### Task 2: Implement Checkpoint Manager

**Files:**
- Create: `Odoo 19/Research-Log/active-run/checkpoint.json`
- Create: `Odoo 19/Research-Log/active-run/status.json`
- Modify: (Skill files will use these)

**Step 1: Create initial checkpoint.json template**

```json
{
  "run_id": "",
  "started_at": "",
  "last_checkpoint": "",
  "current_module": "",
  "current_model": "",
  "current_task": "",
  "current_depth_level": 1,
  "modules_completed": [],
  "modules_in_progress": [],
  "modules_pending": [],
  "gaps_found_this_run": 0,
  "verified_entries": 0,
  "depth_escalations_done": 0,
  "unverified_items": 0,
  "status": "idle",
  "stop_requested": false
}
```

**Step 2: Create status.json for active run tracking**

```json
{
  "is_running": false,
  "mode": "deep",
  "time_limit": "60m",
  "checkpoint_interval": "10m",
  "target_modules": "all",
  "run_history": []
}
```

---

### Task 3: Create `/autorestart` Skill

**Files:**
- Create: `~/.claude/skills/autorestart.md` (or appropriate skills directory)

**Step 1: Write the skill file**

```markdown
# AutoResearch - Start/Stop Autonomous Research

## Trigger
`/autorestart [options]` - Start continuous research
`/autorestop` - Stop current research gracefully
`/autorestop --force` - Stop immediately
`/autorestatus` - Show current research status
`/autorelog [lines]` - Show recent activity log

## Options
- `--modules=stock,sale,purchase` - Specific modules to research
- `--mode=deep` - deep (Level 4) | medium (Level 3) | quick (Level 2)
- `--limit=60m` - Time limit (m=minutes, h=hours)
- `--checkpoint=10m` - Save checkpoint every N minutes

## Behavior

### Starting Research
1. Validate Odoo codebase path (`~/odoo/odoo19/odoo/addons/`)
2. Load backlog to understand pending gaps
3. Determine priority order (dependencies, usage frequency)
4. Initialize checkpoint with run_id and start time
5. Begin research loop on highest priority module

### Research Loop (per module)
For each model in module:
1. **Discover**: Scan code for fields/methods
2. **Verify + Depth (parallel)**:
   - Code vs Doc: Read source, confirm behavior, record line numbers
   - Depth Escalation: Explore L1-L4 questions
3. **Document**: Write verified + deep doc to vault
4. **Update Tracking**: Update verified-status.md, backlog.md
5. **Checkpoint**: If interval reached, save progress

### Stopping Research
1. Complete current task gracefully
2. Save final checkpoint
3. Log all findings to activity log
4. Update status to "stopped"

## Checkpoint Logic
- Save every N minutes (default 10m)
- Save after each module completion
- Save before stop
- Include: run_id, current position, gaps found, verified count

## Resume Logic
- On new `/autorestart`, check for existing checkpoint
- If checkpoint exists with status="running", offer resume
- Load checkpoint and continue from current position

## Output
- Updates: Research-Log/backlog.md, Research-Log/verified-status.md
- Activity: Research-Log/active-run/log.md
- Insights: Research-Log/insights/depth-escalations.md
```

**Step 2: Verify skill file is in correct location**

Claude Code will need to confirm the skill is registered in the appropriate skills directory.

---

## Phase 2: Code Scanner (Gap Detection)

### Task 4: Module Scanner

**Files:**
- Create: scanner_module.py (temporary script)
- Test: test_module_scanner.py

**Step 1: Write test for module scanner**

```python
import os

def test_module_scanner_finds_all_modules():
    """Test that scanner finds all modules in addons directory."""
    addons_path = os.path.expanduser("~/odoo/odoo19/odoo/addons/")
    modules = [d for d in os.listdir(addons_path)
               if os.path.isdir(os.path.join(addons_path, d))
               and not d.startswith('_')]
    # Should find stock, sale, purchase, account, etc.
    assert 'stock' in modules
    assert 'sale' in modules
    assert 'purchase' in modules
    assert len(modules) > 100  # Odoo 19 has 304 modules
    print(f"Found {len(modules)} modules")

def test_module_scanner_filters_meta():
    """Test that scanner filters __pycache__, __init__, etc."""
    addons_path = os.path.expanduser("~/odoo/odoo19/odoo/addons/")
    modules = [d for d in os.listdir(addons_path)
               if os.path.isdir(os.path.join(addons_path, d))]
    assert '__pycache__' not in modules
    assert '__init__' not in modules
```

**Step 2: Write minimal module scanner**

```python
import os

def scan_modules(addons_path=None):
    """Return list of module names from addons directory."""
    if not addons_path:
        addons_path = os.path.expanduser("~/odoo/odoo19/odoo/addons/")

    modules = []
    for name in os.listdir(addons_path):
        path = os.path.join(addons_path, name)
        if os.path.isdir(path) and not name.startswith('_'):
            modules.append(name)

    return sorted(modules)

if __name__ == "__main__":
    modules = scan_modules()
    print(f"Found {len(modules)} modules")
    print(modules[:20])
```

**Step 3: Run test to verify**

Run: `python scanner_module.py`
Expected: Lists all Odoo modules

**Step 4: Commit**

```bash
git add scanner_module.py
git commit -m "feat: add module scanner for gap detection"
```

---

### Task 5: Model Scanner

**Files:**
- Create: scanner_model.py
- Test: test_model_scanner.py

**Step 1: Write test for model scanner**

```python
import os

def test_model_scanner_finds_stock_models():
    """Test that scanner finds stock module models."""
    models = scan_models('stock')
    model_names = [m['name'] for m in models]
    assert 'stock.quant' in model_names
    assert 'stock.picking' in model_names
    assert 'stock.move' in model_names
    print(f"Found {len(models)} models in stock: {model_names}")

def test_model_scanner_returns_fields():
    """Test that scanner returns field information."""
    models = scan_models('stock')
    quant = next(m for m in models if m['name'] == 'stock.quant')
    fields = quant['fields']
    field_names = [f['name'] for f in fields]
    assert 'quantity' in field_names
    assert 'location_id' in field_names
```

**Step 2: Write model scanner**

```python
import os
import re

def scan_models(module_name, addons_path=None):
    """Scan a module and return its models with fields and methods."""
    if not addons_path:
        addons_path = os.path.expanduser("~/odoo/odoo19/odoo/addons/")

    module_path = os.path.join(addons_path, module_name, 'models')
    if not os.path.isdir(module_path):
        return []

    models = []
    for filename in os.listdir(module_path):
        if filename.endswith('.py') and filename != '__init__.py':
            filepath = os.path.join(module_path, filename)
            with open(filepath, 'r') as f:
                content = f.read()

            # Parse models using regex
            # Look for class definitions inheriting from models.Model
            class_pattern = r'class (\w+)\(models\.Model\):'
            for match in re.finditer(class_pattern, content):
                model_name = match.group(1)
                # Find _name attribute
                name_match = re.search(r'_name\s*=\s*["\'](\w+\.\w+)["\']', content[match.start():match.start()+500])
                if name_match:
                    full_name = name_match.group(1)
                    model_info = {
                        'name': full_name,
                        'file': filename,
                        'fields': extract_fields(content),
                        'methods': extract_methods(content)
                    }
                    models.append(model_info)

    return models

def extract_fields(content):
    """Extract field definitions from model content."""
    # Look for field declarations: name = fields.Xxx(...)
    field_pattern = r'(\w+)\s*=\s*fields?\.\w+\('
    matches = re.findall(field_pattern, content)
    return [{'name': m} for m in matches if not m.startswith('_')]

def extract_methods(content):
    """Extract method definitions from model content."""
    # Look for def method_name(self, ...)
    method_pattern = r'def (\w+)\(self.*?\):'
    matches = re.findall(method_pattern, content)
    return [{'name': m} for m in matches if not m.startswith('_') or m.startswith('__')]
```

**Step 3: Run test**

Run: `python scanner_model.py stock`
Expected: Lists stock models with fields

**Step 4: Commit**

```bash
git add scanner_model.py
git commit -m "feat: add model scanner with field/method extraction"
```

---

### Task 6: Gap Comparison Engine

**Files:**
- Create: gap_detector.py
- Modify: Research-Log/backlog.md

**Step 1: Write gap detector**

```python
import os

def detect_gaps(module_scanner, model_scanner, vault_path):
    """Compare code vs vault to find gaps."""
    gaps = []

    # 1. Get all modules from code
    code_modules = set(module_scanner())

    # 2. Get documented modules from vault
    vault_modules = set(get_vault_modules(vault_path))

    # 3. Missing modules
    missing_modules = code_modules - vault_modules
    for mod in missing_modules:
        gaps.append({
            'type': 'missing_module',
            'module': mod,
            'priority': 'critical' if is_core_module(mod) else 'high',
            'description': f'Module {mod} not documented'
        })

    # 4. For documented modules, check models
    for mod in vault_modules:
        code_models = set(m['name'] for m in model_scanner(mod))
        vault_models = set(get_vault_models(vault_path, mod))

        missing_models = code_models - vault_models
        for model in missing_models:
            gaps.append({
                'type': 'missing_model',
                'module': mod,
                'model': model,
                'priority': 'high',
                'description': f'Model {model} in {mod} not documented'
            })

    return gaps

def is_core_module(module_name):
    """Check if module is core (base, product, stock, sale, purchase, account)."""
    core = ['base', 'product', 'stock', 'sale', 'purchase', 'account', 'mrp', 'crm']
    return module_name in core

def get_vault_modules(vault_path):
    """Get list of documented modules from vault."""
    modules_dir = os.path.join(vault_path, 'Modules')
    if not os.path.isdir(modules_dir):
        return []
    return [f.replace('.md', '') for f in os.listdir(modules_dir) if f.endswith('.md')]

def get_vault_models(vault_path, module_name):
    """Get list of models documented in module."""
    # Parse from module markdown file
    # Look for ## Model: or similar headers
    return []
```

**Step 2: Test gap detector**

Run: `python gap_detector.py`
Expected: Lists all gaps between code and vault

**Step 3: Commit**

```bash
git add gap_detector.py
git commit -m "feat: add gap detection comparing code vs vault"
```

---

## Phase 3: Parallel Verification + Depth

### Task 7: Code Verification Engine

**Files:**
- Create: verification_engine.py

**Step 1: Write verification engine**

```python
import os
import re

class VerificationEngine:
    """Verify documentation against actual code."""

    def __init__(self, addons_path=None):
        self.addons_path = addons_path or os.path.expanduser("~/odoo/odoo19/odoo/addons/")

    def verify_model(self, module, model_name):
        """Verify a model exists and extract verified information."""
        result = {
            'verified': False,
            'source_file': None,
            'line_number': None,
            'fields': [],
            'methods': [],
            'confidence': 'unknown'
        }

        # Find model file
        model_path = os.path.join(self.addons_path, module, 'models')
        for filename in os.listdir(model_path):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(model_path, filename)
                with open(filepath, 'r') as f:
                    lines = f.readlines()

                # Find model class
                for i, line in enumerate(lines, 1):
                    if f'_name = "{model_name}"' in line or f"_name = '{model_name}'" in line:
                        result['verified'] = True
                        result['source_file'] = filepath
                        result['line_number'] = i
                        result['fields'] = self._extract_fields(filepath)
                        result['methods'] = self._extract_methods(filepath)
                        result['confidence'] = 'high'
                        break

        return result

    def verify_field(self, module, model_name, field_name):
        """Verify a field exists and extract its definition."""
        model_info = self.verify_model(module, model_name)
        if not model_info['verified']:
            return {'verified': False}

        # Search for field definition
        filepath = model_info['source_file']
        with open(filepath, 'r') as f:
            content = f.read()

        # Look for field pattern
        pattern = rf'{field_name}\s*=\s*fields?\.\w+\(.*?\)'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return {
                'verified': True,
                'definition': match.group(0),
                'source_file': filepath
            }

        return {'verified': False, 'note': 'Field definition not found in expected format'}

    def _extract_fields(self, filepath):
        """Extract all fields from a model file."""
        with open(filepath, 'r') as f:
            content = f.read()

        # Pattern: name = fields.Type(options)
        pattern = r'(\w+)\s*=\s*fields?\.\w+\('
        matches = re.findall(pattern, content)
        return [m for m in matches if not m.startswith('_')]

    def _extract_methods(self, filepath):
        """Extract all public methods from a model file."""
        with open(filepath, 'r') as f:
            content = f.read()

        # Pattern: def method_name(self, ...)
        pattern = r'def (\w+)\(self.*?\):'
        matches = re.findall(pattern, content)
        return [m for m in matches if not m.startswith('_')]
```

**Step 2: Test verification engine**

```python
def test_verification_engine():
    ve = VerificationEngine()
    result = ve.verify_model('stock', 'stock.quant')
    assert result['verified'] == True
    assert 'quantity' in [f['name'] for f in result['fields']]
    print(f"Verified stock.quant: {result}")
```

**Step 3: Commit**

```bash
git add verification_engine.py
git commit -m "feat: add verification engine for code vs doc"
```

---

### Task 8: Depth Escalation Engine

**Files:**
- Create: depth_engine.py

**Step 1: Write depth escalation engine**

```python
class DepthEscalationEngine:
    """Explore depth of documentation through escalation levels."""

    def __init__(self, verification_engine):
        self.ve = verification_engine

    def escalate_field(self, module, model_name, field_name):
        """Explore depth for a field through L1-L4."""
        result = {
            'level_1': {},  # Surface
            'level_2': {},  # Context
            'level_3': {},  # Edge Cases
            'level_4': {},  # Historical
            'unanswered': []
        }

        # Level 1: What is this?
        verify_result = self.ve.verify_field(module, model_name, field_name)
        result['level_1'] = {
            'exists': verify_result['verified'],
            'definition': verify_result.get('definition', 'Not found'),
            'source': verify_result.get('source_file')
        }

        if not verify_result['verified']:
            result['unanswered'].append(f"L1: Field {field_name} not verified")
            return result

        # Level 2: Why does this exist?
        # Extract context from field definition
        definition = verify_result.get('definition', '')
        result['level_2'] = {
            'purpose': self._infer_purpose(definition),
            'related_methods': self._find_related_methods(module, model_name, field_name),
            'usage_patterns': self._find_usage_patterns(module, model_name, field_name)
        }

        # Level 3: What are edge cases?
        result['level_3'] = {
            'edge_values': self._question_edge_values(definition),
            'validation': self._check_validation(definition),
            'constraints': self._check_constraints(definition)
        }

        # Level 4: Historical context
        result['level_4'] = {
            'version_introduced': 'Unknown (need Odoo changelog)',
            'changes_in_v19': 'Unknown (need comparison)',
            'deprecation': 'Unknown'
        }

        return result

    def escalate_method(self, module, model_name, method_name):
        """Explore depth for a method through L1-L4."""
        result = {
            'level_1': {},
            'level_2': {},
            'level_3': {},
            'level_4': {},
            'unanswered': []
        }

        # Level 1: What is this?
        method_info = self._read_method(module, model_name, method_name)
        result['level_1'] = {
            'exists': method_info is not None,
            'signature': method_info.get('signature') if method_info else None,
            'source_file': method_info.get('file') if method_info else None
        }

        if not method_info:
            result['unanswered'].append(f"L1: Method {method_name} not found")
            return result

        # Level 2: Why does this exist?
        result['level_2'] = {
            'purpose': self._infer_method_purpose(method_info),
            'callers': self._find_callers(module, model_name, method_name),
            'callees': self._find_callees(method_info),
            'transaction_context': self._check_transaction(method_info)
        }

        # Level 3: Edge cases
        result['level_3'] = {
            'exception_paths': self._find_exceptions(method_info),
            'side_effects': self._find_side_effects(method_info),
            'concurrency': self._check_concurrency(method_info),
            'security': self._check_security(method_info)
        }

        # Level 4: Historical
        result['level_4'] = {
            'version_changes': 'Unknown (need version comparison)',
            'migration_notes': 'Unknown'
        }

        return result

    def _infer_purpose(self, definition):
        """Infer field purpose from definition."""
        # Simple heuristics based on field type and name
        if 'Float' in definition:
            return "Numeric value (quantity, price, percentage)"
        if 'Char' in definition:
            return "Text value (name, code, description)"
        if 'Date' in definition:
            return "Date/time value"
        if 'Many2one' in definition:
            return "Reference to another record"
        return "Unknown purpose"

    def _find_related_methods(self, module, model_name, field_name):
        """Find methods that use this field."""
        return []  # Placeholder - would need code analysis

    def _question_edge_values(self, definition):
        """Generate questions about edge cases."""
        questions = []
        if 'Float' in definition or 'Integer' in definition:
            questions.append("What happens at zero? Negative values? Max values?")
        if 'Char' in definition:
            questions.append("Max length? Empty string handling?")
        return questions

    def _check_validation(self, definition):
        return {'has_required': 'required' in definition.lower()}

    def _check_constraints(self, definition):
        return {'has_constraint': 'constraint' in definition.lower()}

    def _read_method(self, module, model_name, method_name):
        """Read method source code."""
        return None  # Placeholder

    def _infer_method_purpose(self, method_info):
        return "Unknown - needs code analysis"

    def _find_callers(self, module, model_name, method_name):
        return []  # Placeholder

    def _find_callees(self, method_info):
        return []  # Placeholder

    def _check_transaction(self, method_info):
        return {'has_commit': 'commit' in str(method_info).lower()}

    def _find_exceptions(self, method_info):
        return []  # Placeholder

    def _find_side_effects(self, method_info):
        return []  # Placeholder

    def _check_concurrency(self, method_info):
        return {'has_lock': False, 'note': 'Not found in code'}

    def _check_security(self, method_info):
        return {'uses_sudo': 'sudo()' in str(method_info).lower()}
```

**Step 2: Commit**

```bash
git add depth_engine.py
git commit -m "feat: add depth escalation engine for L1-L4 exploration"
```

---

### Task 9: Parallel Execution of Verify + Depth

**Files:**
- Create: research_agent.py
- Modify: autorestart skill

**Step 1: Write research agent with parallel execution**

```python
import concurrent.futures
from verification_engine import VerificationEngine
from depth_engine import DepthEscalationEngine

class ResearchAgent:
    """Main research agent that runs verification + depth in parallel."""

    def __init__(self, addons_path=None):
        self.ve = VerificationEngine(addons_path)
        self.de = DepthEscalationEngine(self.ve)
        self.checkpoint_interval = 600  # 10 minutes
        self.last_checkpoint = time.time()

    def research_model(self, module, model_name):
        """Research a model with parallel verification + depth."""
        results = {
            'module': module,
            'model': model_name,
            'verification': None,
            'depth': None,
            'documentation': None
        }

        # Run verification and depth in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            ver_future = executor.submit(self.ve.verify_model, module, model_name)
            depth_future = executor.submit(self._depth_explore_model, module, model_name)

            results['verification'] = ver_future.result()
            results['depth'] = depth_future.result()

        # Generate documentation from results
        results['documentation'] = self._generate_doc(results)

        return results

    def _depth_explore_model(self, module, model_name):
        """Explore depth for all fields and methods in model."""
        depth_result = {
            'fields': [],
            'methods': []
        }

        # Get model info
        model_info = self.ve.verify_model(module, model_name)
        if not model_info['verified']:
            return depth_result

        # For each field, run depth escalation
        for field in model_info['fields']:
            field_depth = self.de.escalate_field(module, model_name, field['name'])
            depth_result['fields'].append({
                'name': field['name'],
                'depth': field_depth
            })

        # For each method, run depth escalation
        for method in model_info['methods']:
            method_depth = self.de.escalate_method(module, model_name, method['name'])
            depth_result['methods'].append({
                'name': method['name'],
                'depth': method_depth
            })

        return depth_result

    def _generate_doc(self, results):
        """Generate documentation markdown from verification + depth results."""
        verification = results['verification']
        depth = results['depth']

        doc = f"""---
type: model
module: {results['module']}
model: {results['model']}
verification_status: {"verified" if verification['verified'] else "unverified"}
verified_at: {datetime.now().strftime('%Y-%m-%d')}
confidence: {verification.get('confidence', 'unknown')}
source: {verification.get('source_file', 'Unknown')}
---

# {results['model']}

## Verification

**Status:** {"✅ Verified" if verification['verified'] else "❌ Not Verified"}
**Source:** {verification.get('source_file', 'Unknown')}
**Line:** {verification.get('line_number', 'Unknown')}

## Fields

"""
        # Add fields with depth
        for field in depth.get('fields', []):
            doc += f"### {field['name']}\n\n"
            doc += f"- **L1 (Surface):** {field['depth']['level_1'].get('definition', 'N/A')}\n"
            doc += f"- **L2 (Context):** {field['depth']['level_2'].get('purpose', 'Unknown')}\n"

            l3_questions = field['depth']['level_3'].get('edge_values', [])
            if l3_questions:
                doc += "- **L3 (Edge Cases):**\n"
                for q in l3_questions:
                    doc += f"  - ⚠️ {q}\n"

            doc += "\n"

        doc += "## Methods\n\n"
        for method in depth.get('methods', []):
            doc += f"### {method['name']}\n\n"
            l1 = method['depth']['level_1']
            l2 = method['depth']['level_2']
            l3 = method['depth']['level_3']

            doc += f"- **Signature:** {l1.get('signature', 'Unknown')}\n"
            doc += f"- **Purpose:** {l2.get('purpose', 'Unknown')}\n"
            doc += f"- **Callers:** {len(l2.get('callers', []))} found\n"
            doc += f"- **Callees:** {len(l2.get('callees', []))} found\n"

            if l3.get('concurrency', {}).get('has_lock') == False:
                doc += f"- **Concurrency:** ⚠️ {l3['concurrency']['note']}\n"
            if l3.get('security', {}).get('uses_sudo'):
                doc += "- **Security:** ⚠️ Uses sudo() - ACL bypass possible\n"

            doc += "\n"

        return doc

    def should_checkpoint(self):
        """Check if it's time to save a checkpoint."""
        now = time.time()
        if now - self.last_checkpoint >= self.checkpoint_interval:
            self.last_checkpoint = now
            return True
        return False
```

**Step 2: Commit**

```bash
git add research_agent.py
git commit -m "feat: add research agent with parallel verify + depth"
```

---

## Phase 4: Continuous Operation & Skills

### Task 10: Create Supporting Skills

**Files:**
- Create: `~/.claude/skills/autorestop.md`
- Create: `~/.claude/skills/autorestatus.md`
- Create: `~/.claude/skills/autoverify.md`
- Create: `~/.claude/skills/autorelog.md`

**Step 1: Create autorestop.md**

```markdown
# AutoResearch - Stop

## Trigger
`/autorestop` - Stop current research gracefully
`/autorestop --force` - Stop immediately without saving

## Behavior

### Graceful Stop
1. Complete current model research
2. Save final checkpoint with `stop_requested: true`
3. Log all findings to current run log
4. Update backlog with any new gaps found
5. Update verified-status with new verifications
6. Mark run as "completed" in status.json

### Force Stop
1. Save checkpoint immediately
2. Mark current task as "incomplete"
3. Log "force stopped"
4. On next /autorestart, offer to resume or restart

## Output
- Final checkpoint saved
- Activity log closed
- Status: "stopped" or "force_stopped"
```

**Step 2: Create autorestatus.md**

```markdown
# AutoResearch - Status

## Trigger
`/autorestatus` - Show current research status

## Output

Shows:
- Is research running?
- Current module and model
- Current depth level
- Progress: X/304 modules completed
- Gaps found this session
- Verified entries count
- Time elapsed / time limit
- Last checkpoint time

Example output:
```
AutoResearch Status
===================
Running: Yes
Current: stock.picking (stock.quant completed)
Depth Level: 3/4
Progress: 23/304 modules
Gaps Found: 47 (Critical: 5, High: 12)
Verified: 156 entries
Elapsed: 45m / 60m
Last Checkpoint: 5 minutes ago
```
```

**Step 3: Create autoverify.md**

```markdown
# AutoResearch - Verify Specific Module

## Trigger
`/autoverify module=stock` - Verify specific module documentation

## Options
- `module=stock` - Module to verify
- `model=stock.quant` - Specific model (optional)
- `deep` - Run full L1-L4 depth
- `quick` - Run L1-L2 only

## Behavior
1. Load module documentation
2. Compare with actual code
3. Report discrepancies
4. Update verification status
5. Flag outdated entries
6. Add to backlog if gaps found

## Output
- Verification report for module
- List of verified fields/methods
- List of outdated entries
- List of new gaps found
```

**Step 4: Create autorelog.md**

```markdown
# AutoResearch - Activity Log

## Trigger
`/autorelog [lines=50]` - Show recent activity log

## Options
- `lines=50` - Number of lines to show (default 50)

## Output
Shows recent activity from Research-Log/active-run/log.md:
- Timeline of research actions
- Findings at each checkpoint
- Errors encountered
- Gaps discovered
- Depth escalations completed
```

---

### Task 11: Checkpoint Manager Implementation

**Files:**
- Create: checkpoint_manager.py

**Step 1: Write checkpoint manager**

```python
import json
import os
from datetime import datetime

class CheckpointManager:
    """Manage research checkpointing for resume capability."""

    def __init__(self, log_path=None):
        self.log_path = log_path or "Research-Log/active-run"
        self.checkpoint_file = os.path.join(self.log_path, "checkpoint.json")
        self.status_file = os.path.join(self.log_path, "status.json")

    def save_checkpoint(self, state):
        """Save current research state."""
        state['last_checkpoint'] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w') as f:
            json.dump(state, f, indent=2)
        return True

    def load_checkpoint(self):
        """Load last checkpoint for resume."""
        if not os.path.exists(self.checkpoint_file):
            return None

        with open(self.checkpoint_file, 'r') as f:
            return json.load(f)

    def update_status(self, status):
        """Update run status."""
        with open(self.status_file, 'w') as f:
            json.dump(status, f, indent=2)

    def start_run(self, run_id, options):
        """Initialize new research run."""
        state = {
            'run_id': run_id,
            'started_at': datetime.now().isoformat(),
            'last_checkpoint': datetime.now().isoformat(),
            'options': options,
            'status': 'running'
        }
        self.save_checkpoint(state)

        status = {
            'is_running': True,
            'run_id': run_id,
            'mode': options.get('mode', 'deep'),
            'time_limit': options.get('limit', '60m'),
            'checkpoint_interval': options.get('checkpoint', '10m'),
            'target_modules': options.get('modules', 'all')
        }
        self.update_status(status)

        return state

    def stop_run(self, graceful=True):
        """Stop current run."""
        checkpoint = self.load_checkpoint()
        if checkpoint:
            checkpoint['status'] = 'stopped' if graceful else 'force_stopped'
            checkpoint['stopped_at'] = datetime.now().isoformat()
            self.save_checkpoint(checkpoint)

        status = self.load_status()
        if status:
            status['is_running'] = False
            status['stopped_at'] = datetime.now().isoformat()
            self.update_status(status)

    def load_status(self):
        """Load current status."""
        if not os.path.exists(self.status_file):
            return None
        with open(self.status_file, 'r') as f:
            return json.load(f)
```

**Step 2: Test checkpoint manager**

```python
def test_checkpoint_manager():
    cm = CheckpointManager("/tmp/test_research_log")
    state = cm.start_run("run-2026-04-10-001", {'mode': 'deep'})
    assert state['status'] == 'running'

    loaded = cm.load_checkpoint()
    assert loaded['run_id'] == "run-2026-04-10-001"

    cm.stop_run()
    loaded = cm.load_checkpoint()
    assert loaded['status'] == 'stopped'
```

**Step 3: Commit**

```bash
git add checkpoint_manager.py
git commit -m "feat: add checkpoint manager for save/resume"
```

---

## Phase 5: Integration & Testing

### Task 12: Integration Test - Full Research Cycle

**Files:**
- Create: test_full_cycle.py

**Step 1: Write integration test**

```python
def test_full_research_cycle():
    """Test complete research cycle on a small module."""

    # 1. Initialize
    agent = ResearchAgent()

    # 2. Research one module (use 'base' as it's small)
    # Note: base module has minimal models in addons
    # Use 'stock' for more comprehensive test

    results = agent.research_model('stock', 'stock.quant')

    # 3. Verify results
    assert results['verification']['verified'] == True
    assert len(results['depth']['fields']) > 0
    assert len(results['depth']['methods']) > 0

    # 4. Check documentation generated
    doc = results['documentation']
    assert 'stock.quant' in doc
    assert 'verification_status: verified' in doc
    assert 'quantity' in doc

    # 5. Check depth levels
    quantity_field = next(f for f in results['depth']['fields'] if f['name'] == 'quantity')
    assert 'level_1' in quantity_field['depth']

    print(f"Full cycle test passed!")
    print(f"Verified fields: {len(results['depth']['fields'])}")
    print(f"Verified methods: {len(results['depth']['methods'])}")
```

**Step 2: Run integration test**

Run: `python test_full_cycle.py`
Expected: Test passes, outputs field/method counts

**Step 3: Commit**

```bash
git add test_full_cycle.py
git commit -m "test: add integration test for full research cycle"
```

---

### Task 13: End-to-End Test with Checkpoint

**Files:**
- Create: test_checkpoint_resume.py

**Step 1: Write checkpoint test**

```python
def test_checkpoint_and_resume():
    """Test checkpoint save and resume."""

    # 1. Start run
    cm = CheckpointManager()
    cm.start_run("run-test-001", {'mode': 'quick'})

    # 2. Save some progress
    state = cm.load_checkpoint()
    state['modules_completed'] = ['base', 'product']
    state['modules_in_progress'] = ['stock']
    state['gaps_found_this_run'] = 5
    cm.save_checkpoint(state)

    # 3. Simulate stop
    cm.stop_run()

    # 4. Resume
    resumed_state = cm.load_checkpoint()
    assert resumed_state['modules_completed'] == ['base', 'product']
    assert resumed_state['status'] == 'stopped'

    print("Checkpoint resume test passed!")
```

**Step 2: Run test**

Run: `python test_checkpoint_resume.py`
Expected: Test passes

**Step 3: Commit**

```bash
git add test_checkpoint_resume.py
git commit -m "test: add checkpoint resume test"
```

---

## Phase 6: Documentation Update

### Task 14: Update Vault Documentation

**Files:**
- Modify: Odoo 19/Modules/stock.md
- Create: Research-Log/USER-GUIDE.md

**Step 1: Create user guide**

```markdown
# AutoResearch User Guide

## Quick Start

### Starting Research
```
/autorestart                    # Start with defaults (deep mode, 60min)
/autorestart --modules=stock   # Focus on specific module
/autorestart --mode=quick      # Quick verification only
/autorestart --limit=30m       # Set time limit
```

### Monitoring
```
/autorestatus                  # Show current status
/autorelog 100                 # Show last 100 log lines
```

### Verification
```
/autoverify module=stock       # Verify specific module
/autoverify model=stock.quant  # Verify specific model
```

### Stopping
```
/autorestop                    # Graceful stop (saves progress)
/autorestop --force            # Immediate stop
```

## Understanding Output

### Verification Status
- **Verified:** Code read and confirmed
- **Partial:** Core verified, edge cases need more
- **Outdated:** Code differs from documentation
- **Unknown:** Never been verified

### Depth Levels
- **L1 (Surface):** What is this?
- **L2 (Context):** Why does it exist?
- **L3 (Edge Cases):** What are the boundaries?
- **L4 (Historical):** How did it evolve?

## Checking Progress

### Research Log Location
- Backlog: `Research-Log/backlog.md`
- Verified Status: `Research-Log/verified-status.md`
- Current Run: `Research-Log/active-run/`
- Completed Runs: `Research-Log/completed-runs/`

### Reading Checkpoint
```bash
cat Research-Log/active-run/checkpoint.json
```

### Finding New Gaps
```bash
cat Research-Log/backlog.md | grep -A5 "Critical"
```

## Troubleshooting

### Research stopped unexpectedly
- Check `/autorestatus` for last checkpoint
- Use `/autorestart` to resume from last position

### Gap detection seems incomplete
- Verify `~/odoo/odoo19/odoo/addons/` path is correct
- Check that modules directory exists

### Too many unverified items
- Run `/autorestart --mode=deep` for thorough verification
- Run `/autoverify module=X --deep` for specific module
```

**Step 2: Update stock.md with verification format**

Apply the verified format from Section 3.1 of design doc.

**Step 3: Commit**

```bash
git add Research-Log/USER-GUIDE.md
git commit -m "docs: add AutoResearch user guide"
```

---

## Summary of Tasks

| Phase | Task | Description |
|-------|------|-------------|
| 1 | 1 | Create Research-Log directory structure |
| 1 | 2 | Implement Checkpoint Manager |
| 1 | 3 | Create `/autorestart` skill |
| 2 | 4 | Module Scanner |
| 2 | 5 | Model Scanner |
| 2 | 6 | Gap Detection Engine |
| 3 | 7 | Code Verification Engine |
| 3 | 8 | Depth Escalation Engine |
| 3 | 9 | Research Agent (parallel execution) |
| 4 | 10 | Supporting skills (stop, status, verify, log) |
| 4 | 11 | Checkpoint Manager (full implementation) |
| 5 | 12 | Integration test - full cycle |
| 5 | 13 | Integration test - checkpoint resume |
| 6 | 14 | User guide and documentation |

---

*Plan created: 2026-04-10*
*Estimated implementation: 6 phases, 14 tasks*
*Status: Ready for execution*