# 🎬 SentinelAI Event Flow Documentation

## Overview

This document describes the complete event delivery pipeline in SentinelAI, from detection to frontend display.

```
ai_worker/
├── camera reads frame
├── zone processor detects event
├── EventCooldownManager filters duplicates
└── HTTP POST to backend/event
    │
    backend/main.py
    ├── /event endpoint validates schema
    ├── process_event() calculates suspicion
    ├── trigger_alert() enriches with LLM
    ├── alert_broadcast_queue.put()
    └── /ws/alerts broadcasts to WebSocket clients
        │
        dashboard (Next.js)
        └── monitors.js WebSocket listener
            ├── JSON.parse() message
            ├── console.log([WS_MESSAGE_RX])
            └── AlertPopup displays alert
```

---

## Phase 1: AI Worker Event Emission

### 1.1 Event Creation

**Location**: `ai_worker/zones/*.py` in zone processor `process_frame()` methods

**Process**:
1. Zone detector (e.g., `_process_shared_weapons()`) analyzes frame
2. Returns `DetectionEvent` dataclass with:
   - `event_type`: str (e.g., "weapon_detected", "crowd_formation")
   - `confidence`: float (0.0-1.0)
   - `bounding_boxes`: List[List[int]] (e.g., [[x1,y1,x2,y2]])
   - `metadata`: Dict (zone-specific data)

**Example**:
```python
return DetectionEvent(
    event_type="weapon_detected",
    confidence=0.92,
    bounding_boxes=[[100, 100, 200, 200]],
    metadata={
        "weapon_type": "knife",
        "near_person": True,
        "person_distance": 150.5,
        "person_id": 42,
    },
)
```

### 1.2 Event Formatting

**Location**: `ai_worker/worker.py` in `_format_events()` method

**Process**:
- Converts `DetectionEvent` to backend schema
- Adds worker context (camera_id, zone, tenant_id, timestamp)
- Generates unique `event_id` from event_type and timestamp

**Output Schema**:
```json
{
  "event_id": "evt_weapon_detected_1699564800000",
  "tenant_id": "default",
  "camera_id": "cam1",
  "zone": "school_ground",
  "event_type": "weapon_detected",
  "confidence": 0.92,
  "timestamp": 1699564800.123,
  "bounding_boxes": [[100, 100, 200, 200]],
  "severity_score": 0.92,
  "metadata": {
    "weapon_type": "knife",
    "near_person": true,
    "person_distance": 150.5,
    "person_id": 42,
    "source": "weapon_model"
  },
  "global_person_id": null,
  "after_hours": false
}
```

### 1.3 Event Filtering (Cooldown Management)

**Location**: `ai_worker/worker.py` in `EventCooldownManager` class

**Purpose**: Prevent event flooding from repeated detections

**Key Logic**:
```python
class EventCooldownManager:
    def should_emit(self, event_key: str, confidence: float) -> bool:
        # Emit if:
        # 1. First occurrence (never seen before)
        # 2. Cooldown expired (10s default since last event_type)
        # 3. Confidence increased >10% (escalation detection)
        
        last_time = self.last_emit_times.get(event_key)
        last_conf = self.last_confidences.get(event_key)
        
        if last_time is None:
            return True  # First time
        
        if time.time() - last_time > self.cooldown_seconds:
            return True  # Cooldown expired
        
        if confidence > last_conf + 0.10:
            return True  # Confidence increased
        
        return False  # Suppressed
```

**Logging**:
- `[EVENT_PASS_COOLDOWN]` - Event passed filtering, will be emitted
- `[EVENT_SUPPRESSED]` - Event filtered out, within cooldown window

### 1.4 HTTP Delivery

**Location**: `ai_worker/worker.py` in `_send_event()` method

**Process**:
1. POST event JSON to `http://localhost:8000/event`
2. Log `[EVENT_EMIT]` before send
3. Handle response:
   - Status 200: `[EVENT_DELIVERY_OK]`
   - Timeout: `[EVENT_TIMEOUT]`
   - Connection error: `[EVENT_NO_CONNECTION]`
   - Other error: `[EVENT_DELIVERY_FAIL]`, `[EVENT_SEND_ERROR]`

