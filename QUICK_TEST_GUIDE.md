# 🚀 Quick Event Flow Testing Guide

**Purpose**: Verify that events are properly flowing through detection → broadcast → rendering  
**Expected Time**: 10 minutes

---

## Setup (All in Separate Terminals)

### Terminal 1: Start Backend
```bash
cd c:\Users\joshua moses\SecVidA\backend
uvicorn main:app --reload --port 8000
```

**Success indicators**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Terminal 2: Start Frontend
```bash
cd c:\Users\joshua moses\SecVidA\dashboard
npm run dev
```

**Success indicators**:
```
ready - started server on 0.0.0.0:3000, url: http://localhost:3000
```

### Terminal 3: Open Browser DevTools
```
1. Go to http://localhost:3000
2. Press F12 (or Right-click → Inspect)
3. Click "Console" tab
4. Clear console (Ctrl+L)
```

---

## Test 1: Send Debug Ping Event (30 seconds)

### In Terminal 4:
```bash
curl http://localhost:8000/api/debug/ping
```

### Monitor These Outputs:

#### Backend Terminal (Terminal 1)
**Should see**:
```
[WS_PAYLOAD_DEBUG] Sending to 1 clients: id=evt_... has_event=True has_alert=True
```

If you DON'T see this:
- ❌ Backend not broadcasting (check error logs)
- ❌ Event not created (check POST /event handler)

#### Frontend Console (F12)
**Should see in order**:
```
[WS_RAW_MESSAGE] {"id":"evt_pinged_20250218_..." ...}
[WS_PAYLOAD_STRUCTURE] {has_id: true, has_alert: true, has_event: true, ...}
[WS_EXTRACTED_FIELDS] {incident_id: "evt_...", cameraId: "debug", ...}
[INCIDENT_MERGE] {incident_id: "evt_...", event_type: "debug_ping", ...}
[INCIDENT_ADDED_TO_LIST] evt_pinged_20250218_...
[INCIDENT_DUPLICATE_IN_LIST] evt_pinged_20250218_... (second ping)
```

If MISSING:
- `[WS_RAW_MESSAGE]` only? WebSocket connected but handler broken
- ALL missing? WebSocket not connected (check backend for active connections)

#### Frontend UI (http://localhost:3000)
**Should see**:
1. Click "Incidents" tab (red icon)
2. Top of the incident list shows new event
3. Card displays: `debug_ping` | `debug` zone | timestamp
4. Expand "🔧 DEBUG: Raw Incident JSON" → shows your event in JSON

If MISSING:
- Event in console but not in UI? IncidentList component rendering broken
- Event in debug JSON but not in card? IncidentList filtering issue

---

## Test 2: Real Worker Detection (2-3 minutes)

### In Terminal 4:
```bash
cd c:\Users\joshua moses\SecVidA\ai_worker
python test_worker.py school_ground ..\test_videos\school\demo.mp4
```

### Monitor These Outputs:

#### Backend Terminal (Terminal 1)
**Should see multiple**: `[WS_PAYLOAD_DEBUG]` messages as events detected

**Example**:
```
[WS_PAYLOAD_DEBUG] Sending to 1 clients: id=evt_person_detected_... has_event=True has_alert=True
[WS_PAYLOAD_DEBUG] Sending to 1 clients: id=evt_crowd_formation_... has_event=True has_alert=True
```

#### Frontend Console (F12)
**Should see events flowing in real-time**:
```
[WS_RAW_MESSAGE] ...
[WS_PAYLOAD_STRUCTURE] ...
[INCIDENT_ADDED_TO_LIST] evt_person_detected_...
[INCIDENT_ADDED_TO_LIST] evt_crowd_formation_...
[INCIDENT_ADDED_TO_LIST] evt_running_detected_...
```

#### Frontend UI
**Should see**:
1. Incidents tab shows new events appearing in real-time
2. Events listed from newest to oldest
3. Each card shows: event_type | zone | camera | timestamp | priority badge
4. Scroll to "🔧 DEBUG: Raw Incident JSON" → matches UI cards

---

