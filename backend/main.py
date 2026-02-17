from fastapi import FastAPI, WebSocket, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import importlib.util
import sys
import os
import io
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas
import cv2

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Import event engine and alert service
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../event_engine')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../alert_service')))
try:
    from engine import process_event
    from service import trigger_alert
except ImportError:
    process_event = lambda event: {"incident": False}
    trigger_alert = lambda incident: {"alert": False, "summary": "(mock)"}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from typing import List
import asyncio

alerts_history = []  # In-memory for MVP
incidents = {}  # incident_id: {event, alert}
# --- WebSocket broadcast state ---
active_alert_clients: List[WebSocket] = []
alert_broadcast_queue: asyncio.Queue = asyncio.Queue()

@app.get("/health")
def health():
    return {"status": "ok"}


# Event ingest endpoint
@app.post("/event")
async def receive_event(event: dict, request: Request = None):
    logging.info(f"Received event: {event}")
    result = process_event(event)
    if result.get("incident"):
        alert = trigger_alert(result)
        incident_id = event.get("event_id")
        incidents[incident_id] = {"event": event, "alert": alert}
        alerts_history.append({"event": event, "alert": alert})
        logging.info(f"Alert triggered: {alert}")
        # Broadcast to all connected WebSocket clients
        await alert_broadcast_queue.put({"event": event, "alert": alert})
        return {"received": True, "alert": alert, "incident_id": incident_id}
    return {"received": True, "alert": None}


# WebSocket for real-time alerts (broadcasts new alerts to all connected clients)
@app.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket):
    await websocket.accept()
    active_alert_clients.append(websocket)
    try:
        # On connect, send the last alert if available
        if alerts_history:
            await websocket.send_json(alerts_history[-1])
        else:
            await websocket.send_json({"msg": "No alerts yet."})
        # Listen for new alerts and send them as they arrive
        while True:
            alert = await alert_broadcast_queue.get()
            await websocket.send_json(alert)
    except Exception:
        pass
    finally:
        if websocket in active_alert_clients:
            active_alert_clients.remove(websocket)

# --- LLM Summary Endpoint ---
@app.get("/incident/{incident_id}/summary")
async def get_llm_summary(incident_id: str):
    incident = incidents.get(incident_id)
    if not incident:
        return {"error": "Incident not found"}
    # For MVP, use alert summary
    return {"summary": incident["alert"].get("summary", "No summary available")}

# --- PDF Export Endpoint ---
@app.get("/incident/{incident_id}/pdf")
async def get_incident_pdf(incident_id: str):
    incident = incidents.get(incident_id)
    if not incident:
        return Response(content="Incident not found", status_code=404)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica", 14)
    p.drawString(100, 800, f"Incident Report: {incident_id}")
    p.setFont("Helvetica", 10)
    p.drawString(100, 780, f"Event Type: {incident['event'].get('event_type')}")
    p.drawString(100, 765, f"Zone: {incident['event'].get('zone')}")
    p.drawString(100, 750, f"Time: {incident['event'].get('timestamp')}")
    p.drawString(100, 735, f"Summary: {incident['alert'].get('summary')}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=incident_{incident_id}.pdf"})

# --- Camera Feed Endpoint (MJPEG webcam stream with detection overlay) ---
import base64
import ast
def gen_frames_with_overlay():
    # Try camera indexes 0-3, use first available
    cap = None
    for idx in range(4):
        test_cap = cv2.VideoCapture(idx)
        if test_cap.isOpened():
            cap = test_cap
            print(f"[Camera Feed] Using camera index {idx}")
            break
        test_cap.release()
    if cap is None:
        print("[Camera Feed] No available camera found (indexes 0-3). Exiting.")
        return
    while True:
        success, frame = cap.read()
        if not success:
            break
        # Overlay latest detection boxes if available
        if alerts_history and alerts_history[-1]["event"].get("bounding_boxes"):
            try:
                boxes = alerts_history[-1]["event"]["bounding_boxes"]
                # If boxes are stringified, parse them
                if isinstance(boxes, str):
                    boxes = ast.literal_eval(boxes)
                for box in boxes:
                    if len(box) == 4:
                        x1, y1, x2, y2 = box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0,0,255), 2)
            except Exception as e:
                pass
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    cap.release()

@app.get("/camera_feed")
def camera_feed():
    return StreamingResponse(gen_frames_with_overlay(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
