#!/usr/bin/env python3
"""
Automatic documentation generator for Eventyay modules.

This script scans the app/eventyay directory and generates RST files
for modules that don't have documentation yet.
"""

import os
import sys
from pathlib import Path

# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'app'))

def get_module_docstring(module_path):
    """Try to get the docstring of a module."""
    try:
        # Convert file path to module path
        rel_path = module_path.relative_to(Path(__file__).parent.parent / 'app')
        module_name = str(rel_path).replace('/', '.').replace('.py', '')
        
        # Try to import and get docstring
        exec(f"import {module_name}")
        mod = eval(module_name)
        return getattr(mod, '__doc__', None) or "No description available"
    except:
        return "Module documentation"

def should_document(module_path):
    """Check if a module should be documented."""
    # Skip __init__, __pycache__, migrations, tests
    if '__pycache__' in str(module_path):
        return False
    if '/migrations/' in str(module_path):
        return False
    if '/tests/' in str(module_path):
        return False
    if module_path.name.startswith('test_'):
        return False
    if module_path.name in ['__init__.py', '__main__.py']:
        return False
    return True

def find_undocumented_modules():
    """Find Python modules in app/eventyay that aren't documented."""
    app_dir = Path(__file__).parent.parent / 'app' / 'eventyay'
    
    # Important top-level modules to document
    priority_modules = [
        'base/services',
        'base/exporters',
        'base/forms',
        'features/live/modules',
        'features/analytics',
        'features/integrations',
        'features/social',
        'api/serializers',
        'api/views',
        'control/views',
        'presale/views',
        'helpers',
        'common',
    ]
    
    modules_to_document = {}
    
    for module_dir in priority_modules:
        full_path = app_dir / module_dir
        if not full_path.exists():
            continue
            
        # Find all .py files
        for py_file in full_path.rglob('*.py'):
            if should_document(py_file):
                rel_path = py_file.relative_to(app_dir)
                module_path = 'eventyay.' + str(rel_path).replace('/', '.').replace('.py', '')
                modules_to_document[module_path] = py_file
    
    return modules_to_document

def generate_services_doc():
    """Generate comprehensive services documentation."""
    services_dir = Path(__file__).parent.parent / 'app' / 'eventyay' / 'base' / 'services'
    
    content = []
    content.append(".. highlight:: python")
    content.append("   :linenothreshold: 5")
    content.append("")
    content.append("Services Module Reference")
    content.append("=========================")
    content.append("")
    content.append("Complete reference for all service modules in ``eventyay.base.services``.")
    content.append("")
    
    # Group services by category
    categories = {
        'Order Management': ['orders', 'cart', 'pricing', 'quotas'],
        'Payment & Invoicing': ['invoices', 'mail'],
        'Check-in & Tickets': ['checkin', 'tickets'],
        'Video & Streaming': ['bbb', 'janus', 'turn', 'room', 'chat'],
        'Interactive Features': ['poll', 'poster', 'question', 'roulette'],
        'Exhibition': ['exhibition', 'reactions'],
        'User & Auth': ['auth', 'user'],
        'Event Management': ['event', 'cancelevent'],
        'Data Management': ['export', 'orderimport', 'shredder', 'cleanup'],
        'System': ['tasks', 'locking', 'notifications', 'stats', 'update_check'],
    }
    
    for category, services in categories.items():
        content.append(category)
        content.append("-" * len(category))
        content.append("")
        
        for service in services:
            service_file = services_dir / f"{service}.py"
            if service_file.exists():
                content.append(f".. automodule:: eventyay.base.services.{service}")
                content.append("   :members:")
                content.append("   :undoc-members:")
                content.append("   :show-inheritance:")
                content.append("")
    
    return '\n'.join(content)

def main():
    """Main function."""
    print("Generating automatic documentation...")
    
    # Generate services reference
    services_doc = generate_services_doc()
    output_file = Path(__file__).parent / 'development' / 'api' / 'services_reference.rst'
    output_file.write_text(services_doc)
    print(f"✓ Created: {output_file}")
    
    # Find undocumented modules
    undocumented = find_undocumented_modules()
    print(f"\nFound {len(undocumented)} modules that could be documented")
    print("\nPriority modules for documentation:")
    for module_path in sorted(undocumented.keys())[:20]:
        print(f"  - {module_path}")
    
    print("\n✓ Documentation generation complete!")
    print(f"✓ Created services_reference.rst with comprehensive service documentation")

if __name__ == '__main__':
    main()

