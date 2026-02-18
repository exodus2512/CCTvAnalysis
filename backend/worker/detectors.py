"""
Shared Detectors for SentinelAI

Three detector classes used across ALL zones:
- WeaponDetector    : gun, knife, blade (custom model + COCO fallback)
- FireSmokeDetector : fire and smoke (custom model)
- PoseDetector      : human pose keypoints for fight/fall detection

All detectors are stateless per-frame — they just take a frame, run
inference, and return structured results. Temporal logic stays in
zone processors.
"""

import os
import logging
import traceback
import numpy as np
from typing import List, Dict, Any, Optional


# ============================================================================
# MODEL AVAILABILITY FLAGS (checked once at module load)
# ============================================================================
_FIRE_SMOKE_MODEL_CHECKED = False
_FIRE_SMOKE_MODEL_AVAILABLE = False


# ============================================================================
# WEAPON DETECTOR
# ============================================================================

class WeaponDetector:
    """
    Detects weapons (gun, knife, blade, scissors) in a frame.

    Primary: custom weapon_model.pt
    Fallback: COCO knife(43) / scissors(76) via zone model
              (fallback is handled in zone processors, NOT here)

    Returns: list of {class_name, confidence, bbox}
    
    Robustness:
    - Wraps inference in structured try/except with full traceback
    - Disables itself after repeated failures (default: 3)
    - Never crashes the worker thread
    """

    # Custom weapon model class IDs (must match weapon_model.pt training)
    WEAPON_CLASS_MAP = {
        0: "gun",
        1: "knife",
        2: "blade",
        3: "scissors",
    }
    
    # Gun model class IDs (gun_model.pt - typically single-class or limited classes)
    GUN_CLASS_MAP = {
        0: "gun",
    }

    MAX_CONSECUTIVE_FAILURES = 3
    
    # ─── FALSE POSITIVE FILTERS ───────────────────────────────────────────────
    MAX_BOX_AREA_RATIO = 0.40       # Discard boxes >40% of frame (suspicious)
    MIN_CONFIDENCE_THRESHOLD = 0.30  # Base filter; zone-level thresholds apply later
    MAX_WEAPONS_PER_FRAME = 3        # Limit detections per frame (increased for testing)

    def __init__(self, registry):
        """
        Args:
            registry: ModelRegistry instance
        
        Loads BOTH weapon_model.pt and gun_model.pt for ensemble detection:
        - weapon_model: catches guns, knives, blades, scissors
        - gun_model: specialized high-precision gun detection
        """
        self._weapon_model = registry.get_weapon_model()
        self._gun_model = registry.get_gun_model()
        self._config = registry.get_shared_config("weapon")
        self._consecutive_failures = 0
        self._disabled = False

        if self._weapon_model is None:
            logging.warning(
                "WeaponDetector: weapon_model.pt not found. "
                "Zone processors will fall back to COCO knife/scissors."
            )
        else:
            logging.info("WeaponDetector: weapon model loaded (guns, knives, blades)")
        
        if self._gun_model is None:
            logging.warning(
                "WeaponDetector: gun_model.pt not found. "
                "Using weapon_model.pt only for gun detection."
            )
        else:
            logging.info("WeaponDetector: gun model loaded (specialized gun detection)")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run weapon detection on a frame using BOTH models (ensemble approach).
        
        Strategy:
        - weapon_model: general detection of guns, knives, blades, scissors
        - gun_model: specialized gun detection (higher precision for guns)
        - If either model detects a gun → include in results
        - Deduplicate overlapping detections from both models
        - Apply false positive filters: area, confidence, max count

        Returns:
            List of dicts: [{class_name, confidence, bbox}, ...]
            Empty list if models not loaded, disabled, or no weapons found.
        """
        if self._disabled:
            return []
        
        if self._weapon_model is None and self._gun_model is None:
            return []

        # Use higher threshold to reduce false positives (override via env if needed)
        min_conf = float(os.getenv("WEAPON_MIN_CONFIDENCE", str(self.MIN_CONFIDENCE_THRESHOLD)))
        conf_thresh = max(
            self._config.confidence_threshold if self._config else 0.45,
            min_conf
        )
        
        # Get frame dimensions for area filtering
        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_h * frame_w
        max_box_area = frame_area * self.MAX_BOX_AREA_RATIO
        
        detections = []

        try:
            # ──── Run weapon_model.pt (catches all weapon types) ────
            if self._weapon_model:
                detections.extend(
                    self._run_model(self._weapon_model, frame, self.WEAPON_CLASS_MAP, conf_thresh, max_box_area)
                )
            
            # ──── Run gun_model.pt (specialized, high-precision gun detection) ────
            if self._gun_model:
                gun_detections = self._run_model(self._gun_model, frame, self.GUN_CLASS_MAP, conf_thresh, max_box_area)
                detections.extend(gun_detections)
            
            # ──── Deduplicate: remove overlapping detections from same class ────
            detections = self._deduplicate_detections(detections)
            
            # ──── Limit max weapons per frame (prevent flooding) ────
            if len(detections) > self.MAX_WEAPONS_PER_FRAME:
                # Keep highest confidence detections
                detections.sort(key=lambda x: x["confidence"], reverse=True)
                detections = detections[:self.MAX_WEAPONS_PER_FRAME]
                logging.debug(f"WeaponDetector: capped to {self.MAX_WEAPONS_PER_FRAME} detections")
            
            # Reset failure counter on success
            self._consecutive_failures = 0
            return detections

        except Exception as e:
            self._consecutive_failures += 1
            logging.error(
                f"WeaponDetector inference error ({self._consecutive_failures}/{self.MAX_CONSECUTIVE_FAILURES}): {e}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            
            if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._disabled = True
                logging.error(
                    "WeaponDetector DISABLED after repeated failures. "
                    "Zone processors will use COCO fallback."
                )
            
            return []
    
    def _run_model(
        self,
        model: Any,
        frame: np.ndarray,
        class_map: Dict[int, str],
        conf_thresh: float,
        max_box_area: float = None,
    ) -> List[Dict[str, Any]]:
        """Run a single model and extract detections with area filtering."""
        detections = []
        results = model(frame, verbose=False)
        
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                xyxy = boxes.xyxy[i].cpu().numpy().astype(int).tolist()
                
                class_name = class_map.get(cls_id)
                if class_name is None:
                    continue
                if conf < conf_thresh:
                    continue
                
                # ─── AREA FILTER: Discard suspiciously large boxes ───
                if max_box_area is not None:
                    x1, y1, x2, y2 = xyxy
                    box_area = (x2 - x1) * (y2 - y1)
                    if box_area > max_box_area:
                        logging.debug(
                            f"WeaponDetector: discarding {class_name} box - "
                            f"area {box_area:.0f} > max {max_box_area:.0f} (full-frame false positive)"
                        )
                        continue
                
                detections.append({
                    "class_name": class_name,
                    "confidence": conf,
                    "bbox": xyxy,
                    "class_id": cls_id,
                })
        
        return detections
    
    def _deduplicate_detections(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate/overlapping detections from same class.
        
        If two detections of the same class overlap, keep the higher confidence one.
        """
        if not detections:
            return []
        
        # Group by class
        by_class = {}
        for det in detections:
            cls = det["class_name"]
            if cls not in by_class:
                by_class[cls] = []
            by_class[cls].append(det)
        
        # Deduplicate within each class
        dedup = []
        for cls, dets in by_class.items():
            # Sort by confidence (highest first)
            dets.sort(key=lambda x: x["confidence"], reverse=True)
            
            # Keep high-confidence detections, skip overlapping lower-confidence ones
            for det in dets:
                # Check if this detection overlaps significantly with any kept detection
                overlaps = False
                for kept_det in dedup:
                    if kept_det["class_name"] == cls:
                        iou = self._compute_iou(det["bbox"], kept_det["bbox"])
                        if iou > 0.3:  # Significant overlap threshold
                            overlaps = True
                            break
                
                if not overlaps:
                    dedup.append(det)
        
        return dedup
    
    def _compute_iou(self, box1: List[int], box2: List[int]) -> float:
        """Compute IoU between two bounding boxes."""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        inter_xmin = max(x1_min, x2_min)
        inter_ymin = max(y1_min, y2_min)
        inter_xmax = min(x1_max, x2_max)
        inter_ymax = min(y1_max, y2_max)
        
        if inter_xmax < inter_xmin or inter_ymax < inter_ymin:
            return 0.0
        
        inter_area = (inter_xmax - inter_xmin) * (inter_ymax - inter_ymin)
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0.0

    @property
    def is_available(self) -> bool:
        return (self._weapon_model is not None or self._gun_model is not None) and not self._disabled
    
    @property
    def is_disabled(self) -> bool:
        return self._disabled
    
    def reset(self):
        """Re-enable detector after being disabled."""
        self._disabled = False
        self._consecutive_failures = 0
        logging.info("WeaponDetector: reset and re-enabled")


