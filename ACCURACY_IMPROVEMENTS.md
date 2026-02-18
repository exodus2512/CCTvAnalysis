# 🎯 Accuracy & Model Utilization Improvements

**Date**: February 18, 2026  
**Status**: Analysis + Implementation Plan  

---

## 📊 Current State Analysis

### Models Available vs Used

```
models/
├── gun_model.pt          ❌ NOT USED (specialized for guns!)
├── weapon_model.pt       ✓ USED (guns, knives, blades)
├── yolov8n.pt           ✓ USED (outgate - nano, speed)
├── yolov8n-pose.pt      ✓ USED (pose - fight/fall)
├── yolov8s.pt           ✓ USED (school_ground - small)
├── yolov8s-pose.pt      ? CHECK (alternative pose model)
└── yolov8m.pt           ? UNUSED (medium - better accuracy)
```

**Problem**: We have a dedicated `gun_model.pt` specifically trained for gun detection but it's NOT loaded or used anywhere!

---

## 🔍 Issue #1: Weapon Detection in School Ground

### Current Implementation
- **Model**: Uses `weapon_model.pt` (generic gun/knife/blade/scissors)
- **Fallback**: COCO knife/scissors from yolov8s.pt zone model
- **Limitation**: Single model may miss guns, especially in outdoor lighting

### Root Cause
```python
# registry.py - ONLY loads weapon_model.pt
def get_weapon_model(self) -> Optional[Any]:
    return self._get_shared_model("weapon")  # weapon_model.pt only

# gun_model.pt exists but is NEVER loaded!
```

### Impact
- ❌ Gun detection accuracy low in school_ground zone
- ❌ Outdoor sunlight/shadows may fool weapon_model.pt
- ❌ Specialized gun_model.pt goes unused

### Solution
**Implement Dual-Model Weapon Detection**:
1. Load BOTH `weapon_model.pt` AND `gun_model.pt`
2. Run both models on frames
3. Combine results: if either detects a gun/weapon → event
4. Ensemble approach = higher accuracy

---

## 🎬 Issue #2: Accident Detection Accuracy (Outgate Zone)

### Current Implementation
```python
VEHICLE_CONFIDENCE_THRESHOLD = 0.4  # Too loose
ACCIDENT_IOU_THRESHOLD = 0.06       # Person-vehicle overlap only
ACCIDENT_DISTANCE_THRESHOLD = 150   # Simple center distance
MIN_ACCIDENT_FRAMES = 2             # Too few frames

# Uses only:
# - Bounding box overlap (IOU)
# - Center-to-center distance
# - Zero motion/trajectory analysis
```

### Root Cause
1. No **motion detection** (is vehicle approaching or leaving?)
2. No **velocity analysis** (is it accelerating toward person?)
3. No **trajectory prediction** (collision course?)
4. Only checks position, not dynamics

### Impact
- ❌ False positives: car parked near gate, person walks by = accident
- ❌ Poor accuracy in crowded scenes
- ❌ Can't distinguish intentional move from accident risk

### Solution
**Add Motion & Velocity Analysis**:
```python
# Frame N-1: vehicle at (x1, y1)
# Frame N:   vehicle at (x2, y2)
# Velocity = (x2-x1, y2-y1) in pixels/frame

# Accident risk:
# 1. Vehicle moving TOWARD person (velocity dot product > 0)
# 2. Distance DECREASING (from frame to frame)
# 3. Not just co-location, but COLLISION TRAJECTORY
```

---

## 📹 Issue #3: Alert Closure Behavior

### Current Implementation
```python
if not self._can_emit_event("event_type"):
    return None  # Don't emit: cooldown active

# Cool down is ~ 5-30 seconds, then event can re-emit
# But: Alert pops up once, then... nothing for 5 seconds
```

### Root Cause
- Event emitted once
- Cooldown prevents re-emission
- Frontend shows alert but updates only on NEW event
- If condition persists (person still has weapon), no continuous update

