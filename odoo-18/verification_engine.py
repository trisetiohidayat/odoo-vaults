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
        if not os.path.isdir(model_path):
            return result

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

        # Look for field pattern - more flexible matching
        field_patterns = [
            rf'{field_name}\s*=\s*fields\.\w+\(',
            rf'{field_name}\s*=\s*\w+\(.*?\)',  # Direct field type
        ]

        for pattern in field_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return {
                    'verified': True,
                    'definition': match.group(0),
                    'source_file': filepath
                }

        return {'verified': False, 'note': 'Field definition not found'}

    def _extract_fields(self, filepath):
        """Extract all fields from a model file."""
        with open(filepath, 'r') as f:
            content = f.read()

        # Pattern: name = fields.Type(options)
        field_types = ['Char', 'Integer', 'Float', 'Boolean', 'Date', 'DateTime',
                      'Text', 'Many2one', 'One2many', 'Many2many', 'Binary',
                      'Html', 'Selection', 'Monetary', 'Reference']
        field_pattern = r'(\w+)\s*=\s*(?:fields\.)?(\w+)\('
        matches = re.findall(field_pattern, content)
        return [{'name': m[0], 'type': m[1]} for m in matches
                if not m[0].startswith('_') and m[1] in field_types]

    def _extract_methods(self, filepath):
        """Extract all public methods from a model file."""
        with open(filepath, 'r') as f:
            content = f.read()

        # Pattern: def method_name(self, ...)
        method_pattern = r'def (\w+)\(self.*?\):'
        matches = re.findall(method_pattern, content)
        return [{'name': m} for m in matches if not m.startswith('_')]


def test_verification_engine():
    ve = VerificationEngine()
    result = ve.verify_model('stock', 'stock.quant')
    assert result['verified'] == True, f"Expected stock.quant to be verified, got {result}"
    assert 'quantity' in [f['name'] for f in result['fields']], \
        f"Expected 'quantity' field, got {[f['name'] for f in result['fields']]}"
    print(f"Verified stock.quant: {result}")


if __name__ == '__main__':
    test_verification_engine()