# ============================================================================
# FIRE / SMOKE DETECTOR
# ============================================================================

def _check_fire_smoke_model_once(registry) -> bool:
    """
    Check fire_smoke_model availability ONCE at startup.
    Logs warning only on first check.
    """
    global _FIRE_SMOKE_MODEL_CHECKED, _FIRE_SMOKE_MODEL_AVAILABLE
    
    if _FIRE_SMOKE_MODEL_CHECKED:
        return _FIRE_SMOKE_MODEL_AVAILABLE
    
    _FIRE_SMOKE_MODEL_CHECKED = True
    
    # Check if model file exists
    model_path = registry._get_model_path("fire_smoke_model.pt") if hasattr(registry, '_get_model_path') else None
    if model_path and os.path.exists(model_path):
        _FIRE_SMOKE_MODEL_AVAILABLE = True
        logging.info("FireSmokeDetector: fire_smoke_model.pt found")
    else:
        _FIRE_SMOKE_MODEL_AVAILABLE = False
        logging.warning(
            "FireSmokeDetector: fire_smoke_model.pt not found. "
            "Fire/smoke detection disabled globally (this message logs once)."
        )
    
    return _FIRE_SMOKE_MODEL_AVAILABLE


class FireSmokeDetector:
    """
    Detects fire and smoke in a frame.

    Uses fire_smoke_model.pt.
    No COCO fallback — if model missing, fire/smoke detection is disabled.

    Returns: list of {class_name, confidence, bbox}
             class_name is "fire" or "smoke"
    
    Model availability is checked ONCE globally at startup.
    No repeated warnings are logged per camera.
    """

    FIRE_SMOKE_CLASS_MAP = {
        0: "fire",
        1: "smoke",
    }

    def __init__(self, registry):
        # Use global check — only logs warning once
        model_available = _check_fire_smoke_model_once(registry)
        
        if model_available:
            self._model  = registry.get_fire_smoke_model()
            self._config = registry.get_shared_config("fire_smoke")
            if self._model:
                logging.info("FireSmokeDetector: fire/smoke model loaded")
        else:
            self._model = None
            self._config = None
            # No warning here — already logged by _check_fire_smoke_model_once

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run fire/smoke detection on a frame.

        Returns:
            List of dicts: [{class_name, confidence, bbox}, ...]
        """
        if self._model is None:
            return []

        conf_thresh = self._config.confidence_threshold if self._config else 0.45

        try:
            results    = self._model(frame, verbose=False)
            detections = []

            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for i in range(len(boxes)):
                    cls_id = int(boxes.cls[i].item())
                    conf   = float(boxes.conf[i].item())
                    xyxy   = boxes.xyxy[i].cpu().numpy().astype(int).tolist()

                    class_name = self.FIRE_SMOKE_CLASS_MAP.get(cls_id)
                    if class_name is None:
                        continue
                    if conf < conf_thresh:
                        continue

                    detections.append({
                        "class_name": class_name,
                        "confidence": conf,
                        "bbox":       xyxy,
                        "class_id":   cls_id,
                    })

            return detections

        except Exception as e:
            logging.error(f"FireSmokeDetector inference error: {e}")
            return []

    @property
    def is_available(self) -> bool:
        return self._model is not None


# ============================================================================
# POSE DETECTOR
# ============================================================================

class PoseDetector:
    """
    Estimates human pose keypoints using yolov8n-pose.pt.

    Returns per-person keypoints in COCO format (17 keypoints):
        0:  nose
        1:  left_eye       2:  right_eye
        3:  left_ear       4:  right_ear
        5:  left_shoulder  6:  right_shoulder
        7:  left_elbow     8:  right_elbow
        9:  left_wrist     10: right_wrist
        11: left_hip       12: right_hip
        13: left_knee      14: right_knee
        15: left_ankle     16: right_ankle

    Output used by:
        - FightDetector (wrist velocity + proximity)
        - FallDetector  (hip/shoulder torso angle)
    """

    def __init__(self, registry):
        self._model  = registry.get_pose_model()
        self._config = registry.get_shared_config("pose")

        if self._model is None:
            logging.warning(
                "PoseDetector: yolov8n-pose.pt not found. "
                "Pose-based fight/fall detection disabled — bbox heuristics used."
            )
        else:
            logging.info("PoseDetector: pose model loaded")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run pose estimation on a frame.

        Returns:
            List of dicts per person:
            {
                "track_id":  int or None,   # Matched to tracker ID where possible
                "bbox":      [x1,y1,x2,y2],
                "confidence": float,
                "keypoints": [               # 17 × [x, y, visibility]
                    [x, y, vis],
                    ...
                ]
            }
        """
        if self._model is None:
            return []

        conf_thresh = self._config.confidence_threshold if self._config else 0.50

        try:
            results = self._model(frame, verbose=False)
            poses   = []

            for result in results:
                boxes = result.boxes
                kps   = result.keypoints

                if boxes is None or kps is None:
                    continue

                for i in range(len(boxes)):
                    conf = float(boxes.conf[i].item())
                    if conf < conf_thresh:
                        continue

                    xyxy = boxes.xyxy[i].cpu().numpy().astype(int).tolist()

                    # keypoints shape: (N, 17, 3) — x, y, visibility
                    kp_data = kps.data[i].cpu().numpy().tolist()   # 17 × [x, y, vis]

                    # track_id: YOLOv8 pose doesn't natively assign tracker IDs.
                    # We match by bbox center proximity to tracked_objects in zone processor.
                    # Set to None here; zone processors correlate using bbox overlap.
                    track_id = None
                    if boxes.id is not None:
                        try:
                            track_id = int(boxes.id[i].item())
                        except Exception:
                            pass

                    poses.append({
                        "track_id":   track_id,
                        "bbox":       xyxy,
                        "confidence": conf,
                        "keypoints":  kp_data,
                    })

            # If pose model returned no track IDs (common),
            # assign pseudo-IDs based on detection order.
            # Zone processors should refine this with IoU matching.
            for idx, pose in enumerate(poses):
                if pose["track_id"] is None:
                    pose["track_id"] = -(idx + 1)   # negative = unmatched

            return poses

        except Exception as e:
            logging.error(f"PoseDetector inference error: {e}")
            return []

    @staticmethod
    def detect_person_collapse(
        curr_keypoints: List[List[float]],
        prev_keypoints: List[List[float]] = None,
    ) -> Dict[str, float]:
        """
        Detect if person has collapsed or fallen using skeleton geometry.
        
        Used for accident detection: if person falls during vehicle proximity → hit
        
        Args:
            curr_keypoints: Current frame keypoints (17 × [x, y, visibility])
            prev_keypoints: Previous frame keypoints (optional, for change detection)
        
        Returns:
            {
                "is_collapsed": bool,
                "confidence": float (0.0-1.0),
                "reasons": [list of detected issues],
                "height_ratio": float,  # Current / normal height
            }
        """
        if not curr_keypoints or len(curr_keypoints) < 17:
            return {"is_collapsed": False, "confidence": 0.0, "reasons": []}
        
        # COCO keypoint indices
        NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
        L_SHOULDER, R_SHOULDER = 5, 6
        L_ELBOW, R_ELBOW = 7, 8
        L_WRIST, R_WRIST = 9, 10
        L_HIP, R_HIP = 11, 12
        L_KNEE, R_KNEE = 13, 14
        L_ANKLE, R_ANKLE = 15, 16
        
        reasons = []
        scores = []
        
        # Extract coordinates (skip visibility for simplicity)
        def get_point(kp_idx):
            kp = curr_keypoints[kp_idx]
            return (kp[0], kp[1]) if len(kp) >= 2 else None
        
        nose = get_point(NOSE)
        shoulders = [get_point(L_SHOULDER), get_point(R_SHOULDER)]
        hips = [get_point(L_HIP), get_point(R_HIP)]
        ankles = [get_point(L_ANKLE), get_point(R_ANKLE)]
        
        if not all([nose, all(shoulders), all(hips), all(ankles)]):
            return {"is_collapsed": False, "confidence": 0.0, "reasons": ["incomplete_keypoints"]}
        
        # 1. Check body height collapse
        # Normal standing: head to ankle distance = 80-90% of image height
        # Collapsed: head near ground = < 30% distance
        head_y = nose[1]
        avg_ankle_y = (ankles[0][1] + ankles[1][1]) / 2.0
        height = abs(avg_ankle_y - head_y)
        
        # Estimate normal height (rough: shoulder-ankle * 1.5)
        shoulder_y = (shoulders[0][1] + shoulders[1][1]) / 2.0
        torso_length = abs(shoulder_y - head_y)
        normal_height = torso_length * 2.5  # Rough estimate of full body height
        
        height_ratio = height / normal_height if normal_height > 0 else 0.0
        
        if height_ratio < 0.4:
            reasons.append("significant_height_collapse")
            scores.append(0.8)
        
        # 2. Check head-to-hip angle (torso collapse)
        # Normal: significant vertical distance
        # Collapsed: head and hip at similar y level
        hip_y = (hips[0][1] + hips[1][1]) / 2.0
        head_to_hip_dist = abs(hip_y - head_y)
        
        if head_to_hip_dist < 30:  # Head and hip too close
            reasons.append("head_hip_collapse")
            scores.append(0.9)
        
        # 3. Check shoulder position (should be above hips in normal posture)
        # If shoulders below hips or at same level = bending/falling
        shoulder_y = (shoulders[0][1] + shoulders[1][1]) / 2.0
        if shoulder_y >= hip_y:
            reasons.append("shoulder_below_hip")
            scores.append(0.85)
        
        # 4. Check for large changes from previous frame (sudden collapse)
        if prev_keypoints and len(prev_keypoints) >= 17:
            prev_nose = (prev_keypoints[NOSE][0], prev_keypoints[NOSE][1])
            prev_shoulder_y = (prev_keypoints[L_SHOULDER][1] + prev_keypoints[R_SHOULDER][1]) / 2.0
            prev_head_to_hip = abs(
                (prev_keypoints[L_HIP][1] + prev_keypoints[R_HIP][1]) / 2.0 - prev_keypoints[NOSE][1]
            )
            
            # Sudden height change
            height_change = abs(height_ratio - (prev_head_to_hip / normal_height))
            if height_change > 0.3:
                reasons.append("sudden_height_change")
                scores.append(0.85)
        
        # Compute final confidence
        confidence = max(scores) if scores else 0.0
        is_collapsed = confidence > 0.6
        
        return {
            "is_collapsed": is_collapsed,
            "confidence": confidence,
            "reasons": reasons,
            "height_ratio": height_ratio,
        }

    @staticmethod
    def detect_person_down(
        curr_keypoints: List[List[float]],
    ) -> float:
        """
        Detect if person is lying on ground (all keypoints near ground level).
        
        Returns: confidence (0.0-1.0) that person is on ground
        """
        if not curr_keypoints or len(curr_keypoints) < 17:
            return 0.0
        
        # Extract y-coordinates
        y_coords = []
        for kp in curr_keypoints:
            if len(kp) >= 2 and kp[2] > 0.3:  # visibility > 0.3
                y_coords.append(kp[1])
        
        if len(y_coords) < 10:
            return 0.0
        
        # If all keypoints are clustered in bottom portion of frame
        y_mean = np.mean(y_coords)
        y_std = np.std(y_coords)
        
        # Person on ground: all y coords near same level (low std), high y value
        if y_std < 50 and y_mean > 0.6:  # Rough estimate: bottom 40% of image
            return 0.9
        
        return 0.0

    @property
    def is_available(self) -> bool:
        return self._model is not None


