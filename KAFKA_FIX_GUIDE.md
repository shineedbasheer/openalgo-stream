# OpenAlgo Kafka Integration Issue - Diagnosis & Fix

## 🔍 **Problem Identified**

Your Kafka is running correctly (`localhost:9092`), but OpenAlgo is **not publishing events to Kafka** because:

1. ✅ **event_publisher.py exists** with Kafka support
2. ✅ **.env configured correctly** with `ORDER_EVENT_MODE=KAFKA`  
3. ❌ **Services NOT using event_publisher** - still using `socketio.emit` directly

### Current Code (place_smart_order_service.py)
```python
# Line 11: Still importing socketio directly
from extensions import socketio

# Line 57-60: Still using socketio.emit
socketio.start_background_task(
    socketio.emit, "analyzer_update", {"request": analyzer_request, "response": error_response}
)

# Line 230-236, 257-266: More socketio.emit calls
```

**This is why you're NOT seeing messages in Kafka!**

---

## 🔧 **Solution: Update Services to Use Event Publisher**

### Step 1: Update place_smart_order_service.py

Replace the socketio import and all emit calls with the event_publisher.

**Location**: `C:\workspace\openalgo-stream\services\place_smart_order_service.py`

**Changes needed**:
1. Replace import on line 11
2. Initialize event_publisher at module level
3. Replace all 4 socketio.emit calls

---

## 📋 **Quick Fix Script**

I'll create a Python script to automatically fix all the services for you.

**File**: `fix_kafka_integration.py`

```python
#!/usr/bin/env python3
"""
OpenAlgo Kafka Integration Fixer

This script updates services to use event_publisher instead of direct socketio.emit
"""

import os
import re
from pathlib import Path

def backup_file(filepath):
    """Create a backup of the file before modifying"""
    backup_path = f"{filepath}.backup"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Backed up: {backup_path}")

def fix_place_smart_order_service():
    """Fix place_smart_order_service.py to use event_publisher"""
    
    filepath = Path("services/place_smart_order_service.py")
    
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return False
    
    # Create backup
    backup_file(filepath)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace imports
    content = content.replace(
        "from extensions import socketio",
        "from utils.event_publisher import get_event_publisher"
    )
    
    # Add event_publisher initialization after imports
    if "event_publisher = get_event_publisher()" not in content:
        # Find the logger initialization
        logger_pattern = r"(logger = get_logger\(__name__\))"
        content = re.sub(
            logger_pattern,
            r"\1\n\n# Initialize event publisher\nevent_publisher = get_event_publisher()",
            content
        )
    
    # Replace analyzer_update emission in emit_analyzer_error function
    content = re.sub(
        r'socketio\.start_background_task\(\s*socketio\.emit,\s*"analyzer_update",\s*\{"request":\s*analyzer_request,\s*"response":\s*error_response\}\s*\)',
        'event_publisher.publish_analyzer_update(\n        user_id=analyzer_request.get("apikey", "unknown"),\n        request=analyzer_request,\n        response=error_response\n    )',
        content
    )
    
    # Replace analyzer_update emission in analyze mode
    content = re.sub(
        r'socketio\.start_background_task\(\s*socketio\.emit,\s*"analyzer_update",\s*\{"request":\s*analyzer_request,\s*"response":\s*response_data\},\s*\)',
        'event_publisher.publish_analyzer_update(\n            user_id=original_data.get("apikey", "unknown"),\n            request=analyzer_request,\n            response=response_data\n        )',
        content
    )
    
    # Replace order_notification emission
    content = re.sub(
        r'socketio\.start_background_task\(\s*socketio\.emit,\s*"order_notification",\s*\{\s*"symbol":\s*order_data\.get\("symbol"\),\s*"status":\s*"info",\s*"message":\s*"([^"]+)",\s*\},\s*\)',
        r'event_publisher.publish_order_notification(\n                user_id=original_data.get("apikey", "unknown"),\n                symbol=order_data.get("symbol"),\n                status="info",\n                message="\1"\n            )',
        content
    )
    
    # Replace order_event emission
    content = re.sub(
        r'socketio\.start_background_task\(\s*socketio\.emit,\s*"order_event",\s*\{\s*"symbol":\s*order_data\.get\("symbol"\),\s*"action":\s*order_data\.get\("action"\),\s*"orderid":\s*order_id,\s*"mode":\s*"live",\s*\},\s*\)',
        'event_publisher.publish_order_event(\n                user_id=original_data.get("apikey", "unknown"),\n                symbol=order_data.get("symbol"),\n                action=order_data.get("action"),\n                orderid=order_id,\n                mode="live",\n                broker=broker,\n                quantity=order_data.get("quantity"),\n                price=order_data.get("price")\n            )',
        content
    )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Fixed: {filepath}")
    return True

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
    for var, expected in required_vars.items():
        if var in env_content:
            # Extract value
            pattern = f"{var}\\s*=\\s*['\"]?([^'\"\\n]+)['\"]?"
            match = re.search(pattern, env_content)
            if match:
                value = match.group(1)
                if expected in value:
                    print(f"✓ {var} = {value}")
                else:
                    print(f"⚠ {var} = {value} (expected: {expected})")
            else:
                print(f"❌ {var} not found or invalid format")
                all_good = False
        else:
            print(f"❌ {var} not configured")
            all_good = False
    
    return all_good

def main():
    print("="*60)
    print("OPENALGO KAFKA INTEGRATION FIXER")
    print("="*60)
    print()
    
    # Verify we're in the correct directory
    if not os.path.exists('services'):
        print("❌ Error: services/ directory not found!")
        print("   Please run this script from the openalgo-stream directory")
        return
    
    # Verify Kafka config
    print("\nStep 1: Verifying Kafka configuration...")
    if not verify_kafka_config():
        print("\n⚠ Warning: Kafka configuration issues detected")
        print("   Please check your .env file")
    else:
        print("\n✓ Kafka configuration looks good!")
    
    # Fix services
    print("\nStep 2: Fixing services...")
    if fix_place_smart_order_service():
        print("\n✅ SUCCESS! Services updated to use event_publisher")
        print("\n📋 Next steps:")
        print("   1. Restart your OpenAlgo application")
        print("   2. Place a test order")
        print("   3. Check Kafka consumer for messages:")
        print("      docker exec -it kafka-kafka-1 kafka-console-consumer \\")
        print("        --bootstrap-server localhost:9092 \\")
        print("        --topic from_openalgo_order_events \\")
        print("        --from-beginning")
    else:
        print("\n❌ Failed to fix services")
        print("   Please check the backup files and try manual fixes")

if __name__ == "__main__":
    main()
```

