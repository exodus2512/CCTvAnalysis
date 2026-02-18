# SentinelAI - Frontend Component Hierarchy & UI Breakdown

## Component Tree

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          SENTINELAI COMPONENT HIERARCHY                                  │
└──────────────────────────────────────────────────────────────────────────────────────────┘

_app.js
├── ThemeProvider (contexts/ThemeContext.js)
│   └── ToastProvider (components/ui/Toast.js)
│       └── Component (Page)


pages/
├── index.js (Landing/Config Page)
│   ├── Hero Section
│   │   ├── Logo & Header
│   │   ├── Quick Stats (cameras, active, online)
│   │   └── Feature Pills
│   │
│   ├── Module Selection
│   │   └── ModuleCard × 3 (home, school, office)
│   │       ├── Icon
│   │       ├── Label
│   │       ├── Description
│   │       └── CheckCircle (selected)
│   │
│   ├── Zone Capabilities
│   │   └── ZoneCard × 4 (outgate, corridor, school_ground, classroom)
│   │       ├── ZoneIcon
│   │       ├── Label
│   │       ├── Description
│   │       └── Badge (model name)
│   │
│   ├── Camera Configuration
│   │   ├── Header (title + Add Camera button)
│   │   └── Camera Table
│   │       ├── Table Header (name, zone, status, active, actions)
│   │       └── Camera Row × N
│   │           ├── Camera Icon
│   │           ├── Name
│   │           ├── Zone Badge
│   │           ├── StatusIndicator
│   │           ├── Checkbox (active)
│   │           └── Actions (Edit, Delete)
│   │
│   ├── Start Monitoring CTA
│   │   └── Button (Start Monitoring)
│   │
│   ├── CameraFormModal (Add/Edit - Legacy)
│   │   ├── Input (name)
│   │   ├── Select (zone)
│   │   └── Buttons (Cancel, Submit)
│   │
│   ├── SetupWizard (New - Step-Based)
│   │   ├── Step 1: Camera Info
│   │   │   ├── Input (name)
│   │   │   ├── Select (source type: test_video/rtsp)
│   │   │   └── Input (RTSP URL - conditional)
│   │   ├── Step 2: Zone Assignment
│   │   │   └── ZoneCard Grid (4 zones)
│   │   ├── Step 3: Test Stream Preview
│   │   │   ├── Preview Area (MJPEG)
│   │   │   ├── Test Button
│   │   │   └── Status Indicator
│   │   └── Step 4: Confirm
│   │       ├── Config Summary Card
│   │       └── Save Button
│   │
│   ├── GoogleLogin (OAuth)
│   │   ├── AuthStatus (header)
│   │   │   ├── User Avatar
│   │   │   ├── User Info
│   │   │   └── Sign Out Button
│   │   └── GoogleLoginButton
│   │
│   └── Footer
│
│
└── monitor.js (Monitoring Dashboard)
    └── DashboardLayout
        ├── Sidebar
        │   ├── Logo
        │   ├── Navigation
        │   │   └── NavItem × 5 (Dashboard, Cameras, Incidents, Analytics, Settings)
        │   ├── Theme Toggle
        │   ├── WebSocket Status
        │   └── Back to Config Link
        │
        ├── TopBar
        │   ├── Title & Subtitle
        │   ├── Stats (Active Cameras, Total Incidents, Critical)
        │   ├── WebSocket Status
        │   └── Alert Bell
        │
        └── Main Content (Tab-based)
            │
            ├── MonitoringView (tab=monitoring)
            │   ├── Camera Grid (2/3 width)
            │   │   └── CameraCard × N
            │   │       ├── Video Feed (MJPEG)
            │   │       ├── Top Overlay (Live Badge, Status, Zone)
            │   │       ├── Bottom Overlay (Name, Model)
            │   │       ├── Expand Button
            │   │       └── Alert Badge (if active)
            │   │
            │   └── Right Panel (1/3 width)
            │       ├── Active Alerts Card
            │       │   └── AlertPopupNew × N
            │       │       ├── Header (type, priority, time)
            │       │       ├── Meta (camera, zone, timestamp)
            │       │       ├── Summary
            │       │       ├── AI Analysis (expandable)
            │       │       └── Actions (Resolve, View, PDF)
            │       │
            │       ├── Quick Stats
            │       │   └── StatBox × 2 (Active Cameras, Incidents Today)
            │       │
            │       └── Mini Analytics
            │           └── By Type Stats
            │
            ├── CamerasView (tab=cameras)
            │   └── Camera Grid (3 columns)
            │       └── CameraCard × N
            │           ├── Video Preview
            │           ├── Status Badge
            │           ├── Name
            │           ├── Zone
            │           └── Expand Button
            │
            ├── IncidentsView (tab=incidents)
            │   └── IncidentTimeline
            │       ├── Search Bar
            │       ├── Filter Button
            │       ├── Filter Panel (zone, type, priority)
            │       ├── Incident List
            │       │   └── IncidentRow × N
            │       │       ├── Priority Indicator
            │       │       ├── Type
            │       │       ├── Camera
            │       │       ├── Zone
            │       │       ├── Time
            │       │       └── Actions (Resolve)
            │       └── Pagination
            │
            ├── AnalyticsView (tab=analytics)
            │   └── AnalyticsCharts
            │       ├── Summary Stats (4 StatBoxes)
            │       │   ├── Total Incidents
            │       │   ├── Today
            │       │   ├── Avg Per Day
            │       │   └── Critical
            │       │
            │       ├── Bar Chart (By Type)
            │       ├── Pie Chart (By Zone)
            │       ├── Line Chart (7-day Trend)
            │       └── Priority Distribution (Pie)
            │
            └── SettingsView (tab=settings)
                └── Settings Card
                    ├── Backend URL
                    ├── WebSocket Status
                    ├── Refresh Rate
                    └── Theme
