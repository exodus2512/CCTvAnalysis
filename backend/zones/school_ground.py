"""
School Ground Zone Processor

Events:
- crowd_formation:    Large clustered group in outdoor area
- fight:              Physical altercation (pose-based + bbox fallback)
- weapon_detected:    Gun/knife/blade detected (shared model, + COCO fallback)
- fall_detected:      Person fall via pose keypoints
- fire_smoke_detected: Fire or smoke detected (shared model)
- after_hours_intrusion: Person detected outside school hours
"""

import numpy as np
from typing import List, Dict, Optional
from .base import (
    BaseZoneProcessor,
    TrackedObject,
    FrameMetadata,
    DetectionEvent,
)

# COCO weapon classes — used as fallback when custom weapon model not loaded
COCO_WEAPON_CLASSES = {"knife", "scissors"}


class SchoolGroundProcessor(BaseZoneProcessor):
    """
    School ground zone processor.

    Uses yolov8s.pt (same as corridor).
    Thresholds adjusted for larger outdoor areas.
    Fall detection via pose keypoints (hip/shoulder/knee angle).
    """

    ZONE_NAME   = "school_ground"
    EVENT_TYPES = [
        "crowd_formation",
        "fight",
        "weapon_detected",
        "fall_detected",
        "fire_smoke_detected",
        "after_hours_intrusion",
    ]
    MODEL_NAME = "yolov8s.pt"

    # ── Crowd ────────────────────────────────────────────────────────
    MIN_CROWD_SIZE             = 4
    CLUSTER_DISTANCE_THRESHOLD = 200.0
    MIN_CROWD_DURATION         = 2.5

    # ── Fight (bbox fallback) ────────────────────────────────────────
    FIGHT_OVERLAP_THRESHOLD = 0.08
    FIGHT_MOTION_THRESHOLD  = 40.0
    MIN_FIGHT_FRAMES        = 3

    # ── Fight (pose) ─────────────────────────────────────────────────
    POSE_WRIST_SPEED_THRESHOLD = 25.0
    POSE_PROXIMITY_THRESHOLD   = 140

    # ── Fall detection ───────────────────────────────────────────────
    # A person is considered fallen when:
    #   - bbox aspect ratio width/height > FALL_ASPECT_RATIO_THRESHOLD  (lying flat)
    #   - OR pose hip-shoulder vertical angle is near horizontal
    FALL_ASPECT_RATIO_THRESHOLD = 1.4    # width > 1.4× height → likely lying
    FALL_POSE_ANGLE_THRESHOLD   = 45.0   # degrees from vertical
    MIN_FALL_FRAMES             = 3
    FALL_MOTION_COOLDOWN        = 1.5    # don't trigger if person still moving fast

    # ── COCO weapon (fallback) ───────────────────────────────────────
    COCO_WEAPON_CONFIDENCE = 0.30
    MIN_WEAPON_FRAMES      = 2

    def __init__(self, camera_id: str):
        super().__init__(camera_id)
        self._crowd_start_time  = None
        self._fight_frame_count = 0
        self._fall_frame_count  = 0
        self._coco_weapon_frames = 0
        self._pose_history: Dict[int, list] = {}

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

        shared  = shared_detections or {}
        poses   = shared.get("poses", [])
        self.temporal_buffer.add_frame(tracked_objects, metadata.timestamp)

        persons = [o for o in tracked_objects if o.class_name == "person"]
        # COCO knife/scissors from zone model (fallback when weapon_model.pt missing)
        coco_weapons = [o for o in tracked_objects if o.class_name in COCO_WEAPON_CLASSES]

        events: List[DetectionEvent] = []

        # 1. Weapon — shared model (returns None if model not loaded)
        weapon_event = self._process_shared_weapons(shared, persons)
        if weapon_event:
            events.append(weapon_event)
        elif not weapon_event and coco_weapons:
            # Fallback: use COCO knife/scissors from zone model
            coco_event = self._detect_coco_weapon(coco_weapons, persons)
            if coco_event:
                events.append(coco_event)

        # 2. Fire / smoke
        fire_event = self._process_shared_fire_smoke(shared)
        if fire_event:
            events.append(fire_event)

        # 3. Fight
        fight_event = self._detect_fight(persons, poses, metadata)
        if fight_event:
            events.append(fight_event)

        # 4. Fall
        fall_event = self._detect_fall(persons, poses)
        if fall_event:
            events.append(fall_event)

        # 5. Crowd
        crowd_event = self._detect_crowd(persons, metadata)
        if crowd_event:
            events.append(crowd_event)

        return events

    # ================================================================
    # Crowd detection
    # ================================================================

    def _detect_crowd(
        self,
        persons:  List[TrackedObject],
        metadata: FrameMetadata,
    ) -> Optional[DetectionEvent]:
        # FRAME-LEVEL COOLDOWN: Prevent re-triggering within cooldown window
        if not self._can_emit_event("crowd_formation"):
            self._update_suspicion("crowd_formation", False)
            return None

        if len(persons) < self.MIN_CROWD_SIZE:
            self._crowd_start_time = None
            self._update_suspicion("crowd_formation", False)
            self.temporal_buffer.reset_event("crowd_formation")
            return None

        spread = self._compute_cluster_spread(persons)
        if spread > self.CLUSTER_DISTANCE_THRESHOLD:
            self._crowd_start_time = None
            self._update_suspicion("crowd_formation", False)
            self.temporal_buffer.reset_event("crowd_formation")
            return None

        if self._crowd_start_time is None:
            self._crowd_start_time = metadata.timestamp

        duration  = metadata.timestamp - self._crowd_start_time
        suspicion = self._update_suspicion("crowd_formation", True, increment=0.12)

        if duration < self.MIN_CROWD_DURATION:
            return None
        if suspicion < self.SUSPICION_THRESHOLD:
            return None
        if not self._can_emit_event("crowd_formation"):
            return None

        avg_conf = float(np.mean([p.confidence for p in persons]))
        self._mark_event_emitted("crowd_formation")
        self._crowd_start_time = None

        return DetectionEvent(
            event_type="crowd_formation",
            confidence=avg_conf,
            bounding_boxes=[p.bbox for p in persons],
            metadata={
                "person_count":  len(persons),
                "cluster_spread": round(spread, 1),
                "duration":      round(duration, 2),
                "zone":          "school_ground",
            },
        )

    # ================================================================
    # Fight detection
    # ================================================================

    def _detect_fight(
        self,
        persons:  List[TrackedObject],
        poses:    list,
        metadata: FrameMetadata,
    ) -> Optional[DetectionEvent]:
        # FRAME-LEVEL COOLDOWN: Prevent re-triggering within cooldown window
        if not self._can_emit_event("fight"):
            self._update_suspicion("fight", False)
            return None

        if len(persons) < 2:
            self._fight_frame_count = 0
            self._update_suspicion("fight", False)
            return None

        # Align poses to tracked persons before building history
        poses = self._align_poses_with_tracks(poses, persons)

        for pose in poses:
            pid = pose.get("track_id")
            kps = pose.get("keypoints")
            if pid is not None and kps is not None:
                if pid not in self._pose_history:
                    self._pose_history[pid] = []
                self._pose_history[pid].append(kps)
                if len(self._pose_history[pid]) > 10:
                    self._pose_history[pid].pop(0)

        fight_detected, candidates = (False, [])
        if poses:
            fight_detected, candidates = self._pose_fight_check(persons, poses)
        if not fight_detected:
            fight_detected, candidates = self._bbox_fight_check(persons)

        if not fight_detected:
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

        best = max(candidates, key=lambda x: x["score"])
        self._mark_event_emitted("fight")
        self._fight_frame_count = 0

        return DetectionEvent(
            event_type="fight",
            confidence=best["confidence"],
            bounding_boxes=[best["p1"].bbox, best["p2"].bbox],
            metadata={
                "person_ids":     [best["p1"].object_id, best["p2"].object_id],
                "detection_mode": best.get("mode", "bbox"),
                "zone":           "school_ground",
            },
        )

    def _pose_fight_check(self, persons, poses):
        pose_map   = {p["track_id"]: p["keypoints"] for p in poses
                      if "track_id" in p and "keypoints" in p}
        candidates = []
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2  = persons[i], persons[j]
                kps1    = pose_map.get(p1.object_id)
                kps2    = pose_map.get(p2.object_id)
                if kps1 is None or kps2 is None:
                    continue
                wrist_speed = self._compute_wrist_speed(p1.object_id, kps1)
                dist        = self.distance_between_centers(p1.center, p2.center)
                if wrist_speed > self.POSE_WRIST_SPEED_THRESHOLD and dist < self.POSE_PROXIMITY_THRESHOLD:
                    avg_conf = (p1.confidence + p2.confidence) / 2
                    candidates.append({
                        "p1": p1, "p2": p2,
                        "confidence": avg_conf,
                        "score": wrist_speed / 100 + (1 - dist / 500),
                        "mode": "pose",
                    })
        return bool(candidates), candidates

    def _bbox_fight_check(self, persons):
        candidates = []
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2 = persons[i], persons[j]
                iou    = self.compute_iou(p1.bbox, p2.bbox)
                if iou > self.FIGHT_OVERLAP_THRESHOLD:
                    m1 = self.temporal_buffer.compute_motion_intensity(p1.object_id)
                    m2 = self.temporal_buffer.compute_motion_intensity(p2.object_id)
                    avg_conf = (p1.confidence + p2.confidence) / 2
                    if avg_conf >= 0.5:
                        candidates.append({
                            "p1": p1, "p2": p2,
                            "confidence": avg_conf,
                            "score": iou + (m1 + m2) / 200,
                            "mode": "bbox",
                        })
        return bool(candidates), candidates

    def _compute_wrist_speed(self, track_id: int, current_kps) -> float:
        history = self._pose_history.get(track_id, [])
        if len(history) < 2:
            return 0.0
        prev_kps = history[-2]
        try:
            speeds = []
            for idx in [9, 10]:
                if len(current_kps) > idx and len(prev_kps) > idx:
                    c = current_kps[idx][:2]
                    p = prev_kps[idx][:2]
                    speeds.append(float(np.hypot(c[0] - p[0], c[1] - p[1])))
            return float(np.mean(speeds)) if speeds else 0.0
        except Exception:
            return 0.0

    # ================================================================
    # Fall detection
    # ================================================================

    def _detect_fall(
        self,
        persons: List[TrackedObject],
        poses:   list,
    ) -> Optional[DetectionEvent]:
        """
        Detect a fallen person using two methods:
        1. Pose-based: hip-shoulder angle near horizontal (< FALL_POSE_ANGLE_THRESHOLD)
        2. Bbox aspect ratio fallback: width > height × threshold
        """
        # FRAME-LEVEL COOLDOWN: Prevent re-triggering within cooldown window
        if not self._can_emit_event("fall_detected"):
            self._update_suspicion("fall_detected", False)
            return None
        
        if not persons:
            self._fall_frame_count = 0
            self._update_suspicion("fall_detected", False)
            return None

        poses = self._align_poses_with_tracks(poses, persons)
        pose_map = {p["track_id"]: p["keypoints"] for p in poses
                if "track_id" in p and "keypoints" in p}

        fall_candidates = []

        for person in persons:
            # Check if person is still moving (skip if running/falling in motion)
            motion = self.temporal_buffer.compute_motion_intensity(person.object_id)
            if motion > 60:     # still rapidly moving — not a stable fall
                continue

            fallen = False
            angle  = None

            # Method 1: Pose keypoint angle
            kps = pose_map.get(person.object_id)
            if kps is not None:
                angle  = self._compute_body_angle(kps)
                fallen = (angle is not None and angle < self.FALL_POSE_ANGLE_THRESHOLD)

            # Method 2: Bbox aspect ratio fallback
            if not fallen:
                x1, y1, x2, y2 = person.bbox
                w = x2 - x1
                h = y2 - y1
                if h > 0 and (w / h) > self.FALL_ASPECT_RATIO_THRESHOLD:
                    fallen = True

            if fallen:
                fall_candidates.append({
                    "person": person,
                    "angle":  angle,
                    "motion": motion,
                })

        if not fall_candidates:
            self._fall_frame_count = 0
            self._update_suspicion("fall_detected", False)
            return None

        self._fall_frame_count += 1
        suspicion = self._update_suspicion("fall_detected", True, increment=0.25)

        if self._fall_frame_count < self.MIN_FALL_FRAMES:
            return None
        if suspicion < self.SUSPICION_THRESHOLD:
            return None
        if not self._can_emit_event("fall_detected"):
            return None

        best = fall_candidates[0]   # first fallen person found
        self._mark_event_emitted("fall_detected")
        self._fall_frame_count = 0

        return DetectionEvent(
            event_type="fall_detected",
            confidence=best["person"].confidence,
            bounding_boxes=[best["person"].bbox],
            metadata={
                "person_id":      best["person"].object_id,
                "body_angle":     round(best["angle"], 1) if best["angle"] else None,
                "motion":         round(best["motion"], 1),
                "detection_mode": "pose" if best["angle"] is not None else "aspect_ratio",
                "zone":           "school_ground",
            },
        )

    def _compute_body_angle(self, keypoints) -> Optional[float]:
        """
        Compute angle (degrees) of the torso from vertical.

        Uses left shoulder (5) and left hip (11), or right equivalents.
        0° = perfectly upright, 90° = lying flat.
        Returns None if keypoints insufficient.
        """
        try:
            # COCO pose: 5=left_shoulder, 6=right_shoulder, 11=left_hip, 12=right_hip
            pairs = [(5, 11), (6, 12)]
            angles = []
            for s_idx, h_idx in pairs:
                if len(keypoints) > max(s_idx, h_idx):
                    shoulder = keypoints[s_idx][:2]
                    hip      = keypoints[h_idx][:2]
                    dx = shoulder[0] - hip[0]
                    dy = shoulder[1] - hip[1]    # positive = down in image
                    # Angle from vertical: arctan(dx/dy)
                    if abs(dy) > 1e-3:
                        angle = abs(float(np.degrees(np.arctan2(abs(dx), abs(dy)))))
                        angles.append(angle)
            return float(np.mean(angles)) if angles else None
        except Exception:
            return None

    # ================================================================
    # COCO weapon fallback (knife/scissors from zone model)
    # ================================================================

    def _detect_coco_weapon(
        self,
        weapons: List[TrackedObject],
        persons: List[TrackedObject],
    ) -> Optional[DetectionEvent]:
        """Fallback weapon detection using COCO knife/scissors classes."""
        confident = [w for w in weapons if w.confidence >= self.COCO_WEAPON_CONFIDENCE]
        if not confident:
            self._coco_weapon_frames = 0
            self._update_suspicion("weapon_detected", False)
            return None

        self._coco_weapon_frames += 1
        suspicion = self._update_suspicion("weapon_detected", True, increment=0.30)

        if self._coco_weapon_frames < self.MIN_WEAPON_FRAMES:
            return None
        if suspicion < 0.50:
            return None
        if not self._can_emit_event("weapon_detected"):
            return None

        best = max(confident, key=lambda w: w.confidence)

        # Find closest person
        closest_person, min_dist = None, float("inf")
        for person in persons:
            dist = self.distance_between_centers(best.center, person.center)
            if dist < min_dist:
                min_dist       = dist
                closest_person = person

        self._mark_event_emitted("weapon_detected")
        self._coco_weapon_frames = 0

        bboxes = [best.bbox]
        if closest_person:
            bboxes.append(closest_person.bbox)

        return DetectionEvent(
            event_type="weapon_detected",
            confidence=best.confidence,
            bounding_boxes=bboxes,
            metadata={
                "weapon_type":     best.class_name,
                "near_person":     min_dist < 200,
                "person_distance": round(min_dist, 1),
                "person_id":       closest_person.object_id if closest_person else None,
                "source":          "coco_fallback",
                "zone":            "school_ground",
            },
        )