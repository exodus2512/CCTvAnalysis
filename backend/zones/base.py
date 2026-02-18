"""
Base Zone Processor - Abstract base class for zone-specific detection.

All zone processors must inherit from this class and implement:
- process_frame(frame, tracked_objects, metadata, shared_detections) -> List[events]

shared_detections (injected by worker.py SharedDetectors):
    {
        "weapons":    [{class_name, confidence, bbox}, ...],
        "fire_smoke": [{class_name, confidence, bbox}, ...],
        "poses":      [{track_id, keypoints, bbox},   ...],
    }
"""

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import time
import numpy as np


@dataclass
class TrackedObject:
    """Represents a tracked object from ByteTrack."""
    object_id:    int
    class_name:   str
    bbox:         List[int]                     # [x1, y1, x2, y2]
    confidence:   float
    motion_vector: Tuple[float, float] = (0.0, 0.0)
    timestamp:    float = field(default_factory=time.time)

    @property
    def center(self) -> Tuple[int, int]:
        return (
            (self.bbox[0] + self.bbox[2]) // 2,
            (self.bbox[1] + self.bbox[3]) // 2,
        )

    @property
    def area(self) -> int:
        return (self.bbox[2] - self.bbox[0]) * (self.bbox[3] - self.bbox[1])


@dataclass
class FrameMetadata:
    """Metadata about the current frame being processed."""
    camera_id:  str
    frame_idx:  int
    timestamp:  float
    frame_size: Tuple[int, int]       # (width, height)


@dataclass
class DetectionEvent:
    """Event emitted by a zone processor."""
    event_type:     str
    confidence:     float
    bounding_boxes: List[List[int]]
    metadata:       Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# TEMPORAL BUFFER
# ============================================================================

class TemporalBuffer:
    """
    Multi-frame verification buffer.

    Stores tracked objects across frames for temporal analysis.
    Events are only emitted after sustained detection.
    """

    def __init__(self, max_frames: int = 15, camera_id: str = ""):
        self.max_frames  = max_frames
        self.camera_id   = camera_id
        self.frames: deque = deque(maxlen=max_frames)

        self.event_counters:    Dict[str, int]   = {}
        self.event_start_times: Dict[str, float] = {}

        # object_id → position history (center, timestamp)
        self.object_positions: Dict[int, deque] = {}

    def add_frame(self, tracked_objects: List[TrackedObject], timestamp: float):
        self.frames.append({"objects": tracked_objects, "timestamp": timestamp})

        for obj in tracked_objects:
            if obj.object_id not in self.object_positions:
                self.object_positions[obj.object_id] = deque(maxlen=10)
            self.object_positions[obj.object_id].append((obj.center, timestamp))

        current_ids = {obj.object_id for obj in tracked_objects}
        for obj_id in list(self.object_positions):
            positions = self.object_positions[obj_id]
            if obj_id not in current_ids and positions and time.time() - positions[-1][1] > 5.0:
                del self.object_positions[obj_id]

    def get_recent_objects(self, n_frames: int = 5) -> List[List[TrackedObject]]:
        return [f["objects"] for f in list(self.frames)[-n_frames:]]

    def increment_event(self, event_type: str) -> int:
        if event_type not in self.event_counters:
            self.event_counters[event_type]    = 0
            self.event_start_times[event_type] = time.time()
        self.event_counters[event_type] += 1
        return self.event_counters[event_type]

    def reset_event(self, event_type: str):
        self.event_counters[event_type] = 0
        self.event_start_times.pop(event_type, None)

    def get_event_duration(self, event_type: str) -> float:
        start = self.event_start_times.get(event_type)
        return 0.0 if start is None else time.time() - start

    def compute_motion_intensity(self, object_id: int) -> float:
        positions = self.object_positions.get(object_id)
        if not positions or len(positions) < 2:
            return 0.0
        pl = list(positions)
        total = sum(
            np.hypot(pl[i][0][0] - pl[i-1][0][0], pl[i][0][1] - pl[i-1][0][1])
            for i in range(1, len(pl))
        )
        dt = pl[-1][1] - pl[0][1]
        return total / dt if dt > 0 else 0.0


