#!/usr/bin/env python3
"""
OpenAlgo Kafka Integration Fixer

This script updates services to use event_publisher instead of direct socketio.emit calls.
It creates backups before making changes so you can revert if needed.

Usage:
    python fix_kafka_integration.py
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime

def backup_file(filepath):
    """Create a timestamped backup of the file before modifying"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.backup_{timestamp}"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Backed up: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to backup {filepath}: {e}")
        return False

def fix_place_smart_order_service():
    """Fix place_smart_order_service.py to use event_publisher"""
    
    filepath = Path("services/place_smart_order_service.py")
    
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return False
    
    print(f"\n📝 Processing: {filepath}")
    
    # Create backup
    if not backup_file(filepath):
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        # Change 1: Replace import
        if "from extensions import socketio" in content:
            content = content.replace(
                "from extensions import socketio",
                "from utils.event_publisher import get_event_publisher"
            )
            changes_made += 1
            print("  ✓ Updated import statement")
        
        # Change 2: Add event_publisher initialization
        if "event_publisher = get_event_publisher()" not in content:
            # Find the logger initialization and add event_publisher after it
            logger_pattern = r"(# Initialize logger\nlogger = get_logger\(__name__\))"
            replacement = r"\1\n\n# Initialize event publisher\nevent_publisher = get_event_publisher()"
            content = re.sub(logger_pattern, replacement, content)
            changes_made += 1
            print("  ✓ Added event_publisher initialization")
        
        # Change 3: Fix emit_analyzer_error function (around line 57-60)
        pattern1 = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"analyzer_update",\s*\{"request":\s*analyzer_request,\s*"response":\s*error_response\}\s*\)'
        replacement1 = '''event_publisher.publish_analyzer_update(
        user_id=analyzer_request.get("apikey", "unknown"),
        request=analyzer_request,
        response=error_response
    )'''
        if re.search(pattern1, content):
            content = re.sub(pattern1, replacement1, content)
            changes_made += 1
            print("  ✓ Fixed emit_analyzer_error function")
        
        # Change 4: Fix analyzer_update emission in analyze mode (around line 189-193)
        pattern2 = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"analyzer_update",\s*\{"request":\s*analyzer_request,\s*"response":\s*response_data\},?\s*\)'
        replacement2 = '''event_publisher.publish_analyzer_update(
            user_id=original_data.get("apikey", "unknown"),
            request=analyzer_request,
            response=response_data
        )'''
        if re.search(pattern2, content):
            content = re.sub(pattern2, replacement2, content)
            changes_made += 1
            print("  ✓ Fixed analyzer_update emission in analyze mode")
        
        # Change 5: Fix order_notification emission (around line 230-236)
        pattern3 = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"order_notification",\s*\{\s*"symbol":\s*order_data\.get\("symbol"\),\s*"status":\s*"info",\s*"message":\s*"([^"]+)",\s*\},?\s*\)'
        replacement3 = r'''event_publisher.publish_order_notification(
                user_id=original_data.get("apikey", "unknown"),
                symbol=order_data.get("symbol"),
                status="info",
                message="\1"
            )'''
        if re.search(pattern3, content):
            content = re.sub(pattern3, replacement3, content)
            changes_made += 1
            print("  ✓ Fixed order_notification emission")
        
        # Change 6: Fix order_event emission (around line 257-266)
        pattern4 = r'socketio\.start_background_task\(\s*socketio\.emit,\s*"order_event",\s*\{\s*"symbol":\s*order_data\.get\("symbol"\),\s*"action":\s*order_data\.get\("action"\),\s*"orderid":\s*order_id,\s*"mode":\s*"live",\s*\},?\s*\)'
        replacement4 = '''event_publisher.publish_order_event(
                user_id=original_data.get("apikey", "unknown"),
                symbol=order_data.get("symbol"),
                action=order_data.get("action"),
                orderid=order_id,
                mode="live",
                broker=broker,
                quantity=order_data.get("quantity"),
                price=order_data.get("price")
            )'''
        if re.search(pattern4, content):
            content = re.sub(pattern4, replacement4, content)
            changes_made += 1
            print("  ✓ Fixed order_event emission")
        
        # Write the modified content
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n✅ Successfully updated {filepath}")
            print(f"   {changes_made} changes made")
            return True
        else:
            print(f"\n⚠️  No changes needed for {filepath} (already updated?)")
            return True
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_kafka_config():
    """Verify Kafka configuration in .env"""
    print("\n" + "="*60)
    print("KAFKA CONFIGURATION VERIFICATION")
    print("="*60)
    
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        return False
    
    with open('.env', 'r') as f:
        env_content = f.read()
    
    required_vars = {
        'ORDER_EVENT_MODE': 'KAFKA',
        'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092',
        'KAFKA_ORDER_EVENTS_TOPIC': 'from_openalgo_order_events'
    }
    
    all_good = True
    for var, expected_pattern in required_vars.items():
        pattern = f"{var}\\s*=\\s*['\"]?([^'\"\\n]+)['\"]?"
        match = re.search(pattern, env_content)
        
        if match:
            value = match.group(1)
            if expected_pattern.lower() in value.lower():
                print(f"✓ {var} = {value}")
            else:
                print(f"⚠  {var} = {value}")
                if var == 'ORDER_EVENT_MODE':
                    print(f"   Expected: {expected_pattern}")
                    print(f"   Kafka events will not work unless ORDER_EVENT_MODE=KAFKA")
                    all_good = False
        else:
            print(f"❌ {var} not found in .env")
            all_good = False
    
    print()
    return all_good