**Logging Example**:
```
[EVENT_EMIT] id=evt_weapon_detected_1699564800000 camera=cam1 type=weapon_detected confidence=0.92 endpoint=http://localhost:8000/event
✓ [EVENT_DELIVERY_OK] id=evt_weapon_detected_1699564800000 type=weapon_detected camera=cam1 status=200
```

---

## Phase 2: Backend Event Reception & Processing

### 2.1 HTTP Endpoint

**Endpoint**: `POST /event`

**Location**: `backend/main.py` (lines 630-691)

**Request**: JSON event object from worker

**Validation**:
```python
required_fields = ['event_id', 'camera_id', 'zone', 'event_type', 'confidence', 'timestamp']
missing = [f for f in required_fields if f not in event]
if missing:
    logging.warning(f"[EVENT_SCHEMA_INVALID] event_id={event_id} missing_fields={missing}")
```

**Processing**:
1. Log `[EVENT_RX_ACCEPT]` with full event details
2. Call `process_event()` from `event_engine` → calculates suspicion score
3. Call `trigger_alert()` from `alert_service` → generates AI summary

**Logging Example**:
```
[EVENT_RX_ACCEPT] event_id=evt_weapon_detected_1699564800000 camera=cam1 zone=school_ground detected_by_zone=school_ground event_type=weapon_detected confidence=0.92 boxes=1 ts=1699564800.123
[EVENT_INCIDENT_DETECTED] event_id=evt_weapon_detected_1699564800000 type=weapon_detected camera=cam1 zone=school_ground priority=critical suspicion=0.85 frames=12
[ALERT_PAYLOAD] {"event": {...}, "alert": {...}, "priority": "critical", "summary": "..."}
```

### 2.2 Alert Queuing

**Component**: `asyncio.Queue` named `alert_broadcast_queue`

**Payload Structure**:
```python
{
    "event": {event object from worker},
    "alert": {
        "priority": "critical|high|medium|low",
        "summary": "AI-generated explanation",
        "suspicion_score": 0.85,
        "recommended_actions": ["action1", "action2"],
        "llm_explanation": "detailed analysis..."
    }
}
```

**Logging**:
```
[BROADCAST_QUEUED] event_id=evt_weapon_detected_1699564800000 type=weapon_detected queue_size=3
```

---

## Phase 3: WebSocket Real-Time Delivery

### 3.1 WebSocket Endpoint

**Endpoint**: `WS /ws/alerts`

**Location**: `backend/main.py` (lines 697-769)

**Client Management**:
- Store active connections in `active_alert_clients` list
- Track client ID via `id(websocket)`

**Connection Lifecycle**:

1. **Connect**:
   ```
   [WS_CLIENT_CONNECTED] id=140729874563456 active_clients=5
   [WS_INITIAL_ALERT] client=140729874563456 event_type=weapon_detected
   ```

2. **Broadcast Loop**:
   ```
   [WS_BROADCAST_START] event_id=evt_weapon_detected_1699564800000 type=weapon_detected clients=5
   [WS_SEND_OK] event_id=evt_weapon_detected_1699564800000 client=0 type=weapon_detected
   [WS_SEND_OK] event_id=evt_weapon_detected_1699564800000 client=1 type=weapon_detected
   [WS_SEND_FAIL] event_id=evt_weapon_detected_1699564800000 client=2 error=connection closed
   [WS_CLIENT_REMOVED] event_id=evt_weapon_detected_1699564800000 remaining=4
   [WS_BROADCAST_DONE] event_id=evt_weapon_detected_1699564800000 type=weapon_detected success=4/5
   ```

3. **Disconnect**:
   ```
   [WS_CLIENT_DISCONNECTED] id=140729874563456 remaining_clients=4
   ```

### 3.2 Message Format

**Per-client broadcast**: JSON-stringified alert object

```json
{
  "event": {
    "event_id": "evt_weapon_detected_1699564800000",
    "camera_id": "cam1",
    "zone": "school_ground",
    "event_type": "weapon_detected",
    "confidence": 0.92,
    "timestamp": 1699564800.123,
    "bounding_boxes": [[100, 100, 200, 200]],
    "metadata": {...}
  },
  "alert": {
    "priority": "critical",
    "summary": "Weapon detected near person in school ground",
    "suspicion_score": 0.85,
    "recommended_actions": ["notify_admin", "record_video"],
    "llm_explanation": "..."
  }
}
```