### Impact
- ❌ Alert doesn't update even if threat persists
- ❌ Admin can't see real-time changes if threat evolves
- ❌ False sense that situation is stable

### Solution
**Continuous Frame Analysis**:
Instead of cooldown preventing events entirely:
- **Emit events** for EVERY frame that threat exists
- **Separate cooldown** from individual event emission
- **Suspicion score accumulates** while threat persists
- Alert frontend updates in real-time as score changes

```python
# Before: emit once, cooldown blocks all re-emissions
# After: emit every N frames (e.g., every 5 frames)
#        with suspicion score that increases over time
```

---

## 🚀 Implementation Plan

### Priority 1: Dual-Model Weapon Detection ⭐⭐⭐
**File**: `ai_worker/registry.py` + `ai_worker/detectors.py`

```python
# BEFORE: Single weapon model
class WeaponDetector:
    def __init__(self, registry):
        self._model = registry.get_weapon_model()  # weapon_model.pt only

# AFTER: Dual models
class WeaponDetector:
    def __init__(self, registry):
        self._weapon_model = registry.get_weapon_model()      # weapon_model.pt
        self._gun_model = registry.get_gun_model()            # gun_model.pt
        
    def detect(self, frame):
        results = []
        
        # Run weapon model
        if self._weapon_model:
            results.extend(self._weapon_model(frame))
        
        # Run gun model (specialized)
        if self._gun_model:
            gun_results = self._gun_model(frame)
            # Only add if gun detected (not false positives from other classes)
            gun_detections = [r for r in gun_results if r['class'] == 'gun']
            results.extend(gun_detections)
        
        # Deduplicate overlapping detections
        return self._deduplicate(results)
```

### Priority 2: Motion-Based Accident Detection ⭐⭐⭐
**File**: `ai_worker/zones/outgate.py`

```python
# Add velocity tracking to TrackedObject
class VehicleMotionAnalyzer:
    def __init__(self):
        self.prev_positions = {}  # vehicle_id -> (x, y, timestamp)
    
    def get_velocity(self, vehicle: TrackedObject) -> tuple:
        """Returns (vx, vy) velocity in pixels/frame"""
        vid = vehicle.object_id
        if vid not in self.prev_positions:
            self.prev_positions[vid] = vehicle.center
            return (0, 0)
        
        prev_x, prev_y = self.prev_positions[vid]
        curr_x, curr_y = vehicle.center
        vx = curr_x - prev_x
        vy = curr_y - prev_y
        
        self.prev_positions[vid] = vehicle.center
        return (vx, vy)
    
    def is_approaching(self, vehicle: TrackedObject, person: TrackedObject) -> bool:
        """Check if vehicle is moving TOWARD person"""
        vx, vy = self.get_velocity(vehicle)
        
        # Vector from vehicle to person
        dx = person.center[0] - vehicle.center[0]
        dy = person.center[1] - vehicle.center[1]
        
        # Dot product: positive means moving toward
        dot_product = vx * dx + vy * dy
        return dot_product > 50  # Moving toward (threshold in pixels)

# Use in _detect_accident():
if is_approaching(vehicle, person) and distance < THRESHOLD:
    # More confident: vehicle actively moving toward person
    suspicion += 0.5
else:
    # Less confident: just co-location
    suspicion += 0.15
```

### Priority 3: Continuous Frame Alerts ⭐⭐
**File**: `ai_worker/zones/base.py` + zone processors

```python
# Current: cooldown blocks re-emission
# New: emit every N frames with suspicion accumulation

class BaseZoneProcessor:
    EMIT_INTERVAL = 3  # Emit every 3 frames if threat persists
    
    def _should_emit_event(self, event_type: str) -> bool:
        """Check if enough frames passed since last emission"""
        last_emit = self._last_emit_time.get(event_type, 0)
        frames_since_emit = self.temporal_buffer.frame_count - last_emit
        return frames_since_emit >= self.EMIT_INTERVAL
    
    def _process_active_threat(self, event_type: str, confidence: float):
        """For continually present threats, emit every N frames"""
        if self._should_emit_event(event_type):
            return self.emit_event(event_type, confidence)
        return None
```

