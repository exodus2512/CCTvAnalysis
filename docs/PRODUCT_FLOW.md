# SentinelAI - Complete Product Flow

## Overview

Real-time AI-powered school security monitoring system using YOLOv8 for zone-based threat detection.

---

## Application Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           SENTINELAI PRODUCT FLOW                            │
└──────────────────────────────────────────────────────────────────────────────┘

[1] Landing Page (pages/index.js)
        │
        ├── Organization/Tenant Input [FUTURE: Multi-tenant ready via data/tenants.json]
        │
        ├── Google OAuth Login [FUTURE: Auth integration placeholder]
        │
        ▼
[2] Module Selection (Card-Based UI)
        │
        ├── Home Module
        ├── School Module ← Default
        └── Office Module
        │
        ▼
[3] setup wizard
        │
        ├── View configured cameras from test_videos/{module}/
        ├── Add new cameras (name, zone assignment)
        ├── Edit existing cameras
        ├── Delete cameras
        ├── Enable/disable cameras
        └── Real-time health status indicators
        │
        ▼
[4] Zone Assignment (Auto-bind AI Worker)
        │
        ├── outgate   → yolov8n.pt (Vehicle detection, gate accidents)
        ├── corridor  → yolov8s.pt (Crowd formation, fights)
        ├── school_ground → yolov8s.pt (Violence, weapons)
        └── classroom → yolov8m.pt (Mobile phone usage)
        │
        ▼
[5] Start Monitoring → Navigate to /monitor
        │
        │   ┌────────────────────────────────────────────┐
        │   │          BACKEND PROCESSING                │
        │   │                                            │
        │   │  RTSP/Video → AI Worker → Detection       │
        │   │       → Event Engine → POST /event        │
        │   │       → WebSocket Broadcast               │
        │   └────────────────────────────────────────────┘
        │
        ▼
[6] Monitoring Dashboard (pages/monitor.js)
        │
        ├── Live Camera Grid (MJPEG streams)
        ├── Real-time Alert Popups
        ├── Incident Timeline
        ├── Quick Stats Panel
        └── Analytics Overview
        │
        ▼
[7] Sidebar Navigation
        │
        ├── Dashboard   → Live monitoring view
        ├── Cameras     → Camera management grid
        ├── Incidents   → History with filters/search/pagination
        ├── Analytics   → Charts & trends
        └── Settings    → System configuration
```

---

## Flow States

### 1. Initial Configuration State
```
User arrives → Landing Page → Selects Module → Configures Cameras → Starts Monitoring
```

### 2. Monitoring State
```
Video Feed → AI Detection → Event POST → Engine Processing → Alert Broadcast → UI Update
```

### 3. Alert Handling State
```
Alert Received → Toast/Popup → Camera Highlight → User Action (View/Resolve/Export PDF)
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                      │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │   AI Worker     │
                    │  (Zone Model)   │
                    └────────┬────────┘
                             │ POST /event
                             ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Frontend       │◄───│  FastAPI        │───►│  Event Engine   │
│  (Next.js)      │ WS │  Backend        │    │  (engine.py)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        ▲                      │                       │
        │                      ▼                       ▼
        │              ┌─────────────────┐    ┌─────────────────┐
        │              │  In-Memory      │    │  Alert Service  │
        │              │  State          │    │  (service.py)   │
        │              │  - cameras      │    └─────────────────┘
        │              │  - incidents    │
        │              │  - alerts       │
        └──────────────┴─────────────────┘
            HTTP/MJPEG/WebSocket

```

---

## Event Lifecycle

1. **Detection**: AI Worker processes video frame
2. **Event Creation**: Structured event with camera_id, zone, event_type, confidence, bounding_boxes
3. **Event POST**: Worker posts to `/event` endpoint
4. **Engine Processing**: Event engine analyzes suspicion score, timeline, priority
5. **Incident Creation**: If incident detected, stored in memory + triggers alert
6. **WebSocket Broadcast**: Alert pushed to all connected clients
7. **UI Update**: Frontend receives alert, updates:
   - Active alerts panel
   - Camera highlight
   - Incident list
   - Toast notification
8. **User Action**: View details, mark resolved, export PDF

---

## Session Persistence

- Configuration stored in `localStorage` as `sentinel_config`
- Module selection persists across sessions
- Camera configurations cached on backend (60-second TTL)
- Incidents stored in-memory (cleared on restart)
- Future: Database integration via structured JSON schema

---

## Module-Specific Behavior

| Module | Video Source | Zone Detection |
|--------|--------------|----------------|
| home | test_videos/home/ | All zones |
| school | test_videos/school/ | All zones (default) |
| office | test_videos/office/ | All zones |

---

## Implemented Enhancements

1. **Google OAuth Integration** ✅
   - Login button on landing page (`components/GoogleLogin.js`)
   - AuthStatus component showing user state
   - Mock OAuth flow for demo (ready for next-auth integration)
   - LocalStorage persistence

2. **Setup Wizard** ✅
   - Step-based camera setup (`components/SetupWizard.js`)
   - Camera Info → Zone Assignment → Test Stream → Confirm
   - RTSP stream support
   - Live stream preview verification

---

## Future Enhancements (Multi-Tenant Ready)

1. **Full OAuth Integration**
   - next-auth provider setup
   - JWT token handling
   - Protected routes

2. **Tenant Management**
   - Organization creation
   - User roles (admin, viewer)
   - Per-tenant camera configs

3. **Database Migration**
   - PostgreSQL/SQLite support
   - Persistent incidents
   - Historical analytics

See `data/tenants.json` for prepared multi-tenant schema.
