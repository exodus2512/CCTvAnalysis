"""
Model and Tracker Registry for SentinelAI.

Manages zone-specific YOLO models and ByteTrack trackers.

Architecture:
- One YOLO model per zone (loaded once at startup)
- Shared special-purpose models: pose, weapon, fire/smoke
- One tracker per camera (maintains object identity)

Model roles:
    Zone models     → person/vehicle/phone detection per zone
    Pose model      → fight detection + fall detection (all zones)
    Weapon model    → gun/knife/sharp object detection (all zones)
    Fire/smoke model→ fire and smoke detection (all zones)
"""

import os
import logging
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

# ============================================================================
# YOLO CLASS IDs (COCO + custom)
# ============================================================================

# Standard COCO class IDs used across zones
COCO_CLASSES = {
    0:  "person",
    2:  "car",
    3:  "motorcycle",
    5:  "bus",
    7:  "truck",
    43: "knife",
    44: "fork",
    67: "cell phone",
    76: "scissors",
}

# Weapon class IDs from COCO (used as fallback if custom weapon model unavailable)
COCO_WEAPON_CLASSES = {43, 76}           # knife, scissors
VEHICLE_CLASSES     = {2, 3, 5, 7}       # car, motorcycle, bus, truck

# Custom weapon model class IDs (weapon_model.pt)
# These are the class IDs your fine-tuned weapon model outputs.
# Update these to match your actual model's class list.
WEAPON_MODEL_CLASSES = {
    0: "gun",
    1: "knife",
    2: "blade",
    3: "scissors",
}

# Fire/smoke model class IDs (fire_smoke_model.pt)
FIRE_SMOKE_MODEL_CLASSES = {
    0: "fire",
    1: "smoke",
}


# ============================================================================
# ZONE MODEL CONFIGURATION
# ============================================================================

@dataclass
class ZoneModelConfig:
    """Configuration for a zone-specific detection model."""
    model_file: str
    confidence_threshold: float
    classes: list           # YOLO class IDs this zone model should detect
    description: str


# Per-zone primary detection models
# These handle person/vehicle/phone detection for each zone.
# Weapon + fire/smoke + pose are loaded separately and run on ALL zones.
ZONE_MODEL_CONFIGS: Dict[str, ZoneModelConfig] = {
    "outgate": ZoneModelConfig(
        model_file="yolov8n.pt",
        confidence_threshold=0.5,
        classes=[0, 2, 3, 5, 7],           # person + all vehicles
        description="Vehicle + person detection (speed priority)",
    ),
    "corridor": ZoneModelConfig(
        model_file="yolov8s.pt",
        confidence_threshold=0.5,
        classes=[0, 43, 76],                 # person + knife + scissors (COCO fallback)
        description="Person detection (balanced accuracy)",
    ),
    "school_ground": ZoneModelConfig(
        model_file="yolov8s.pt",
        confidence_threshold=0.40,           # Lower threshold for outdoor cameras
        classes=[0, 43, 76],                 # person + knife + scissors (COCO fallback)
        description="Person detection (outdoor, with weapon fallback)",
    ),
    "classroom": ZoneModelConfig(
        model_file="yolov8m.pt",
        confidence_threshold=0.4,
        classes=[0, 67],                     # person + cell phone
        description="Person + phone detection (accuracy priority)",
    ),
}

# ---- Shared model configs (not zone-specific) ----

@dataclass
class SharedModelConfig:
    """Configuration for a shared model used across all zones."""
    model_file: str
    confidence_threshold: float
    description: str
    # class_ids are defined in the model-specific dicts above


SHARED_MODEL_CONFIGS: Dict[str, SharedModelConfig] = {
    "pose": SharedModelConfig(
        model_file="yolov8n-pose.pt",
        confidence_threshold=0.5,
        description="Pose estimation for fight + fall detection (all zones)",
    ),
    "weapon": SharedModelConfig(
        model_file="weapon_model.pt",
        confidence_threshold=0.45,
        description="Fine-tuned weapon detector: gun, knife, blade (all zones)",
    ),
    "gun": SharedModelConfig(
        model_file="gun_model.pt",
        confidence_threshold=0.50,
        description="Specialized gun detector for high-precision gun detection (school_ground priority)",
    ),
    "fire_smoke": SharedModelConfig(
        model_file="fire_smoke_model.pt",
        confidence_threshold=0.45,
        description="Fire and smoke detection (all zones)",
    ),
}


