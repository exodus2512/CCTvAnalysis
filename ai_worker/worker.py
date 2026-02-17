import os
import cv2
import time
import numpy as np
import redis
import base64
import logging
import requests
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Config
FRAME_FPS = int(os.getenv("FRAME_FPS", 5))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CAMERA_URL = os.getenv("CAMERA_URL", "0")  # Default to webcam
QUEUE_NAME = os.getenv("FRAME_QUEUE", "frames")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/event")
TENANT_ID = os.getenv("TENANT_ID", "school1")
CAMERA_ID = os.getenv("CAMERA_ID", "cam1")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def connect_redis():
    """
    Try to connect to Redis. If unavailable (common on local dev),
    return None so callers can gracefully fall back to direct camera mode.
    """
    try:
        r = redis.Redis.from_url(REDIS_URL)
        # Light ping to validate connection
        r.ping()
        logging.info(f"Connected to Redis at {REDIS_URL}")
        return r
    except Exception as e:
        logging.warning(
            f"Redis not available at {REDIS_URL} ({e}). "
            "Falling back to in-process camera mode."
        )
        return None

def encode_frame(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')

def decode_frame(frame_data):
    img_bytes = base64.b64decode(frame_data)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

# --- RTSP Ingest (unchanged) ---
def stream_frames(rtsp_url=CAMERA_URL, fps=FRAME_FPS):
    # Try camera indexes 0-3, use first available
    cap = None
    for idx in range(4):
        test_cap = cv2.VideoCapture(idx)
        if test_cap.isOpened():
            cap = test_cap
            logging.info(f"Using camera index {idx} for frame ingest.")
            break
        test_cap.release()
    if cap is None:
        logging.error("No available camera found (indexes 0-3). Exiting.")
        return
    r = connect_redis()
    if r is None:
        logging.error(
            "Redis is not available. stream_frames() will exit because it "
            "cannot push frames to a queue. Either start Redis or run "
            "'python worker.py worker <event_type>' to process directly from camera."
        )
        cap.release()
        return
    frame_count = 0
    logging.info(f"Starting frame ingest at {fps} FPS")
    while True:
        ret, frame = cap.read()
        if not ret:
            logging.warning("Failed to read frame. Exiting.")
            break
        # Encode frame as base64 JPEG
        frame_data = encode_frame(frame)
        # Push to Redis queue
        r.lpush(QUEUE_NAME, frame_data)
        frame_count += 1
        logging.info(f"Frame {frame_count} pushed to queue '{QUEUE_NAME}'")
        time.sleep(1.0 / fps)
    cap.release()
    logging.info("Stream ended.")

# --- Fight Detection Logic ---

# --- Simulated Detection Models ---
def load_yolov8():
    # Placeholder: replace with actual YOLOv8 model loading
    class DummyModel:
        def __call__(self, frame):
            h, w, _ = frame.shape
            # Simulate detection: people, vehicles, objects, smoke, fire
            people = np.random.randint(1, 8)
            vehicles = np.random.randint(0, 2)
            objects = np.random.randint(0, 2)
            smoke = np.random.choice([0, 1], p=[0.95, 0.05])
            fire = np.random.choice([0, 1], p=[0.97, 0.03])
            boxes = {
                "person": [[np.random.randint(0, w//2), np.random.randint(0, h//2), np.random.randint(40, 100), np.random.randint(80, 200)] for _ in range(people)],
                "vehicle": [[np.random.randint(w//2, w-100), np.random.randint(h//2, h-100), np.random.randint(60, 180), np.random.randint(60, 180)] for _ in range(vehicles)],
                "object": [[np.random.randint(0, w-100), np.random.randint(0, h-100), np.random.randint(30, 80), np.random.randint(30, 80)] for _ in range(objects)],
                "smoke": smoke,
                "fire": fire
            }
            return boxes
    return DummyModel()

# --- Event Detection Functions ---
def detect_fight(boxes, frame, min_people=3, cluster_thresh=120):
    people_boxes = boxes.get("person", [])
    if len(people_boxes) < min_people:
        return False, 0.0, []
    centers = np.array([[(b[0]+b[2])//2, (b[1]+b[3])//2] for b in people_boxes])
    dists = np.linalg.norm(centers - centers.mean(axis=0), axis=1)
    cluster_score = np.mean(dists)
    fight = cluster_score < cluster_thresh
    confidence = 0.8 if fight else 0.3
    return fight, confidence, people_boxes

def detect_gate_accident(boxes, frame):
    # Simulate: vehicle + person + random impact
    if boxes["vehicle"] and boxes["person"] and np.random.rand() > 0.7:
        return True, 0.85, boxes["vehicle"] + boxes["person"]
    return False, 0.0, []

def detect_intrusion(boxes, frame):
    # Simulate: person in restricted zone after hours
    if boxes["person"] and np.random.rand() > 0.8:
        return True, 0.75, boxes["person"]
    return False, 0.0, []

def detect_abandoned_object(boxes, frame):
    # Simulate: object stationary
    if boxes["object"] and np.random.rand() > 0.85:
        return True, 0.7, boxes["object"]
    return False, 0.0, []

def detect_fire_smoke(boxes, frame):
    # Simulate: smoke or fire
    if boxes["smoke"]:
        return True, 0.8, []
    if boxes["fire"]:
        return True, 0.9, []
    return False, 0.0, []

def detect_exam_malpractice(boxes, frame):
    # Simulate: head pose anomaly, sideways gaze, suspicious hand-object
    if boxes["person"] and np.random.rand() > 0.92:
        return True, 0.7, boxes["person"]
    return False, 0.0, []

def send_event(event):
    try:
        resp = requests.post(BACKEND_URL, json=event, timeout=2)
        logging.info(f"Event sent: {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to send event: {e}")


def event_worker(event_type):
    model = load_yolov8()
    logging.info(f"{event_type.capitalize()} detection worker started.")
    detect_map = {
        "fight": detect_fight,
        "gate_accident": detect_gate_accident,
        "intrusion": detect_intrusion,
        "abandoned_object": detect_abandoned_object,
        "fire_smoke": detect_fire_smoke,
        "exam_malpractice": detect_exam_malpractice
    }

    # Try Redis first; if not available, fall back to reading frames
    # directly from the camera so local dev works without extra infra.
    r = connect_redis()

    # --- Direct camera mode (no Redis) ---
    if r is None:
        cap = None
        for idx in range(4):
            test_cap = cv2.VideoCapture(idx)
            if test_cap.isOpened():
                cap = test_cap
                logging.info(
                    f"Using camera index {idx} for {event_type} detection (direct mode)."
                )
                break
            test_cap.release()
        if cap is None:
            logging.error("No available camera found (indexes 0-3). Exiting worker.")
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                logging.warning("Failed to read frame in direct mode. Exiting worker.")
                break
            boxes = model(frame)
            detect_fn = detect_map.get(event_type)
            if not detect_fn:
                logging.error(f"Unknown event type: {event_type}")
                break
            detected, confidence, used_boxes = detect_fn(boxes, frame)
            if detected:
                event = {
                    "event_id": f"evt_{event_type}_{int(time.time()*1000)}",
                    "tenant_id": TENANT_ID,
                    "camera_id": CAMERA_ID,
                    "event_type": event_type,
                    "confidence": confidence,
                    "timestamp": time.time(),
                    "bounding_boxes": used_boxes,
                    "zone": "Corridor A",
                    "severity_score": confidence,
                }
                logging.info(
                    f"{event_type.replace('_', ' ').capitalize()} detected (direct): {event}"
                )
                send_event(event)
            time.sleep(1.0 / FRAME_FPS)

        cap.release()
        logging.info(f"{event_type.capitalize()} detection worker stopped (direct mode).")
        return

    # --- Redis queue mode (original behavior) ---
    while True:
        frame_data = r.rpop(QUEUE_NAME)
        if not frame_data:
            time.sleep(0.1)
            continue
        frame = decode_frame(frame_data)
        boxes = model(frame)
        detect_fn = detect_map.get(event_type)
        if not detect_fn:
            logging.error(f"Unknown event type: {event_type}")
            break
        detected, confidence, used_boxes = detect_fn(boxes, frame)
        if detected:
            event = {
                "event_id": f"evt_{event_type}_{int(time.time()*1000)}",
                "tenant_id": TENANT_ID,
                "camera_id": CAMERA_ID,
                "event_type": event_type,
                "confidence": confidence,
                "timestamp": time.time(),
                "bounding_boxes": used_boxes,
                "zone": "Corridor A",
                "severity_score": confidence,
            }
            logging.info(
                f"{event_type.replace('_', ' ').capitalize()} detected: {event}"
            )
            send_event(event)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "worker":
        event_type = sys.argv[2]
        event_worker(event_type)
    else:
        stream_frames()
