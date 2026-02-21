# OpenAlgo Event Modes - Complete Guide

## 🎯 Quick Fix (Run This First!)

```powershell
cd C:\workspace\openalgo-stream
.\fix_all_modes.bat
```

This will:
- ✅ Fix all event publishing code
- ✅ Test all three modes
- ✅ Create testing script

---

## 📋 Three Modes Explained

### Mode 1: SOCKETIO (UI Only) 📱

**When to use:** Simple deployments, development, no external integration needed

**Configuration (.env):**
```bash
ORDER_EVENT_MODE='SOCKETIO'
```

**What happens:**
- ✅ Events sent to Socket.IO (WebSocket)
- ✅ Real-time UI updates in browser
- ❌ NO Kafka messages
- ❌ NO event persistence

**Test:**
1. Restart OpenAlgo
2. Open browser DevTools (F12) → Console
3. Place order
4. See: `Socket.IO: order_event received`

---

### Mode 2: KAFKA (External Systems Only) 🏢

**When to use:** Headless deployments, microservices, API-only systems

**Configuration (.env):**
```bash
ORDER_EVENT_MODE='KAFKA'
KAFKA_BOOTSTRAP_SERVERS='localhost:9092'
KAFKA_ORDER_EVENTS_TOPIC='from_openalgo_order_events'
```

**What happens:**
- ❌ NO Socket.IO events
- ❌ NO real-time UI updates
- ✅ Events sent to Kafka
- ✅ Event persistence
- ✅ External systems can consume

**Test:**
1. Restart OpenAlgo
2. Run Kafka consumer:
   ```bash
   docker exec -it kafka-kafka-1 kafka-console-consumer \
     --bootstrap-server localhost:9092 \
     --topic from_openalgo_order_events \
     --from-beginning
   ```
3. Place order
4. See JSON message in Kafka

---

### Mode 3: BOTH (Hybrid) 🚀 **RECOMMENDED**

**When to use:** Production, full-featured systems, need both UI and integrations

**Configuration (.env):**
```bash
ORDER_EVENT_MODE='BOTH'
KAFKA_BOOTSTRAP_SERVERS='localhost:9092'
KAFKA_ORDER_EVENTS_TOPIC='from_openalgo_order_events'
```

**What happens:**
- ✅ Events sent to Socket.IO (WebSocket)
- ✅ Real-time UI updates
- ✅ Events sent to Kafka
- ✅ Event persistence
- ✅ External systems can consume
- ✅ Best of both worlds!

**Test:**
1. Restart OpenAlgo
2. **Terminal 1** - Kafka consumer:
   ```bash
   docker exec -it kafka-kafka-1 kafka-console-consumer \
     --bootstrap-server localhost:9092 \
     --topic from_openalgo_order_events \
     --from-beginning
   ```
3. **Browser** - Open DevTools (F12) → Console
4. Place order
5. See events in **BOTH** Kafka and browser console

---

## 🔧 How to Switch Modes

### Step 1: Edit .env

```powershell
notepad .env
```

Change the line:
```bash
# Current
ORDER_EVENT_MODE='KAFKA'

# To one of these
ORDER_EVENT_MODE='SOCKETIO'  # UI only
ORDER_EVENT_MODE='KAFKA'     # Kafka only
ORDER_EVENT_MODE='BOTH'      # Both (recommended)
```

### Step 2: Restart OpenAlgo

```powershell
# Stop (Ctrl+C if running)
python app.py
```

### Step 3: Verify

**Look for in logs:**

**SOCKETIO mode:**
```
✓ Using Socket.IO for order events (default)
```

**KAFKA mode:**
```
✓ Using Kafka for order events
  Kafka topic: from_openalgo_order_events
  Kafka servers: localhost:9092
```

**BOTH mode:**
```
✓ Using BOTH Socket.IO and Kafka for order events
  Kafka topic: from_openalgo_order_events
  Kafka servers: localhost:9092
```

---

## 🧪 Testing Without Restarting

Use the test script:

```powershell
python test_event_modes.py
```

**Menu:**
```
1. SOCKETIO - Test Socket.IO only
2. KAFKA    - Test Kafka only
3. BOTH     - Test both simultaneously
4. ALL      - Test all three modes
```

This sends test events without restarting OpenAlgo!

---

## ✅ Verification Checklist

### For SOCKETIO Mode:
- [ ] .env has `ORDER_EVENT_MODE='SOCKETIO'`
- [ ] Restarted OpenAlgo
- [ ] Log shows "Using Socket.IO for order events"
- [ ] Browser console shows Socket.IO events
- [ ] Kafka consumer shows NO messages (expected)