```

---

## UI Components Library

### Layout Components (`components/layout/`)

| Component | File | Description |
|-----------|------|-------------|
| `DashboardLayout` | `index.js` | Main layout wrapper with Sidebar + TopBar |
| `Sidebar` | `Sidebar.js` | Navigation, theme toggle, WS status |
| `TopBar` | `TopBar.js` | Page title, stats, alerts |

### UI Primitives (`components/ui/`)

| Component | File | Description |
|-----------|------|-------------|
| `Badge` | `Badge.js` | Status/priority badges with variants |
| `Button` | `Button.js` | Primary/secondary/ghost buttons |
| `Card` | `Card.js` | CardHeader, CardTitle, CardContent |
| `EmptyState` | `EmptyState.js` | NoIncidents, NoAlerts, NoCameras |
| `Input` | `Input.js` | Input, Select, Checkbox |
| `Modal` | `Modal.js` | Modal dialog |
| `Skeleton` | `Skeleton.js` | Loading skeletons |
| `StatBox` | `StatBox.js` | Animated stat counter |
| `StatusIndicator` | `StatusIndicator.js` | Online/offline/error indicator |
| `Toast` | `Toast.js` | ToastProvider and useToast hook |

### Feature Components (`components/`)

| Component | File | Description |
|-----------|------|-------------|
| `AlertPopupNew` | `AlertPopupNew.js` | Full alert card with actions |
| `AnalyticsCharts` | `AnalyticsCharts.js` | Recharts visualizations |
| `AnalyticsPanel` | `AnalyticsPanel.js` | Compact analytics summary |
| `IncidentTimeline` | `IncidentTimeline.js` | Filterable incident list |
| `CameraFeed` | `CameraFeed.js` | MJPEG video display |
| `MultiCameraGrid` | `MultiCameraGrid.js` | Grid layout for cameras |
| `AddCameraForm` | `AddCameraForm.js` | Camera creation form |
| `CameraConfig` | `CameraConfig.js` | Camera settings |
| `ModuleSelector` | `ModuleSelector.js` | Module selection cards |
| `SetupWizard` | `SetupWizard.js` | 4-step camera setup wizard (NEW) |
| `GoogleLogin` | `GoogleLogin.js` | OAuth login + AuthStatus (NEW) |

### Hooks (`hooks/`)

| Hook | File | Description |
|------|------|-------------|
| `useWebSocket` | `useWebSocket.js` | WS connection, auto-reconnect, alerts |

### Contexts (`contexts/`)

| Context | File | Description |
|---------|------|-------------|
| `ThemeProvider` | `ThemeContext.js` | Light/dark theme management |

### Libraries (`lib/`)

| File | Description |
|------|-------------|
| `constants.js` | BACKEND_URL, ZONES, MODULES, COLORS |
| `utils.js` | Helper functions (formatters, classnames) |

---

## Page-Level UI Breakdown

### 1. Landing Page (`/`)

**Purpose**: Initial configuration and module selection

**Sections**:
1. **Hero**
   - Logo with gradient background
   - Quick stats (cameras, active, online)
   - Feature pills (Real-time, YOLOv8, Multi-Zone)

2. **Module Selection**
   - 3-column card grid
   - Visual selection with checkmark
   - Module-specific descriptions

3. **Zone Capabilities**
   - 4-column grid
   - Zone icons with descriptions
   - Model badges

4. **Camera Configuration**
   - Data table with CRUD actions
   - Real-time health status
   - Inline toggle for active state

5. **Start CTA**
   - Gradient banner
   - Active camera count
   - Large start button

---

### 2. Monitoring Dashboard (`/monitor`)

**Purpose**: Real-time surveillance and alert management

**Layout**: 3-column (Sidebar | Main | Right Panel)

**Tabs**:
- `monitoring`: Default view with camera grid + alerts
- `cameras`: Camera management grid
- `incidents`: Historical incident list
- `analytics`: Charts and trends
- `settings`: System configuration

---

### 3. Incidents Page (`/monitor?tab=incidents`)

**Purpose**: Search, filter, and manage past incidents

**Features**:
- Full-text search
- Multi-filter (zone, type, priority)
- Pagination (15 per page)
- Mark as resolved
- PDF export

---

### 4. Analytics Page (`/monitor?tab=analytics`)

**Purpose**: Visualize incident patterns and trends

**Charts**:
1. **Bar Chart**: Incidents by event type
2. **Pie Chart**: Incidents by zone
3. **Line Chart**: 7-day trend with priority breakdown
4. **Stat Counters**: Animated totals

---

### 5. Settings Page (`/monitor?tab=settings`)

**Purpose**: System configuration and health monitoring

**Settings**:
- Backend URL display
- WebSocket connection status
- Data refresh rate
- Theme preference

---

## Implemented Features Checklist

| Feature | Status | Component |
|---------|--------|-----------|
| Sidebar (5 nav items) | ✅ | `Sidebar.js` |
| TopBar (stats, alerts, WS) | ✅ | `TopBar.js` |
| Module Selector (card-based) | ✅ | `index.js` |
| Camera Grid (MJPEG) | ✅ | `monitor.js` |
| Alert Popup (priority styling) | ✅ | `AlertPopupNew.js` |
| Real-time Timeline | ✅ | `IncidentTimeline.js` |
| Filter (zone/type/priority) | ✅ | `IncidentTimeline.js` |
| Search | ✅ | `IncidentTimeline.js` |
| Pagination | ✅ | `IncidentTimeline.js` |
| Export PDF | ✅ | Backend `/incident/{id}/pdf` |
| Bar Chart (By Type) | ✅ | `AnalyticsCharts.js` |
| Pie Chart (By Zone) | ✅ | `AnalyticsCharts.js` |
| Time Trend Line | ✅ | `AnalyticsCharts.js` |
| Animated Stat Counters | ✅ | `StatBox.js` |
| WebSocket auto-reconnect | ✅ | `useWebSocket.js` |
| Deduplicated alerts | ✅ | `useWebSocket.js` |
| Camera health indicators | ✅ | `StatusIndicator.js` |
| Light/Dark theme | ✅ | `ThemeContext.js` |
| Toast notifications | ✅ | `Toast.js` |
| Loading skeletons | ✅ | `Skeleton.js` |
| Empty states | ✅ | `EmptyState.js` |
| Camera highlight on alert | ✅ | `monitor.js` |
| Mark alert resolved | ✅ | `useWebSocket.js` |
| Settings page | ✅ | `monitor.js` (SettingsView) |
| Worker status | ✅ | System health endpoint |

---

## Future Enhancements

| Feature | Status | Notes |
|---------|--------|-------|
| Google OAuth | 🔮 | Placeholder ready |
| Tenant Creation | 🔮 | JSON schema prepared |
| CCTV Setup Wizard | 🔮 | Can extend CameraFormModal |
| Test Stream Preview | 🔮 | MJPEG endpoint exists |
| RTSP Configuration | 🔮 | Backend supports rtsp:// |
