#!/usr/bin/env python3
"""
OpenAlgo BOTH Mode Diagnostic Tool

This script diagnoses why Kafka messages aren't being sent in BOTH mode.
"""

import os
import sys
from pathlib import Path

def check_env_config():
    """Check .env configuration"""
    print("="*60)
    print("STEP 1: CHECKING .ENV CONFIGURATION")
    print("="*60)
    
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        return False
    
    with open('.env', 'r') as f:
        content = f.read()
    
    # Check ORDER_EVENT_MODE
    if "ORDER_EVENT_MODE='BOTH'" in content or 'ORDER_EVENT_MODE="BOTH"' in content or 'ORDER_EVENT_MODE=BOTH' in content:
        print("✓ ORDER_EVENT_MODE is set to BOTH")
    else:
        print("❌ ORDER_EVENT_MODE is NOT set to BOTH")
        print("   Current value:", end=" ")
        for line in content.split('\n'):
            if 'ORDER_EVENT_MODE' in line and not line.strip().startswith('#'):
                print(line.strip())
                break
        print("\n   FIX: Edit .env and set:")
        print("   ORDER_EVENT_MODE='BOTH'")
        return False
    
    # Check Kafka config
    kafka_ok = True
    if 'KAFKA_BOOTSTRAP_SERVERS' not in content or "KAFKA_BOOTSTRAP_SERVERS=''" in content:
        print("❌ KAFKA_BOOTSTRAP_SERVERS not configured")
        kafka_ok = False
    else:
        print("✓ KAFKA_BOOTSTRAP_SERVERS is configured")
    
    if 'KAFKA_ORDER_EVENTS_TOPIC' not in content or "KAFKA_ORDER_EVENTS_TOPIC=''" in content:
        print("❌ KAFKA_ORDER_EVENTS_TOPIC not configured")
        kafka_ok = False
    else:
        print("✓ KAFKA_ORDER_EVENTS_TOPIC is configured")
    
    print()
    return kafka_ok

