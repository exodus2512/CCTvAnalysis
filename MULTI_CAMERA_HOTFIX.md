# Multi-Camera Detection Hotfix

## Problem Summary
When running **more than 2 camera feeds** with zone-specific models, detection would fail and "accident" events would flood excessively. This was reported as:
> "if i run those separate zone models on more than two video feed. it is not detecting and the accident is flooding and not working properly"

## Root Cause Analysis
The detection pipeline had a **double-gating issue** with misaligned cooldown logic:

### Zone-Level Cooldown (Broken Loop)
Each zone processor tracks last emission time per event type (`_last_event_times`), but had **no frame-level guard**. This caused:

```python
Frame 1: suspicion = 0.4 (below 0.6 threshold) → no emit
Frame 2: suspicion = 0.55 (below 0.6 threshold) → no emit  
Frame 3: suspicion = 0.7 (ABOVE threshold) → EMIT + RESET
Frame 4: suspicion = 0.4 again → IMMEDIATELY begins accumulating...
Frame 5: suspicion = 0.55 → still below threshold
Frame 6: suspicion = 0.7 → EMIT again (if 8-second cooldown expired)
```

### Multi-Camera Parallelism
With >2 cameras:
- Each camera worker runs in a separate thread
- Each zone processor has its own `_last_event_times` dictionary
- Cooldown accumulation happens in parallel, leading to saturated output
- Event flooding occurs while global `EventCooldownManager` struggles to filter duplicates

## Solution Implemented

### Frame-Level Cooldown Guards
Added **early-return cooldown checks** at the start of each detection method, **before suspicion accumulation**:

```python
def _detect_accident(self, vehicles, persons, poses=None):
    # FRAME-LEVEL COOLDOWN: Prevent re-triggering within cooldown window
    if not self._can_emit_event("gate_accident"):
        self._update_suspicion("gate_accident", False)  # Decay suspicion during cooldown
        return None
    
    # ... rest of detection logic ...
```

This ensures:
1. **No suspicion accumulation** during cooldown window (suspicion decays instead)
2. **Clean separation**: Cooldown gate before all detection work
3. **Per-event-type enforcement**: Each event type respects its cooldown (5-10 seconds)

### Files Modified
All zone processors updated with frame-level cooldown checks:

| File | Methods Updated | Events Protected |
|------|-----------------|-----------------|
| `backend/zones/outgate.py` | `_detect_vehicle()`, `_detect_accident()` | vehicle_detected (5s), gate_accident (8s) |
| `backend/zones/corridor.py` | `_detect_crowd()`, `_detect_fight()` | crowd_formation (6s), fight (8s) |
| `backend/zones/school_ground.py` | `_detect_crowd()`, `_detect_fight()`, `_detect_fall()` | crowd_formation (6s), fight (8s), fall_detected (6s) |
| `backend/zones/classroom.py` | `_detect_mobile_usage()`, `_detect_fight()` | mobile_usage (4s), fight (8s) |

## Event Cooldown Schedule
Enforced via per-event-type durations in `base.py`:

```python
_event_cooldowns = {
    "weapon_detected": 10.0,      # Serious event
    "fight": 8.0,                 # Moderate
    "gate_accident": 8.0,         # Moderate
    "vehicle_detected": 5.0,      # Frequent
    "crowd_formation": 6.0,       # Moderate
    "fire_smoke_detected": 10.0,  # Serious
    "mobile_usage": 4.0,          # Frequent
    "fall_detected": 6.0,         # Moderate
}
```

## Expected Improvements

✅ **Multi-camera support**: 3+ feeds can now run simultaneously without detection saturation  
✅ **Reduced event flooding**: Accident events respect cooldown between emissions  
✅ **Cleaner suspicion tracking**: Suspicion decays during cooldown instead of accumulating to re-trigger  
✅ **Per-event-type enforcement**: Each event type obeys its appropriate cooldown period  

## Testing Instructions

1. **Start backend:**
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

2. **Configure 3+ cameras** in the dashboard (SetupWizard)

3. **Start detection worker:**
   ```bash
   cd backend/worker
   python worker.py
   ```

4. **Monitor logs:**
   ```bash
   # Look for:
   # [EVENT_PASS_COOLDOWN] → Event emitted within expected cooldown window
   # [EVENT_SUPPRESSED] → Duplicate event blocked
   # [WORKER_STATS] → Frame counts, event totals per camera
   ```

5. **Verify detection:**
   - Vehicle crossing in outgate zone → single "vehicle_detected" every 5 seconds
   - Crowd gathering in corridor → single "crowd_formation" every 6 seconds
   - Fight scenario in school_ground → single "fight" every 8 seconds

## Rollback Instructions
If issues arise, the changes are minimal and isolated:
1. Remove the `if not self._can_emit_event()` checks from each detection method
2. The rest of the detection logic is unchanged
3. Zone processors will revert to previous behavior (may re-trigger)

## Performance Impact
- **Minimal**: Early returns save suspicion calculation cycles during cooldown
- **Positive**: Fewer events processed = lower backend load, cleaner dashboard
- **No inference overhead**: YOLO models still run at same speed

## Future Improvements
1. **Adaptive cooldowns**: Adjust cooldown based on confidence scores
2. **Per-zone cooldown customization**: Different zones might need different intervals
3. **Event batching**: Group related events within cooldown window for better context
4. **Cooldown metrics**: Export cooldown stats to WebSocket for dashboard monitoring
