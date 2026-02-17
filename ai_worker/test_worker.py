
import os
import cv2
import time
import numpy as np
import requests
import base64
import logging
from worker import load_yolov8, detect_fight, detect_gate_accident, detect_intrusion, detect_abandoned_object, detect_fire_smoke, detect_exam_malpractice

# Config (copy from worker.py or set defaults)
FRAME_FPS = int(os.getenv("FRAME_FPS", 5))
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/event")
TENANT_ID = os.getenv("TENANT_ID", "school1")
CAMERA_ID = os.getenv("CAMERA_ID", "cam1")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def encode_frame(frame):
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')

def send_event(event):
    try:
        resp = requests.post(BACKEND_URL, json=event, timeout=2)
        logging.info(f"Event sent: {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to send event: {e}")

def event_worker_from_video(event_type, video_path):
    model = load_yolov8()
    logging.info(f"{event_type.capitalize()} detection worker started (video mode).")
    detect_map = {
        "fight": detect_fight,
        "gate_accident": detect_gate_accident,
        "intrusion": detect_intrusion,
        "abandoned_object": detect_abandoned_object,
        "fire_smoke": detect_fire_smoke,
        "exam_malpractice": detect_exam_malpractice
    }

    if not os.path.exists(video_path):
        logging.error(f"Video file not found: {video_path}")
        return
    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
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
            logging.info(f"{event_type.replace('_', ' ').capitalize()} detected (video): {event}")
            send_event(event)
        frame_idx += 1
        time.sleep(1.0 / FRAME_FPS)
    cap.release()
    logging.info(f"{event_type.capitalize()} detection worker stopped (video mode).")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python test_worker.py <event_type> <video_path>")
    else:
        event_type = sys.argv[1]
        video_path = sys.argv[2]
        event_worker_from_video(event_type, video_path)


