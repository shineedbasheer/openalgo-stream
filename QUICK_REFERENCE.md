# OpenAlgo Event Publishing - Quick Reference

## 🚀 One-Minute Setup for BOTH Mode

```powershell
# 1. Add BOTH mode support
.\add_both_mode.bat

# 2. Edit .env
ORDER_EVENT_MODE='BOTH'

# 3. Restart
python app.py
```

**Done!** Events now flow to Socket.IO (UI) AND Kafka (external systems)! ✨

---

## 📋 Available Modes

| Mode | .env Setting | Description | Use When |
|------|-------------|-------------|----------|
| **SOCKETIO** | `ORDER_EVENT_MODE='SOCKETIO'` | UI only | Simple deployments |
| **KAFKA** | `ORDER_EVENT_MODE='KAFKA'` | External systems only | Headless/API-only |
| **BOTH** | `ORDER_EVENT_MODE='BOTH'` | UI + External systems | Production (recommended) |

---

## ✅ Quick Tests

### Test Socket.IO (UI)
1. Open browser DevTools (F12) → Console
2. Place order
3. See: `Socket.IO: order_event received`

### Test Kafka (External)
```bash
docker exec -it kafka-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic from_openalgo_order_events \
  --from-beginning
```

---

## 🎯 When to Use Each Mode

### SOCKETIO Mode
✅ Development/Testing  
✅ Simple setups  
✅ No external integration needed  
❌ No event persistence  

### KAFKA Mode
✅ API-only deployments  
✅ Microservices architecture  
✅ Event-driven systems  
❌ No real-time UI updates  

### BOTH Mode (Recommended)
✅ Production deployments  
✅ Real-time UI + Analytics  
✅ Compliance requirements  
✅ Best of both worlds  

---

## 🔧 Commands

```powershell
# Add BOTH mode
.\add_both_mode.bat

# Fix Kafka integration (if needed)
.\fix_kafka_integration.bat

# Reset password
.\reset_password.bat
```

---

## 📊 What Gets Published

| Event | Frequency | Socket.IO | Kafka |
|-------|-----------|-----------|-------|
| Order placed | ~100/day | ✅ | ✅ |
| Analyzer update | ~1000/day | ✅ | ✅ |
| Notifications | ~20/day | ✅ | ✅ |
| Contract download | ~5/day | ✅ | ✅ |
| Password change | ~2/month | ✅ | ✅ |

---

## 🎓 Examples

### Frontend (Socket.IO)
```javascript
socket.on('order_event', (data) => {
  showNotification(`Order ${data.orderid} placed`);
});
```

### Backend (Kafka Consumer)
```python
from kafka import KafkaConsumer
consumer = KafkaConsumer('from_openalgo_order_events')
for msg in consumer:
    process_order_event(msg.value)
```

---

## 🐛 Troubleshooting

**No events in Kafka?**
→ Check: `ORDER_EVENT_MODE='BOTH'` in .env  
→ Run: `.\fix_kafka_integration.bat`  

**No events in UI?**
→ Check browser console for Socket.IO errors  
→ Verify Socket.IO connection  

**Both not working?**
→ Check logs: `Get-Content log\application.log -Tail 100`  
→ Read: `BOTH_MODE_GUIDE.md`  

---

## 📚 Full Guides

- **BOTH_MODE_GUIDE.md** - Complete guide with architecture
- **KAFKA_FIX_GUIDE.md** - Kafka integration troubleshooting
- **PASSWORD_RESET_GUIDE.md** - Reset credentials

---

**Quick Help**: 
```powershell
# View guides
notepad BOTH_MODE_GUIDE.md
notepad KAFKA_FIX_GUIDE.md

# Check current mode
type .env | findstr ORDER_EVENT_MODE
```
