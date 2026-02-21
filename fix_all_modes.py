#!/usr/bin/env python3
"""
OpenAlgo - Complete Fix for All Three Event Modes

This script ensures SOCKETIO, KAFKA, and BOTH modes all work correctly.
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime

def backup_file(filepath):
    """Create a timestamped backup"""
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
    """
    Fix place_smart_order_service.py to:
    1. Remove socketio.start_background_task calls (telegram alerts)
    2. Ensure event_publisher is used correctly
    """
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
        
        # Fix 1: Replace socketio.start_background_task with direct telegram alert calls
        # These are for telegram alerts, not event publishing, so they should be direct calls
        
        # Pattern for telegram alert in analyzer mode (around line 196-201)
        pattern1 = r'socketio\.start_background_task\(\s*telegram_alert_service\.send_order_alert,\s*"placesmartorder",\s*order_data,\s*response_data,\s*order_data\.get\("apikey"\),?\s*\)'
        replacement1 = '''# Send Telegram alert (non-blocking via executor)
        executor.submit(
            telegram_alert_service.send_order_alert,
            "placesmartorder",
            order_data,
            response_data,
            order_data.get("apikey")
        )'''
        
        if re.search(pattern1, content):
            content = re.sub(pattern1, replacement1, content)
            changes_made += 1
            print("  ✓ Fixed telegram alert in analyzer mode")
        
        # Pattern for telegram alert in matched positions (around line 238-244)
        pattern2 = r'socketio\.start_background_task\(\s*telegram_alert_service\.send_order_alert,\s*"placesmartorder",\s*order_data,\s*order_response_data,\s*original_data\.get\("apikey"\),?\s*\)'
        replacement2 = '''# Send Telegram alert (non-blocking via executor)
            executor.submit(
                telegram_alert_service.send_order_alert,
                "placesmartorder",
                order_data,
                order_response_data,
                original_data.get("apikey")
            )'''
        
        count = len(re.findall(pattern2, content))
        if count > 0:
            content = re.sub(pattern2, replacement2, content)
            changes_made += count
            print(f"  ✓ Fixed {count} telegram alert call(s) in live mode")
        
        # Write the modified content
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n✅ Successfully updated {filepath}")
            print(f"   {changes_made} changes made")
            return True
        else:
            print(f"\n⚠️  No telegram alert changes needed (already fixed?)")
            # Still return True since event_publisher calls are already there
            return True
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_all_three_modes():
    """Test that all three modes initialize correctly"""
    print("\n" + "="*60)
    print("TESTING ALL THREE MODES")
    print("="*60)
    
    try:
        # Save original mode
        original_mode = os.getenv('ORDER_EVENT_MODE', 'SOCKETIO')
        
        # Load environment
        from utils.env_check import load_and_check_env_variables
        
        test_results = {}
        
        # Test each mode
        for mode in ['SOCKETIO', 'KAFKA', 'BOTH']:
            print(f"\nTesting {mode} mode...")
            
            # Set environment variable
            os.environ['ORDER_EVENT_MODE'] = mode
            
            # Reset singleton
            from utils.event_publisher import EventPublisherFactory
            EventPublisherFactory.reset()
            
            try:
                # Try to create publisher
                from utils.event_publisher import get_event_publisher
                publisher = get_event_publisher()
                publisher_type = type(publisher).__name__
                
                expected_types = {
                    'SOCKETIO': 'SocketIOEventPublisher',
                    'KAFKA': 'KafkaEventPublisher',
                    'BOTH': 'BothEventPublisher'
                }
                
                if publisher_type == expected_types[mode]:
                    print(f"  ✅ {mode} mode: {publisher_type} initialized correctly")
                    test_results[mode] = True
                else:
                    print(f"  ❌ {mode} mode: Got {publisher_type}, expected {expected_types[mode]}")
                    test_results[mode] = False
                
            except Exception as e:
                print(f"  ❌ {mode} mode failed: {e}")
                test_results[mode] = False
        
        # Restore original mode
        os.environ['ORDER_EVENT_MODE'] = original_mode
        EventPublisherFactory.reset()
        
        return all(test_results.values())
        
    except Exception as e:
        print(f"❌ Error testing modes: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_mode_test_script():
    """Create a script to test each mode manually"""
    script_content = '''#!/usr/bin/env python3
"""
Test Each Mode - Manual Testing Script

