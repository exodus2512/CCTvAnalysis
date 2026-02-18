"""
Corridor Zone Processor

Events:
- crowd_formation:    Large clustered group in corridor
- fight:              Physical altercation (pose-based + bbox fallback)
- weapon_detected:    Gun/knife/blade detected (shared model)
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


class CorridorProcessor(BaseZoneProcessor):
    """
    Corridor zone processor.

    Uses yolov8s.pt for person detection.
    Fight detection: pose keypoints (primary) + bbox IoU (fallback).
    Weapon + fire/smoke from shared detectors.
    """

    ZONE_NAME   = "corridor"
    EVENT_TYPES = [
        "crowd_formation",
        "fight",
        "weapon_detected",
        "fire_smoke_detected",
        "after_hours_intrusion",
    ]
    MODEL_NAME = "yolov8s.pt"

    # ── Crowd detection ──────────────────────────────────────────────
    MIN_CROWD_SIZE             = 4
    CLUSTER_DISTANCE_THRESHOLD = 160.0
    MIN_CROWD_DURATION         = 2.0    # seconds

    # ── Fight detection (bbox fallback) ──────────────────────────────
    FIGHT_OVERLAP_THRESHOLD = 0.10
    FIGHT_MOTION_THRESHOLD  = 40.0
    MIN_FIGHT_FRAMES        = 3

    # ── Fight detection (pose-based) ─────────────────────────────────
    POSE_WRIST_SPEED_THRESHOLD  = 25.0
    POSE_PROXIMITY_THRESHOLD    = 130

    def __init__(self, camera_id: str):
        super().__init__(camera_id)
        self._crowd_start_time = None
        self._fight_frame_count = 0
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

        shared = shared_detections or {}
        self.temporal_buffer.add_frame(tracked_objects, metadata.timestamp)

        persons = [o for o in tracked_objects if o.class_name == "person"]
        events:  List[DetectionEvent] = []

        # Priority order: weapon > fire/smoke > fight > crowd
        weapon_event = self._process_shared_weapons(shared, persons)
        if weapon_event:
            events.append(weapon_event)

        fire_event = self._process_shared_fire_smoke(shared)
        if fire_event:
            events.append(fire_event)

        fight_event = self._detect_fight(persons, shared.get("poses", []), metadata)
        if fight_event:
            events.append(fight_event)

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
                "zone":          "corridor",
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

        fight_detected  = False
        fight_candidates = []

        if poses:
            fight_detected, fight_candidates = self._pose_fight_check(persons, poses)

        if not fight_detected:
            fight_detected, fight_candidates = self._bbox_fight_check(persons)

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

        best = max(fight_candidates, key=lambda x: x["score"])
        self._mark_event_emitted("fight")
        self._fight_frame_count = 0

        return DetectionEvent(
            event_type="fight",
            confidence=best["confidence"],
            bounding_boxes=[best["p1"].bbox, best["p2"].bbox],
            metadata={
                "person_ids":     [best["p1"].object_id, best["p2"].object_id],
                "detection_mode": best.get("mode", "bbox"),
                "zone":           "corridor",
            },
        )

    def _pose_fight_check(self, persons, poses):
        pose_map   = {p["track_id"]: p["keypoints"] for p in poses
                      if "track_id" in p and "keypoints" in p}
        candidates = []

        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2 = persons[i], persons[j]
                kps1   = pose_map.get(p1.object_id)
                kps2   = pose_map.get(p2.object_id)
                if kps1 is None or kps2 is None:
                    continue

                wrist_speed = self._compute_wrist_speed(p1.object_id, kps1)
                dist        = self.distance_between_centers(p1.center, p2.center)

                if (wrist_speed > self.POSE_WRIST_SPEED_THRESHOLD
                        and dist < self.POSE_PROXIMITY_THRESHOLD):
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
        history = self._pose_history.get(track_id, [])
        if len(history) < 2:
            return 0.0
        prev_kps = history[-2]
        try:
            speeds = []
            for idx in [9, 10]:   # left wrist, right wrist (COCO)
                if len(current_kps) > idx and len(prev_kps) > idx:
                    c = current_kps[idx][:2]
                    p = prev_kps[idx][:2]
                    speeds.append(float(np.hypot(c[0] - p[0], c[1] - p[1])))
            return float(np.mean(speeds)) if speeds else 0.0
        except Exception:
            return 0.0

    def _bbox_fight_check(self, persons):
        candidates = []
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                p1, p2  = persons[i], persons[j]
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