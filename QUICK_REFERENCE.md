# 🎬 SentinelAI Event Flow - Quick Reference Card

## 📋 Event Journey in 30 Seconds

```
AI Worker (frame 30fps)
    ↓ [EVENT_EMIT] - Detects weapon/crowd
    ↓ EventCooldownManager filters duplicates
    ↓ HTTP POST → http://localhost:8000/event
    ↓
Backend (FastAPI)
    ↓ [EVENT_RX_ACCEPT] - Validates schema
    ↓ process_event() - Calculates suspicion
    ↓ trigger_alert() - Generates AI summary
    ↓ [BROADCAST_QUEUED] - Adds to async queue
    ↓
WebSocket (/ws/alerts)
    ↓ [WS_BROADCAST_START] - Ready to send
    ↓ [WS_SEND_OK] - Sent to each client
    ↓
Frontend (Next.js)
    ↓ [WS_MESSAGE_RX] - Received message
    ↓ [ALERT_DISPLAYED] - Popup shown
    ✓ User sees alert immediately
```

---

## 🚀 Start System (3 Terminals)

**Terminal 1 - Backend**:
```bash
cd backend
uvicorn main:app --reload --port 8000
```
Look for: "Application startup complete"

**Terminal 2 - Frontend**:
```bash
cd dashboard
npm run dev
```
Look for: "ready - started server on"

**Terminal 3 - Test**:
```bash
# Option A: Quick test without worker
curl http://localhost:8000/api/debug/ping

# Option B: Full test
python scripts/test_event_flow.py

# Option C: Real detection
python ai_worker/test_worker.py school_ground test_videos/school/demo.mp4
```

---

## 🔍 Logging Tags Cheat Sheet

### Worker Emission (`ai_worker/worker.py`)
| Tag | Meaning | Example |
|-----|---------|---------|
| `[EVENT_EMIT]` | Event detected, sending to backend | Before HTTP POST |
| `[EVENT_DELIVERY_OK]` | Backend received (HTTP 200) | After successful POST |
| `[EVENT_SUPPRESSED]` | Filtered by cooldown | Duplicate within 10s |
| `[EVENT_PASS_COOLDOWN]` | Passed filter, will emit | First occurrence or escalation |

**Full example**:
```
[EVENT_PASS_COOLDOWN] event_id=evt_weapon_detected_100 camera=cam1
[EVENT_EMIT] id=evt_weapon_detected_1699564800000 type=weapon_detected confidence=0.92
✓ [EVENT_DELIVERY_OK] id=evt_weapon_detected_1699564800000 status=200
```

### Backend Reception (`backend/main.py`)
| Tag | Meaning | Action |
|-----|---------|--------|
| `[EVENT_SCHEMA_INVALID]` ⚠️ | Missing required fields | Check event_type, camera_id, etc |
| `[EVENT_RX_ACCEPT]` | Event received & validated | Normal operation |
| `[EVENT_INCIDENT_DETECTED]` | Suspicion >threshold | Alert generated |
| `[BROADCAST_QUEUED]` | Alert sent to WebSocket queue | Event in pipeline |

**Full example**:
```
[EVENT_RX_ACCEPT] event_id=evt_weapon_detected_1699564800000 camera=cam1 zone=school_ground confidence=0.92
[EVENT_INCIDENT_DETECTED] event_id=evt_weapon_detected_1699564800000 type=weapon_detected priority=critical
[BROADCAST_QUEUED] event_id=evt_weapon_detected_1699564800000 queue_size=3
```

### WebSocket Broadcast (`backend/main.py`)
| Tag | Meaning | Clients |
|-----|---------|---------|
| `[WS_CLIENT_CONNECTED]` | Browser connected | +1 |
| `[WS_BROADCAST_START]` | Starting send to all | N clients |
| `[WS_SEND_OK]` | Sent to one client | ✓ delivered |
| `[WS_SEND_FAIL]` | Failed to send | ✗ removed |
| `[WS_CLIENT_DISCONNECTED]` | Browser disconnected | -1 |

**Full example**:
```
[WS_CLIENT_CONNECTED] id=140729874563456 active_clients=5
[WS_BROADCAST_START] event_id=evt_weapon_detected_1699564800000 clients=5
[WS_SEND_OK] event_id=evt_weapon_detected_1699564800000 client=0 type=weapon_detected
[WS_SEND_OK] event_id=evt_weapon_detected_1699564800000 client=1 type=weapon_detected
[WS_CLIENT_DISCONNECTED] id=140729874563456 remaining_clients=4
```

### Frontend Logging (Browser Console)
| Tag | Meaning | Console Output |
|-----|---------|--------|
| `[WS_CONNECT_ATTEMPT]` | Connecting to WebSocket | Log: Connection starting |
| `[WS_CONNECTED]` | Connected successfully | Log: Ready for alerts |
| `[WS_MESSAGE_RX]` | Received from server | Log: Object with event details |
| `[ALERT_PROCESS]` | Processing for display | Log: camera_id, event_type |
| `[ALERT_DISPLAYED]` | Popup shown | Log: priority, event_type |

**Full example** (F12 Console):
```
[WS_CONNECT_ATTEMPT] url=ws://localhost:8000/ws/alerts
[WS_CONNECTED] ready for alerts
[WS_MESSAGE_RX] {event_type: 'weapon_detected', camera_id: 'cam1', ...}
[ALERT_PROCESS] {camera_id: 'cam1', event_type: 'weapon_detected'}
[ALERT_DISPLAYED] {camera_id: 'cam1', priority: 'critical'}
```

