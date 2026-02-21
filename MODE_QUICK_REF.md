# OpenAlgo Event Modes - Quick Reference Card

## 🚀 QUICK FIX (Do This First!)

```powershell
cd C:\workspace\openalgo-stream
.\fix_all_modes.bat
```

---

## 📋 Three Modes - At a Glance

| Mode | .env Setting | UI Updates | Kafka Messages | Use For |
|------|-------------|------------|----------------|---------|
| **SOCKETIO** | `ORDER_EVENT_MODE='SOCKETIO'` | ✅ Yes | ❌ No | Development, Simple setups |
| **KAFKA** | `ORDER_EVENT_MODE='KAFKA'` | ❌ No | ✅ Yes | API-only, Microservices |
| **BOTH** | `ORDER_EVENT_MODE='BOTH'` | ✅ Yes | ✅ Yes | **Production (Recommended)** |

---

## ⚡ How to Switch Modes (2 Steps)

### 1. Edit .env
```powershell
notepad .env
```
Change `ORDER_EVENT_MODE='...'` to your desired mode

### 2. Restart
```powershell
python app.py
```

Done! ✅

---

## ✅ Quick Tests

### SOCKETIO Mode
```
Browser Console (F12) → Should see: Socket.IO event
Kafka Consumer → Should see: NOTHING (expected)
```

### KAFKA Mode
```
Browser Console → Should see: NOTHING (expected)
Kafka Consumer → Should see: JSON messages
```

### BOTH Mode
```
Browser Console → Should see: Socket.IO event
Kafka Consumer → Should see: JSON messages
BOTH at the same time! ✨
```

---

## 🧪 Test Without Restarting

```powershell
python test_event_modes.py
```

Choose mode to test → Sends test event → See results!

---

## 🔍 Troubleshooting

### Nothing works?
```powershell
.\fix_all_modes.bat
python app.py
```

### Wrong mode?
```powershell
type .env | findstr ORDER_EVENT_MODE
notepad .env  # Fix it
python app.py
```

### Kafka consumer command
```bash
docker exec -it kafka-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic from_openalgo_order_events \
  --from-beginning
```

---

## 📚 Full Documentation

- **ALL_MODES_GUIDE.md** - Complete guide with examples
- **BOTH_MODE_GUIDE.md** - BOTH mode deep dive
- **KAFKA_FIX_GUIDE.md** - Kafka troubleshooting

---

## 💡 Pro Tips

✅ **Use BOTH mode** in production for maximum flexibility  
✅ **Test with** `python test_event_modes.py` before going live  
✅ **Check logs** at startup to verify mode:  
   - SOCKETIO: "Using Socket.IO for order events"  
   - KAFKA: "Using Kafka for order events"  
   - BOTH: "Using BOTH Socket.IO and Kafka"

---

**Quick Help:**
```powershell
# Fix everything
.\fix_all_modes.bat

# Test modes
python test_event_modes.py

# Diagnose
python diagnose_both_mode.py

# Current mode
type .env | findstr ORDER
```

**That's it!** 🎉