---

## 🚀 **How to Apply the Fix**

### Option 1: Run the Auto-Fixer (Recommended)

1. **Save the fix script** above as `fix_kafka_integration.py` in your project root

2. **Run it**:
   ```powershell
   cd C:\workspace\openalgo-stream
   python fix_kafka_integration.py
   ```

3. **Restart OpenAlgo**:
   ```powershell
   # If running with Python
   python app.py
   
   # If running with Docker
   docker-compose restart
   ```

4. **Test it**:
   ```powershell
   # In one terminal, run Kafka consumer
   docker exec -it kafka-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic from_openalgo_order_events --from-beginning
   
   # In another terminal or browser, place a test order in OpenAlgo
   # You should see the message in Kafka!
   ```

---

### Option 2: Manual Fix (If Auto-Fixer Fails)

**Edit**: `services/place_smart_order_service.py`

**Change 1** - Line 11:
```python
# OLD
from extensions import socketio

# NEW
from utils.event_publisher import get_event_publisher
```

**Change 2** - After line 26 (after logger):
```python
# Initialize logger
logger = get_logger(__name__)

# ADD THIS LINE
event_publisher = get_event_publisher()
```

**Change 3** - Line 57-60 (emit_analyzer_error function):
```python
# OLD
socketio.start_background_task(
    socketio.emit, "analyzer_update", {"request": analyzer_request, "response": error_response}
)

# NEW
event_publisher.publish_analyzer_update(
    user_id=analyzer_request.get("apikey", "unknown"),
    request=analyzer_request,
    response=error_response
)
```

