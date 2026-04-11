"""
Depth Escalation Engine for Odoo 19 Documentation

Explores documentation depth through 4 escalation levels:
- L1: Surface (what is this?)
- L2: Context (why does it exist?)
- L3: Edge Cases (what are the boundaries?)
- L4: Historical (how did it evolve?)
"""

import os
import re

class DepthEscalationEngine:
    """Explore depth of documentation through escalation levels."""

    def __init__(self, verification_engine):
        self.ve = verification_engine
        self.addons_path = self.ve.addons_path

    def escalate_field(self, module, model_name, field_name):
        """Explore depth for a field through L1-L4."""
        result = {
            'level_1': {},
            'level_2': {},
            'level_3': {},
            'level_4': {},
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
        definition = verify_result.get('definition', '')
        result['level_2'] = {
            'purpose': self._infer_purpose(definition),
            'related_methods': self._find_related_methods(module, model_name, field_name),
            'usage_patterns': self._find_usage_patterns(module, model_name, field_name)
        }

        # Level 3: Edge cases
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
        """Infer field purpose from its definition."""
        if 'Float' in definition or 'Monetary' in definition:
            return "Numeric value (quantity, price, percentage)"
        if 'Integer' in definition:
            return "Integer value (count, sequence, id reference)"
        if 'Char' in definition:
            return "Text value (name, code, description)"
        if 'Date' in definition or 'DateTime' in definition:
            return "Date/time value"
        if 'Many2one' in definition:
            return "Reference to another record"
        if 'One2many' in definition or 'Many2many' in definition:
            return "Collection of related records"
        if 'Boolean' in definition:
            return "Boolean flag (true/false state)"
        if 'Text' in definition or 'Html' in definition:
            return "Long text content"
        if 'Binary' in definition:
            return "Binary data (file, image)"
        return "Unknown purpose"

    def _find_related_methods(self, module, model_name, field_name):
        """Find methods that operate on or with this field."""
        methods = []
        model_path = os.path.join(self.addons_path, module, 'models')
        if not os.path.isdir(model_path):
            return methods

        for filename in os.listdir(model_path):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(model_path, filename)
                with open(filepath, 'r') as f:
                    content = f.read()

                # Find methods that reference this field
                # Look for field assignments in onchange/compute
                patterns = [
                    rf'def\s+\w+\([^)]*{field_name}[^)]*\):',
                    rf"['\"]{field_name}['\"].*?in\s+self\.ids",
                    rf'self\.{field_name}',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        if match.startswith('def '):
                            method_name = re.match(r'def\s+(\w+)', match)
                            if method_name:
                                methods.append(method_name.group(1))
                        else:
                            # Try to extract context
                            methods.append(f"uses_{field_name}")

        # Remove duplicates and return
        return list(set([m for m in methods if not m.startswith('uses_')]))[:10]

    def _find_usage_patterns(self, module, model_name, field_name):
        """Find common usage patterns for this field."""
        patterns = []
        model_path = os.path.join(self.addons_path, module, 'models')
        if not os.path.isdir(model_path):
            return patterns

        for filename in os.listdir(model_path):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(model_path, filename)
                with open(filepath, 'r') as f:
                    content = f.read()

                # Find read/write patterns
                if f'self.{field_name}' in content:
                    patterns.append('direct_field_access')
                if f'self.mapped("{field_name}")' in content or f'mapped("{field_name}")' in content:
                    patterns.append('mapped_access')
                if f'self.filtered(lambda r: r.{field_name}' in content:
                    patterns.append('filtered_access')
                if f'"{field_name}":' in content or f"'{field_name}':" in content:
                    patterns.append('dict_key')

        return list(set(patterns))

    def _question_edge_values(self, definition):
        """Generate questions about edge values."""
        questions = []
        if 'Float' in definition or 'Integer' in definition or 'Monetary' in definition:
            questions.append("What happens at zero? Negative values? Max values?")
            questions.append("Precision/rounding behavior at scale?")
        if 'Char' in definition:
            questions.append("Max length? Empty string handling? Unicode support?")
        if 'Date' in definition or 'DateTime' in definition:
            questions.append("Timezone handling? NULL date representation?")
        if 'Many2one' in definition:
            questions.append("What happens when referenced record is deleted?")
        if 'selection' in definition.lower():
            questions.append("What happens with invalid selection value on migration?")
        return questions

    def _check_validation(self, definition):
        """Check validation requirements."""
        return {
            'has_required': 'required=True' in definition or 'required = True' in definition,
            'has_default': 'default=' in definition,
            'has_compute': 'compute=' in definition,
            'has_related': 'related=' in definition,
        }

    def _check_constraints(self, definition):
        """Check constraint definitions."""
        return {
            'has_constraint': 'constraint' in definition.lower(),
            'has_help': 'help=' in definition,
        }

    def _read_method(self, module, model_name, method_name):
        """Read method details from model file."""
        model_path = os.path.join(self.addons_path, module, 'models')
        if not os.path.isdir(model_path):
            return None

        for filename in os.listdir(model_path):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(model_path, filename)
                with open(filepath, 'r') as f:
                    content = f.read()

                # Find method definition
                # Pattern: def method_name(self, ...): body
                pattern = rf'(def\s+{method_name}\s*\(.*?\):.*?)(?=\n    def |\nclass |\Z)'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    method_body = match.group(1)
                    # Extract signature
                    sig_match = re.match(rf'def\s+{method_name}\((.*?)\):', method_body)
                    params = sig_match.group(1) if sig_match else ''

                    return {
                        'name': method_name,
                        'signature': f"{method_name}({params})",
                        'body': method_body,
                        'file': filepath
                    }

        return None

    def _infer_method_purpose(self, method_info):
        """Infer method purpose from its name and body."""
        name = method_info.get('name', '')
        body = method_info.get('body', '')

        # Name-based inference
        if name.startswith('action_'):
            return "UI action/button handler"
        if name.startswith('onchange_'):
            return "Onchange handler for dynamic form behavior"
        if name.startswith('compute_') or '_compute_' in name:
            return "Computed field calculation"
        if name.startswith('search_') or '_search' in name:
            return "Custom search domain logic"
        if name.startswith('_onchange'):
            return "Internal onchange method"
        if name.startswith('_compute'):
            return "Internal computed field method"
        if name == 'create' or name == 'write':
            return "ORM override for record lifecycle"
        if 'check' in name or 'validate' in name:
            return "Validation logic"
        if name.startswith('get_') or name.startswith('_get_'):
            return "Getter/calculator method"

        # Body-based inference
        if 'self.write(' in body or 'self.ensure_one()' in body:
            return "Record modification"
        if '@api.model' in body:
            return "Model-level (class) method"
        if '@api.constrains' in body:
            return "Validation constraint"
        if '@api.depends' in body:
            return "Reactive/dependent computation"

        return "Unknown - needs code analysis"

    def _find_callers(self, module, model_name, method_name):
        """Find methods that call this method."""
        callers = []
        model_path = os.path.join(self.addons_path, module, 'models')
        if not os.path.isdir(model_path):
            return callers

        for filename in os.listdir(model_path):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(model_path, filename)
                with open(filepath, 'r') as f:
                    content = f.read()

                # Find methods that call this method
                call_patterns = [
                    rf'def\s+(\w+)\([^)]*\):.*?self\.{method_name}\(',
                    rf'def\s+(\w+)\([^)]*\):.*?{method_name}\(',
                ]
                for pattern in call_patterns:
                    matches = re.findall(pattern, content, re.DOTALL)
                    callers.extend(matches)

        return list(set(callers))

    def _find_callees(self, method_info):
        """Find methods/functions called by this method."""
        callees = []
        body = method_info.get('body', '')

        # Find self.method() calls
        call_pattern = r'self\.(\w+)\('
        matches = re.findall(call_pattern, body)
        callees.extend([f"self.{m}()" for m in matches])

        # Find other method calls
        other_calls = re.findall(r'(\w+)\([^)]*\.(?:env|cr|uid)\)', body)
        callees.extend(other_calls)

        return list(set(callees))[:15]  # Limit to 15

    def _check_transaction(self, method_info):
        """Check transaction handling."""
        body = method_info.get('body', '')
        return {
            'has_commit': 'commit()' in body or 'self.env.cr.commit()' in body,
            'has_rollback': 'rollback()' in body or 'self.env.cr.rollback()' in body,
            'has_flush': 'flush()' in body or 'self.env.flush()' in body,
        }

    def _find_exceptions(self, method_info):
        """Find exception handling patterns."""
        body = method_info.get('body', '')
        exceptions = []

        try_blocks = re.findall(r'try\s*:.*?(?=except)', body, re.DOTALL)
        for block in try_blocks:
            except_clauses = re.findall(r'except\s+(\w+Error)', block)
            exceptions.extend(except_clauses)

        return list(set(exceptions))

    def _find_side_effects(self, method_info):
        """Find side effects in method."""
        side_effects = []
        body = method_info.get('body', '')

        if 'self.write(' in body:
            side_effects.append('writes_to_database')
        if 'self.create(' in body:
            side_effects.append('creates_records')
        if 'self.unlink(' in body:
            side_effects.append('deletes_records')
        if 'action_' in method_info.get('name', ''):
            side_effects.append('ui_action_trigger')
        if '@api.returns' in body:
            side_effects.append('returns_recordset')
        if 'raise ' in body:
            side_effects.append('raises_exceptions')

        return side_effects

    def _check_concurrency(self, method_info):
        """Check for concurrency controls."""
        body = method_info.get('body', '')
        return {
            'has_lock': 'lock_for_update' in body or 'LOCK' in body.upper(),
            'has_select_for_update': 'select for update' in body.lower() or 'for_update' in body,
            'note': 'Concurrency check performed' if any([
                'lock_for_update' in body,
                'for_update' in body,
                'select for update' in body.lower()
            ]) else 'No concurrency control found'
        }

    def _check_security(self, method_info):
        """Check for security patterns."""
        body = method_info.get('body', '')
        return {
            'uses_sudo': 'sudo()' in body,
            'uses_crsudo': 'crsudo' in body,
            'has_check_access': 'check_access' in body,
            'has_access_rights': 'access_rights' in body,
        }


def test_depth_engine():
    """Test the depth escalation engine."""
    from verification_engine import VerificationEngine

    ve = VerificationEngine()
    de = DepthEscalationEngine(ve)

    print("=" * 70)
    print("DEPTH ESCALATION ENGINE TEST")
    print("=" * 70)

    # Test field escalation
    print("\n--- Testing escalate_field for stock.quant.quantity ---\n")
    result = de.escalate_field('stock', 'stock.quant', 'quantity')

    print("LEVEL 1: What is this?")
    print(f"  Exists: {result['level_1']['exists']}")
    print(f"  Definition: {result['level_1']['definition']}")
    print(f"  Source: {result['level_1']['source']}")

    print("\nLEVEL 2: Why does this exist?")
    print(f"  Purpose: {result['level_2']['purpose']}")
    print(f"  Related Methods: {result['level_2']['related_methods']}")
    print(f"  Usage Patterns: {result['level_2']['usage_patterns']}")

    print("\nLEVEL 3: Edge Cases & Boundaries")
    print(f"  Edge Value Questions: {result['level_3']['edge_values']}")
    print(f"  Validation: {result['level_3']['validation']}")
    print(f"  Constraints: {result['level_3']['constraints']}")

    print("\nLEVEL 4: Historical Context")
    print(f"  Version Introduced: {result['level_4']['version_introduced']}")
    print(f"  Changes in v19: {result['level_4']['changes_in_v19']}")
    print(f"  Deprecation: {result['level_4']['deprecation']}")

    if result['unanswered']:
        print(f"\nUNANSWERED: {result['unanswered']}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    return result


if __name__ == '__main__':
    test_depth_engine()
