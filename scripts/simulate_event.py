import requests
import time

# Simulate sending a fight event to backend

event = {
    "event_id": "evt1",
    "tenant_id": "school1",
    "camera_id": "cam1",
    "event_type": "fight",
    "confidence": 0.85,
    "timestamp": time.time(),
    "bounding_boxes": [[100,100,200,200]],
    "zone": "Corridor A",
    "severity_score": 0.9
}

resp = requests.post("http://localhost:8000/event", json=event)
print(resp.json())