---

## Phase 4: Frontend WebSocket Reception

### 4.1 WebSocket Connection

**Location**: `dashboard/pages/monitor.js` in `useEffect` hook

**Connection Code**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/alerts');

ws.onopen = () => {
    console.log('[WS_CONNECT_ATTEMPT] url=ws://localhost:8000/ws/alerts');
    console.log('[WS_CONNECTED] ready for alerts');
};
```

### 4.2 Message Reception & Logging

**Raw WebSocket logs**:
```javascript
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('[WS_MESSAGE_RX]', {
        has_alert: true,
        has_event: true,
        event_type: 'weapon_detected',
        event_id: 'evt_weapon_detected_1699564800000',
        camera_id: 'cam1',
    });
```

**Expected console output** (browser DevTools):
```
[WS_CONNECT_ATTEMPT] url=ws://localhost:8000/ws/alerts
[WS_CONNECTED] ready for alerts
[WS_MESSAGE_RX] {
  has_alert: true,
  has_event: true,
  event_type: 'weapon_detected',
  event_id: 'evt_weapon_detected_1699564800000',
  camera_id: 'cam1'
}
[ALERT_PROCESS] {
  camera_id: 'cam1',
  event_type: 'weapon_detected',
  event_id: 'evt_weapon_detected_1699564800000'
}
[ALERT_DISPLAYED] {
  camera_id: 'cam1',
  event_type: 'weapon_detected',
  priority: 'critical'
}
```

### 4.3 Alert Display

**Location**: `dashboard/components/AlertPopup.js`

**Component Logic**:
```javascript
export default function AlertPopup({ alert, onDismiss }) {
    const event = alert.event || {};
    const eventInfo = EVENT_LABELS[event.event_type];  // "🔪 Weapon Detected"
    const zoneInfo = ZONE_LABELS[event.zone];          // "🏃 School Ground"
    const priority = alert.priority;                    // "critical" → red styling
    
    return (
        <div className={`border-l-4 ${PRIORITY_STYLES[priority].border}`}>
            {/* Header with event type and zone */}
            {/* Stats: Confidence, Suspicion, Time */}
            {/* LLM Explanation */}
            {/* Recommended Actions */}
        </div>
    );
}
```

**Visual Output**:
```
┌─────────────────────────────────────────┐
│ 🔪 Weapon Detected                   [CRITICAL]
│ 🏃 School Ground • cam1
├─────────────────────────────────────────┤
│ Confidence: 92%  | Suspicion: 85%  | Time: 14:32:15
├─────────────────────────────────────────┤
│ AI Analysis:
│ "Weapon detected near person in school ground.
│  Immediate intervention recommended."
├─────────────────────────────────────────┤
│ Recommended Actions:
│ ✓ Notify administrator
│ ✓ Record video evidence
│ ✓ Lock zone access
├─────────────────────────────────────────┤
│ [View Camera]        [Dismiss]
└─────────────────────────────────────────┘
```

---

## Debugging & Testing

### Debug Endpoint

**URL**: `GET http://localhost:8000/api/debug/ping`

**Purpose**: Test event flow without running worker

**Response**:
```json
{
  "msg": "Debug ping sent",
  "event_id": "debug_ping_1699564800000",
  "ws_clients": 5,
  "queue_depth": 2
}
```

**Usage**:
```bash
# Terminal 1: Start backend
cd backend && uvicorn main:app --reload

# Terminal 2: Start frontend  
cd dashboard && npm run dev

# Terminal 3: Send debug ping
curl http://localhost:8000/api/debug/ping

# Terminal 4: Run full test suite
python scripts/test_event_flow.py
```

### Log Filtering

**Backend logs** (follow event_id):
```bash
# Worker emission
grep "\[EVENT_EMIT\]" backend.log

# Backend reception
grep "\[EVENT_RX_ACCEPT\]" backend.log

# Incident detected
grep "\[EVENT_INCIDENT_DETECTED\]" backend.log

# WebSocket broadcast
grep "\[WS_BROADCAST" backend.log
```