def check_kafka_python_installed():
    """Check if kafka-python is installed"""
    print("="*60)
    print("CHECKING DEPENDENCIES")
    print("="*60)
    
    try:
        import kafka
        print("✓ kafka-python is installed")
        return True
    except ImportError:
        print("❌ kafka-python is NOT installed")
        print("\n   Install with: pip install kafka-python==2.0.2")
        return False

def main():
    print("="*60)
    print("OPENALGO KAFKA INTEGRATION FIXER")
    print("="*60)
    print()
    
    # Verify we're in the correct directory
    if not os.path.exists('services'):
        print("❌ Error: services/ directory not found!")
        print("   Please run this script from the openalgo-stream directory")
        print("\n   Usage:")
        print("     cd C:\\workspace\\openalgo-stream")
        print("     python fix_kafka_integration.py")
        sys.exit(1)
    
    # Check dependencies
    if not check_kafka_python_installed():
        print("\n⚠️  Warning: kafka-python not installed")
        response = input("\n   Continue anyway? (yes/no): ").lower()
        if response != 'yes':
            print("   Installation cancelled.")
            sys.exit(1)
    
    # Verify Kafka config
    print("\n" + "="*60)
    print("STEP 1: VERIFYING KAFKA CONFIGURATION")
    print("="*60)
    
    config_ok = verify_kafka_config()
    if not config_ok:
        print("⚠️  Warning: Kafka configuration issues detected")
        response = input("\nContinue with fixing the code anyway? (yes/no): ").lower()
        if response != 'yes':
            print("Operation cancelled.")
            sys.exit(1)
    
    # Fix services
    print("="*60)
    print("STEP 2: UPDATING SERVICE FILES")
    print("="*60)
    
    success = fix_place_smart_order_service()
    
    if success:
        print("\n" + "="*60)
        print("✅ SUCCESS! KAFKA INTEGRATION UPDATED")
        print("="*60)
        print("\n📋 Next steps:")
        print("   1. Restart your OpenAlgo application")
        print("   2. Place a test order")
        print("   3. Check Kafka consumer for messages:")
        print("\n      docker exec -it kafka-kafka-1 kafka-console-consumer \\")
        print("        --bootstrap-server localhost:9092 \\")
        print("        --topic from_openalgo_order_events \\")
        print("        --from-beginning")
        print("\n   4. You should see JSON messages like:")
        print('      {"event_type": "order_event", "timestamp": "...", ...}')
        print("\n💡 If you need to revert changes, restore from backup files:")
        print("   services/place_smart_order_service.py.backup_*")
    else:
        print("\n" + "="*60)
        print("❌ FAILED TO UPDATE FILES")
        print("="*60)
        print("\n   Please check the error messages above")
        print("   You can try manual fixes using KAFKA_FIX_GUIDE.md")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
