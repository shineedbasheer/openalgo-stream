"""
Fix all services with event_publisher initialization issues
This script adds lazy initialization to all service files
"""

import os
import re

# List of service files that need fixing
SERVICE_FILES = [
    'basket_order_service.py',
    'options_multiorder_service.py',
    'place_options_order_service.py',
    'split_order_service.py',
]

SERVICES_DIR = 'services'

# Replacement patterns
OLD_PATTERN = r"# Initialize event publisher\nevent_publisher = get_event_publisher\(\)"

NEW_CODE = """# Event publisher will be initialized lazily (not at import time)
event_publisher = None

def _get_event_publisher():
    \"\"\"Get event publisher with lazy initialization\"\"\"
    global event_publisher
    if event_publisher is None:
        event_publisher = get_event_publisher()
    return event_publisher"""

print("=" * 80)
print("Fixing Event Publisher Initialization in Service Files")
print("=" * 80)
print()

for filename in SERVICE_FILES:
    filepath = os.path.join(SERVICES_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"⚠ {filename} not found, skipping...")
        continue
    
    print(f"Processing {filename}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already fixed
    if '_get_event_publisher()' in content:
        print(f"  ✓ Already fixed, skipping")
        continue
    
    # Replace initialization
    new_content = re.sub(OLD_PATTERN, NEW_CODE, content)
    
    # Replace all event_publisher. calls with _get_event_publisher().
    new_content = re.sub(
        r'\bevent_publisher\.publish',
        '_get_event_publisher().publish',
        new_content
    )
    
    if new_content != content:
        # Create backup
        backup_path = filepath + '.backup_lazy_init'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Write fixed version
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"  ✓ Fixed (backup created at {backup_path})")
    else:
        print(f"  ⚠ No changes made")

print()
print("=" * 80)
print("Done! Remember to:")
print("1. Clear Python cache: clear_cache_and_restart.bat")
print("2. Restart your Flask application")
print("=" * 80)
