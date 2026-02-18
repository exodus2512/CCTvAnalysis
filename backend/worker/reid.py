"""
Cross-Camera Re-Identification Manager for SentinelAI

Assigns a global_person_id to tracked objects across multiple cameras.

Approach:
- Appearance embedding: extract a colour histogram + spatial feature vector
  from each person crop (lightweight, no extra model required).
- Optional: if torchreid or a dedicated Re-ID model is available, use that
  for much better accuracy.
- Gallery: stores (embedding, camera_id, last_seen) per global_person_id.
- Matching: cosine similarity between current embedding and gallery.
- If similarity > threshold → same person → reuse global_person_id.
- If no match → assign new global_person_id.

Cross-camera events:
- When the same global_person_id is seen in two different cameras within
  a configurable time window, enrich events with cross_camera=True and
  the list of cameras the person was seen in.
"""

import os
import time
import logging
import threading
import numpy as np
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

# ── Config ────────────────────────────────────────────────────────────────────
REID_SIMILARITY_THRESHOLD = float(os.getenv("REID_SIMILARITY_THRESHOLD", "0.65"))
REID_GALLERY_TTL          = float(os.getenv("REID_GALLERY_TTL",          "120"))   # seconds
REID_CROSS_CAMERA_WINDOW  = float(os.getenv("REID_CROSS_CAMERA_WINDOW",  "30"))    # seconds


# ============================================================================
# EMBEDDING EXTRACTOR
# ============================================================================