---

## 🐛 Debugging Flowchart

```
Event not reaching backend?
├─ Worker logs: grep "[EVENT_EMIT]" 
│  └─ Not found? → Worker not detecting or not posting
├─ Backend logs: grep "[EVENT_RX_ACCEPT]"
│  └─ Not found? → HTTP POST failing, check endpoint URL
└─ Check connectivity: curl http://localhost:8000/api/stats

Event reaching backend but not frontend?
├─ Backend logs: grep "[WS_BROADCAST"
│  └─ Not found? → No incidents detected (suspicion too low)
├─ Backend logs: grep "[WS_SEND_OK]"
│  └─ Not found? → WebSocket clients connected but send failed
└─ Browser: F12 Console filter "[WS_"
   └─ No logs? → WebSocket not connected or URL wrong

Alert popup not showing?
├─ Browser console: [ALERT_DISPLAYED] missing
│  └─ Check AlertPopup.js component rendering
├─ Schema mismatch?
│  └─ Compare event fields vs EVENT_LABELS dict
└─ Duplicate suppression filtering it out?
   └─ Check [ALERT_DUPLICATE_SUPPRESSED] logs
```

---

## 📊 Expected Timing

| Step | Expected Time |
|------|---|
| Worker detects → POST HTTP | <100ms |
| Backend receives → Incident decision | <10ms |
| Backend → WebSocket broadcast | <5ms |
| WebSocket → Browser receives | <100ms |
| **Total**: Detection to display | **<300ms** |

---

## 🔧 Configuration

**Worker** (`ai_worker/worker.py` or `.env`):
```python
BACKEND_URL = "http://localhost:8000/event"
COOLDOWN_WINDOW_SECONDS = 10
CONFIDENCE_INCREASE_THRESHOLD = 0.10  # Break cooldown if +10%
```

**Backend** (`backend/main.py`):
```python
# All hardcoded, auto-configured
alert_broadcast_queue = asyncio.Queue()  # Async event delivery
active_alert_clients = []  # WebSocket connections
```

**Frontend** (`dashboard/pages/monitor.js`):
```javascript
const BACKEND_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/alerts';
// Reconnect every 3s if disconnected
```

---

## ✅ Health Check Commands

```bash
# Backend running?
curl http://localhost:8000/api/stats

# WebSocket responsive?
wscat -c ws://localhost:8000/ws/alerts

# Send debug ping
curl http://localhost:8000/api/debug/ping

# Run full test
python scripts/test_event_flow.py

# Check frontend is ready
curl http://localhost:3000
```

---

## 🎯 Log Tailing for Development

```bash
# All event flow logs (worker + backend)
tail -f backend.log | grep -E "\[EVENT|\[WS_|\[BROADCAST"

# Only failures
tail -f backend.log | grep -E "FAIL|ERROR|timeout"

# Only WebSocket activity
tail -f backend.log | grep "\[WS_"

# Browser console (F12)
Filter input: "[WS_" or "[ALERT"
```

---

## 📁 Key Files Quick Reference

| File | Purpose | Key Functions |
|------|---------|---|
| `ai_worker/worker.py` | Event emission & filtering | `_send_event()`, `EventCooldownManager` |
| `ai_worker/detectors.py` | Detection models | `WeaponDetector`, `FireSmokeDetector` |
| `backend/main.py` | Event reception & WebSocket | POST `/event`, WS `/ws/alerts` |
| `dashboard/pages/monitor.js` | Frontend WebSocket listener | `ws.onmessage`, event state |
| `scripts/test_event_flow.py` | End-to-end testing | 5 comprehensive tests |
| `EVENT_FLOW.md` | Complete documentation | Full architecture & debugging guide |

---

## 🚨 Common Issues & Fixes

| Issue | Log Evidence | Fix |
|-------|---|---|
| No `[EVENT_EMIT]` | Worker not detecting | Confidence threshold too high? Video has actual events? |
| `[EVENT_SUPPRESSED]` too much | Cooldown blocking | Increase cooldown or lower threshold in `EventCooldownManager` |
| No `[WS_SEND_OK]` | Clients connected but `[WS_SEND_FAIL]` | Check network, check client code handles async |
| `[WS_PARSE_ERROR]` in browser | Console shows JSON error | Check event schema matches `EVENT_LABELS` dict |
| Alert popup blank | Component renders but empty | Check alert.event exists, check field names |
| Infinite reconnect loop | `[WS_CLOSED]` every 3s | Backend crashed? Check `/api/stats` endpoint |

---

## 📞 Emergency Restart

```bash
# Kill all processes
pkill -f "uvicorn"
pkill -f "npm run dev"
pkill -f "python.*worker"

# Clear any stuck ports
lsof -i :8000 | grep -v PID | awk '{print $2}' | xargs kill -9

# Restart fresh (Terminal 1)
cd backend && uvicorn main:app --reload --port 8000

# (Terminal 2)
cd dashboard && npm run dev

# (Terminal 3)  
python scripts/test_event_flow.py
```

---

**Print this card and keep it next to your monitor while developing!**

Last updated: November 2024 | SentinelAI Event Flow v1.0