# ============================================================================
# MODEL REGISTRY
# ============================================================================

class ModelRegistry:
    """
    Registry for all YOLO models used by SentinelAI.

    Zone models (one per zone):
        outgate       → yolov8n.pt
        corridor      → yolov8s.pt
        school_ground → yolov8s.pt
        classroom     → yolov8m.pt

    Shared models (loaded once, used by all zones):
        pose       → yolov8n-pose.pt   (fight + fall detection)
        weapon     → weapon_model.pt   (gun/knife detection)
        fire_smoke → fire_smoke_model.pt (fire/smoke detection)

    Fallback: if a model file is missing, falls back to yolov8n.pt.
    Shared models that are missing will return None — the calling detector
    should gracefully degrade to COCO fallback detection.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._zone_models:   Dict[str, Any] = {}
        self._shared_models: Dict[str, Any] = {}
        self._fallback_model = None
        self._initialized = True
        self._load_lock = threading.Lock()

        logging.info("ModelRegistry initialized (zone + shared models)")

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    def _get_model_path(self, model_file: str) -> str:
        """Resolve model file path — local > env dir > ultralytics auto-download."""
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 1. Check worker/models/ subfolder first
        models_dir = os.path.join(base_dir, "models")
        local_path = os.path.join(models_dir, model_file)
        if os.path.exists(local_path):
            return local_path

        # 1b. Check backend/models/ (new monorepo layout)
        parent_models_dir = os.path.abspath(os.path.join(base_dir, "..", "models"))
        parent_path = os.path.join(parent_models_dir, model_file)
        if os.path.exists(parent_path):
            return parent_path

        # 2. Check same directory as registry.py
        flat_path = os.path.join(base_dir, model_file)
        if os.path.exists(flat_path):
            return flat_path

        # 3. Check env-configured model dir
        env_dir = os.getenv("YOLO_MODEL_DIR", "")
        if env_dir:
            env_path = os.path.join(env_dir, model_file)
            if os.path.exists(env_path):
                return env_path

        # 4. Return bare name — ultralytics will auto-download standard models
        return model_file

    def _load_model(self, model_file: str, allow_missing: bool = False) -> Optional[Any]:
        """
        Load a YOLO model by filename.

        Args:
            model_file:    filename, e.g. 'yolov8n.pt' or 'weapon_model.pt'
            allow_missing: if True, return None instead of raising on failure
                           (used for custom models that may not be present yet)
        """
        try:
            from ultralytics import YOLO
            path = self._get_model_path(model_file)
            model = YOLO(path)
            logging.info(f"Loaded model: {model_file}")
            return model
        except Exception as e:
            if allow_missing:
                logging.warning(f"Custom model '{model_file}' not found — will use fallback: {e}")
                return None
            logging.error(f"Failed to load model '{model_file}': {e}")
            return None

    # ------------------------------------------------------------------
    # Zone model access
    # ------------------------------------------------------------------

    def get_model(self, zone: str) -> Any:
        """
        Get the primary YOLO model for a zone.

        Falls back to yolov8n.pt if zone model unavailable.
        """
        with self._load_lock:
            if zone in self._zone_models:
                return self._zone_models[zone]

            config = ZONE_MODEL_CONFIGS.get(zone)
            if not config:
                logging.warning(f"Unknown zone '{zone}' — using fallback model")
                return self._get_fallback()

            model = self._load_model(config.model_file)
            if model is None:
                logging.warning(f"Zone model failed for '{zone}' — using fallback")
                model = self._get_fallback()

            self._zone_models[zone] = model
            return model

    def get_config(self, zone: str) -> ZoneModelConfig:
        """Get ZoneModelConfig for a zone (falls back to corridor config)."""
        return ZONE_MODEL_CONFIGS.get(zone, ZONE_MODEL_CONFIGS["corridor"])

    # ------------------------------------------------------------------
    # Shared model access
    # ------------------------------------------------------------------

    def get_pose_model(self) -> Optional[Any]:
        """
        Get the pose estimation model (yolov8n-pose.pt).

        Used by: fight_detector, fall_detector (all zones).
        Returns None if model file is missing.
        """
        return self._get_shared_model("pose")

    def get_weapon_model(self) -> Optional[Any]:
        """
        Get the weapon detection model (weapon_model.pt).

        Used by: all zones for gun/knife detection.
        Returns None if model file is missing — callers should fall back to
        COCO knife/scissors detection via the zone model.
        """
        return self._get_shared_model("weapon")

    def get_gun_model(self) -> Optional[Any]:
        """
        Get the specialized gun detection model (gun_model.pt).

        Used by: WeaponDetector for high-precision gun detection in school_ground.
        Works alongside weapon_model.pt for dual-model ensemble approach.
        Returns None if model file is missing.
        """
        return self._get_shared_model("gun")

    def get_fire_smoke_model(self) -> Optional[Any]:
        """
        Get the fire/smoke detection model (fire_smoke_model.pt).

        Used by: all zones.
        Returns None if model file is missing.
        """
        return self._get_shared_model("fire_smoke")

    def _get_shared_model(self, key: str) -> Optional[Any]:
        """Load and cache a shared model by key."""
        with self._load_lock:
            if key in self._shared_models:
                return self._shared_models[key]

            config = SHARED_MODEL_CONFIGS.get(key)
            if not config:
                logging.error(f"Unknown shared model key: '{key}'")
                return None

            # Custom models are allowed to be missing (allow_missing=True)
            model = self._load_model(config.model_file, allow_missing=True)
            self._shared_models[key] = model          # Cache even if None
            return model

    # ------------------------------------------------------------------
    # Shared config access
    # ------------------------------------------------------------------

    def get_shared_config(self, key: str) -> Optional[SharedModelConfig]:
        """Get SharedModelConfig for pose/weapon/fire_smoke."""
        return SHARED_MODEL_CONFIGS.get(key)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _get_fallback(self) -> Any:
        """Return (and cache) the yolov8n fallback model."""
        if self._fallback_model is None:
            self._fallback_model = self._load_model("yolov8n.pt")
        return self._fallback_model

    def preload_all_models(self):
        """
        Preload every zone + shared model at startup.

        Call this once before any workers start to avoid cold-start latency.
        """
        logging.info("Preloading all models...")

        for zone in ZONE_MODEL_CONFIGS:
            self.get_model(zone)

        for key in SHARED_MODEL_CONFIGS:
            self._get_shared_model(key)

        loaded_zones   = [z for z, m in self._zone_models.items()   if m is not None]
        loaded_shared  = [k for k, m in self._shared_models.items() if m is not None]
        missing_shared = [k for k, m in self._shared_models.items() if m is None]

        logging.info(f"Zone models loaded   : {loaded_zones}")
        logging.info(f"Shared models loaded : {loaded_shared}")
        if missing_shared:
            logging.warning(
                f"Shared models missing (will use COCO fallback): {missing_shared}"
            )

    def is_shared_model_available(self, key: str) -> bool:
        """Check whether a shared model (pose/weapon/fire_smoke) is loaded."""
        return self._shared_models.get(key) is not None


# ============================================================================
# TRACKER REGISTRY
# ============================================================================

@dataclass
class TrackedObjectData:
    """Standardised data structure for a tracked object leaving the tracker."""
    object_id:    int
    class_id:     int
    class_name:   str
    bbox:         list          # [x1, y1, x2, y2]
    confidence:   float
    motion_vector: tuple = (0.0, 0.0)
    timestamp:    float  = 0.0


class SimpleTracker:
    """
    Centroid-based tracker — fallback when ByteTrack is unavailable.

    Maintains object identity across frames using:
    - Centroid distance (greedy Hungarian-lite matching)
    - Class consistency
    - Configurable max-disappear tolerance
    """

    def __init__(self, max_disappeared: int = 10, max_distance: float = 100.0):
        self._next_id       = 0
        self._objects: Dict[int, dict] = {}
        self._max_disappeared = max_disappeared
        self._max_distance    = max_distance

    def update(self, detections: list) -> list:
        import time
        import numpy as np

        now = time.time()

        if not detections:
            for obj_id in list(self._objects):
                self._objects[obj_id]["disappeared"] += 1
                if self._objects[obj_id]["disappeared"] > self._max_disappeared:
                    del self._objects[obj_id]
            return []

        input_centroids = []
        for det in detections:
            b = det["bbox"]
            input_centroids.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))

        if not self._objects:
            for i, det in enumerate(detections):
                self._register(det, input_centroids[i], now)
        else:
            obj_ids        = list(self._objects.keys())
            obj_centroids  = [self._objects[oid]["centroid"] for oid in obj_ids]

            D = np.zeros((len(obj_ids), len(input_centroids)))
            for i, oc in enumerate(obj_centroids):
                for j, ic in enumerate(input_centroids):
                    D[i, j] = np.hypot(oc[0] - ic[0], oc[1] - ic[1])

            matched_rows, matched_cols = set(), set()
            for idx in np.argsort(D.flatten()):
                r, c = divmod(int(idx), len(input_centroids))
                if r in matched_rows or c in matched_cols:
                    continue
                if D[r, c] > self._max_distance:
                    continue

                oid = obj_ids[r]
                det = detections[c]
                prev = self._objects[oid]["centroid"]
                nc   = input_centroids[c]
                self._objects[oid].update({
                    "centroid":   nc,
                    "bbox":       det["bbox"],
                    "class_name": det["class_name"],
                    "confidence": det["confidence"],
                    "motion":     (nc[0] - prev[0], nc[1] - prev[1]),
                    "timestamp":  now,
                    "disappeared": 0,
                })
                matched_rows.add(r)
                matched_cols.add(c)

            for r in set(range(len(obj_ids))) - matched_rows:
                oid = obj_ids[r]
                self._objects[oid]["disappeared"] += 1
                if self._objects[oid]["disappeared"] > self._max_disappeared:
                    del self._objects[oid]

            for c in set(range(len(input_centroids))) - matched_cols:
                self._register(detections[c], input_centroids[c], now)

        return [
            TrackedObjectData(
                object_id=oid,
                class_id=obj.get("class_id", 0),
                class_name=obj["class_name"],
                bbox=obj["bbox"],
                confidence=obj["confidence"],
                motion_vector=obj.get("motion", (0.0, 0.0)),
                timestamp=obj["timestamp"],
            )
            for oid, obj in self._objects.items()
            if obj["disappeared"] == 0
        ]

    def _register(self, det: dict, centroid: tuple, ts: float):
        self._objects[self._next_id] = {
            "centroid":    centroid,
            "bbox":        det["bbox"],
            "class_name":  det["class_name"],
            "class_id":    det.get("class_id", 0),
            "confidence":  det["confidence"],
            "motion":      (0.0, 0.0),
            "timestamp":   ts,
            "disappeared": 0,
        }
        self._next_id += 1

    def reset(self):
        self._objects.clear()
        self._next_id = 0


class TrackerRegistry:
    """
    Per-camera tracker registry.

    Each camera gets its own tracker instance so object IDs remain
    camera-local.  ByteTrack is used when available; SimpleTracker
    is the fallback.
    """

    _instance = None
    _lock     = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._trackers: Dict[str, Any] = {}
        self._tracker_type = self._detect_tracker_type()
        self._initialized  = True
        self._lock         = threading.Lock()

        logging.info(f"TrackerRegistry initialized (backend: {self._tracker_type})")

    def _detect_tracker_type(self) -> str:
        try:
            from supervision import ByteTrack
            return "bytetrack_sv"
        except ImportError:
            pass
        try:
            from boxmot import BYTETracker
            return "bytetrack_boxmot"
        except ImportError:
            pass
        logging.warning("ByteTrack not available — using SimpleTracker")
        return "simple"

    def _create_tracker(self) -> Any:
        if self._tracker_type == "bytetrack_sv":
            from supervision import ByteTrack
            return ByteTrack()
        if self._tracker_type == "bytetrack_boxmot":
            from boxmot import BYTETracker
            return BYTETracker()
        return SimpleTracker()

    def get_tracker(self, camera_id: str) -> Any:
        with self._lock:
            if camera_id not in self._trackers:
                self._trackers[camera_id] = self._create_tracker()
                logging.info(f"Created tracker for camera: {camera_id}")
            return self._trackers[camera_id]

    def reset_tracker(self, camera_id: str):
        with self._lock:
            if camera_id in self._trackers:
                t = self._trackers[camera_id]
                if hasattr(t, "reset"):
                    t.reset()
                else:
                    self._trackers[camera_id] = self._create_tracker()

    def remove_tracker(self, camera_id: str):
        with self._lock:
            self._trackers.pop(camera_id, None)


# ============================================================================
# GLOBAL REGISTRY ACCESSORS
# ============================================================================

def get_model_registry() -> ModelRegistry:
    """Return the singleton ModelRegistry."""
    return ModelRegistry()


def get_tracker_registry() -> TrackerRegistry:
    """Return the singleton TrackerRegistry."""
    return TrackerRegistry()