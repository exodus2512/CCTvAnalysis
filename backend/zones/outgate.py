"""
Outgate Zone Processor — Vehicle detection and gate accidents.

Events:
- vehicle_detected: Vehicle (car/bus/truck/motorcycle) in gate area
- gate_accident:    Vehicle-person collision/impact incident

Accident Detection Pipeline (4-stage):
  Stage 1 — Velocity:     speed = dist(curr, prev) / dt
  Stage 2 — Direction:    dot(velocity, vehicle→person) > 0 → approaching
  Stage 3 — Proximity:    dist(vehicle, person) < threshold
  Stage 4 — IoU/Overlap:  IoU(vehicle_box, person_box) > 0.3
  Bonus   — Sudden Stop:  speed_prev >> speed_curr while near person → impact

Temporal confirmation requires ALL of:
  • At least MIN_ACCIDENT_FRAMES consecutive qualifying frames
  • Suspicion score above SUSPICION_THRESHOLD
  • Both vehicle AND person tracked (not single-frame phantom)
"""

import time
import logging
import numpy as np
from collections import deque
from typing import List, Dict, Tuple, Optional
from .base import (
    BaseZoneProcessor,
    TrackedObject,
    FrameMetadata,
    DetectionEvent,
)

VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Vehicle Motion Analyzer — full physics-based tracker
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class VehicleMotionAnalyzer:
    """
    Per-vehicle motion tracker with velocity history, direction vector,
    and sudden-stop detection.

    Stores a sliding window of recent positions+timestamps per track ID
    so we can compute instantaneous velocity AND detect deceleration.
    """

    HISTORY_LEN = 8          # frames of position history to keep
    MIN_SPEED_PX = 2.0       # px/frame — below this the vehicle is "stationary"
    SUDDEN_STOP_RATIO = 0.25 # speed_curr / speed_prev < this → sudden stop

    def __init__(self):
        # track_id → deque of (center_x, center_y, timestamp)
        self._history: Dict[int, deque] = {}

    # ── public API ──────────────────────────────────────────────────

    def update(self, vehicle: TrackedObject, timestamp: float):
        """Record the vehicle's current position. Call once per frame per vehicle."""
        vid = vehicle.object_id
        if vid not in self._history:
            self._history[vid] = deque(maxlen=self.HISTORY_LEN)
        self._history[vid].append((*vehicle.center, timestamp))

    def get_velocity_vector(self, vid: int) -> Tuple[float, float]:
        """Return (vx, vy) in px/frame between last two observations."""
        hist = self._history.get(vid)
        if not hist or len(hist) < 2:
            return (0.0, 0.0)
        x1, y1, _ = hist[-2]
        x2, y2, _ = hist[-1]
        return (float(x2 - x1), float(y2 - y1))

    def get_speed(self, vid: int) -> float:
        """Scalar speed in px/frame."""
        vx, vy = self.get_velocity_vector(vid)
        return float(np.hypot(vx, vy))

    def get_speed_over_time(self, vid: int) -> float:
        """Speed in px/second using timestamps (more robust across variable FPS)."""
        hist = self._history.get(vid)
        if not hist or len(hist) < 2:
            return 0.0
        x1, y1, t1 = hist[-2]
        x2, y2, t2 = hist[-1]
        dt = t2 - t1
        if dt <= 0:
            return 0.0
        return float(np.hypot(x2 - x1, y2 - y1) / dt)

    def is_approaching(self, vid: int, person: TrackedObject) -> bool:
        """
        Stage 2 — Direction check.
        True if the vehicle's velocity vector points toward the person
        (dot product of velocity and vehicle→person vector is positive).
        """
        vx, vy = self.get_velocity_vector(vid)
        speed = np.hypot(vx, vy)
        if speed < self.MIN_SPEED_PX:
            return False

        hist = self._history.get(vid)
        if not hist:
            return False
        veh_x, veh_y, _ = hist[-1]
        px, py = person.center

        # Direction FROM vehicle TO person
        dx = float(px - veh_x)
        dy = float(py - veh_y)

        # Normalize dot product by magnitudes → cos(angle)
        dist_to_person = np.hypot(dx, dy)
        if dist_to_person < 1.0:
            return True  # Already overlapping
        cos_angle = (vx * dx + vy * dy) / (speed * dist_to_person)
        # cos > 0.3 ≈ within ±72° cone toward person
        return cos_angle > 0.3

    def is_sudden_stop(self, vid: int) -> bool:
        """
        Stage 4 bonus — Sudden Stop detection.
        True if a vehicle that was moving fast has abruptly decelerated
        (speed ratio drops below SUDDEN_STOP_RATIO).
        Indicates a possible impact/collision.
        """
        hist = self._history.get(vid)
        if not hist or len(hist) < 3:
            return False

        # Compute speeds for last 3 data-points
        speeds = []
        pts = list(hist)
        for i in range(1, len(pts)):
            dx = pts[i][0] - pts[i - 1][0]
            dy = pts[i][1] - pts[i - 1][1]
            speeds.append(float(np.hypot(dx, dy)))

        if len(speeds) < 2:
            return False

        prev_speed = max(speeds[:-1])   # peak recent speed
        curr_speed = speeds[-1]         # current speed

        if prev_speed < 5.0:
            return False  # Was never moving fast enough to matter

        ratio = curr_speed / prev_speed if prev_speed > 0 else 1.0
        return ratio < self.SUDDEN_STOP_RATIO

    def cleanup(self, active_ids: List[int]):
        """Remove history for vehicles no longer being tracked."""
        lost = [vid for vid in self._history if vid not in active_ids]
        for vid in lost:
            del self._history[vid]

    def has_track(self, vid: int) -> bool:
        """True if vehicle has at least 2 frames of track data (properly tracked)."""
        hist = self._history.get(vid)
        return hist is not None and len(hist) >= 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Outgate Zone Processor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class OutgateProcessor(BaseZoneProcessor):
    """
    Outgate zone processor for vehicle and accident detection.

    Uses yolov8n.pt (speed priority for real-time vehicle tracking).

    gate_accident 4-stage pipeline:
      1. Velocity       — is vehicle moving?
      2. Direction       — toward person?
      3. Proximity       — close enough?
      4. IoU + Overlap   — bounding boxes overlapping?
      Bonus: Sudden Stop — high speed → near-zero while near person
    """

    ZONE_NAME = "outgate"
    EVENT_TYPES = ["vehicle_detected", "gate_accident"]
    MODEL_NAME = "yolov8n.pt"

    # ── Vehicle detection thresholds ──
    VEHICLE_CONFIDENCE_THRESHOLD = 0.45

    # ── Accident detection thresholds ──
    # Calibrated for real CCTV footage (wide-angle street cameras)
    #
    # Stage 3 — Proximity (center-to-center distance in pixels)
    ACCIDENT_PROXIMITY_THRESHOLD = 200     # Wide-angle CCTV: objects appear smaller
    ACCIDENT_CLOSE_PROXIMITY = 100         # Very close — high danger zone
    #
    # Stage 4 — IoU overlap
    # Real-world: car near person/motorcycle typically yields IoU 0.05-0.20
    # Only a direct hit/run-over reaches IoU > 0.25
    ACCIDENT_IOU_THRESHOLD = 0.15          # IoU > 0.15 = strong overlap signal
    ACCIDENT_IOU_SOFT_THRESHOLD = 0.05     # IoU 0.05-0.15 = partial overlap
    #
    # Temporal confirmation
    MIN_ACCIDENT_FRAMES = 3                # 3 consecutive qualifying frames
    MIN_VEHICLE_TRACK_FRAMES = 2           # Vehicle must be tracked for >=2 frames
    #
    # Suspicion increments (per qualifying frame)
    SUSPICION_INCREMENT_STRONG = 0.30      # IoU > 0.15 OR sudden-stop near person
    SUSPICION_INCREMENT_MODERATE = 0.18    # Approaching + proximate OR soft IoU + motion
    SUSPICION_INCREMENT_WEAK = 0.08        # Approaching only OR proximity + soft overlap

    def __init__(self, camera_id: str):
        super().__init__(camera_id)
        self._accident_frame_count = 0
        self._motion_analyzer = VehicleMotionAnalyzer()
        self._prev_poses: Dict[int, List[List[float]]] = {}

        # Track vehicle presence for post-impact detection
        self._last_vehicle_time: float = 0.0
        self._last_vehicle_ids: List[int] = []
        self._VEHICLE_MEMORY_SECONDS: float = 2.0
    
    def process_frame(
        self,
        frame: np.ndarray,
        tracked_objects: List[TrackedObject],
        metadata: FrameMetadata,
        shared_detections: Dict[str, list] = None,
    ) -> List[DetectionEvent]:
        """Process frame for outgate zone events."""
        self.temporal_buffer.add_frame(tracked_objects, metadata.timestamp)

        vehicles = [o for o in tracked_objects if o.class_name in VEHICLE_CLASSES]
        persons  = [o for o in tracked_objects if o.class_name == "person"]
        poses    = (shared_detections or {}).get("poses", [])

        # ── Update motion tracker for every vehicle FIRST ──
        for v in vehicles:
            self._motion_analyzer.update(v, metadata.timestamp)
        active_ids = [v.object_id for v in vehicles]
        self._motion_analyzer.cleanup(active_ids)

        events: List[DetectionEvent] = []

        # 1. Vehicle Detection
        ve = self._detect_vehicle(vehicles)
        if ve:
            events.append(ve)

        # 2. Gate Accident (4-stage pipeline)
        ae = self._detect_accident(vehicles, persons, poses, metadata)
        if ae:
            events.append(ae)

        # Update pose history for next frame
        self._update_pose_history(poses)

        return events
    
    def _detect_vehicle(self, vehicles: List[TrackedObject]) -> Optional[DetectionEvent]:
        """Detect vehicles in gate area with frame-level cooldown."""
        if not self._can_emit_event("vehicle_detected"):
            self._update_suspicion("vehicle_detected", False)
            return None

        if not vehicles:
            self._update_suspicion("vehicle_detected", False)
            return None

        confident = [v for v in vehicles if v.confidence >= self.VEHICLE_CONFIDENCE_THRESHOLD]
        if not confident:
            self._update_suspicion("vehicle_detected", False)
            return None

        suspicion = self._update_suspicion("vehicle_detected", True, increment=0.20)
        frame_count = self.temporal_buffer.increment_event("vehicle_detected")

        if frame_count < 2 or suspicion < 0.4:
            return None

        best = max(confident, key=lambda v: v.confidence)
        self._mark_event_emitted("vehicle_detected")
        self.temporal_buffer.reset_event("vehicle_detected")

        return DetectionEvent(
            event_type="vehicle_detected",
            confidence=best.confidence,
            bounding_boxes=[v.bbox for v in confident[:5]],
            metadata={
                "vehicle_count": len(confident),
                "vehicle_ids": [v.object_id for v in confident[:5]],
            },
        )

    # ────────────────────────────────────────────────────────────────
    #  4-Stage Accident Detection Pipeline
    # ────────────────────────────────────────────────────────────────

    def _detect_accident(
        self,
        vehicles: List[TrackedObject],
        persons: List[TrackedObject],
        poses: List[Dict] = None,
        metadata: FrameMetadata = None,
    ) -> Optional[DetectionEvent]:
        """
        Gate accident detection with strict 4-stage verification.

        Stage 1 — Velocity:     Is the vehicle moving?
        Stage 2 — Direction:    Is it heading toward a person?
        Stage 3 — Proximity:    Are vehicle & person close?
        Stage 4 — IoU/Overlap:  Do their bounding boxes overlap?
        Bonus   — Sudden Stop:  Did the vehicle abruptly decelerate near a person?

        Mitigations against false positives:
        • Vehicle must be tracked for ≥ MIN_VEHICLE_TRACK_FRAMES (not a phantom)
        • Person must be detected in the SAME frame as the vehicle
        • Needs MIN_ACCIDENT_FRAMES consecutive qualifying frames
        • Suspicion must exceed SUSPICION_THRESHOLD before emission
        • Frame-level cooldown prevents re-triggering
        """
        # ── Cooldown gate ──
        if not self._can_emit_event("gate_accident"):
            self._update_suspicion("gate_accident", False)
            return None

        # ── Track vehicle presence for post-impact window ──
        if vehicles:
            self._last_vehicle_time = time.time()
            self._last_vehicle_ids = [v.object_id for v in vehicles]

        vehicle_recently_seen = (
            (time.time() - self._last_vehicle_time) < self._VEHICLE_MEMORY_SECONDS
        )

        # ── Both vehicle AND person must be present ──
        # (mitigates: "Person not detected in same frame")
        if not persons:
            self._reset_accident_state()
            return None

        if not vehicles and not vehicle_recently_seen:
            self._reset_accident_state()
            return None

        # ── Evaluate every (vehicle, person) pair through 4 stages ──
        collision_candidates: List[Dict] = []

        for vehicle in vehicles:
            vid = vehicle.object_id

            # MITIGATION: Vehicle must have proper tracking history
            # (rejects single-frame phantom detections)
            if not self._motion_analyzer.has_track(vid):
                logging.debug(
                    f"[ACCIDENT_SKIP] vehicle {vid} has no track history — skipping"
                )
                continue

            speed = self._motion_analyzer.get_speed(vid)
            is_sudden_stop = self._motion_analyzer.is_sudden_stop(vid)

            for person in persons:
                # ── Stage 3 — Proximity ──
                dist = self.distance_between_centers(vehicle.center, person.center)
                is_proximate = dist < self.ACCIDENT_PROXIMITY_THRESHOLD
                is_very_close = dist < self.ACCIDENT_CLOSE_PROXIMITY

                # ── Stage 4 — IoU Overlap ──
                iou = self.compute_iou(vehicle.bbox, person.bbox)
                is_strong_overlap = iou > self.ACCIDENT_IOU_THRESHOLD      # > 0.15
                is_soft_overlap = iou > self.ACCIDENT_IOU_SOFT_THRESHOLD   # > 0.05

                # ── Stage 2 — Direction (is vehicle heading toward person?) ──
                is_approaching = self._motion_analyzer.is_approaching(vid, person)

                # ── Stage 1 — Velocity (is vehicle moving?) ──
                is_moving = speed > VehicleMotionAnalyzer.MIN_SPEED_PX

                # ── Classify the collision signal strength ──
                # Priority order: strongest signals first
                signal = "none"
                increment = 0.0

                if is_strong_overlap:
                    # STRONG: bounding boxes significantly overlap (IoU > 0.15)
                    signal = "strong_overlap"
                    increment = self.SUSPICION_INCREMENT_STRONG

                elif is_sudden_stop and is_proximate:
                    # STRONG: vehicle was fast, suddenly stopped near person
                    signal = "sudden_stop"
                    increment = self.SUSPICION_INCREMENT_STRONG

                elif is_very_close and is_moving:
                    # STRONG: vehicle moving while extremely close to person
                    signal = "moving_very_close"
                    increment = self.SUSPICION_INCREMENT_STRONG

                elif is_approaching and is_proximate:
                    # MODERATE: vehicle heading toward person and within range
                    signal = "approaching_proximate"
                    increment = self.SUSPICION_INCREMENT_MODERATE

                elif is_soft_overlap and (is_moving or is_approaching):
                    # MODERATE: partial bbox overlap with motion
                    signal = "soft_overlap_motion"
                    increment = self.SUSPICION_INCREMENT_MODERATE

                elif is_approaching and is_moving:
                    # WEAK: vehicle actively moving toward person (not yet close)
                    # Catches imminent collisions before proximity threshold hit
                    signal = "approaching_moving"
                    increment = self.SUSPICION_INCREMENT_WEAK

                elif is_proximate and is_soft_overlap:
                    # WEAK: close + partial overlap but no motion backup
                    signal = "proximity_soft_overlap"
                    increment = self.SUSPICION_INCREMENT_WEAK

                # Skip pairs with no qualifying signal
                if signal == "none":
                    continue

                # Minimum confidence filter (lowered for CCTV quality)
                avg_conf = (person.confidence + vehicle.confidence) / 2
                if avg_conf < 0.35:
                    continue

                collision_candidates.append({
                    "person": person,
                    "vehicle": vehicle,
                    "iou": iou,
                    "distance": dist,
                    "speed": speed,
                    "is_approaching": is_approaching,
                    "is_sudden_stop": is_sudden_stop,
                    "signal": signal,
                    "increment": increment,
                    "confidence": avg_conf,
                })

        # ── Check skeleton-based impact (person collapse after being hit) ──
        impact_score = self._check_skeleton_impact(persons, poses)

        # Skeleton collapse + recent vehicle = boost existing candidates
        if impact_score > 0.7 and vehicle_recently_seen and collision_candidates:
            for c in collision_candidates:
                c["increment"] = max(c["increment"], self.SUSPICION_INCREMENT_STRONG)
                c["signal"] = f"{c['signal']}+skeleton_collapse"

        # ── No candidates at all → reset ──
        if not collision_candidates:
            # Even a strong skeleton collapse alone is NOT enough without
            # a qualifying vehicle-person pair (mitigates false collapse triggers)
            self._reset_accident_state()
            return None

        # ── Temporal confirmation ──
        self._accident_frame_count += 1

        # Pick the strongest candidate
        best = max(collision_candidates, key=lambda c: (c["increment"], c["iou"]))

        suspicion = self._update_suspicion(
            "gate_accident", True, increment=best["increment"]
        )

        logging.debug(
            f"[ACCIDENT_EVAL] camera={self.camera_id} "
            f"frame={self._accident_frame_count}/{self.MIN_ACCIDENT_FRAMES} "
            f"signal={best['signal']} iou={best['iou']:.3f} dist={best['distance']:.0f} "
            f"speed={best['speed']:.1f} suspicion={suspicion:.2f} "
            f"skeleton={impact_score:.2f}"
        )

        # MITIGATION: Need sustained detection across multiple frames
        # (rejects single-frame flukes)
        if self._accident_frame_count < self.MIN_ACCIDENT_FRAMES:
            return None

        if suspicion < self.SUSPICION_THRESHOLD:
            return None

        # ── Emit ──
        self._mark_event_emitted("gate_accident")
        self._reset_accident_state()

        return DetectionEvent(
            event_type="gate_accident",
            confidence=best["confidence"],
            bounding_boxes=[best["person"].bbox, best["vehicle"].bbox],
            metadata={
                "person_id": best["person"].object_id,
                "vehicle_id": best["vehicle"].object_id,
                "iou": round(best["iou"], 3),
                "distance": round(best["distance"], 1),
                "vehicle_speed": round(best["speed"], 1),
                "is_approaching": best["is_approaching"],
                "is_sudden_stop": best["is_sudden_stop"],
                "signal": best["signal"],
                "suspicion_score": round(suspicion, 2),
                "skeleton_impact_score": round(impact_score, 2),
                "qualifying_frames": self.MIN_ACCIDENT_FRAMES,
            },
        )

    def _reset_accident_state(self):
        """Reset all accident accumulation state."""
        self._accident_frame_count = 0
        self._update_suspicion("gate_accident", False)
        self.temporal_buffer.reset_event("gate_accident")
    
    def _check_skeleton_impact(self, persons: List[TrackedObject], poses: List[Dict]) -> float:
        """
        Check if any person shows signs of impact using skeleton data.
        
        Returns: confidence score (0.0-1.0) that person was hit
        """
        if not poses:
            return 0.0
        
        from detectors import PoseDetector
        
        max_impact_score = 0.0
        
        for pose in poses:
            keypoints = pose.get("keypoints", [])
            if not keypoints:
                continue
            
            # Get previous keypoints for this person (by track_id)
            track_id = pose.get("track_id")
            prev_keypoints = self._prev_poses.get(track_id)
            
            # Detect collapse
            result = PoseDetector.detect_person_collapse(keypoints, prev_keypoints)
            if result.get("is_collapsed"):
                max_impact_score = max(max_impact_score, result.get("confidence", 0.0))
        
        return max_impact_score
    
    def _update_pose_history(self, poses: List[Dict]):
        """Store current poses for next frame comparison."""
        if not poses:
            return
        
        for pose in poses:
            track_id = pose.get("track_id")
            keypoints = pose.get("keypoints")
            if track_id is not None and keypoints:
                self._prev_poses[track_id] = keypoints
