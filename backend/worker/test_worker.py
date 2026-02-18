"""
Test Worker for SentinelAI - Zone-based Video Processing with New Pipeline

Usage:
    python test_worker.py <zone> <video_path> [camera_id] [--no-preview] [--legacy]
    
Zones:
    - all: Run ALL detectors simultaneously (multi-zone mode)
    - outgate: Vehicle detection, accident detection (yolov8n.pt)
    - corridor: Crowd formation, fight detection (yolov8s.pt)
    - school_ground: Crowd formation, fight detection (yolov8s.pt)
    - classroom: Mobile phone usage detection (yolov8m.pt)

Examples:
    python test_worker.py all "../test_videos/Video Project.mp4"  # All zones
    python test_worker.py corridor "../test_videos/fight.mp4"
    python test_worker.py outgate "../test_videos/gate.mp4" cam_gate1
    python test_worker.py classroom "../test_videos/classroom.mp4" --no-preview

New Architecture:
    YOLO -> Tracker -> Zone Processor -> Temporal Buffer -> Event Engine -> Alert

Flags:
    --no-preview  : Run without video preview window
    --legacy      : Use legacy detection (bypasses new pipeline)
"""

import os
import sys
import cv2
import time
import logging
import requests
from typing import Optional, List, Dict

# Add worker and backend root directories to path for imports
WORKER_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.abspath(os.path.join(WORKER_DIR, ".."))
for path in (WORKER_DIR, BACKEND_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

# Import both new pipeline and legacy functions
from worker import (
    # New pipeline classes
    DetectionPipeline,
    CameraWorker,
    MultiZonePipeline,
    # Legacy functions
    load_yolov8,
    run_inference,
    detect_all_events,
    annotate_frame,
    get_frame_history,
    ZONE_TYPES,
)

# Import registry for model info
try:
    from registry import get_model_registry, ZONE_MODEL_CONFIGS
    HAS_REGISTRY = True
except ImportError:
    HAS_REGISTRY = False
    ZONE_MODEL_CONFIGS = {}

# Config
FRAME_FPS = int(os.getenv("FRAME_FPS", 5))
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/event")
TENANT_ID = os.getenv("TENANT_ID", "school1")

# Setup colored logging
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname:8s}{self.RESET}"
        return super().format(record)

handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter(
    fmt='%(asctime)s %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
))
logging.basicConfig(level=logging.INFO, handlers=[handler])


def send_event(event: dict):
    """Send event to backend."""
    try:
        resp = requests.post(BACKEND_URL, json=event, timeout=5)
        if resp.status_code == 200:
            logging.info(f"✓ Event sent successfully -> {event['event_type']}")
        else:
            logging.warning(f"⚠ Event sent but received status {resp.status_code}")
    except requests.exceptions.Timeout:
        logging.error(f"✗ Backend timeout - event not delivered")
    except requests.exceptions.ConnectionError:
        logging.error(f"✗ Cannot connect to backend at {BACKEND_URL}")
    except Exception as e:
        logging.error(f"✗ Failed to send event: {e}")


def process_video(zone: str, video_path: str, camera_id: str = "cam1", show_preview: bool = True, use_legacy: bool = False):
    """
    Process a video file for zone-based detection.
    
    Args:
        zone: Zone type (outgate, corridor, school_ground, classroom, or "all" for multi-zone)
        video_path: Path to video file
        camera_id: Camera identifier
        show_preview: Whether to show OpenCV preview window
        use_legacy: If True, use legacy detection; else use new pipeline
    """
    if zone.lower() == "all":
        # Multi-zone mode - process ALL detectors
        process_video_multizone(video_path, camera_id, show_preview)
    elif use_legacy:
        process_video_legacy(zone, video_path, camera_id, show_preview)
    else:
        process_video_new_pipeline(zone, video_path, camera_id, show_preview)