# ============================================================================
# BASE ZONE PROCESSOR
# ============================================================================

# Empty shared_detections sentinel used as default argument
_EMPTY_SHARED: Dict[str, List] = {"weapons": [], "fire_smoke": [], "poses": []}


class BaseZoneProcessor(ABC):
    """
    Abstract base class for zone-specific detection processors.

    Subclasses implement process_frame() and optionally call the shared
    detection helpers defined here:
        _process_shared_weapons(shared)    → DetectionEvent | None
        _process_shared_fire_smoke(shared) → DetectionEvent | None

    These helpers are zone-agnostic and work identically in every zone.
    """

    ZONE_NAME:  str       = "base"
    EVENT_TYPES: List[str] = []

    MIN_FRAMES_FOR_EVENT: int   = 3
    SUSPICION_THRESHOLD:  float = 0.6

    # Weapon / fire-smoke shared thresholds (override per zone if needed)
    WEAPON_CONFIDENCE_THRESHOLD    = 0.40
    # Per-zone weapon thresholds (override default by zone name)
    # school_ground has lowest threshold for maximum sensitivity
    WEAPON_CONFIDENCE_BY_ZONE = {
        "school_ground": 0.35,      # Very low - outdoor needs sensitivity
        "corridor": 0.55,           # Lower to catch more
        "outgate": 0.50,
        "classroom": 0.50,
    }
    FIRE_SMOKE_CONFIDENCE_THRESHOLD = 0.45
    MIN_WEAPON_FRAMES              = 2
    MIN_FIRE_SMOKE_FRAMES          = 2

    def __init__(self, camera_id: str):
        self.camera_id      = camera_id
        self.temporal_buffer = TemporalBuffer(max_frames=15, camera_id=camera_id)
        self.suspicion_scores:    Dict[str, float] = {}
        self._last_event_times:   Dict[str, float] = {}
        
        # Per-event-type cooldowns (in seconds)
        # Different events need different cooldown periods
        self._event_cooldowns: Dict[str, float] = {
            "weapon_detected": 10.0,      # Weapon: longer cooldown (serious event)
            "fight": 8.0,                 # Fight: moderate cooldown
            "gate_accident": 8.0,         # Accident: moderate cooldown
            "vehicle_detected": 5.0,      # Vehicle: shorter cooldown (frequent)
            "crowd_formation": 6.0,       # Crowd: moderate cooldown
            "fire_smoke_detected": 10.0,  # Fire: longer cooldown (serious)
            "mobile_usage": 4.0,          # Mobile: shorter cooldown
            "fall_detected": 6.0,         # Fall: moderate cooldown
        }
        self._default_cooldown: float = 5.0  # Default for unlisted events

        # Shared detector frame counters (per zone instance)
        self._weapon_frame_count    = 0
        self._fire_smoke_frame_count = 0

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def process_frame(
        self,
        frame:           np.ndarray,
        tracked_objects: List[TrackedObject],
        metadata:        FrameMetadata,
        shared_detections: Dict[str, List] = None,
    ) -> List[DetectionEvent]:
        """
        Process a frame and return detected events.

        Args:
            frame:             BGR image from OpenCV
            tracked_objects:   Objects from the tracker (stable IDs)
            metadata:          Frame metadata
            shared_detections: Output from SharedDetectors.run() —
                               contains weapons / fire_smoke / poses.
                               May be None for backward compatibility.

        Returns:
            List of DetectionEvent (only after temporal + suspicion verification)
        """
        pass

    # ------------------------------------------------------------------
    # Shared detection helpers (called by every zone's process_frame)
    # ------------------------------------------------------------------

    def _process_shared_weapons(
        self,
        shared:  Dict[str, List],
        persons: List[TrackedObject],
    ) -> Optional[DetectionEvent]:
        """
        Emit weapon_detected from shared weapon detector output.

        Works across all zones — zone processors call this and append
        the result to their events list.

        Args:
            shared:  shared_detections dict from worker
            persons: person TrackedObjects in this frame
        """
        import logging
        
        detections = (shared or {}).get("weapons", [])

        # Fallback: if custom weapon model not loaded, shared["weapons"] is
        # empty but the zone model may have detected knife/scissors from COCO.
        # Those would already be in tracked_objects as class_name knife/scissors.
        # Zone processors handle that path themselves.

        zone_name = getattr(self, "ZONE_NAME", "")
        threshold = self.WEAPON_CONFIDENCE_BY_ZONE.get(zone_name, self.WEAPON_CONFIDENCE_THRESHOLD)
        confident = [
            d for d in detections
            if d.get("confidence", 0) >= threshold
        ]

        # Debug logging for school_ground zone
        if zone_name == "school_ground" and detections:
            logging.info(
                f"[WEAPON_PROCESS] zone={zone_name} total_dets={len(detections)} "
                f"threshold={threshold} confident={len(confident)} "
                f"max_conf={max((d.get('confidence', 0) for d in detections), default=0):.2f}"
            )

        if not confident:
            self._weapon_frame_count = 0
            self._update_suspicion("weapon_detected", False)
            return None

        self._weapon_frame_count += 1
        suspicion = self._update_suspicion("weapon_detected", True, increment=0.30)

        # Debug for school_ground
        if zone_name == "school_ground":
            logging.info(
                f"[WEAPON_CHECK] zone={zone_name} frame_count={self._weapon_frame_count} "
                f"suspicion={suspicion:.2f} min_frames={self.MIN_WEAPON_FRAMES}"
            )

        if self._weapon_frame_count < self.MIN_WEAPON_FRAMES:
            return None
        if suspicion < 0.50:          # lower bar for safety events
            return None
        if not self._can_emit_event("weapon_detected"):
            return None

        best = max(confident, key=lambda d: d["confidence"])

        # Find nearest person
        closest_person, min_dist = None, float("inf")
        bw = best.get("bbox", [0, 0, 0, 0])
        w_center = ((bw[0] + bw[2]) // 2, (bw[1] + bw[3]) // 2)

        for person in persons:
            dist = self.distance_between_centers(w_center, person.center)
            if dist < min_dist:
                min_dist      = dist
                closest_person = person

        near_person = min_dist < 200

        self._mark_event_emitted("weapon_detected")
        self._weapon_frame_count = 0

        bboxes = [best["bbox"]]
        if closest_person:
            bboxes.append(closest_person.bbox)

        return DetectionEvent(
            event_type="weapon_detected",
            confidence=best["confidence"],
            bounding_boxes=bboxes,
            metadata={
                "weapon_type":     best.get("class_name", "unknown"),
                "near_person":     near_person,
                "person_distance": round(min_dist, 1) if near_person else None,
                "person_id":       closest_person.object_id if closest_person else None,
                "source":          "weapon_model",
            },
        )

    def _process_shared_fire_smoke(
        self,
        shared: Dict[str, List],
    ) -> Optional[DetectionEvent]:
        """
        Emit fire_smoke_detected from shared fire/smoke detector output.
        Works across all zones.
        """
        detections = (shared or {}).get("fire_smoke", [])

        confident = [
            d for d in detections
            if d.get("confidence", 0) >= self.FIRE_SMOKE_CONFIDENCE_THRESHOLD
        ]

        if not confident:
            self._fire_smoke_frame_count = 0
            self._update_suspicion("fire_smoke_detected", False)
            return None

        self._fire_smoke_frame_count += 1
        suspicion = self._update_suspicion("fire_smoke_detected", True, increment=0.35)

        if self._fire_smoke_frame_count < self.MIN_FIRE_SMOKE_FRAMES:
            return None
        if suspicion < 0.45:
            return None
        if not self._can_emit_event("fire_smoke_detected"):
            return None

        best = max(confident, key=lambda d: d["confidence"])

        self._mark_event_emitted("fire_smoke_detected")
        self._fire_smoke_frame_count = 0

        return DetectionEvent(
            event_type="fire_smoke_detected",
            confidence=best["confidence"],
            bounding_boxes=[d["bbox"] for d in confident],
            metadata={
                "type":  best.get("class_name", "unknown"),   # "fire" or "smoke"
                "count": len(confident),
                "source": "fire_smoke_model",
            },
        )

    # ------------------------------------------------------------------
    # Pose ↔ track alignment helper
    # ------------------------------------------------------------------

    def _align_poses_with_tracks(
        self,
        poses: List[Dict[str, Any]],
        persons: List[TrackedObject],
        iou_threshold: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """
        Assign tracker IDs to pose detections using IoU with tracked persons.

        Pose detector often returns no track_id; this aligns poses to tracked
        person boxes so pose-based fight/fall checks work reliably.
        """
        if not poses or not persons:
            return poses

        for pose in poses:
            if pose.get("track_id") is not None and pose.get("track_id") >= 0:
                continue

            best_person = None
            best_iou = 0.0
            for person in persons:
                iou = self.compute_iou(pose.get("bbox", [0, 0, 0, 0]), person.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_person = person

            if best_person is not None and best_iou >= iou_threshold:
                pose["track_id"] = best_person.object_id

        return poses

    # ------------------------------------------------------------------
    # Suspicion + cooldown helpers (with per-event-type cooldowns)
    # ------------------------------------------------------------------

    def _get_event_cooldown(self, event_type: str) -> float:
        """Get cooldown duration for specific event type."""
        return self._event_cooldowns.get(event_type, self._default_cooldown)

    def _can_emit_event(self, event_type: str) -> bool:
        """Check if event can be emitted based on per-event-type cooldown."""
        cooldown = self._get_event_cooldown(event_type)
        return time.time() - self._last_event_times.get(event_type, 0) >= cooldown

    def _mark_event_emitted(self, event_type: str):
        self._last_event_times[event_type] = time.time()

    def _update_suspicion(
        self,
        event_type: str,
        detected:   bool,
        increment:  float = 0.15,
        decay:      float = 0.08,
    ) -> float:
        current = self.suspicion_scores.get(event_type, 0.0)
        new     = min(1.0, current + increment) if detected else max(0.0, current - decay)
        self.suspicion_scores[event_type] = new
        return new

    # ------------------------------------------------------------------
    # Geometry helpers (unchanged)
    # ------------------------------------------------------------------

    def _compute_centroid(self, objects: List[TrackedObject]) -> Optional[Tuple[float, float]]:
        if not objects:
            return None
        centers = np.array([obj.center for obj in objects])
        return tuple(centers.mean(axis=0))

    def _compute_cluster_spread(self, objects: List[TrackedObject]) -> float:
        if len(objects) < 2:
            return 0.0
        centroid = self._compute_centroid(objects)
        if centroid is None:
            return 0.0
        return float(np.mean([
            np.hypot(obj.center[0] - centroid[0], obj.center[1] - centroid[1])
            for obj in objects
        ]))

    @staticmethod
    def compute_iou(box1: List[int], box2: List[int]) -> float:
        x1 = max(box1[0], box2[0]); y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2]); y2 = min(box1[3], box2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        a1    = (box1[2] - box1[0]) * (box1[3] - box1[1])
        a2    = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def distance_between_centers(
        c1: Tuple[int, int], c2: Tuple[int, int]
    ) -> float:
        return float(np.hypot(c1[0] - c2[0], c1[1] - c2[1]))