import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Tuple

"""
Lightweight, in-memory event engine for school / campus safety.

Responsibilities:
- Keep short-term state per (tenant, camera, event_type)
- Apply suspicion scoring + simple multi-frame verification
- Emit a normalized "incident" payload with an attached playbook
  describing what the alert layer should do.

This keeps the backend + alert service simple and lets us evolve
thresholds and logic here without touching the API surface.
"""

# Per-event-type configuration
EVENT_CONFIG: Dict[str, Dict] = {
    # 1) Fight / Violence / Crowd formation
    "fight": {
        "window_sec": 5.0,
        "min_frames": 3,
        "threshold": 0.65,  # avg confidence in the window
        "priority": "high",
        "playbook": {
            "scenario": "fight_violence_crowd",
            "send_high_priority_alert": True,
            "include_snapshot": True,
            "include_llm_explanation": True,
            "push_live_camera_link": True,
            "notify_nearest_staff": True,
            "mark_incident_timeline": True,
        },
    },
    # 2) Exam malpractice
    "exam_malpractice": {
        "window_sec": 10.0,
        "min_frames": 2,
        "threshold": 0.6,
        "priority": "medium",
        "playbook": {
            "scenario": "exam_malpractice",
            "flag_timestamped_clips": True,
            "lock_clip_in_evidence_store": True,
            "notify_invigilator": True,
            "include_snapshot": True,
            "suggest_evidence_summary": True,
        },
    },
    # 3) Accident at gate / road-facing camera
    "gate_accident": {
        "window_sec": 4.0,
        "min_frames": 1,
        "threshold": 0.8,
        "priority": "critical",
        "playbook": {
            "scenario": "gate_accident",
            "auto_call_ambulance": True,
            "notify_security_and_admin": True,
            "attach_location": True,
            "push_live_camera_link": True,
        },
    },
    # 4) Unauthorized entry / after-hours intrusion
    "intrusion": {
        "window_sec": 8.0,
        "min_frames": 2,
        "threshold": 0.7,
        "priority": "high",
        "playbook": {
            "scenario": "unauthorized_entry",
            "notify_security": True,
            "lock_gates_if_integrated": True,
            "create_incident": True,
            "start_high_fidelity_recording": True,
        },
    },
    # 5) Abandoned baggage / object
    "abandoned_object": {
        "window_sec": 20.0,
        "min_frames": 2,
        "threshold": 0.65,
        "priority": "high",
        "playbook": {
            "scenario": "abandoned_object",
            "timestamped_alert": True,
            "run_reid_probe": True,
            "auto_zone_lockdown_if_high_risk": True,
        },
    },
    # 6) Fire / smoke
    "fire_smoke": {
        "window_sec": 3.0,
        "min_frames": 1,
        "threshold": 0.75,
        "priority": "critical",
        "playbook": {
            "scenario": "fire_smoke",
            "immediate_emergency_notification": True,
            "auto_call_fire_service": True,
            "open_evacuation_map": True,
            "show_muster_point_guidance": True,
        },
    },
}


# (tenant_id, camera_id, event_type) → deque of recent frames
_recent_events: Dict[Tuple[str, str, str], Deque[Dict]] = defaultdict(
    lambda: deque(maxlen=64)
)


def _make_key(event: Dict) -> Tuple[str, str, str]:
    return (
        str(event.get("tenant_id", "default")),
        str(event.get("camera_id", "unknown")),
        str(event.get("event_type", "unknown")),
    )


def _update_state(key: Tuple[str, str, str], event: Dict, window_sec: float) -> List[Dict]:
    """
    Append the current frame to the buffer and prune anything outside `window_sec`.
    """
    now = float(event.get("timestamp", time.time()))
    buf = _recent_events[key]
    buf.append(
        {
            "ts": now,
            "confidence": float(event.get("confidence", 0.0)),
        }
    )
    # Keep only items within the time window
    while buf and (now - buf[0]["ts"]) > window_sec:
        buf.popleft()
    return list(buf)


def _compute_suspicion_score(frames: List[Dict]) -> float:
    if not frames:
        return 0.0
    return sum(f["confidence"] for f in frames) / len(frames)


def process_event(event: Dict) -> Dict:
    """
    Core decision function used by the backend.

    Input: raw event emitted by the AI worker.
    Output:
        - incident: bool
        - event: original event
        - suspicion_score: float
        - priority: str (low/medium/high/critical)
        - playbook: dict describing downstream actions
        - timeline: simple struct (first_seen, last_seen, frames_considered)
    """
    event_type = event.get("event_type")
    config = EVENT_CONFIG.get(event_type)
    if not config:
        # Unknown / unsupported type – just echo back
        return {"incident": False, "event": event, "suspicion_score": 0.0}

    key = _make_key(event)
    window_sec = float(config["window_sec"])
    frames = _update_state(key, event, window_sec)
    suspicion_score = _compute_suspicion_score(frames)

    # Multi-frame verification
    enough_frames = len(frames) >= config["min_frames"]
    over_threshold = suspicion_score >= config["threshold"]
    is_incident = bool(enough_frames and over_threshold)

    timeline = {}
    if frames:
        timeline = {
            "first_seen": frames[0]["ts"],
            "last_seen": frames[-1]["ts"],
            "frames_considered": len(frames),
        }

    base_payload = {
        "event": event,
        "suspicion_score": suspicion_score,
        "priority": config["priority"],
        "playbook": config["playbook"],
        "timeline": timeline,
    }

    if not is_incident:
        base_payload["incident"] = False
        return base_payload

    base_payload["incident"] = True
    return base_payload
