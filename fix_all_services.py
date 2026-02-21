#!/usr/bin/env python3
"""
OpenAlgo - Fix ALL Services for Event Publishing

This script finds and fixes ALL services that use socketio.emit
and converts them to use event_publisher for all three modes.
"""

import os
import re
from pathlib import Path
from datetime import datetime

def backup_file(filepath):
    """Create timestamped backup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"❌ Failed to backup {filepath}: {e}")
        return False

def find_services_with_socketio():
    """Find all services that import or use socketio"""
    services_dir = Path("services")
    
    if not services_dir.exists():
        print("❌ services/ directory not found!")
        return []
    
    services_with_socketio = []
    
    for py_file in services_dir.glob("*.py"):
        if py_file.name.startswith('__'):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if file imports socketio or uses it
            if ('from extensions import socketio' in content or
                'socketio.emit' in content or
                'socketio.start_background_task' in content):
                services_with_socketio.append(py_file)
        except Exception as e:
            print(f"⚠️  Could not read {py_file}: {e}")
    
    return services_with_socketio

def fix_service_file(filepath):
    """Fix a single service file"""
    print(f"\n📝 Processing: {filepath.name}")
    
    # Backup first
    print(f"  Creating backup...")
    if not backup_file(filepath):
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes = []
        
        # Change 1: Replace socketio import with event_publisher
        if 'from extensions import socketio' in content:
            content = content.replace(
                'from extensions import socketio',
                'from utils.event_publisher import get_event_publisher'
            )
            changes.append("Updated import statement")
        
        # Change 2: Add event_publisher initialization after logger
        if 'event_publisher = get_event_publisher()' not in content:
            # Find logger initialization and add event_publisher after it
            logger_pattern = r'(# Initialize logger\nlogger = get_logger\(__name__\))'
            if re.search(logger_pattern, content):
                content = re.sub(
                    logger_pattern,
                    r'\1\n\n# Initialize event publisher\nevent_publisher = get_event_publisher()',
                    content
                )
                changes.append("Added event_publisher initialization")
        
        # Change 3: Fix analyzer_update emissions in emit_analyzer_error
        pattern = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"analyzer_update",\s*\{"request":\s*analyzer_request,\s*"response":\s*error_response\}\s*\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                '''event_publisher.publish_analyzer_update(
        user_id=analyzer_request.get("apikey", "unknown"),
        request=analyzer_request,
        response=error_response
    )''',
                content
            )
            changes.append("Fixed analyzer_update emission in error handler")
        
        # Change 4: Fix analyzer_update emissions in analyze mode
        pattern = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"analyzer_update",\s*\{"request":\s*analyzer_request,\s*"response":\s*response_data\},?\s*\)'
        if re.search(pattern, content):
            content = re.sub(
                pattern,
                '''event_publisher.publish_analyzer_update(
            user_id=original_data.get("apikey", "unknown"),
            request=analyzer_request,
            response=response_data
        )''',
                content
            )
            changes.append("Fixed analyzer_update emission in analyze mode")
        
        # Change 5: Fix order_event emissions
        pattern = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"order_event",\s*\{([^}]+)\},?\s*\)'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            # Extract the data dict content
            data_content = match.group(1)
            
            # Parse the fields
            fields = {}
            for line in data_content.split(','):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().strip('"').strip("'")
                    value = value.strip()
                    fields[key] = value
            
            # Build event_publisher call
            replacement = '''event_publisher.publish_order_event(
                user_id=original_data.get("apikey", "unknown"),'''
            
            # Add required fields
            if 'symbol' in fields:
                replacement += f'\n                symbol={fields["symbol"]},'
            if 'action' in fields:
                replacement += f'\n                action={fields["action"]},'
            if 'orderid' in fields:
                replacement += f'\n                orderid={fields["orderid"]},'
            
            # Add mode
            mode_value = fields.get('mode', '"live"')
            replacement += f'\n                mode={mode_value},'
            
            # Add optional fields
            for field in ['exchange', 'price_type', 'product_type', 'broker', 'quantity', 'price']:
                if field in fields:
                    replacement += f'\n                {field}={fields[field]},'
            
            # Remove trailing comma and close
            replacement = replacement.rstrip(',') + '\n            )'
            
            # Replace in content
            content = content.replace(match.group(0), replacement)
            changes.append(f"Fixed order_event emission")
        
        # Change 6: Fix telegram alert background tasks
        pattern = r'socketio\.start_background_task\(\s*telegram_alert_service\.send_order_alert,\s*([^)]+)\)'
        matches = list(re.finditer(pattern, content))
        
        for match in matches:
            args = match.group(1)
            replacement = f'''executor.submit(
            telegram_alert_service.send_order_alert,
            {args}
        )'''
            content = content.replace(match.group(0), replacement)
            changes.append("Fixed telegram alert call")
        
        # Change 7: Fix batch order summary emissions
        pattern = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"basket_order_summary",\s*summary_data,?\s*\)'
        if re.search(pattern, content):
            # For basket orders, we might need a custom event
            content = re.sub(
                pattern,
                '''# Emit basket summary as notification
            for order_result in summary_data.get("results", []):
                if order_result.get("status") == "success":
                    event_publisher.publish_order_event(
                        user_id=summary_data.get("apikey", "unknown"),
                        symbol=order_result.get("symbol", ""),
                        action=order_result.get("action", ""),
                        orderid=order_result.get("orderid", ""),
                        mode="live"
                    )''',
                content
            )
            changes.append("Fixed basket order summary emission")
        
        # Write changes if any were made
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ Fixed: {len(changes)} changes")
            for change in changes:
                print(f"     - {change}")
            return True
        else:
            print(f"  ℹ️  No changes needed (already fixed)")
            return True
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("OPENALGO - FIX ALL SERVICES FOR EVENT PUBLISHING")
    print("="*60)
    print()
    
    # Check directory
    if not os.path.exists('services'):
        print("❌ Error: services/ directory not found!")
        print("   Run this from the openalgo-stream directory")
        return
    
    # Find services that need fixing
    print("🔍 Scanning for services with socketio...")
    services_to_fix = find_services_with_socketio()
    
    if not services_to_fix:
        print("\n✅ No services found with socketio imports!")
        print("   All services are already using event_publisher!")
        return
    
    print(f"\n📋 Found {len(services_to_fix)} service(s) to fix:")
    for service in services_to_fix:
        print(f"   - {service.name}")
    
    print("\n" + "="*60)
    print("FIXING SERVICES")
    print("="*60)
    
    results = {}
    for service in services_to_fix:
        results[service.name] = fix_service_file(service)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"✅ SUCCESS: Fixed {success_count}/{total_count} services")
    else:
        print(f"⚠️  PARTIAL: Fixed {success_count}/{total_count} services")
    
    print("\n📋 Details:")
    for service, success in results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {service}")
    
    if success_count == total_count:
        print("\n" + "="*60)
        print("✅ ALL SERVICES FIXED!")
        print("="*60)
        print("\n📋 Next steps:")
        print("   1. Restart OpenAlgo:")
        print("      python app.py")
        print()
        print("   2. Test each mode:")
        print("      python test_event_modes.py")
        print()
        print("   3. Verify all APIs work:")
        print("      - placeorder")
        print("      - placesmartorder")
        print("      - basketorder")
        print("      - closeposition")
        print("      - cancelorder")
        print()
        print("   4. Check events appear in correct places:")
        print("      - SOCKETIO mode → Browser console only")
        print("      - KAFKA mode → Kafka consumer only")
        print("      - BOTH mode → Both places!")
    else:
        print("\n⚠️  Some services could not be fixed automatically")
        print("   Check the error messages above")
        print("   Restore from backup files if needed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
