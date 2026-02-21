#!/usr/bin/env python3
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
    print(f"\n{'='*60}")
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
    print("\nPublishing test order event...")
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
        print(f"\nVerification:")
        if mode == 'SOCKETIO' or mode == 'BOTH':
            print("  - Check browser console for Socket.IO event")
        if mode == 'KAFKA' or mode == 'BOTH':
            print("  - Check Kafka consumer for message:")
            print("    docker exec -it kafka-kafka-1 kafka-console-consumer \\")
            print("      --bootstrap-server localhost:9092 \\")
            print("      --topic from_openalgo_order_events \\")
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
            input("\nPress Enter to test next mode...")
    else:
        print("Invalid choice!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