### For KAFKA Mode:
- [ ] .env has `ORDER_EVENT_MODE='KAFKA'`
- [ ] Kafka is running (`docker ps`)
- [ ] Restarted OpenAlgo
- [ ] Log shows "Using Kafka for order events"
- [ ] Kafka consumer shows JSON messages
- [ ] Browser console shows NO Socket.IO events (expected)

### For BOTH Mode:
- [ ] .env has `ORDER_EVENT_MODE='BOTH'`
- [ ] Kafka is running
- [ ] Restarted OpenAlgo
- [ ] Log shows "Using BOTH Socket.IO and Kafka"
- [ ] Browser console shows Socket.IO events
- [ ] Kafka consumer shows JSON messages
- [ ] **BOTH** work simultaneously

---

## 📊 Mode Comparison Table

| Feature | SOCKETIO | KAFKA | BOTH |
|---------|----------|-------|------|
| **Real-time UI** | ✅ Yes | ❌ No | ✅ Yes |
| **Kafka events** | ❌ No | ✅ Yes | ✅ Yes |
| **Event persistence** | ❌ No | ✅ Yes | ✅ Yes |
| **Event replay** | ❌ No | ✅ Yes | ✅ Yes |
| **External integration** | ❌ No | ✅ Yes | ✅ Yes |
| **Latency (UI)** | ~50ms | N/A | ~50ms |
| **Latency (Kafka)** | N/A | ~100ms | ~100ms |
| **Setup complexity** | Easy | Medium | Medium |
| **Production ready** | ✅ | ✅ | ✅ |
| **Recommended for** | Dev/Simple | API-only | Production |

---

## 🐛 Troubleshooting

### Issue: No events in ANY mode

**Fix:**
```powershell
# 1. Run complete fix
.\fix_all_modes.bat

# 2. Check services use event_publisher
python diagnose_both_mode.py

# 3. Check logs
Get-Content log\application.log -Tail 100
```

### Issue: SOCKETIO works, KAFKA doesn't

**Check:**
1. `.env` has correct mode (`BOTH` or `KAFKA`)
2. Kafka is running: `docker ps`
3. Topic exists: 
   ```bash
   docker exec -it kafka-kafka-1 kafka-topics --list --bootstrap-server localhost:9092
   ```
4. Restart OpenAlgo after changing .env

### Issue: KAFKA works, SOCKETIO doesn't

**Check:**
1. `.env` has correct mode (`BOTH` or `SOCKETIO`)
2. Browser has Socket.IO connection
3. Check browser console for Socket.IO errors
4. Restart OpenAlgo

### Issue: Mode seems wrong

**Verify actual mode:**
```powershell
# Check .env
type .env | findstr ORDER_EVENT_MODE

# Check logs
Get-Content log\application.log -Tail 50 | Select-String "event"

# Test runtime
python test_event_modes.py
```

---

## 📚 Quick Commands

```powershell
# Complete fix
.\fix_all_modes.bat

# Test modes
python test_event_modes.py

# Diagnose issues
python diagnose_both_mode.py

# Check current mode
type .env | findstr ORDER_EVENT_MODE

# Kafka consumer
docker exec -it kafka-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic from_openalgo_order_events --from-beginning

# Check Kafka topics
docker exec -it kafka-kafka-1 kafka-topics --list --bootstrap-server localhost:9092

# OpenAlgo logs
Get-Content log\application.log -Tail 100

# Restart OpenAlgo
python app.py
```

---

## 🎯 Recommended Setup

**For Development:**
```bash
ORDER_EVENT_MODE='SOCKETIO'
```

**For Production:**
```bash
ORDER_EVENT_MODE='BOTH'
KAFKA_BOOTSTRAP_SERVERS='kafka1:9092,kafka2:9092,kafka3:9092'
KAFKA_ORDER_EVENTS_TOPIC='from_openalgo_order_events'
KAFKA_PRODUCER_ACKS='all'
KAFKA_PRODUCER_COMPRESSION='snappy'
```

---

## 📖 What Gets Published

All modes publish these events (to Socket.IO, Kafka, or both):

| Event Type | Trigger | Frequency |
|------------|---------|-----------|
| `order_event` | Order placed successfully | ~100/day |
| `analyzer_update` | Sandbox/analyzer mode | ~1000/day |
| `order_notification` | Position matched, etc. | ~20/day |
| `master_contract_download` | Contract download | ~5/day |
| `password_change` | Password changed | ~2/month |

**Example Kafka message:**
```json
{
  "event_type": "order_event",
  "timestamp": "2026-02-06T12:00:00.000Z",
  "user_id": "user_api_key",
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

**Created**: February 2026  
**Version**: 1.0  
**Status**: All Three Modes Working ✨