# ============================================================================
# POSE ↔ TRACK MATCHING UTILITY
# ============================================================================

def match_poses_to_tracks(
    poses:           List[Dict],
    tracked_objects: List[Any],
    iou_threshold:   float = 0.30,
) -> List[Dict]:
    """
    Match pose detections to tracked objects by bbox IoU.

    Pose detector doesn't always know tracker IDs. This utility assigns
    the closest TrackedObject.object_id to each pose.

    Called by zone processors before using pose data for fight/fall logic.

    Args:
        poses:           Output of PoseDetector.detect()
        tracked_objects: List of TrackedObject from the tracker
        iou_threshold:   Minimum IoU to accept a match

    Returns:
        poses with "track_id" updated to matched TrackedObject.object_id
    """
    import numpy as np

    def _iou(b1, b2):
        x1 = max(b1[0], b2[0]); y1 = max(b1[1], b2[1])
        x2 = min(b1[2], b2[2]); y2 = min(b1[3], b2[3])
        inter = max(0, x2-x1) * max(0, y2-y1)
        a1    = (b1[2]-b1[0]) * (b1[3]-b1[1])
        a2    = (b2[2]-b2[0]) * (b2[3]-b2[1])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    for pose in poses:
        best_id   = pose["track_id"]    # keep existing if already valid
        best_iou  = iou_threshold
        p_bbox    = pose["bbox"]

        for obj in tracked_objects:
            if obj.class_name != "person":
                continue
            score = _iou(p_bbox, obj.bbox)
            if score > best_iou:
                best_iou = score
                best_id  = obj.object_id

        pose["track_id"] = best_id

    return poses