**Frontend logs** (open browser DevTools):
```javascript
// All WebSocket messages
console.log() in monitor.js

// AlertPopup display  
console.log() in monitor.js

// Look for [WS_*] tags in console
```

### Event Flow Checklist

- [ ] Worker has `BACKEND_URL` pointing to `/event` endpoint
- [ ] Backend running on `http://localhost:8000`
- [ ] Frontend WebSocket connects to `ws://localhost:8000/ws/alerts`
- [ ] Schema validation passes (no `[EVENT_SCHEMA_INVALID]` warnings)
- [ ] Events reach `[EVENT_INCIDENT_DETECTED]` (not suppressed as non-incidents)
- [ ] WebSocket broadcasts to all clients (`[WS_BROADCAST_START]` → `[WS_SEND_OK]`)
- [ ] Frontend receives and displays alerts (`[WS_MESSAGE_RX]` → `[ALERT_DISPLAYED]`)
- [ ] No errors in browser console or backend logs

---

## Configuration

### Worker Settings (`.env` or code)

```bash
BACKEND_URL=http://localhost:8000/event
COOLDOWN_WINDOW_SECONDS=10
EVENT_COOLDOWN_FRAMES_BEFORE_EMIT=5
CONFIDENCE_INCREASE_THRESHOLD=0.10
```

### Backend Settings

```bash
# No env vars required, all defaults in main.py
# alert_broadcast_queue processes async
# WebSocket timeout: implicit via asyncio operations
```

### Frontend Settings

```javascript
// monitor.js hardcoded:
const BACKEND_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/alerts';

// Reconnect interval: 3000ms
// No max reconnect attempts (infinite retry)
```

---

## Performance Considerations

1. **Event Cooldown**: Prevents 30fps camera from sending 30 events/sec
   - Default: 10s window per event_type per camera
   - Escalation: Breaks through cooldown if confidence increases >10%

2. **Async Processing**: Backend doesn't block on LLM summaries
   - `process_event()` runs sync in request handler
   - `trigger_alert()` may call LLM (slower but async-friendly)
   - WebSocket broadcast fully async

3. **WebSocket Scalability**:
   - Multiple clients get the same message copy
   - Failed sends don't block other clients
   - Dead connections removed automatically

4. **Memory**: 
   - `alerts_history` keeps last 100 alerts
   - `incidents` dict stores full incident records
   - Consider cleanup for production

---

## Troubleshooting

### No events reaching backend

**Check**:
1. Worker logs: Look for `[EVENT_EMIT]` with `endpoint=http://localhost:8000/event`
2. Network: Test with `curl -X POST http://localhost:8000/event -H "Content-Type: application/json" -d '{"event_id":"test"}'`
3. Backend: Check if `/event` handler is registered

### Events not showing in frontend

**Check**:
1. Browser console for `[WS_MESSAGE_RX]` logs
2. Backend logs for `[WS_SEND_OK]` or `[WS_SEND_FAIL]`
3. WebSocket URL: Must be `ws://` not `http://`
4. CORS: Verify no CORS errors in browser console

### Duplicate events on screen

**Check**:
1. Worker cooldown may be disabled
2. Frontend duplicate suppression logic in `monitor.js` line ~60-80
3. Same event_id or same event_type: Check `getAlertKey()` and `getEventType()` functions

### WebSocket keeps reconnecting

**Check**:
1. Backend crashes or hangs: Check `/event` endpoint for exceptions
2. Network issues: Try `debug/ping` endpoint
3. Browser: Clear console for old connection errors

---

## Success Indicators

✅ **All green when**:
- `[EVENT_EMIT]` → `[EVENT_DELIVERY_OK]` visible in worker logs (0-50ms latency)
- `[EVENT_RX_ACCEPT]` visible in backend logs (<10ms after emit)
- `[WS_BROADCAST_START]` → `[WS_BROADCAST_DONE]` visible in backend logs
- `[WS_MESSAGE_RX]` visible in browser console (<100ms after backend broadcast)
- AlertPopup appears in dashboard within 1-2 seconds of detection

---

**Last Updated**: November 2024  
**Project**: SentinelAI School Security Monitoring System  
**Status**: Event flow verified end-to-end with comprehensive logging
