# SentinelAI - System Architecture

## Logical Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                   SENTINELAI ARCHITECTURE                                │
└──────────────────────────────────────────────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             FRONTEND LAYER (Next.js SaaS Dashboard)                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Landing   │  │  Monitoring │  │  Incidents  │  │  Analytics  │  │  Settings   │ │
│  │   Page      │  │  Dashboard  │  │    Page     │  │    Page     │  │    Page     │ │
│  │             │  │             │  │             │  │             │  │             │ │
│  │ • Module    │  │ • Camera    │  │ • Filter    │  │ • Bar Chart │  │ • Config    │ │
│  │   Selector  │  │   Grid      │  │ • Search    │  │ • Pie Chart │  │ • Health    │ │
│  │ • Camera    │  │ • Alerts    │  │ • Paginate  │  │ • Trend     │  │ • Theme     │ │
│  │   Config    │  │ • Timeline  │  │ • Export    │  │ • Stats     │  │ • Workers   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                                                        │
│  ┌────────────────────────────────── Shared UI Layer ─────────────────────────────┐   │
│  │ ThemeProvider │ ToastProvider │ WebSocket Hook │ Layout (Sidebar + TopBar)     │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                           │
                     HTTP REST             │              WebSocket
                     MJPEG Stream          │              /ws/alerts
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND LAYER (FastAPI + Python)                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌───────────────────────────────────── REST API ─────────────────────────────────┐   │
│  │                                                                                │   │
│  │  GET  /api/cameras         POST /api/camera/{id}     GET  /api/zones          │   │
│  │  GET  /api/camera/{id}     DELETE /api/camera/{id}   GET  /api/modules        │   │
│  │  POST /api/camera          POST /api/camera/{id}/zone                         │   │
│  │  GET  /api/camera/{id}/health                                                 │   │
│  │  GET  /api/system/health   GET  /api/stats           GET  /api/test_videos    │   │
│  │  POST /event               GET  /incidents           GET  /incident/{id}/pdf  │   │
│  │                                                                                │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  ┌───────────────────────────────────── WebSocket ────────────────────────────────┐   │
│  │  WS /ws/alerts → Real-time alert broadcast to all connected clients           │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  ┌───────────────────────────────────── MJPEG Stream ─────────────────────────────┐   │
│  │  GET /video/{camera_id} → Live video frame stream with detection overlays     │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  ┌─────────────────────────── Processing Pipeline ────────────────────────────────┐   │
│  │                                                                                │   │
│  │  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐  │   │
│  │  │ Event       │ ──► │ Engine      │ ──► │ Alert       │ ──► │ Broadcast   │  │   │
│  │  │ Receiver    │     │ (engine.py) │     │ (service.py)│     │ Queue       │  │   │
│  │  │ POST /event │     │ Suspicion   │     │ Priority    │     │ WebSocket   │  │   │
│  │  │             │     │ Scoring     │     │ Summary     │     │ Clients     │  │   │
│  │  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘  │   │
│  │                                                                                │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  ┌─────────────────────────── In-Memory State ────────────────────────────────────┐   │
│  │  camera_configs: Dict    │    incidents: Dict    │    alerts_history: List    │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                           ▲
                                           │ POST /event
                                           │
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          AI WORKER LAYER (Zone-Based Pipelines)                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌────────────────────────────── Zone Processors ─────────────────────────────────┐   │
│  │                                                                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │   │
│  │  │   Outgate   │  │  Corridor   │  │   School    │  │  Classroom  │           │   │
│  │  │   Zone      │  │   Zone      │  │   Ground    │  │   Zone      │           │   │
│  │  │             │  │             │  │   Zone      │  │             │           │   │
│  │  │ yolov8n.pt  │  │ yolov8s.pt  │  │ yolov8s.pt  │  │ yolov8m.pt  │           │   │
│  │  │             │  │             │  │             │  │             │           │   │
│  │  │ • Vehicle   │  │ • Crowd     │  │ • Crowd     │  │ • Mobile    │           │   │
│  │  │ • Accident  │  │ • Fight     │  │ • Fight     │  │   Phone     │           │   │
│  │  │             │  │             │  │ • Weapon    │  │             │           │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘           │   │
│  │                                                                                │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│  ┌────────────────────────────── Shared Components ───────────────────────────────┐   │
│  │                                                                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │   │
│  │  │   YOLO      │  │   Tracker   │  │  Behaviour  │  │  Detectors  │           │   │
│  │  │   Models    │  │   (ReID)    │  │  Analysis   │  │  (Shared)   │           │   │
│  │  │             │  │             │  │             │  │             │           │   │
│  │  │ • General   │  │ • Object    │  │ • Pose      │  │ • fight     │           │   │
│  │  │ • Pose      │  │   Tracking  │  │   Analysis  │  │ • crowd     │           │   │
│  │  │ • Weapon    │  │ • Temporal  │  │ • Violence  │  │ • mobile    │           │   │
│  │  │             │  │             │  │   Detection │  │ • weapon    │           │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘           │   │
│  │                                                                                │   │
│  └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
                                           ▲
                                           │
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              VIDEO SOURCE LAYER                                        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │
│  │   RTSP      │  │   Test      │  │   Webcam    │  │   USB       │                   │
│  │   Stream    │  │   Videos    │  │   Sources   │  │   Cameras   │                   │
│  │             │  │             │  │             │  │             │                   │
│  │ rtsp://...  │  │ test_videos/│  │ /dev/video* │  │ /dev/usb*   │                   │
│  │             │  │ {module}/   │  │             │  │             │                   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘                   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer Responsibilities

### Frontend Layer (Next.js)
- **SaaS Dashboard**: Professional multi-page application
- **Real-time Updates**: WebSocket connection for live alerts
- **Theme Support**: Light/Dark mode with persistence
- **Responsive Design**: Mobile-friendly Tailwind CSS

### Backend Layer (FastAPI)
- **REST API**: CRUD operations for cameras, incidents, stats
- **WebSocket**: Real-time alert broadcasting
- **MJPEG Streaming**: Live video feeds with detection overlays
- **Event Processing**: Suspicion scoring and priority assignment

### AI Worker Layer
- **Zone-Based Detection**: Model selection based on zone type
- **Shared Detectors**: Reusable detection components
- **Tracker**: Object tracking and temporal analysis
- **Behaviour Analysis**: Pose estimation and violence detection

### Video Source Layer
- **RTSP Streams**: Production camera feeds
- **Test Videos**: Development/demo video files
- **Webcams**: USB camera support

---

## Communication Protocols

| From | To | Protocol | Endpoint |
|------|-----|----------|----------|
| Frontend | Backend | HTTP REST | /api/* |
| Frontend | Backend | WebSocket | /ws/alerts |
| Frontend | Backend | MJPEG | /video/{id} |
| AI Worker | Backend | HTTP POST | /event |
| Backend | Frontend | WebSocket Push | Alert broadcast |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React 18, Tailwind CSS, Framer Motion, Recharts |
| Backend | FastAPI, Python 3.10+, Uvicorn, OpenCV |
| AI | YOLOv8 (ultralytics), PyTorch |
| State | In-memory (Dict) - Database ready |
| Streaming | MJPEG over HTTP |
| Real-time | WebSocket (native) |

---

## Scalability Path

1. **Horizontal Scaling**
   - Multiple AI workers per zone
   - Load balancer for backend
   - Redis for shared state

2. **Database Integration**
   - PostgreSQL for incidents
   - Redis for camera state
   - S3 for video clips

3. **Multi-Tenant**
   - Tenant isolation
   - Per-tenant API keys
   - Tenant-scoped data