def check_event_publisher():
    """Check if BOTH mode exists in event_publisher.py"""
    print("="*60)
    print("STEP 2: CHECKING EVENT_PUBLISHER.PY")
    print("="*60)
    
    filepath = Path("utils/event_publisher.py")
    
    if not filepath.exists():
        print("❌ utils/event_publisher.py not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for BothEventPublisher class
    if "class BothEventPublisher" in content:
        print("✓ BothEventPublisher class exists")
    else:
        print("❌ BothEventPublisher class NOT found!")
        print("\n   FIX: Run add_both_mode.py to add BOTH mode support")
        print("   python add_both_mode.py")
        return False
    
    # Check if factory supports BOTH mode
    if "if mode == 'BOTH':" in content:
        print("✓ EventPublisherFactory supports BOTH mode")
    else:
        print("❌ EventPublisherFactory does NOT support BOTH mode!")
        print("\n   FIX: Run add_both_mode.py to update factory")
        print("   python add_both_mode.py")
        return False
    
    print()
    return True

def check_services_using_event_publisher():
    """Check if services are using event_publisher instead of socketio"""
    print("="*60)
    print("STEP 3: CHECKING SERVICES")
    print("="*60)
    
    filepath = Path("services/place_smart_order_service.py")
    
    if not filepath.exists():
        print("❌ services/place_smart_order_service.py not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if using event_publisher
    if "from utils.event_publisher import get_event_publisher" in content:
        print("✓ Service imports get_event_publisher")
    else:
        print("❌ Service still imports socketio directly!")
        print("\n   FIX: Run fix_kafka_integration.py")
        print("   python fix_kafka_integration.py")
        return False
    
    if "event_publisher = get_event_publisher()" in content:
        print("✓ Service initializes event_publisher")
    else:
        print("❌ Service doesn't initialize event_publisher!")
        print("\n   FIX: Run fix_kafka_integration.py")
        print("   python fix_kafka_integration.py")
        return False
    
    # Check if still using socketio.emit
    if "socketio.emit" in content or "socketio.start_background_task" in content:
        print("⚠️  WARNING: Service still contains socketio.emit calls!")
        print("   This might interfere with event_publisher")
        print("\n   FIX: Run fix_kafka_integration.py to replace all socketio.emit")
        print("   python fix_kafka_integration.py")
        return False
    else:
        print("✓ Service uses event_publisher (no socketio.emit)")
    
    print()
    return True

def test_event_publisher_runtime():
    """Test if event_publisher can initialize in BOTH mode"""
    print("="*60)
    print("STEP 4: TESTING EVENT PUBLISHER RUNTIME")
    print("="*60)
    
    try:
        # Load environment
        from utils.env_check import load_and_check_env_variables
        load_and_check_env_variables()
        
        # Try to create event publisher
        from utils.event_publisher import get_event_publisher
        
        publisher = get_event_publisher()
        publisher_type = type(publisher).__name__
        
        print(f"✓ Event publisher initialized: {publisher_type}")
        
        if publisher_type == "BothEventPublisher":
            print("✅ SUCCESS: Using BothEventPublisher (BOTH mode)")
            return True
        elif publisher_type == "SocketIOEventPublisher":
            print("⚠️  WARNING: Using SocketIOEventPublisher (Socket.IO only)")
            print("   Kafka messages will NOT be sent!")
            print("\n   Possible causes:")
            print("   1. ORDER_EVENT_MODE not set to 'BOTH' in .env")
            print("   2. Kafka configuration missing in .env")
            print("   3. BothEventPublisher class not found in event_publisher.py")
            return False
        elif publisher_type == "KafkaEventPublisher":
            print("⚠️  WARNING: Using KafkaEventPublisher (Kafka only)")
            print("   Socket.IO messages will NOT be sent!")
            return False
        else:
            print(f"❌ Unknown publisher type: {publisher_type}")
            return False
            
    except Exception as e:
        print(f"❌ Error initializing event publisher: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_kafka_connection():
    """Test Kafka connection"""
    print("\n" + "="*60)
    print("STEP 5: TESTING KAFKA CONNECTION")
    print("="*60)
    
    try:
        from kafka import KafkaProducer
        import json
        
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        print(f"Testing connection to: {bootstrap_servers}")
        
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=5000
        )
        
        print("✓ Kafka connection successful")
        
        # Try to send a test message
        topic = os.getenv('KAFKA_ORDER_EVENTS_TOPIC', 'from_openalgo_order_events')
        print(f"Sending test message to topic: {topic}")
        
        test_message = {
            "test": True,
            "message": "Diagnostic test from OpenAlgo"
        }
        
        future = producer.send(topic, value=test_message)
        result = future.get(timeout=10)
        
        print(f"✅ Test message sent successfully!")
        print(f"   Partition: {result.partition}")
        print(f"   Offset: {result.offset}")
        
        producer.close()
        
        print("\n   Now check your Kafka consumer - you should see the test message!")
        return True
        
    except ImportError:
        print("❌ kafka-python not installed")
        print("\n   FIX: pip install kafka-python==2.0.2")
        return False
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")
        print("\n   Possible causes:")
        print("   1. Kafka is not running")
        print("   2. Wrong KAFKA_BOOTSTRAP_SERVERS in .env")
        print("   3. Network/firewall issues")
        return False

def show_summary(results):
    """Show summary of diagnostic results"""
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    
    all_passed = all(results.values())
    
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {step}")
    
    print("\n" + "="*60)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED!")
        print("="*60)
        print("\nYour configuration looks good. If Kafka still doesn't work:")
        print("\n1. Restart OpenAlgo:")
        print("   python app.py")
        print("\n2. Check OpenAlgo logs for errors:")
        print("   Get-Content log\\application.log -Tail 100")
        print("\n3. Place a test order and check both:")
        print("   - Browser console for Socket.IO events")
        print("   - Kafka consumer for messages")
    else:
        print("❌ SOME CHECKS FAILED!")
        print("="*60)
        print("\nFollow the FIX instructions above for each failed check.")
        print("\nQuick fixes:")
        print("1. If event_publisher missing BOTH mode:")
        print("   python add_both_mode.py")
        print("\n2. If services not using event_publisher:")
        print("   python fix_kafka_integration.py")
        print("\n3. If .env not configured:")
        print("   Edit .env and set ORDER_EVENT_MODE='BOTH'")

def main():
    print("="*60)
    print("OPENALGO BOTH MODE DIAGNOSTIC TOOL")
    print("="*60)
    print("\nThis tool will check why Kafka messages aren't being sent")
    print("even though Socket.IO (UI) is working.")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('utils'):
        print("❌ Error: utils/ directory not found!")
        print("   Please run this script from the openalgo-stream directory")
        sys.exit(1)
    
    results = {}
    
    # Run checks
    results['Environment Config'] = check_env_config()
    results['Event Publisher Code'] = check_event_publisher()
    results['Service Integration'] = check_services_using_event_publisher()
    results['Runtime Test'] = test_event_publisher_runtime()
    results['Kafka Connection'] = test_kafka_connection()
    
    # Show summary
    show_summary(results)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Diagnostic cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