class AppearanceEmbedder:
    """
    Lightweight appearance feature extractor.

    Primary: torchreid OSNet (if available).
    Fallback: colour histogram in HSV space (16×8×8 bins = 1024-dim vector).

    The fallback is fast and runs on CPU with no extra dependencies.
    """

    def __init__(self):
        self._backend = self._init_backend()
        logging.info(f"AppearanceEmbedder: using {self._backend} backend")

    def _init_backend(self) -> str:
        try:
            import torchreid
            self._reid_model = torchreid.utils.FeatureExtractor(
                model_name="osnet_x0_25",
                device="cpu",
            )
            return "torchreid"
        except Exception:
            pass
        return "histogram"

    def extract(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract appearance embedding from a person crop.

        Args:
            crop: BGR image of the person (any size)

        Returns:
            1-D numpy float32 array, or None on failure
        """
        if crop is None or crop.size == 0:
            return None

        try:
            if self._backend == "torchreid":
                return self._torchreid_embed(crop)
            return self._histogram_embed(crop)
        except Exception as e:
            logging.debug(f"AppearanceEmbedder error: {e}")
            return None

    def _torchreid_embed(self, crop: np.ndarray) -> np.ndarray:
        import cv2
        import torch
        resized = cv2.resize(crop, (128, 256))
        features = self._reid_model([resized])
        emb = features[0].cpu().numpy()
        return emb / (np.linalg.norm(emb) + 1e-6)

    def _histogram_embed(self, crop: np.ndarray) -> np.ndarray:
        """
        HSV colour histogram embedding.
        Bins: H=16, S=8, V=8 → 1024-dim vector.
        Normalised to unit length.
        """
        import cv2
        resized = cv2.resize(crop, (64, 128))
        hsv     = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        hist    = cv2.calcHist(
            [hsv], [0, 1, 2],
            None,
            [16, 8, 8],
            [0, 180, 0, 256, 0, 256],
        )
        hist = hist.flatten().astype(np.float32)
        norm = np.linalg.norm(hist)
        return hist / (norm + 1e-6)


# ============================================================================
# GALLERY
# ============================================================================

class PersonGallery:
    """
    Thread-safe gallery of known person appearances.

    Each entry stores:
    - embedding:   appearance feature vector
    - camera_ids:  set of cameras where person was seen
    - last_seen:   timestamp of last sighting
    """

    def __init__(self, ttl: float = REID_GALLERY_TTL):
        self._ttl   = ttl
        self._lock  = threading.Lock()
        self._next_id = 1
        # global_person_id → {embedding, camera_ids, last_seen}
        self._gallery: Dict[int, dict] = {}

    def match_or_register(
        self,
        embedding:  np.ndarray,
        camera_id:  str,
        threshold:  float = REID_SIMILARITY_THRESHOLD,
    ) -> Tuple[int, float]:
        """
        Find the best matching person in the gallery or register a new one.

        Returns:
            (global_person_id, similarity_score)
            If new person: similarity_score = 0.0
        """
        with self._lock:
            self._expire()

            best_id    = None
            best_sim   = 0.0

            for gid, entry in self._gallery.items():
                sim = float(np.dot(embedding, entry["embedding"]))
                if sim > best_sim:
                    best_sim = sim
                    best_id  = gid

            if best_id is not None and best_sim >= threshold:
                # Update existing entry
                entry = self._gallery[best_id]
                # Exponential moving average of embedding
                alpha = 0.3
                entry["embedding"] = (
                    alpha * embedding + (1 - alpha) * entry["embedding"]
                )
                entry["embedding"] /= (np.linalg.norm(entry["embedding"]) + 1e-6)
                entry["camera_ids"].add(camera_id)
                entry["last_seen"] = time.time()
                return best_id, best_sim
            else:
                # Register new person
                new_id = self._next_id
                self._next_id += 1
                self._gallery[new_id] = {
                    "embedding":  embedding.copy(),
                    "camera_ids": {camera_id},
                    "last_seen":  time.time(),
                }
                return new_id, 0.0

    def get_cameras(self, global_person_id: int) -> List[str]:
        """Get all cameras where this person has been seen."""
        with self._lock:
            entry = self._gallery.get(global_person_id)
            return list(entry["camera_ids"]) if entry else []

    def get_last_seen(self, global_person_id: int) -> Optional[float]:
        with self._lock:
            entry = self._gallery.get(global_person_id)
            return entry["last_seen"] if entry else None

    def _expire(self):
        """Remove stale gallery entries (called under lock)."""
        now    = time.time()
        stale  = [gid for gid, e in self._gallery.items()
                  if now - e["last_seen"] > self._ttl]
        for gid in stale:
            del self._gallery[gid]

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._gallery)


# ============================================================================
# REID MANAGER
# ============================================================================

class ReidManager:
    """
    Cross-camera person Re-ID manager.

    Called by worker.py after zone processors run (in _format_events step).

    Responsibilities:
    1. Extract appearance embeddings for person bboxes in each event
    2. Match/register in gallery → assign global_person_id
    3. Enrich event dicts with global_person_id + cross_camera metadata
    4. Flag events where same person seen in multiple cameras recently
    """

    def __init__(self):
        self._embedder = AppearanceEmbedder()
        self._gallery  = PersonGallery(ttl=REID_GALLERY_TTL)

        # camera_id → [(global_person_id, timestamp)]
        self._camera_sightings: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
        self._lock = threading.Lock()

        logging.info("ReidManager ready")

    def enrich_events(
        self,
        events:          List[Dict],
        tracked_objects: List[Any],    # List[TrackedObject]
        camera_id:       str,
        frame:           Optional[np.ndarray] = None,
    ) -> List[Dict]:
        """
        Enrich event dicts with Re-ID information.

        Args:
            events:          Formatted event dicts from DetectionPipeline
            tracked_objects: TrackedObject list from this frame
            camera_id:       Camera that produced these events
            frame:           Optional — needed to extract crop for embedding.
                             If None, Re-ID still works but with less accuracy.

        Returns:
            events with added fields:
                global_person_id: int | None
                cross_camera:     bool
                seen_in_cameras:  List[str]
        """
        if not events:
            return events

        # Build a map: object_id → TrackedObject (for crop extraction)
        obj_map = {obj.object_id: obj for obj in tracked_objects}

        for event in events:
            person_id = event.get("metadata", {}).get("person_id")
            if person_id is None:
                # Try to infer from person_ids list (fight events)
                person_ids = event.get("metadata", {}).get("person_ids", [])
                person_id  = person_ids[0] if person_ids else None

            if person_id is None:
                event.setdefault("global_person_id", None)
                event.setdefault("cross_camera", False)
                event.setdefault("seen_in_cameras", [camera_id])
                continue

            tracked_obj = obj_map.get(person_id)
            embedding   = self._get_embedding(frame, tracked_obj)

            if embedding is None:
                event.setdefault("global_person_id", None)
                event.setdefault("cross_camera", False)
                event.setdefault("seen_in_cameras", [camera_id])
                continue

            global_id, sim = self._gallery.match_or_register(embedding, camera_id)
            cameras_seen   = self._gallery.get_cameras(global_id)
            cross_camera   = len(cameras_seen) > 1

            event["global_person_id"] = global_id
            event["cross_camera"]     = cross_camera
            event["seen_in_cameras"]  = cameras_seen

            if cross_camera:
                logging.info(
                    f"Re-ID: global_person_id={global_id} seen in "
                    f"{cameras_seen} (sim={sim:.2f})"
                )
                event["severity_score"] = min(
                    1.0, event.get("severity_score", event["confidence"]) * 1.3
                )

            # Record sighting
            with self._lock:
                self._camera_sightings[camera_id].append((global_id, time.time()))
                # Trim old sightings
                cutoff = time.time() - REID_CROSS_CAMERA_WINDOW
                self._camera_sightings[camera_id] = [
                    (gid, ts) for gid, ts in self._camera_sightings[camera_id]
                    if ts > cutoff
                ]

        return events

    def _get_embedding(
        self,
        frame:       Optional[np.ndarray],
        tracked_obj: Optional[Any],
    ) -> Optional[np.ndarray]:
        """Extract embedding from person crop."""
        if tracked_obj is None:
            return None

        if frame is not None:
            try:
                x1, y1, x2, y2 = tracked_obj.bbox
                x1, y1 = max(0, x1), max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    return self._embedder.extract(crop)
            except Exception:
                pass

        # Fallback: embed the bbox coordinates as a position feature
        # (weaker but better than nothing when frame not available)
        bbox = np.array(tracked_obj.bbox, dtype=np.float32)
        bbox /= (np.linalg.norm(bbox) + 1e-6)
        return bbox

    def get_cross_camera_persons(
        self,
        window_seconds: float = REID_CROSS_CAMERA_WINDOW,
    ) -> List[Dict]:
        """
        Get all persons currently seen in more than one camera.

        Returns list of:
        {
            global_person_id: int,
            cameras:          List[str],
            last_seen:        float,
        }
        """
        now    = time.time()
        result = []

        with self._lock:
            # Build recent sightings across cameras
            recent_by_person: Dict[int, set] = defaultdict(set)
            for cam_id, sightings in self._camera_sightings.items():
                for gid, ts in sightings:
                    if now - ts <= window_seconds:
                        recent_by_person[gid].add(cam_id)

        for gid, cams in recent_by_person.items():
            if len(cams) > 1:
                result.append({
                    "global_person_id": gid,
                    "cameras":          list(cams),
                    "last_seen":        self._gallery.get_last_seen(gid),
                })

        return result

    @property
    def gallery_size(self) -> int:
        return self._gallery.size