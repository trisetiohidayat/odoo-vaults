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
            class_pattern = r'class\s+\w+\([^)]*models[^)]*\):'
            for match in re.finditer(class_pattern, content):
                model_name = match.group(0).split('(')[0].replace('class ', '')
                # Find _name attribute within first 2000 chars of class definition
                search_window = content[match.start():match.start()+2000]
                name_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', search_window)
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
    # Common Odoo field types (both fields.Type and direct Type(...) patterns)
    known_field_types = {
        'Char', 'Integer', 'Float', 'Boolean', 'Date', 'DateTime', 'Text',
        'Many2one', 'One2many', 'Many2many', 'Binary', 'Html', 'Selection',
        'Monetary', 'Reference', 'Serialized', 'Json', 'Image', 'File', 'Time',
        'Related', 'Computed', 'Property',
    }
    # Match both fields.Xxx(...) and direct Xxx(...) patterns
    field_pattern = r'(\w+)\s*=\s*(?:fields\.)?(\w+)\('
    matches = re.findall(field_pattern, content)
    return [{'name': name, 'type': ftype} for name, ftype in matches
            if ftype in known_field_types and not name.startswith('_')]

def extract_methods(content):
    """Extract method definitions from model content."""
    # Look for def method_name(self, ...)
    method_pattern = r'def (\w+)\(self.*?\):'
    matches = re.findall(method_pattern, content)
    return [{'name': m} for m in matches if not m.startswith('_')]


if __name__ == "__main__":
    import sys
    module = sys.argv[1] if len(sys.argv) > 1 else "stock"
    results = scan_models(module)
    print(f"Models found in '{module}' module:\n")
    for model in results:
        print(f"  Model: {model['name']} (file: {model['file']})")
        print(f"    Fields ({len(model['fields'])}): {[f['name'] for f in model['fields'][:10]]}{'...' if len(model['fields']) > 10 else ''}")
        print(f"    Methods ({len(model['methods'])}): {[m['name'] for m in model['methods'][:10]]}{'...' if len(model['methods']) > 10 else ''}")
        print()
    print(f"Total: {len(results)} models")
