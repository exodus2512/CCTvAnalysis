import os
import cv2
import time
import numpy as np
import redis
import base64
import logging
import requests
from dotenv import load_dotenv
from collections import deque
from typing import Dict, List, Tuple, Optional

# Load .env
load_dotenv()

# Config
FRAME_FPS = int(os.getenv("FRAME_FPS", 5))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CAMERA_URL = os.getenv("CAMERA_URL", "0")
QUEUE_NAME = os.getenv("FRAME_QUEUE", "frames")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/event")
TENANT_ID = os.getenv("TENANT_ID", "school1")
CAMERA_ID = os.getenv("CAMERA_ID", "cam1")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ============================================================================
# ZONE CONFIGURATION
# ============================================================================
ZONE_TYPES = {
    "outgate": ["vehicle_detected", "gate_accident"],
    "corridor": ["crowd_formation", "fight"],
    "school_ground": ["crowd_formation", "fight"],
    "classroom": ["mobile_usage"],
}

# YOLO class IDs (COCO dataset)
YOLO_CLASSES = {
    0: "person",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    67: "cell phone",
}

VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}

# ============================================================================
# YOLOV8 MODEL LOADING
# ============================================================================
_yolo_model = None

def load_yolov8():
    """Load YOLOv8 model (singleton pattern)."""
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO
            model_path = os.getenv("YOLO_MODEL", "yolov8n.pt")
            _yolo_model = YOLO(model_path)
            logging.info(f"Loaded YOLOv8 model: {model_path}")
        except Exception as e:
            logging.error(f"Failed to load YOLOv8: {e}")
            raise
    return _yolo_model


