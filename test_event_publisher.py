"""
Test script to diagnose event publishing issues
Run this to check if the event publisher is working correctly
"""

import os
import sys

# Set environment variables before importing
os.environ['ORDER_EVENT_MODE'] = 'BOTH'
os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:9092'
os.environ['KAFKA_ORDER_EVENTS_TOPIC'] = 'from_openalgo_order_events'

print("=" * 80)
print("Event Publisher Diagnostic Test")
print("=" * 80)
print()

# Test 1: Check environment variables
print("Test 1: Environment Variables")
print("-" * 80)
print(f"ORDER_EVENT_MODE: {os.getenv('ORDER_EVENT_MODE')}")
print(f"KAFKA_BOOTSTRAP_SERVERS: {os.getenv('KAFKA_BOOTSTRAP_SERVERS')}")
print(f"KAFKA_ORDER_EVENTS_TOPIC: {os.getenv('KAFKA_ORDER_EVENTS_TOPIC')}")
print()

# Test 2: Try to import event publisher
print("Test 2: Import Event Publisher")
print("-" * 80)
try:
    from utils.event_publisher import get_event_publisher
    print("✓ Successfully imported get_event_publisher")
except Exception as e:
    print(f"✗ Failed to import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
print()

# Test 3: Initialize event publisher
print("Test 3: Initialize Event Publisher")
print("-" * 80)
try:
    event_publisher = get_event_publisher()
    print(f"✓ Event publisher initialized: {type(event_publisher).__name__}")
    
    # Check if it's BothEventPublisher and if Kafka is available
    if hasattr(event_publisher, 'kafka_publisher'):
        if event_publisher.kafka_publisher is None:
            print("⚠ Kafka publisher is None (Kafka not available)")
        else:
            print("✓ Kafka publisher is initialized")
    
    if hasattr(event_publisher, 'socketio_publisher'):
        print("✓ Socket.IO publisher is initialized")
        
except Exception as e:
    print(f"✗ Failed to initialize: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
print()

# Test 4: Try to publish a test event
print("Test 4: Publish Test Order Event")
print("-" * 80)
try:
    result = event_publisher.publish_order_event(
        user_id="test_user",
        symbol="SBIN-EQ",
        action="BUY",
        orderid="TEST123",
        mode="live",
        exchange="NSE",
        price_type="MARKET",
        product_type="MIS"
    )
    if result:
        print("✓ Event published successfully")
    else:
        print("✗ Event publishing returned False")
except Exception as e:
    print(f"✗ Failed to publish event: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 5: Check Socket.IO
print("Test 5: Socket.IO Check")
print("-" * 80)
try:
    from extensions import socketio
    print(f"✓ Socket.IO instance exists: {socketio}")
    print(f"  Socket.IO async_mode: {socketio.async_mode}")
except Exception as e:
    print(f"✗ Failed to import socketio: {e}")
print()

# Test 6: Check Kafka connectivity (if BOTH mode)
if os.getenv('ORDER_EVENT_MODE') == 'BOTH':
    print("Test 6: Kafka Connectivity")
    print("-" * 80)
    try:
        from kafka import KafkaProducer
        import json
        
        producer = KafkaProducer(
            bootstrap_servers='localhost:9092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=5000
        )
        
        # Try to send a test message
        future = producer.send(
            'from_openalgo_order_events',
            value={"test": "message"}
        )
        
        # Wait for result with timeout
        record_metadata = future.get(timeout=10)
        print(f"✓ Kafka is reachable and accepting messages")
        print(f"  Topic: {record_metadata.topic}")
        print(f"  Partition: {record_metadata.partition}")
        print(f"  Offset: {record_metadata.offset}")
        
        producer.close()
        
    except ImportError:
        print("✗ kafka-python is not installed")
        print("  Install with: pip install kafka-python==2.0.2")
    except Exception as e:
        print(f"✗ Kafka connection failed: {e}")
        print("  Make sure Kafka is running at localhost:9092")
    print()

print("=" * 80)
print("Diagnostic Test Complete")
print("=" * 80)