## Expected Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND                                                          │
├─────────────────────────────────────────────────────────────────┤
│ POST /event (from worker)                                       │
│   ↓                                                              │
│ Event engine processes                                           │
│   ↓                                                              │
│ [WS_PAYLOAD_DEBUG] ← ← ← ← ← ← MONITOR THIS IN LOGS            │
│   ↓                                                              │
│ WebSocket broadcast to all clients                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ {"id": "evt_...", "event": {...}, "alert": {...}}
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ FRONTEND (Browser)                                               │
├─────────────────────────────────────────────────────────────────┤
│ ws.onmessage()                                                  │
│   ↓                                                              │
│ [WS_RAW_MESSAGE] ← ← ← ← MONITOR IN CONSOLE (F12)             │
│   ↓                                                              │
│ JSON.parse()                                                    │
│   ↓                                                              │
│ [WS_PAYLOAD_STRUCTURE] validate schema                          │
│   ↓                                                              │
│ Build incident_obj = {id, event, alert}                        │
│   ↓                                                              │
│ [INCIDENT_ADDED_TO_LIST] ← ← ← KEY VALIDATION POINT           │
│   ↓                                                              │
│ setIncidentList() add to state                                  │
│   ↓                                                              │
│ IncidentList component renders <IncidentCard/>                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                      VISIBLE IN UI
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ USER SEES (http://localhost:3000)                               │
├─────────────────────────────────────────────────────────────────┤
│ [Incidents Tab]                                                 │
│ ┌─────────────────────────────────────────────────┐            │
│ │ weapon_detected | school_ground | cam1          │            │
│ │ ⚠️ CRITICAL | 2:34:56 PM                        │            │
│ └─────────────────────────────────────────────────┘            │
│ ┌─────────────────────────────────────────────────┐            │
│ │ crowd_formation | corridor | cam3               │            │
│ │ 🔴 HIGH | 2:34:45 PM                            │            │
│ └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✅ Validation Checklist

### After first `curl` debug ping:
- [ ] Backend shows `[WS_PAYLOAD_DEBUG]` (proves broadcasting)
- [ ] Frontend console shows 6+ `[WS_...]` logs (proves receiving)
- [ ] Frontend UI shows incident in timeline (proves rendering)
- [ ] Debug JSON panel shows incident (proves state has data)

**If ANY checkbox fails**:
1. Copy exact error message from terminal
2. Check corresponding section in FRONTEND_DEBUG_FIX.md
3. Verify the associated code change was applied

### After `python test_worker.py`:
- [ ] Multiple `[WS_PAYLOAD_DEBUG]` logs in backend
- [ ] Multiple incidents flowing in console (real-time)
- [ ] Each incident appears immediately in UI (no delay)
- [ ] Incidents stay in list (not replaced by polling)
- [ ] API sync logs appear every 5 seconds: `[API_SYNC]`

**If incidents disappear after 5 seconds**:
- API polling is replacing WebSocket data (FIXED code wasn't deployed)
- Check line 207-248 in `dashboard/pages/monitor.js` for merge logic

---

## Logs to Monitor

### Backend Log Pattern
```bash
# Every event dispatched
[EVENT_RECEIVED] id=evt_... type=weapon_detected zone=school_ground
[COOLDOWN_CHECK] camera=cam1 zone=school_ground passed=true
[ALERT_CREATED] priority=critical
[WS_PAYLOAD_DEBUG] Sending to 1 clients: id=evt_... ✓THIS IS KEY
```

### Frontend Log Pattern
```javascript
// Every WebSocket message received
[WS_RAW_MESSAGE] {"id":"evt_pinged_..."...}
[WS_PAYLOAD_STRUCTURE] {has_id: true, has_event: true, has_alert: true}
[WS_EXTRACTED_FIELDS] {incident_id: "evt_...", cameraId: "cam1"}
[INCIDENT_MERGE] {incident_id: "evt_...", event_type: "weapon_detected"}

// Updates to incident list
[INCIDENT_ADDED_TO_LIST] evt_pinged_20250218_... ✓THIS IS KEY
[API_SYNC] {api_count: 5, current_count: 6} (happens every 5s)
```

---

## Common Issues & Solutions

### ❌ No backend `[WS_PAYLOAD_DEBUG]` logs
**Problem**: Event not being broadcast  
**Fix**:
1. Verify event was received: Check for `[EVENT_RECEIVED]` logs above it
2. Check for errors in event engine: Look for `[⚠️ ERROR]` messages
3. Verify WebSocket client connected: Should see connection log when frontend opens

### ❌ Console has `[WS_RAW_MESSAGE]` but no `[INCIDENT_ADDED_TO_LIST]`
**Problem**: WebSocket message received but not added to state  
**Fix**:
1. Check for JavaScript errors in console (red `X` messages)
2. Verify code change was applied (check line 153-168 in monitor.js)
3. Look for `[WS_EXTRACTED_FIELDS]` - if present, state update function has error

### ❌ Events in console & debug JSON but NOT in IncidentList cards
**Problem**: Data in state but component not rendering  
**Fix**:
1. Check IncidentList component (dashboard/components/IncidentList.js)
2. Verify incident structure: id, event, alert (not null/undefined)
3. Check for filtering logic that might hide events

### ❌ Events disappear after 5 seconds
**Problem**: API polling replaces real-time data  
**Fix**:
1. Check line 207-248 in monitor.js for smart merge logic
2. Verify latest code has `.set()` and `.Map()` usage
3. Check `[API_SYNC]` logs - should show both api_count and current_count

---

## Performance Expectations

| Metric | Expected | Max Acceptable |
|--------|----------|-----------------|
| Event → Backend log | < 50ms | 500ms |
| Backend → WS broadcast | < 10ms | 100ms |
| WebSocket → Console log | < 100ms | 500ms |
| Console → UI render | < 200ms | 1000ms |
| **Total latency** | **< 360ms** | **~2000ms** |

---

## After Verification Passes ✅

If all tests pass:
1. Your frontend event rendering is FIXED
2. You can now deploy to production
3. Remove debug `console.log()` statements if desired (optional)
4. Monitor `[WS_PAYLOAD_DEBUG]` in production for health checks

If any test fails:
1. Document the failure
2. Check corresponding troubleshooting section
3. Run again with fresh browser tab (Ctrl+Shift+Delete cache)

---

**Next Step**: Execute Test 1 and report results in console!
