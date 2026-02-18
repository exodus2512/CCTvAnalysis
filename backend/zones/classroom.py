"""
Classroom Zone Processor

Events:
- mobile_usage:       Student using mobile phone during class
- fight:              Physical altercation between students (pose-based)
- weapon_detected:    Gun/knife/blade detected in classroom (shared model)
- fire_smoke_detected: Fire or smoke detected (shared model)
"""

import numpy as np
from typing import List, Dict, Optional
from .base import (
    BaseZoneProcessor,
    TrackedObject,
    FrameMetadata,
    DetectionEvent,
)


class ClassroomProcessor(BaseZoneProcessor):
    """
    Classroom zone processor.

    Uses yolov8m.pt for person + phone detection (better small objects).
    Fight detection uses pose keypoints from shared pose model.
    Weapon + fire/smoke from shared detectors.
    """

    ZONE_NAME   = "classroom"
    EVENT_TYPES = [
        "mobile_usage",
        "fight",
        "weapon_detected",
        "fire_smoke_detected",
        "after_hours_intrusion",
    ]
    MODEL_NAME = "yolov8m.pt"

    # ── Mobile detection ────────────────────────────────────────────────
    PHONE_CONFIDENCE_THRESHOLD = 0.35
    PHONE_PERSON_IOU_THRESHOLD = 0.03
    MIN_DETECTION_DURATION     = 1.5   # seconds

    # ── Fight detection (pose-based) ─────────────────────────────────
    # Fallback (no pose model): bbox IoU heuristic
    FIGHT_OVERLAP_THRESHOLD = 0.12
    FIGHT_MOTION_THRESHOLD  = 35.0
    MIN_FIGHT_FRAMES        = 3

    # Pose-based fight: wrist/elbow keypoint velocity + proximity
    POSE_FIGHT_WRIST_SPEED_THRESHOLD = 25.0   # px/frame — rapid arm movement
    POSE_FIGHT_PROXIMITY_THRESHOLD   = 120     # px — persons close together

    def __init__(self, camera_id: str):
        super().__init__(camera_id)
        self._mobile_start_time              = None
        self._detected_phone_person_pairs: dict = {}
        self._fight_frame_count              = 0
        # pose history: object_id → list of keypoint arrays
        self._pose_history: Dict[int, list]  = {}

    # ================================================================
    # Main entry point
    # ================================================================

    def process_frame(
        self,
        frame:             np.ndarray,
        tracked_objects:   List[TrackedObject],
        metadata:          FrameMetadata,
        shared_detections: Dict[str, list] = None,
    ) -> List[DetectionEvent]:

        shared = shared_detections or {}
        self.temporal_buffer.add_frame(tracked_objects, metadata.timestamp)

        persons = [o for o in tracked_objects if o.class_name == "person"]
        phones  = [o for o in tracked_objects if o.class_name == "cell phone"]

        events: List[DetectionEvent] = []

        # Priority order: weapon > fire/smoke > fight > mobile
        weapon_event = self._process_shared_weapons(shared, persons)
        if weapon_event:
            events.append(weapon_event)

        fire_event = self._process_shared_fire_smoke(shared)
        if fire_event:
            events.append(fire_event)

        fight_event = self._detect_fight(persons, shared.get("poses", []), metadata)
        if fight_event:
            events.append(fight_event)

        mobile_event = self._detect_mobile_usage(persons, phones, metadata)
        if mobile_event:
            events.append(mobile_event)

        return events

    # ================================================================
    # Mobile usage detection (unchanged logic, cleaned up)
    # ================================================================

    def _detect_mobile_usage(
        self,
        persons:  List[TrackedObject],
        phones:   List[TrackedObject],
        metadata: FrameMetadata,
    ) -> Optional[DetectionEvent]:
        # FRAME-LEVEL COOLDOWN: Prevent re-triggering within cooldown window
        if not self._can_emit_event("mobile_usage"):
            self._update_suspicion("mobile_usage", False)
            return None

        if not persons or not phones:
            self._mobile_start_time = None
            self._update_suspicion("mobile_usage", False)
            self.temporal_buffer.reset_event("mobile_usage")
            return None

        confident_phones = [p for p in phones if p.confidence >= self.PHONE_CONFIDENCE_THRESHOLD]
        if not confident_phones:
            self._mobile_start_time = None
            self._update_suspicion("mobile_usage", False)
            return None

        usage_candidates = []
        for phone in confident_phones:
            for person in persons:
                px1, py1, px2, py2 = person.bbox
                upper_body = [px1, py1, px2, py1 + int((py2 - py1) * 0.6)]
                iou    = self.compute_iou(upper_body, phone.bbox)
                inside = self._is_box_inside(phone.bbox, person.bbox)

                if iou > self.PHONE_PERSON_IOU_THRESHOLD or inside:
                    usage_candidates.append({
                        "person":     person,
                        "phone":      phone,
                        "confidence": (person.confidence + phone.confidence) / 2,
                        "inside":     inside,
                    })

        if not usage_candidates:
            self._mobile_start_time = None
            self._update_suspicion("mobile_usage", False)
            return None

        if self._mobile_start_time is None:
            self._mobile_start_time = metadata.timestamp

        duration  = metadata.timestamp - self._mobile_start_time
        suspicion = self._update_suspicion("mobile_usage", True, increment=0.15)

        if duration < self.MIN_DETECTION_DURATION:
            return None
        if suspicion < self.SUSPICION_THRESHOLD:
            return None
        if not self._can_emit_event("mobile_usage"):
            return None

        best = max(usage_candidates, key=lambda x: x["confidence"])
        self._mark_event_emitted("mobile_usage")
        self._mobile_start_time = None

        return DetectionEvent(
            event_type="mobile_usage",
            confidence=best["confidence"],
            bounding_boxes=[best["person"].bbox, best["phone"].bbox],
            metadata={
                "person_id":          best["person"].object_id,
                "phone_id":           best["phone"].object_id,
                "duration":           round(duration, 2),
                "phone_inside_person": best["inside"],
            },
        )

    # ================================================================
    # Fight detection
    # ================================================================

    def _detect_fight(
        self,
        persons:   List[TrackedObject],
        poses:     list,
        metadata:  FrameMetadata,
    ) -> Optional[DetectionEvent]:
        """
        Fight detection with two strategies:
        1. Pose-based  (if pose model output available): wrist velocity + proximity
        2. BBox heuristic fallback: IoU overlap + motion intensity
        """
        # FRAME-LEVEL COOLDOWN: Prevent re-triggering within cooldown window
        if not self._can_emit_event("fight"):
            self._update_suspicion("fight", False)
            return None
        
        if len(persons) < 2:
            self._fight_frame_count = 0
            self._update_suspicion("fight", False)
            return None

        # Update pose history
        for pose in poses:
            pid = pose.get("track_id")
            kps = pose.get("keypoints")
            if pid is not None and kps is not None:
                if pid not in self._pose_history:
                    self._pose_history[pid] = []
                self._pose_history[pid].append(kps)
                if len(self._pose_history[pid]) > 10:
                    self._pose_history[pid].pop(0)

        fight_detected = False
        fight_candidates = []

        if poses:
            fight_detected, fight_candidates = self._pose_fight_check(persons, poses)

        if not fight_detected:
            # Fallback: IoU + motion heuristic
            fight_detected, fight_candidates = self._bbox_fight_check(persons)

        if not fight_detected or not fight_candidates:
            self._fight_frame_count = 0
            self._update_suspicion("fight", False)
            return None

        self._fight_frame_count += 1
        suspicion = self._update_suspicion("fight", True, increment=0.20)

        if self._fight_frame_count < self.MIN_FIGHT_FRAMES:
            return None
        if suspicion < self.SUSPICION_THRESHOLD:
            return None
        if not self._can_emit_event("fight"):
            return None

        best = max(fight_candidates, key=lambda x: x["score"])
        self._mark_event_emitted("fight")
        self._fight_frame_count = 0

        return DetectionEvent(
            event_type="fight",
            confidence=best["confidence"],
            bounding_boxes=[best["p1"].bbox, best["p2"].bbox],
            metadata={
                "person_ids":    [best["p1"].object_id, best["p2"].object_id],
                "detection_mode": best.get("mode", "bbox"),
                "zone":          "classroom",
            },
        )

    def _pose_fight_check(self, persons, poses):
        """
        Check fight via pose keypoints.
        Wrist (index 9,10) and elbow (7,8) keypoints:
        - High velocity of wrists between frames = striking motion
        - Two persons' keypoints in close proximity = physical contact
        """
        candidates = []

        # Build map: track_id → current keypoints
        pose_map = {p["track_id"]: p["keypoints"] for p in poses if "track_id" in p and "keypoints" in p}

        person_ids = [p.object_id for p in persons]

        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2 = persons[i], persons[j]

                kps1 = pose_map.get(p1.object_id)
                kps2 = pose_map.get(p2.object_id)

                if kps1 is None or kps2 is None:
                    continue

                # Wrist speed for p1 (compare to previous frame)
                wrist_speed = self._compute_wrist_speed(p1.object_id, kps1)

                # Proximity of persons
                dist = self.distance_between_centers(p1.center, p2.center)

                if (wrist_speed > self.POSE_FIGHT_WRIST_SPEED_THRESHOLD
                        and dist < self.POSE_FIGHT_PROXIMITY_THRESHOLD):
                    avg_conf = (p1.confidence + p2.confidence) / 2
                    candidates.append({
                        "p1":         p1,
                        "p2":         p2,
                        "confidence": avg_conf,
                        "score":      wrist_speed / 100 + (1 - dist / 500),
                        "mode":       "pose",
                    })

        return bool(candidates), candidates

    def _compute_wrist_speed(self, track_id: int, current_kps) -> float:
        """Compute average wrist movement speed between last two keypoint frames."""
        history = self._pose_history.get(track_id, [])
        if len(history) < 2:
            return 0.0
        prev_kps = history[-2]
        try:
            # Keypoints indices 9=left wrist, 10=right wrist (COCO pose format)
            speeds = []
            for idx in [9, 10]:
                if len(current_kps) > idx and len(prev_kps) > idx:
                    c = current_kps[idx][:2]
                    p = prev_kps[idx][:2]
                    speeds.append(float(np.hypot(c[0] - p[0], c[1] - p[1])))
            return float(np.mean(speeds)) if speeds else 0.0
        except Exception:
            return 0.0

    def _bbox_fight_check(self, persons):
        """Fallback fight check using bounding box IoU + motion intensity."""
        candidates = []
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2 = persons[i], persons[j]
                iou     = self.compute_iou(p1.bbox, p2.bbox)
                if iou > self.FIGHT_OVERLAP_THRESHOLD:
                    m1 = self.temporal_buffer.compute_motion_intensity(p1.object_id)
                    m2 = self.temporal_buffer.compute_motion_intensity(p2.object_id)
                    avg_conf = (p1.confidence + p2.confidence) / 2
                    if avg_conf >= 0.5:
                        candidates.append({
                            "p1":         p1,
                            "p2":         p2,
                            "confidence": avg_conf,
                            "score":      iou + (m1 + m2) / 200,
                            "mode":       "bbox",
                        })
        return bool(candidates), candidates

    # ================================================================
    # Helpers
    # ================================================================

    @staticmethod
    def _is_box_inside(inner: List[int], outer: List[int]) -> bool:
        return (inner[0] >= outer[0] and inner[1] >= outer[1]
                and inner[2] <= outer[2] and inner[3] <= outer[3])