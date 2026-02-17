# SentinelAI School/College Security Module

Production-ready, modular, scalable, privacy-first AI security system for schools/colleges. Detects threats, triggers alerts, and provides a real-time dashboard.

## Features
- RTSP ingest (camera feeds, or webcam for demo)
- Fight/violence detection (YOLOv8 + tracking)
- Gate accident, intrusion, abandoned object, fire/smoke, exam malpractice detection
- Alert pipeline & event engine
- Dashboard (Next.js + Tailwind)
- LLM summary & PDF export
- Docker deployable

## Quick Start (Demo)
1. Copy `.env.example` to `.env` and fill in values as needed.
2. Install dependencies:
   - Python: `pip install -r requirements.txt` in backend, ai_worker, event_engine, alert_service
   - Dashboard: `npm install` in dashboard
3. Start backend: `cd backend && uvicorn main:app --reload`
4. Start AI worker: `cd ai_worker && python worker.py worker fight` (or any event type)
5. Start dashboard: `cd dashboard && npm run dev`
6. Open dashboard at http://localhost:3000
7. Test live camera feed at http://localhost:8000/live_feed

## Event Types
- fight
- gate_accident
- intrusion
- abandoned_object
- fire_smoke
- exam_malpractice

## Endpoints
- `/event` — POST event ingest
- `/ws/alerts` — WebSocket for real-time alerts
- `/incident/{id}/summary` — LLM summary
- `/incident/{id}/pdf` — PDF export
- `/live_feed` — MJPEG webcam stream

## Scripts
- `scripts/run_demo.sh` — Start all services for demo (Linux/Mac)
- `scripts/simulate_event.py` — Send test event to backend

## Folder Structure
- `backend/` — FastAPI event API
- `ai_worker/` — AI detection (YOLOv8, tracking, event logic)
- `event_engine/` — Rule engine, scoring
- `alert_service/` — Alert, evidence, LLM, S3
- `dashboard/` — Next.js UI
- `scripts/` — Demo/test scripts
- `test_videos/` — Sample videos
- `config/` — Config files

---
MIT License
# SecVidAnalysis
# SecVidAnalysis
# SecVidAnalysis
# CCTvAnalysis
