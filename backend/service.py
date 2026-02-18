import os
import time
from typing import Dict, List

import requests

"""
Alert service for SAAS school module.

This stays transport‑agnostic: instead of actually calling SMS /
WhatsApp / ambulances / fire brigade, it returns a rich `alert`
payload listing *what* would be done so the caller (or another
worker) can integrate with real services later.
"""


def _base_summary(incident: Dict) -> str:
    event = incident.get("event", {})
    event_type = event.get("event_type", "unknown")
    confidence = event.get("confidence", 0.0)
    priority = incident.get("priority", "medium")
    return (
        f"{event_type.replace('_', ' ').title()} detected "
        f"(priority: {priority}, confidence: {confidence:.2f})."
    )


def _scenario_actions(incident: Dict) -> Dict:
    """
    Map the engine playbook into concrete, human-readable actions.
    """
    playbook = incident.get("playbook", {}) or {}
    event = incident.get("event", {}) or {}
    event_type = event.get("event_type")

    actions: List[str] = []
    evidence: Dict = {}
    notifications: Dict = {}
    automations: Dict = {}

    # Common context
    camera_id = event.get("camera_id")
    tenant_id = event.get("tenant_id")
    event_id = event.get("event_id")
    ts = event.get("timestamp", time.time())

    # Snapshot / clip references are symbolic; real system would
    # actually cut frames/segments and persist to storage.
    snapshot_ref = f"snapshot://{tenant_id}/{camera_id}/{event_id}"
    clip_ref = f"clip://{tenant_id}/{camera_id}/{event_id}"

    if playbook.get("include_snapshot"):
        evidence["snapshot_ref"] = snapshot_ref
        actions.append("Captured and stored snapshot of incident frame.")

    if playbook.get("flag_timestamped_clips"):
        evidence["clip_ref"] = clip_ref
        evidence["locked"] = playbook.get("lock_clip_in_evidence_store", False)
        actions.append("Flagged timestamped video clip in evidence store.")

    # Scenario‑specific logic
    scenario = playbook.get("scenario") or event_type

    if scenario == "fight_violence_crowd":
        notifications["security_app"] = {
            "priority": "high",
            "target_role": "nearest_security_or_duty_staff",
        }
        automations["live_view"] = {
            "camera_id": camera_id,
            "action": "open_live_stream_in_client",
        }
        actions.extend(
            [
                "Raised high-priority alert to duty/security app.",
                "Pushed live camera link to nearest staff.",
                "Marked incident timeline for later review.",
            ]
        )

    elif scenario == "exam_malpractice":
        notifications["invigilator"] = {
            "channel": "app",
            "priority": "medium",
        }
        actions.extend(
            [
                "Notified invigilator with snapshot and context.",
                "Locked flagged clip as exam malpractice evidence.",
            ]
        )

    elif scenario == "gate_accident":
        automations["emergency_workflow"] = {
            "type": "ambulance",
            "status": "requested",
        }
        notifications["security_admin"] = {
            "priority": "critical",
            "include_location": True,
            "camera_id": camera_id,
        }
        actions.extend(
            [
                "Triggered ambulance / emergency workflow.",
                "Notified security and admin with camera + location.",
            ]
        )

    elif scenario == "unauthorized_entry":
        notifications["security"] = {"priority": "high"}
        automations["gates"] = {
            "action": "lock_if_integrated",
            "camera_id": camera_id,
        }
        automations["recording"] = {
            "mode": "high_fidelity",
            "started_at": ts,
        }
        actions.extend(
            [
                "Notified security about after-hours intrusion.",
                "Requested gate lock (if integrated).",
                "Started high-fidelity recording around incident.",
            ]
        )

    elif scenario == "abandoned_object":
        automations["reid_probe"] = {
            "action": "identify_subject_who_left_object",
            "clip_ref": clip_ref,
        }
        automations["zone_lockdown"] = {
            "mode": "conditional",
            "trigger": "high_risk_assessment",
        }
        actions.extend(
            [
                "Raised timestamped alert for abandoned object.",
                "Launched ReID probe to find who left the object.",
                "Prepared auto zone lockdown if object is high-risk.",
            ]
        )

    elif scenario == "fire_smoke":
        automations["fire_service"] = {
            "type": "fire",
            "status": "requested",
        }
        notifications["emergency_panel"] = {
            "priority": "critical",
            "include_evac_map": True,
        }
        actions.extend(
            [
                "Raised immediate emergency notification for fire/smoke.",
                "Triggered fire service workflow (if configured).",
                "Displayed evacuation map and muster point guidance.",
            ]
        )

    return {
        "actions": actions,
        "evidence": evidence,
        "notifications": notifications,
        "automations": automations,
    }


def _build_llm_prompt(incident: Dict, scenario_block: Dict, summary: str) -> str:
    event = incident.get("event", {}) or {}
    playbook = incident.get("playbook", {}) or {}

    return (
        "You are an AI safety assistant for a school campus. "
        "Explain to a human operator what was detected on the camera, "
        "why it matters, and what actions the system is taking. "
        "Be concise (3–6 sentences) and non-technical.\n\n"
        f"High-level summary: {summary}\n\n"
        f"Event payload: {event}\n\n"
        f"Configured playbook: {playbook}\n\n"
        f"Derived actions: {scenario_block.get('actions', [])}\n"
    )


def _call_llm(prompt: str) -> str:
    """
    Call a free / OpenAI-compatible LLM endpoint if configured.

    Environment variables:
      - LLM_API_BASE: e.g. https://api.groq.com/openai, https://api.openai.com
      - LLM_API_KEY: API key for the provider
      - LLM_MODEL:   model name (provider-specific)

    If not configured or if the call fails, we fall back to a local,
    deterministic explanation string.
    """
    api_base = os.getenv("LLM_API_BASE")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_base or not api_key:
        return (
            "Automatically generated explanation based on recent frames and "
            "configured safety playbooks. (LLM endpoint is not configured, "
            "so this is a local fallback string.)"
        )

    try:
        url = api_base.rstrip("/") + "/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an AI assistant helping school security staff "
                        "understand incidents detected on CCTV cameras."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
            or "LLM did not return an explanation."
        )
    except Exception:
        return (
            "Automatically generated explanation based on recent frames and "
            "configured safety playbooks. (LLM call failed; using fallback.)"
        )


def trigger_alert(incident: Dict) -> Dict:
    """
    Translate an incident from the engine into a concrete alert description.
    """
    if not incident:
        return {"alert": False, "summary": "No incident data."}

    scenario_block = _scenario_actions(incident)
    summary = _base_summary(incident)

    # Real LLM explanation if configured, otherwise clean fallback.
    prompt = _build_llm_prompt(incident, scenario_block, summary)
    llm_explanation = _call_llm(prompt)

    alert = {
        "alert": True,
        "summary": summary,
        "llm_explanation": llm_explanation,
        "priority": incident.get("priority", "medium"),
        "suspicion_score": incident.get("suspicion_score"),
        "timeline": incident.get("timeline", {}),
        "event": incident.get("event", {}),
        **scenario_block,
    }

    print(f"ALERT: {alert}")
    return alert
