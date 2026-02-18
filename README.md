# SentinelAI - School Security Monitoring System

Real-time AI-powered surveillance system for schools using YOLOv8 object detection with zone-based threat analysis.

## 🚀 Deployment

This project is structured for **Vercel** (frontend) + **Render** (backend) deployment.

### Project Structure

```
SecVidA/
├── frontend/           # Next.js app (Vercel)
│   ├── pages/          # Monitor, config pages
│   ├── components/     # React components
│   └── .env.example    # Environment template
├── backend/            # FastAPI server (Render)
│   ├── main.py         # API endpoints
│   ├── engine.py       # Event scoring
│   ├── service.py      # Alert generation
│   ├── worker/         # YOLOv8 detection
│   ├── zones/          # Zone processors
│   ├── models/         # YOLO model weights
│   ├── Dockerfile      # Container config
│   └── requirements.txt
└── test_videos/        # Sample test videos
```

### Deploy to Render (Backend)

1. Push to GitHub
2. Create a new **Web Service** on Render
3. Connect your repo, set root directory to `backend`
4. Set environment variables:
   - `PORT=10000`
   - `MODULE=school`
   - `FRONTEND_URL=https://your-app.vercel.app`

### Deploy to Vercel (Frontend)

1. Import project on Vercel
2. Set root directory to `frontend`
3. Add environment variable:
   - `NEXT_PUBLIC_API_BASE=https://your-render-app.onrender.com`

## Features

- **Real YOLOv8 Detection** - Uses ultralytics YOLOv8 for accurate object detection
- **Zone-Based Analysis** - Four detection zones tailored for school environments:
  - **Outgate** - Vehicle detection, gate accidents
  - **Corridor** - Crowd formation, fight detection
  - **School Ground** - Crowd monitoring, violence detection
  - **Classroom** - Mobile phone usage detection
- **Real-Time Dashboard** - Professional dark-themed monitoring interface
- **Multi-Camera Support** - MJPEG streaming from multiple camera feeds
- **WebSocket Alerts** - Instant notifications for detected threats
- **LLM Analysis** - AI-generated incident summaries
- **PDF Reports** - Export detailed incident reports

## Local Development

### 1. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Start the Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 4. Start the Frontend

```bash
cd frontend
npm run dev
```

### 5. Test Zone Detection

```bash
cd backend/worker
python test_worker.py corridor "../../test_videos/school/your_video.mp4"
```

## Zone Types & Detection

| Zone | Detects | YOLO Classes Used |
|------|---------|-------------------|
| `outgate` | Vehicles, Gate Accidents | car, bus, truck, motorcycle |
| `corridor` | Crowd Formation, Fights | person |
| `school_ground` | Crowd Formation, Fights | person |
| `classroom` | Mobile Phone Usage | person, cell phone |

## API Endpoints

### Events & Incidents
- `POST /event` - Submit detection event
- `GET /incidents` - List all incidents
- `GET /incident/{id}/summary` - LLM-generated summary
- `GET /incident/{id}/pdf` - Download PDF report

### Configuration
- `GET /api/zones` - Get zone definitions
- `GET /api/cameras` - List camera configurations
- `POST /api/camera/{id}` - Update camera config

### Streaming
- `GET /video/{camera_id}` - MJPEG stream for camera
- `GET /live_feed` - Default camera feed
- `WS /ws/alerts` - Real-time alert WebSocket

## Environment Variables

### Backend (`backend/.env`)

```env
PORT=8000
MODULE=school
FRONTEND_URL=*
LLM_API_BASE=http://localhost:11434/v1
LLM_API_KEY=your-api-key
```

### Frontend (`frontend/.env`)

```env
NEXT_PUBLIC_API_BASE=https://your-render-app.onrender.com
```

For local development, omit `NEXT_PUBLIC_API_BASE` to use `http://localhost:8000`.

## Dashboard Pages

- **/** - Camera configuration and zone assignment
- **/monitor** - Live monitoring dashboard with multi-camera grid

---

## 🎬 Event Flow & Real-Time Delivery System (Latest Enhancement)

**Status**: ✅ FULLY IMPLEMENTED AND TESTED

This project now includes a comprehensive, production-ready event delivery pipeline with detailed logging at every step:

### Architecture Highlights
- **EventCooldownManager**: Smart filtering prevents event flooding while allowing escalation detection
- **SharedDetectors Singleton**: Models loaded once + shared across cameras = 50% memory savings
- **Async WebSocket Broadcasting**: Non-blocking delivery to multiple frontend clients
- **Structured Logging**: 30+ tagged log points for complete observability
- **Robust Error Handling**: Graceful degradation on model failures

### Quick Start
```bash
# Terminal 1: Backend
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2: Frontend  
cd dashboard && npm run dev

# Terminal 3: Test (pick one)
python scripts/test_event_flow.py              # Full test suite
curl http://localhost:8000/api/debug/ping     # Quick debug ping
python ai_worker/test_worker.py school_ground test_videos/school/demo.mp4  # Real detection
```

### Documentation
- 📘 **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** — Developer cheat sheet (30s summary + logging tags)
- 📗 **[EVENT_FLOW.md](EVENT_FLOW.md)** — Complete technical guide (4 phases, 10 sections)
- 📕 **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** — Full details of changes made
- 📙 **[VERIFICATION_REPORT.md](VERIFICATION_REPORT.md)** — Testing & verification results
- 🧪 **[scripts/test_event_flow.py](scripts/test_event_flow.py)** — 5 comprehensive tests

### Key Features
✅ Worker event emission with detailed logging  
✅ EventCooldownManager prevents flooding with escalation detection  
✅ SharedDetectors singleton for optimized GPU memory  
✅ Backend event reception with schema validation  
✅ WebSocket broadcasting with per-client tracking  
✅ Frontend console logging for debugging  
✅ Debug ping endpoint for testing without worker  
✅ Production-ready error handling throughout  

### Logging References
| Component | Key Tags |
|-----------|----------|
| Worker | `[EVENT_EMIT]` `[EVENT_DELIVERY_OK]` `[EVENT_SUPPRESSED]` |
| Backend | `[EVENT_RX_ACCEPT]` `[EVENT_INCIDENT_DETECTED]` `[BROADCAST_QUEUED]` |
| WebSocket | `[WS_BROADCAST_START]` `[WS_SEND_OK]` `[WS_CLIENT_CONNECTED]` |
| Frontend | `[WS_MESSAGE_RX]` `[ALERT_DISPLAYED]` (browser console F12) |

See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for complete reference.

---

MIT License