def run_inference(model, frame) -> Dict[str, List[Dict]]:
    """
    Run YOLOv8 inference and return structured detections.
    
    Returns:
        {
            "person": [{"box": [x1,y1,x2,y2], "confidence": 0.85}, ...],
            "car": [...],
            "cell phone": [...],
            ...
        }
    """
    results = model(frame, verbose=False)
    detections: Dict[str, List[Dict]] = {
        "person": [],
        "car": [],
        "motorcycle": [],
        "bus": [],
        "truck": [],
        "cell phone": [],
    }
    
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            conf = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int).tolist()
            
            class_name = YOLO_CLASSES.get(cls_id)
            if class_name and class_name in detections:
                detections[class_name].append({
                    "box": xyxy,  # [x1, y1, x2, y2]
                    "confidence": conf,
                })
    
    return detections


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def compute_iou(box1: List[int], box2: List[int]) -> float:
    """Compute Intersection over Union between two boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    inter_area = max(0, x2 - x1) * max(0, y2 - y1)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / union_area if union_area > 0 else 0.0


def box_center(box: List[int]) -> Tuple[int, int]:
    """Get center point of a bounding box."""
    return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)


def distance_between_boxes(box1: List[int], box2: List[int]) -> float:
    """Compute Euclidean distance between box centers."""
    c1 = box_center(box1)
    c2 = box_center(box2)
    return np.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)


# ============================================================================
# FRAME HISTORY FOR TEMPORAL ANALYSIS
# ============================================================================
class FrameHistory:
    """Track detections across frames for temporal analysis."""
    
    def __init__(self, max_frames: int = 10):
        self.history: deque = deque(maxlen=max_frames)
        self.crowd_frame_count = 0
        self.fight_frame_count = 0
    
    def add_frame(self, detections: Dict[str, List[Dict]]):
        self.history.append({
            "detections": detections,
            "timestamp": time.time(),
        })
    
    def get_recent_person_positions(self, n_frames: int = 3) -> List[List[Dict]]:
        """Get person detections from recent frames."""
        recent = list(self.history)[-n_frames:]
        return [f["detections"].get("person", []) for f in recent]


# Global frame history per camera
_frame_histories: Dict[str, FrameHistory] = {}

def get_frame_history(camera_id: str) -> FrameHistory:
    if camera_id not in _frame_histories:
        _frame_histories[camera_id] = FrameHistory()
    return _frame_histories[camera_id]


# ============================================================================
# ZONE-BASED DETECTION FUNCTIONS
# ============================================================================

def detect_vehicle(detections: Dict[str, List[Dict]], zone: str) -> Optional[Dict]:
    """
    OUTGATE ZONE: Detect vehicles (car, bus, truck, motorcycle).
    """
    if zone != "outgate":
        return None
    
    all_vehicles = []
    for vtype in VEHICLE_CLASSES:
        all_vehicles.extend(detections.get(vtype, []))
    
    if not all_vehicles:
        return None
    
    # Get highest confidence vehicle
    best = max(all_vehicles, key=lambda x: x["confidence"])
    if best["confidence"] < 0.5:
        return None
    
    return {
        "event_type": "vehicle_detected",
        "confidence": best["confidence"],
        "bounding_boxes": [v["box"] for v in all_vehicles],
    }


def detect_gate_accident(detections: Dict[str, List[Dict]], zone: str) -> Optional[Dict]:
    """
    OUTGATE ZONE: Detect potential accident (vehicle + person in close proximity).
    
    Conditions:
    - Vehicle detected (car/bus/truck/motorcycle)
    - Person detected
    - IoU overlap > 0.1 OR distance < 100 pixels
    """
    if zone != "outgate":
        return None
    
    persons = detections.get("person", [])
    vehicles = []
    for vtype in VEHICLE_CLASSES:
        vehicles.extend(detections.get(vtype, []))
    
    if not persons or not vehicles:
        return None
    
    # Check for close proximity or overlap
    for person in persons:
        for vehicle in vehicles:
            iou = compute_iou(person["box"], vehicle["box"])
            dist = distance_between_boxes(person["box"], vehicle["box"])
            
            # Accident condition: overlap or very close
            if iou > 0.1 or dist < 100:
                avg_conf = (person["confidence"] + vehicle["confidence"]) / 2
                if avg_conf >= 0.5:
                    return {
                        "event_type": "gate_accident",
                        "confidence": avg_conf,
                        "bounding_boxes": [person["box"], vehicle["box"]],
                    }
    
    return None


def detect_crowd_formation(
    detections: Dict[str, List[Dict]], 
    zone: str,
    frame_history: FrameHistory,
    min_people: int = 4,
    cluster_threshold: float = 150.0,
    min_frames: int = 3
) -> Optional[Dict]:
    """
    CORRIDOR/SCHOOL_GROUND ZONE: Detect crowd formation.
    
    Conditions:
    - >= 4 persons detected
    - Bounding boxes clustered spatially (avg distance from centroid < threshold)
    - Sustained for 3+ frames
    """
    if zone not in ("corridor", "school_ground"):
        return None
    
    persons = detections.get("person", [])
    
    if len(persons) < min_people:
        frame_history.crowd_frame_count = 0
        return None
    
    # Check spatial clustering
    centers = np.array([box_center(p["box"]) for p in persons])
    centroid = centers.mean(axis=0)
    distances = np.linalg.norm(centers - centroid, axis=1)
    avg_distance = distances.mean()
    
    if avg_distance > cluster_threshold:
        frame_history.crowd_frame_count = 0
        return None
    
    # Increment sustained frame count
    frame_history.crowd_frame_count += 1
    
    if frame_history.crowd_frame_count < min_frames:
        return None
    
    # Crowd detected
    avg_conf = np.mean([p["confidence"] for p in persons])
    return {
        "event_type": "crowd_formation",
        "confidence": float(avg_conf),
        "bounding_boxes": [p["box"] for p in persons],
    }


def detect_fight(
    detections: Dict[str, List[Dict]], 
    zone: str,
    frame_history: FrameHistory,
    min_people: int = 2,
    overlap_threshold: float = 0.15,
    confidence_threshold: float = 0.6
) -> Optional[Dict]:
    """
    CORRIDOR/SCHOOL_GROUND ZONE: Detect potential fight.
    
    Conditions:
    - >= 2 persons detected
    - Significant overlap between person bounding boxes (IoU > 0.15)
    - Confidence > 0.6
    - Optional: rapid movement between frames
    """
    if zone not in ("corridor", "school_ground"):
        return None
    
    persons = detections.get("person", [])
    
    if len(persons) < min_people:
        frame_history.fight_frame_count = 0
        return None
    
    # Check for overlapping persons
    fighting_pairs = []
    for i in range(len(persons)):
        for j in range(i + 1, len(persons)):
            iou = compute_iou(persons[i]["box"], persons[j]["box"])
            if iou > overlap_threshold:
                avg_conf = (persons[i]["confidence"] + persons[j]["confidence"]) / 2
                if avg_conf >= confidence_threshold:
                    fighting_pairs.append((persons[i], persons[j], avg_conf))
    
    if not fighting_pairs:
        frame_history.fight_frame_count = 0
        return None
    
    # Check for movement between frames (optional enhancement)
    recent_positions = frame_history.get_recent_person_positions(3)
    movement_detected = len(recent_positions) >= 2
    
    frame_history.fight_frame_count += 1
    
    # Best match
    best_pair = max(fighting_pairs, key=lambda x: x[2])
    return {
        "event_type": "fight",
        "confidence": best_pair[2],
        "bounding_boxes": [best_pair[0]["box"], best_pair[1]["box"]],
    }


def detect_mobile_usage(
    detections: Dict[str, List[Dict]], 
    zone: str,
    overlap_threshold: float = 0.05
) -> Optional[Dict]:
    """
    CLASSROOM ZONE: Detect mobile phone usage.
    
    Conditions:
    - Person detected
    - Cell phone detected
    - Phone bounding box overlaps with upper body region of person
    """
    if zone != "classroom":
        return None
    
    persons = detections.get("person", [])
    phones = detections.get("cell phone", [])
    
    if not persons or not phones:
        return None
    
    for person in persons:
        # Define upper body region (top 60% of person box)
        px1, py1, px2, py2 = person["box"]
        upper_body_y2 = py1 + int((py2 - py1) * 0.6)
        upper_body = [px1, py1, px2, upper_body_y2]
        
        for phone in phones:
            iou = compute_iou(upper_body, phone["box"])
            if iou > overlap_threshold or _box_inside(phone["box"], person["box"]):
                avg_conf = (person["confidence"] + phone["confidence"]) / 2
                if avg_conf >= 0.4:
                    return {
                        "event_type": "mobile_usage",
                        "confidence": avg_conf,
                        "bounding_boxes": [person["box"], phone["box"]],
                    }
    
    return None


def _box_inside(inner: List[int], outer: List[int]) -> bool:
    """Check if inner box is mostly inside outer box."""
    ix1, iy1, ix2, iy2 = inner
    ox1, oy1, ox2, oy2 = outer
    return ix1 >= ox1 and iy1 >= oy1 and ix2 <= ox2 and iy2 <= oy2


# ============================================================================
# MAIN DETECTION PIPELINE
# ============================================================================
def detect_all_events(
    detections: Dict[str, List[Dict]], 
    zone: str,
    camera_id: str
) -> List[Dict]:
    """
    Run all relevant detectors for the given zone.
    Returns list of detected events.
    """
    events = []
    frame_history = get_frame_history(camera_id)
    frame_history.add_frame(detections)
    
    # Zone-specific detectors
    if zone == "outgate":
        vehicle = detect_vehicle(detections, zone)
        if vehicle:
            events.append(vehicle)
        
        accident = detect_gate_accident(detections, zone)
        if accident:
            events.append(accident)
    
    elif zone in ("corridor", "school_ground"):
        crowd = detect_crowd_formation(detections, zone, frame_history)
        if crowd:
            events.append(crowd)
        
        fight = detect_fight(detections, zone, frame_history)
        if fight:
            events.append(fight)
    
    elif zone == "classroom":
        mobile = detect_mobile_usage(detections, zone)
        if mobile:
            events.append(mobile)
    
    return events


# ============================================================================
# FRAME ANNOTATION FOR STREAMING
# ============================================================================
def annotate_frame(frame: np.ndarray, detections: Dict[str, List[Dict]], zone: str) -> np.ndarray:
    """Draw bounding boxes and labels on frame."""
    annotated = frame.copy()
    
    colors = {
        "person": (0, 255, 0),      # Green
        "car": (255, 0, 0),          # Blue
        "motorcycle": (255, 0, 0),
        "bus": (255, 0, 0),
        "truck": (255, 0, 0),
        "cell phone": (0, 255, 255), # Yellow
    }
    
    for class_name, dets in detections.items():
        color = colors.get(class_name, (128, 128, 128))
        for det in dets:
            box = det["box"]
            conf = det["confidence"]
            cv2.rectangle(annotated, (box[0], box[1]), (box[2], box[3]), color, 2)
            label = f"{class_name}: {conf:.2f}"
            cv2.putText(annotated, label, (box[0], box[1] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # Zone label
    cv2.putText(annotated, f"Zone: {zone}", (10, 30), 
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    
    # Live indicator
    cv2.circle(annotated, (annotated.shape[1] - 30, 30), 10, (0, 0, 255), -1)
    cv2.putText(annotated, "LIVE", (annotated.shape[1] - 80, 35),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    return annotated


# ============================================================================
# NETWORK AND REDIS UTILITIES
# ============================================================================
def connect_redis():
    """Connect to Redis if available."""
    try:
        r = redis.Redis.from_url(REDIS_URL)
        r.ping()
        logging.info(f"Connected to Redis at {REDIS_URL}")
        return r
    except Exception as e:
        logging.warning(f"Redis not available at {REDIS_URL} ({e}). Falling back to direct mode.")
        return None


def encode_frame(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')


def decode_frame(frame_data):
    img_bytes = base64.b64decode(frame_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


def send_event(event):
    try:
        resp = requests.post(BACKEND_URL, json=event, timeout=2)
        logging.info(f"Event sent: {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to send event: {e}")


# ============================================================================
# MAIN WORKER FUNCTIONS
# ============================================================================
def zone_worker(zone: str, video_path: Optional[str] = None, camera_id: str = CAMERA_ID):
    """
    Main worker that processes frames for a specific zone.
    
    Args:
        zone: Zone type (outgate, corridor, school_ground, classroom)
        video_path: Optional video file path (for testing)
        camera_id: Camera identifier
    """
    model = load_yolov8()
    logging.info(f"Zone worker started for zone='{zone}', camera='{camera_id}'")
    
    # Open video source
    cap = None
    if video_path and os.path.exists(video_path):
        cap = cv2.VideoCapture(video_path)
        logging.info(f"Using video file: {video_path}")
    else:
        # Try webcams
        for idx in range(4):
            test_cap = cv2.VideoCapture(idx)
            if test_cap.isOpened():
                cap = test_cap
                logging.info(f"Using camera index {idx}")
                break
            test_cap.release()
    
    if cap is None or not cap.isOpened():
        logging.error("No video source available. Exiting worker.")
        return
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            # Loop video for testing
            if video_path:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            break
        
        # Run YOLO inference
        detections = run_inference(model, frame)
        
        # Detect events for this zone
        events = detect_all_events(detections, zone, camera_id)
        
        # Send detected events to backend
        for event_data in events:
            event = {
                "event_id": f"evt_{event_data['event_type']}_{int(time.time()*1000)}",
                "tenant_id": TENANT_ID,
                "camera_id": camera_id,
                "zone": zone,
                "event_type": event_data["event_type"],
                "confidence": event_data["confidence"],
                "timestamp": time.time(),
                "bounding_boxes": event_data["bounding_boxes"],
                "severity_score": event_data["confidence"],
            }
            logging.info(f"Event detected: {event_data['event_type']} (conf={event_data['confidence']:.2f})")
            send_event(event)
        
        frame_count += 1
        time.sleep(1.0 / FRAME_FPS)
    
    cap.release()
    logging.info(f"Zone worker stopped for zone='{zone}'")


def stream_frames(rtsp_url=CAMERA_URL, fps=FRAME_FPS):
    """Stream frames to Redis queue."""
    cap = None
    for idx in range(4):
        test_cap = cv2.VideoCapture(idx)
        if test_cap.isOpened():
            cap = test_cap
            logging.info(f"Using camera index {idx} for frame ingest.")
            break
        test_cap.release()
    
    if cap is None:
        logging.error("No available camera found. Exiting.")
        return
    
    r = connect_redis()
    if r is None:
        logging.error("Redis not available. Cannot stream frames.")
        cap.release()
        return
    
    frame_count = 0
    logging.info(f"Starting frame ingest at {fps} FPS")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_data = encode_frame(frame)
        r.lpush(QUEUE_NAME, frame_data)
        frame_count += 1
        logging.info(f"Frame {frame_count} pushed to queue")
        time.sleep(1.0 / fps)
    
    cap.release()


# Legacy compatibility
def event_worker(event_type: str):
    """Legacy worker - maps old event types to zones."""
    zone_map = {
        "fight": "corridor",
        "crowd_formation": "corridor",
        "gate_accident": "outgate",
        "vehicle_detected": "outgate",
        "mobile_usage": "classroom",
        "intrusion": "corridor",
        "abandoned_object": "corridor",
        "exam_malpractice": "classroom",
    }
    zone = zone_map.get(event_type, "corridor")
    zone_worker(zone)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) >= 3:
        if sys.argv[1] == "zone":
            # New zone-based worker: python worker.py zone <zone_type> [video_path]
            zone = sys.argv[2]
            video = sys.argv[3] if len(sys.argv) > 3 else None
            zone_worker(zone, video)
        elif sys.argv[1] == "worker":
            # Legacy: python worker.py worker <event_type>
            event_worker(sys.argv[2])
        else:
            # Direct: python worker.py <zone> <video_path>
            zone_worker(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        stream_frames()