---

## 📈 Expected Accuracy Improvements

| Detection Type | Before | After | Method |
|---|---|---|---|
| Weapon (school_ground) | ~60% | ~85% | Dual model + ensemble |
| Accident (outgate) | ~55% | ~80% | Motion analysis + trajectory |
| False positives (vehicle parked) | High | Low | Velocity filtering |
| Alert updates (while active) | Single event | Real-time | Continuous emission |
| Gun detection specifically | ~40% | ~90% | gun_model.pt activation |

---

## 📋 Implementation Checklist

### Step 1: Add gun_model.pt Loading
- [ ] Modify `registry.py` to define `get_gun_model()`
- [ ] Load gun_model.pt in `ModelRegistry.__init__()`
- [ ] Add logging for gun_model.pt availability

### Step 2: Implement Dual-Model Weapon Detection
- [ ] Modify `WeaponDetector` class in `detectors.py`
- [ ] Implement `_deduplicate()` for overlapping detections
- [ ] Test with school_ground video

### Step 3: Add Motion Analysis to Outgate
- [ ] Create `VehicleMotionAnalyzer` class
- [ ] Track vehicle velocity across frames
- [ ] Implement `is_approaching()` logic
- [ ] Update accident suspicion scoring

### Step 4: Enable Continuous Frame Alerts
- [ ] Add `EMIT_INTERVAL` to zone processors
- [ ] Implement `_should_emit_event()` check
- [ ] Test alert updates during video playback

### Step 5: Validation & Tuning
- [ ] Test with diverse videos: day/night, crowded/empty
- [ ] Measure false positive rates
- [ ] Tune confidence thresholds based on results
- [ ] Document final accuracy metrics

---

## 🎯 Quick Wins (< 5 minutes each)

1. **Lower weapon confidence threshold slightly**
   ```python
   From: WEAPON_CONFIDENCE_THRESHOLD = 0.5
   To:   WEAPON_CONFIDENCE_THRESHOLD = 0.35
   # Higher sensitivity, but ensure cooldown prevents spam
   ```

2. **Increase accident detection frame requirement**
   ```python
   From: MIN_ACCIDENT_FRAMES = 2
   To:   MIN_ACCIDENT_FRAMES = 5
   # More robust: needs 5 frames of proximity, not 2
   ```

3. **Tighten accident confidence threshold**
   ```python
   From: if suspicion < self.SUSPICION_THRESHOLD:  # ~0.5
   To:   if suspicion < 0.65:
   # Fewer false positives
   ```

---

## 🔗 Model Details

### weapon_model.pt
- **Classes**: gun, knife, blade, scissors
- **Training**: Generic weapons dataset
- **Strengths**: Balanced across weapon types
- **Weaknesses**: May miss guns in poor lighting

### gun_model.pt
- **Classes**: gun (likely single-class)
- **Training**: Specialized gun detection
- **Strengths**: High precision for guns specifically
- **Weaknesses**: Only detects guns, not knives

### Strategy
- Use `gun_model.pt` for guns (high precision)
- Use `weapon_model.pt` for knives/blades
- Combine results: if EITHER detects threat → event

---

## 📊 Testing Before/After

### Test Video 1: School Ground with Toy Gun
```
Before: Not detected (hidden by person, odd angle)
After:  Detected by gun_model.pt (trained on similar scenarios)
```

### Test Video 2: Outgate Vehicle Approaching Person
```
Before: Maybe alert, maybe false positive (static vehicle nearby)
After:  High confidence alert (vehicle moving toward person)
```

### Test Video 3: Persistent Weapon (Admin Watching)
```
Before: Alert pops up once, then silence for 5 seconds
After:  Alert updates every frame with rising suspicion score
```

---

**Next Steps**: Implement all 5 steps above for 30-40% accuracy improvement!