def process_video_new_pipeline(zone: str, video_path: str, camera_id: str = "cam1", show_preview: bool = True):
    """
    Process video using the NEW detection pipeline architecture.
    
    Pipeline: YOLO → Tracker → Zone Processor → Temporal Buffer → Events
    """
    if zone not in ZONE_TYPES:
        logging.error(f"Invalid zone '{zone}'. Valid zones: {list(ZONE_TYPES.keys())}")
        return
    
    if not os.path.exists(video_path):
        logging.error(f"Video file not found: {video_path}")
        return
    
    # Get model info
    model_config = ZONE_MODEL_CONFIGS.get(zone) if HAS_REGISTRY else None
    model_file = model_config.model_file if model_config else "yolov8n.pt"
    
    logging.info("="*60)
    logging.info("🎬 SentinelAI Worker Starting (NEW PIPELINE)")
    logging.info("="*60)
    logging.info(f"📍 Zone: {zone}")
    logging.info(f"📹 Video: {os.path.basename(video_path)}")
    logging.info(f"🎯 Camera ID: {camera_id}")
    logging.info(f"🤖 Model: {model_file}")
    logging.info(f"🔍 Events to detect: {', '.join(ZONE_TYPES[zone])}")
    logging.info(f"🔗 Backend: {BACKEND_URL}")
    logging.info("="*60)
    logging.info("Pipeline: YOLO → Tracker → Zone Processor → Temporal Buffer → Events")
    logging.info("="*60)
    
    # Create detection pipeline
    try:
        pipeline = DetectionPipeline(camera_id, zone)
    except Exception as e:
        logging.error(f"Failed to create pipeline: {e}")
        logging.info("Falling back to legacy mode...")
        process_video_legacy(zone, video_path, camera_id, show_preview)
        return
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error(f"Failed to open video: {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS) or FRAME_FPS
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logging.info(f"  Video FPS: {fps:.1f}, Total frames: {total_frames}")
    
    frame_idx = 0
    events_detected = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            # Loop video for continuous testing
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_idx = 0
            continue
        
        # Process frame through the full pipeline
        events = pipeline.process_frame(frame)
        
        # Log detection counts periodically
        if frame_idx % 30 == 0:
            summary = pipeline.get_detections_summary(frame)
            if summary:
                logging.info(f"📈 Frame {frame_idx}: {summary}")
        
        # Send detected events
        for event in events:
            logging.warning(f"🚨 EVENT DETECTED: {event['event_type']} (confidence={event['confidence']:.2f})")
            send_event(event)
            events_detected += 1
        
        # Show preview with annotations
        if show_preview:
            annotated = frame.copy()
            
            # Draw zone and model info
            cv2.putText(annotated, f"Zone: {zone} | Model: {model_file}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Draw event indicator
            if events:
                cv2.putText(annotated, "EVENT DETECTED!", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                
                # Draw bounding boxes
                for event in events:
                    for bbox in event.get("bounding_boxes", []):
                        if len(bbox) == 4:
                            cv2.rectangle(annotated, 
                                         (bbox[0], bbox[1]), (bbox[2], bbox[3]),
                                         (0, 0, 255), 2)
            
            # Status bar
            status = f"Frame: {frame_idx} | Events: {events_detected} | Press 'q' to quit"
            cv2.putText(annotated, status, (10, annotated.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow(f"SentinelAI - {zone} ({camera_id})", annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        frame_idx += 1
        time.sleep(1.0 / FRAME_FPS)
    
    cap.release()
    cv2.destroyAllWindows()
    logging.info(f"Processing complete. Total events detected: {events_detected}")


def process_video_multizone(video_path: str, camera_id: str = "cam1", show_preview: bool = True):
    """
    Process video using ALL zone detectors simultaneously.
    
    This runs outgate, corridor, school_ground, and classroom detection
    on every frame, detecting all possible threat types at once.
    """
    if not os.path.exists(video_path):
        logging.error(f"Video file not found: {video_path}")
        return
    
    logging.info("="*60)
    logging.info("🎬 SentinelAI Worker Starting (MULTI-ZONE MODE)")
    logging.info("="*60)
    logging.info(f"📍 Zones: ALL (outgate, corridor, school_ground, classroom)")
    logging.info(f"📹 Video: {os.path.basename(video_path)}")
    logging.info(f"🎯 Camera ID: {camera_id}")
    logging.info(f"🤖 Models: yolov8n.pt (outgate), yolov8s.pt (corridor/ground), yolov8m.pt (classroom)")
    logging.info(f"🔍 Events: vehicle, accident, crowd, fight, mobile_usage")
    logging.info(f"🔗 Backend: {BACKEND_URL}")
    logging.info("="*60)
    
    # Create multi-zone pipeline
    try:
        pipeline = MultiZonePipeline(camera_id)
    except Exception as e:
        logging.error(f"Failed to create multi-zone pipeline: {e}")
        return
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error(f"Failed to open video: {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS) or FRAME_FPS
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logging.info(f"  Video FPS: {fps:.1f}, Total frames: {total_frames}")
    
    frame_idx = 0
    events_detected = 0
    zone_event_counts = {"outgate": 0, "corridor": 0, "school_ground": 0, "classroom": 0}
    
    # Zone colors for visualization
    zone_colors = {
        "outgate": (0, 165, 255),        # Orange (BGR)
        "corridor": (255, 255, 0),        # Cyan
        "school_ground": (0, 255, 0),     # Green
        "classroom": (255, 0, 255),       # Magenta
    }
    
    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_idx = 0
            continue
        
        # Process frame through ALL zone pipelines
        events = pipeline.process_frame(frame)
        
        # Log detection counts periodically
        if frame_idx % 30 == 0:
            summary = pipeline.get_detections_summary(frame)
            if summary:
                logging.info(f"📈 Frame {frame_idx}: {summary}")
        
        # Send detected events
        for event in events:
            detected_zone = event.get("detected_by_zone", "unknown")
            logging.warning(f"🚨 [{detected_zone.upper()}] {event['event_type']} (conf={event['confidence']:.2f})")
            send_event(event)
            events_detected += 1
            if detected_zone in zone_event_counts:
                zone_event_counts[detected_zone] += 1
        
        # Show preview with multi-zone annotations
        if show_preview:
            annotated = frame.copy()
            
            # Header
            cv2.putText(annotated, "MULTI-ZONE DETECTION (ALL)", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            # Draw events with zone-specific colors
            if events:
                zones_hit = set(e.get("detected_by_zone", "unknown") for e in events)
                cv2.putText(annotated, f"EVENTS: {', '.join(zones_hit)}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                for event in events:
                    detected_zone = event.get("detected_by_zone", "unknown")
                    color = zone_colors.get(detected_zone, (0, 0, 255))
                    
                    for bbox in event.get("bounding_boxes", []):
                        if len(bbox) == 4:
                            cv2.rectangle(annotated, 
                                         (bbox[0], bbox[1]), (bbox[2], bbox[3]),
                                         color, 2)
                            label = f"{detected_zone}: {event['event_type']}"
                            cv2.putText(annotated, label, (bbox[0], bbox[1] - 5),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Zone legend
            y_offset = 90
            for zone, color in zone_colors.items():
                count = zone_event_counts[zone]
                cv2.rectangle(annotated, (10, y_offset), (25, y_offset + 15), color, -1)
                cv2.putText(annotated, f"{zone}: {count}", (30, y_offset + 12),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                y_offset += 20
            
            # Status bar
            status = f"Frame: {frame_idx} | Total Events: {events_detected} | Press 'q' to quit"
            cv2.putText(annotated, status, (10, annotated.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow(f"SentinelAI - MULTI-ZONE ({camera_id})", annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        frame_idx += 1
        time.sleep(1.0 / FRAME_FPS)
    
    cap.release()
    cv2.destroyAllWindows()
    
    logging.info("="*60)
    logging.info("📊 Multi-Zone Detection Summary")
    logging.info("="*60)
    for zone, count in zone_event_counts.items():
        logging.info(f"  {zone}: {count} events")
    logging.info(f"  TOTAL: {events_detected} events")
    logging.info("="*60)


def process_video_legacy(zone: str, video_path: str, camera_id: str = "cam1", show_preview: bool = True):
    """
    Process video using LEGACY detection functions (backward compatibility).
    """
    if zone not in ZONE_TYPES:
        logging.error(f"Invalid zone '{zone}'. Valid zones: {list(ZONE_TYPES.keys())}")
        return
    
    if not os.path.exists(video_path):
        logging.error(f"Video file not found: {video_path}")
        return
    
    logging.info("="*60)
    logging.info("🎬 SentinelAI Worker Starting...")
    logging.info("="*60)
    logging.info(f"📍 Zone: {zone}")
    logging.info(f"📹 Video: {os.path.basename(video_path)}")
    logging.info(f"🎯 Camera ID: {camera_id}")
    logging.info(f"🔍 Events to detect: {', '.join(ZONE_TYPES[zone])}")
    logging.info(f"🔗 Backend: {BACKEND_URL}")
    logging.info("="*60)
    
    # Load model
    model = load_yolov8()
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error(f"Failed to open video: {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS) or FRAME_FPS
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logging.info(f"  Video FPS: {fps:.1f}, Total frames: {total_frames}")
    
    frame_idx = 0
    events_detected = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            # Loop video for continuous testing
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_idx = 0
            continue
        
        # Run YOLO inference
        detections = run_inference(model, frame)
        
        # Log detection counts periodically
        if frame_idx % 30 == 0:
            person_count = len(detections.get("person", []))
            vehicle_count = sum(len(detections.get(v, [])) for v in ["car", "bus", "truck", "motorcycle"])
            phone_count = len(detections.get("cell phone", []))
            logging.info(f"📈 Frame {frame_idx}: persons={person_count}, vehicles={vehicle_count}, phones={phone_count}")
        
        # Detect events for this zone
        events = detect_all_events(detections, zone, camera_id)
        
        # Send detected events
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
            logging.warning(f"🚨 EVENT DETECTED: {event_data['event_type']} (confidence={event_data['confidence']:.2f})")
            send_event(event)
            events_detected += 1
        
        # Show preview with annotations
        if show_preview:
            annotated = annotate_frame(frame, detections, zone)
            
            # Add event indicator if event detected this frame
            if events:
                cv2.putText(annotated, "EVENT DETECTED!", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            
            # Status bar
            status = f"Frame: {frame_idx} | Events: {events_detected} | Press 'q' to quit"
            cv2.putText(annotated, status, (10, annotated.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow(f"SentinelAI - {zone} ({camera_id})", annotated)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        
        frame_idx += 1
        time.sleep(1.0 / FRAME_FPS)
    
    cap.release()
    cv2.destroyAllWindows()
    logging.info(f"Processing complete. Total events detected: {events_detected}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nAvailable zones and their models:")
        print("  all: Runs ALL detectors (multi-zone detection)")
        for zone, events in ZONE_TYPES.items():
            config = ZONE_MODEL_CONFIGS.get(zone) if HAS_REGISTRY else None
            model = config.model_file if config else "yolov8n.pt"
            print(f"  {zone}: {', '.join(events)} (model: {model})")
        sys.exit(1)
    
    zone = sys.argv[1]
    video_path = sys.argv[2]
    camera_id = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("-") else "cam1"
    
    # Validate zone
    valid_zones = list(ZONE_TYPES.keys()) + ["all"]
    if zone.lower() not in valid_zones:
        print(f"Invalid zone '{zone}'. Valid options: {valid_zones}")
        sys.exit(1)
    
    # Check for flags
    show_preview = "--no-preview" not in sys.argv
    use_legacy = "--legacy" in sys.argv
    
    process_video(zone, video_path, camera_id, show_preview, use_legacy)


if __name__ == "__main__":
    main()