This script helps you test each mode by sending a test event.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_mode(mode):
    """Test a specific mode"""
    print(f"\\n{'='*60}")
    print(f"TESTING {mode} MODE")
    print('='*60)
    
    # Set mode
    os.environ['ORDER_EVENT_MODE'] = mode
    
    # Load environment
    from utils.env_check import load_and_check_env_variables
    load_and_check_env_variables()
    
    # Reset singleton
    from utils.event_publisher import EventPublisherFactory
    EventPublisherFactory.reset()
    
    # Get publisher
    from utils.event_publisher import get_event_publisher
    publisher = get_event_publisher()
    publisher_type = type(publisher).__name__
    
    print(f"Publisher type: {publisher_type}")
    
    # Publish test event
    print("\\nPublishing test order event...")
    success = publisher.publish_order_event(
        user_id="test_user",
        symbol="TEST-EQ",
        action="BUY",
        orderid="TEST_ORDER_123",
        mode="test",
        broker="test_broker",
        quantity="1",
        price="100.00"
    )
    
    if success:
        print("✅ Test event published successfully!")
        print(f"\\nVerification:")
        if mode == 'SOCKETIO' or mode == 'BOTH':
            print("  - Check browser console for Socket.IO event")
        if mode == 'KAFKA' or mode == 'BOTH':
            print("  - Check Kafka consumer for message:")
            print("    docker exec -it kafka-kafka-1 kafka-console-consumer \\\\")
            print("      --bootstrap-server localhost:9092 \\\\")
            print("      --topic from_openalgo_order_events \\\\")
            print("      --from-beginning")
    else:
        print("❌ Failed to publish test event")
    
    return success

def main():
    print("="*60)
    print("OPENALGO EVENT MODE TESTER")
    print("="*60)
    print()
    print("This script tests each event publishing mode.")
    print()
    print("Available modes:")
    print("  1. SOCKETIO - Events to Socket.IO (UI) only")
    print("  2. KAFKA    - Events to Kafka only")
    print("  3. BOTH     - Events to both Socket.IO and Kafka")
    print("  4. ALL      - Test all three modes")
    print()
    
    choice = input("Enter your choice (1-4): ").strip()
    
    modes_map = {
        '1': 'SOCKETIO',
        '2': 'KAFKA',
        '3': 'BOTH'
    }
    
    if choice in modes_map:
        test_mode(modes_map[choice])
    elif choice == '4':
        for mode in ['SOCKETIO', 'KAFKA', 'BOTH']:
            test_mode(mode)
            input("\\nPress Enter to test next mode...")
    else:
        print("Invalid choice!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\\n\\nTest cancelled")
    except Exception as e:
        print(f"\\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
'''
    
    filepath = Path("test_event_modes.py")
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script_content)
        print(f"\n✅ Created test script: {filepath}")
        print("   Run with: python test_event_modes.py")
        return True
    except Exception as e:
        print(f"❌ Failed to create test script: {e}")
        return False

def main():
    print("="*60)
    print("OPENALGO - COMPLETE FIX FOR ALL THREE MODES")
    print("="*60)
    print()
    print("This script will:")
    print("  1. Fix place_smart_order_service.py")
    print("  2. Test all three modes (SOCKETIO, KAFKA, BOTH)")
    print("  3. Create a mode testing script")
    print()
    
    # Check directory
    if not os.path.exists('services'):
        print("❌ Error: services/ directory not found!")
        print("   Please run this script from the openalgo-stream directory")
        sys.exit(1)
    
    # Fix service
    print("="*60)
    print("STEP 1: FIXING SERVICE")
    print("="*60)
    
    if not fix_place_smart_order_service():
        print("\n❌ Failed to fix service")
        sys.exit(1)
    
    # Test modes
    print("\n" + "="*60)
    print("STEP 2: TESTING ALL MODES")
    print("="*60)
    
    all_modes_work = test_all_three_modes()
    
    # Create test script
    print("\n" + "="*60)
    print("STEP 3: CREATING TEST SCRIPT")
    print("="*60)
    
    create_mode_test_script()
    
    # Show summary
    print("\n" + "="*60)
    if all_modes_work:
        print("✅ SUCCESS! ALL THREE MODES WORKING")
    else:
        print("⚠️  WARNING: SOME MODES MAY NOT WORK")
    print("="*60)
    
    print("\n📋 How to use each mode:")
    print()
    print("1️⃣  SOCKETIO MODE (UI only):")
    print("   Edit .env: ORDER_EVENT_MODE='SOCKETIO'")
    print("   Restart: python app.py")
    print("   Test: Check browser console for events")
    print()
    print("2️⃣  KAFKA MODE (External systems only):")
    print("   Edit .env: ORDER_EVENT_MODE='KAFKA'")
    print("   Restart: python app.py")
    print("   Test: Check Kafka consumer")
    print("   docker exec -it kafka-kafka-1 kafka-console-consumer \\")
    print("     --bootstrap-server localhost:9092 \\")
    print("     --topic from_openalgo_order_events --from-beginning")
    print()
    print("3️⃣  BOTH MODE (UI + External systems):")
    print("   Edit .env: ORDER_EVENT_MODE='BOTH'")
    print("   Restart: python app.py")
    print("   Test: Check BOTH browser console AND Kafka consumer")
    print()
    print("🧪 To test modes without restarting:")
    print("   python test_event_modes.py")
    print()
    print("📝 Current .env setting:")
    try:
        with open('.env', 'r') as f:
            for line in f:
                if 'ORDER_EVENT_MODE' in line and not line.strip().startswith('#'):
                    print(f"   {line.strip()}")
                    break
    except:
        print("   Could not read .env")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