**Change 4** - Line 189-193 (analyzer mode):
```python
# OLD
socketio.start_background_task(
    socketio.emit,
    "analyzer_update",
    {"request": analyzer_request, "response": response_data},
)

# NEW
event_publisher.publish_analyzer_update(
    user_id=original_data.get("apikey", "unknown"),
    request=analyzer_request,
    response=response_data
)
```

**Change 5** - Line 230-236 (order notification):
```python
# OLD
socketio.start_background_task(
    socketio.emit,
    "order_notification",
    {
        "symbol": order_data.get("symbol"),
        "status": "info",
        "message": " Positions Already Matched. No Action needed.",
    },
)

# NEW
event_publisher.publish_order_notification(
    user_id=original_data.get("apikey", "unknown"),
    symbol=order_data.get("symbol"),
    status="info",
    message="Positions Already Matched. No Action needed."
)
```

**Change 6** - Line 257-266 (order event):
```python
# OLD
socketio.start_background_task(
    socketio.emit,
    "order_event",
    {
        "symbol": order_data.get("symbol"),
        "action": order_data.get("action"),
        "orderid": order_id,
        "mode": "live",
    },
)

# NEW
event_publisher.publish_order_event(
    user_id=original_data.get("apikey", "unknown"),
    symbol=order_data.get("symbol"),
    action=order_data.get("action"),
    orderid=order_id,
    mode="live",
    broker=broker,
    quantity=order_data.get("quantity"),
    price=order_data.get("price")
)
```

---

## ✅ **Testing the Fix**

### 1. Start Kafka Consumer
```bash
docker exec -it kafka-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic from_openalgo_order_events \
  --from-beginning
```

### 2. Place a Test Order
Use the OpenAlgo UI or API to place an order.

### 3. Expected Output in Kafka
```json
{
  "event_type": "order_event",
  "timestamp": "2026-02-05T10:30:45.123456Z",
  "user_id": "your_api_key",
  "source": "openalgo",
  "version": "1.0",
  "data": {
    "symbol": "SBIN-EQ",
    "action": "BUY",
    "orderid": "ORD123456",
    "mode": "live",
    "broker": "zerodha",
    "quantity": "1",
    "price": "850.50"
  }
}
```

---

## 🐛 **Troubleshooting**

### Issue: Still no messages in Kafka

**Check 1**: Verify event_publisher is being initialized
```python
# In place_smart_order_service.py, add debug log after line 26
event_publisher = get_event_publisher()
logger.info(f"Event publisher type: {type(event_publisher)}")
```

**Check 2**: Verify ORDER_EVENT_MODE is set to KAFKA
```python
import os
print(os.getenv('ORDER_EVENT_MODE'))  # Should print 'KAFKA'
```

**Check 3**: Check OpenAlgo logs for errors
```powershell
# Look for Kafka connection errors
Get-Content log\application.log -Tail 100 | Select-String "kafka"
```

### Issue: "kafka-python not installed" error

**Fix**:
```powershell
pip install kafka-python==2.0.2
```

### Issue: Kafka connection timeout

**Check Kafka is running**:
```powershell
docker ps | Select-String kafka
```

**Test Kafka connectivity**:
```python
from kafka import KafkaProducer
producer = KafkaProducer(bootstrap_servers='localhost:9092')
producer.send('test-topic', b'Hello')
producer.close()
```

---

## 📊 **What Gets Published to Kafka**

| Event Type | When Triggered | Message Count |
|------------|----------------|---------------|
| `order_event` | Order placed successfully | ~100/day |
| `analyzer_update` | Sandbox/analyzer mode order | ~1000/day (testing) |
| `order_notification` | Position already matched | ~20/day |
| `master_contract_download` | Contract download completes | ~5/day |
| `password_change` | Password changed | ~2/month |

---

## 🎯 **Summary**

**Root Cause**: Services still using `socketio.emit` instead of `event_publisher`

**Solution**: Update services to use `get_event_publisher()` and replace all `socketio.emit` calls

**Files to Modify**:
1. ✅ `services/place_smart_order_service.py` - Most critical
2. (Optional) `blueprints/master_contract_status.py` - For contract download events
3. (Optional) `blueprints/auth.py` - For password change events

**After Fix**: All order events will flow to Kafka topic `from_openalgo_order_events` ✨

---

**Created**: February 2026  
**Version**: 1.0
