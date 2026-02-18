from fastapi import FastAPI, WebSocket, Request, Response, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
import importlib.util
import sys
import os
import io
import json
import glob
from pathlib import Path
from fastapi.responses import StreamingResponse, JSONResponse
from reportlab.pdfgen import canvas
import cv2
import threading
import time
from typing import Dict, List, Optional
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================
PORT = int(os.getenv("PORT", 8000))
MODULE = os.getenv("MODULE", "school")
LLM_API_BASE = os.getenv("LLM_API_BASE", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "*")  # Set to your Vercel domain in production
AUTO_DISCOVER_TEST_VIDEOS = os.getenv("AUTO_DISCOVER_TEST_VIDEOS", "0").lower() in ("1", "true", "yes", "on")

VIDEO_EXTENSIONS = ("*.mp4", "*.avi", "*.mov", "*.mkv", "*.webm")
ALLOWED_UPLOAD_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ZONE_CYCLE = ["outgate", "corridor", "school_ground", "classroom"]
SUPPORTED_MODULES = ["home", "school", "office"]
DEFAULT_MODULE = MODULE  # Use env var

# Setup logging with colors
import sys
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Colored log formatter."""
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname:8s}{self.RESET}"
        return super().format(record)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter(
    fmt='%(asctime)s %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
))
logging.basicConfig(level=logging.INFO, handlers=[handler])

# Import event engine and alert service (now in same directory)
try:
    from engine import process_event
    from service import trigger_alert
except ImportError:
    process_event = lambda event: {"incident": False}
    trigger_alert = lambda incident: {"alert": False, "summary": "(mock)"}

# Import auth module
try:
    from auth import (
        get_google_auth_url, 
        exchange_code_for_tokens, 
        get_google_user_info,
        get_or_create_user,
        create_jwt_token,
        get_current_user,
        require_auth,
        User,
        TokenResponse,
        FRONTEND_URL,
        JWT_EXPIRATION_HOURS,
    )
    AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
except ImportError as e:
    logging.warning(f"Auth module not available: {e}")
    AUTH_ENABLED = False

app = FastAPI(title="SentinelAI Backend")

# Configure CORS - use FRONTEND_URL env var in production
allowed_origins = ["*"] if FRONTEND_URL == "*" else [
    FRONTEND_URL,
    "http://localhost:3000",  # Local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# IN-MEMORY STATE
# ============================================================================
alerts_history: List[Dict] = []
incidents: Dict[str, Dict] = {}
active_alert_clients: List[WebSocket] = []
alert_broadcast_queue: asyncio.Queue = asyncio.Queue()

# Camera/Zone configuration
camera_configs: Dict[str, Dict] = {}
selected_module: str = DEFAULT_MODULE

# Camera sync caching (prevents repeated discovery)
_camera_sync_cache: Dict[str, float] = {}  # module -> last_sync_timestamp
_CAMERA_SYNC_CACHE_TTL: float = 60.0  # Only re-sync every 60 seconds
_missing_test_videos_logged: bool = False

# Zone definitions
ZONE_TYPES = {
    "outgate": {
        "name": "Outgate / Gate Area",
        "events": ["vehicle_detected", "gate_accident"],
        "description": "Monitor vehicles and potential accidents near gates",
    },
    "corridor": {
        "name": "Corridor / Hallway",
        "events": ["crowd_formation", "fight"],
        "description": "Monitor for crowd gatherings and fights",
    },
    "school_ground": {
        "name": "School Ground / Playground",
        "events": ["crowd_formation", "fight", "weapon_detected"],
        "description": "Monitor outdoor areas for crowd gatherings, fights, and weapons",
    },
    "classroom": {
        "name": "Classroom",
        "events": ["mobile_usage"],
        "description": "Monitor for mobile phone usage during class",
    },
    "all": {
        "name": "Multi-Zone (All Detectors)",
        "events": ["vehicle_detected", "gate_accident", "crowd_formation", "fight", "mobile_usage"],
        "description": "Run all zone detectors simultaneously for comprehensive monitoring",
    },
}


def _get_test_videos_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_videos'))


def _normalize_module(module: Optional[str]) -> str:
    if not module:
        return DEFAULT_MODULE
    module_clean = str(module).strip().lower()
    if module_clean == "workspace":
        module_clean = "office"
    return module_clean if module_clean in SUPPORTED_MODULES else DEFAULT_MODULE


def _module_test_videos_dir(module: Optional[str]) -> str:
    base_dir = _get_test_videos_dir()
    normalized = _normalize_module(module)
    return os.path.join(base_dir, normalized)


def _resolve_video_path(video_path: Optional[str]) -> Optional[str]:
    """Resolve local video paths against common runtime locations."""
    if not video_path:
        return None

    raw = str(video_path).strip()
    if not raw:
        return None

    if raw.startswith(("rtsp://", "http://", "https://")):
        return raw

    if os.path.isabs(raw) and os.path.exists(raw):
        return raw

    backend_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(backend_dir, ".."))
    test_videos_dir = _get_test_videos_dir()

    candidates = [
        os.path.abspath(raw),
        os.path.abspath(os.path.join(backend_dir, raw)),
        os.path.abspath(os.path.join(project_root, raw)),
        os.path.abspath(os.path.join(test_videos_dir, raw)),
        os.path.abspath(os.path.join(test_videos_dir, os.path.basename(raw))),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    return None


def _get_uploaded_videos_dir() -> str:
    upload_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "uploaded_videos"))
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _normalize_camera_id_from_video(video_path: str) -> str:
    stem = Path(video_path).stem.lower().strip()
    cleaned = ''.join(ch if ch.isalnum() else '_' for ch in stem)
    while '__' in cleaned:
        cleaned = cleaned.replace('__', '_')
    cleaned = cleaned.strip('_') or 'video'
    return f"cam_{cleaned}"


def _camera_id_for_module(video_path: str, module: str) -> str:
    base_camera = _normalize_camera_id_from_video(video_path).replace("cam_", "", 1)
    return f"cam_{module}_{base_camera}"


def _friendly_name_from_video(video_path: str) -> str:
    stem = Path(video_path).stem.replace('_', ' ').replace('-', ' ').strip()
    return stem.title() if stem else "Camera"


def _infer_zone_from_name(video_path: str, fallback_index: int) -> str:
    name = Path(video_path).stem.lower()
    keyword_map = {
        "outgate": ["outgate", "gate", "vehicle", "traffic", "parking", "accident"],
        "corridor": ["corridor", "hall", "hallway", "passage", "fight"],
        "school_ground": ["ground", "playground", "field", "yard", "campus", "weapon", "crowd"],
        "classroom": ["class", "classroom", "lecture", "exam"],
    }
    for zone, keywords in keyword_map.items():
        if any(keyword in name for keyword in keywords):
            return zone
    return ZONE_CYCLE[fallback_index % len(ZONE_CYCLE)]


def _infer_zone_from_path(video_path: str, fallback_index: int) -> str:
    zone_dirs = set(ZONE_TYPES.keys()) - {"all"}
    path_parts = [part.lower() for part in Path(video_path).parts]
    for part in path_parts:
        if part in zone_dirs:
            return part
    return _infer_zone_from_name(video_path, fallback_index)


def discover_test_videos(module: Optional[str] = None) -> List[Dict]:
    global _missing_test_videos_logged
    normalized_module = _normalize_module(module or selected_module)
    test_videos_dir = _get_test_videos_dir()
    module_dir = _module_test_videos_dir(normalized_module)
    videos: List[Dict] = []
    logging.info(f"[VIDEO_DISCOVERY] module={normalized_module} base_dir={test_videos_dir} module_dir={module_dir}")
    if not os.path.exists(test_videos_dir):
        if not _missing_test_videos_logged:
            logging.warning(f"[VIDEO_DISCOVERY] test_videos base directory not found: {test_videos_dir}")
            _missing_test_videos_logged = True
        return videos

    candidates: List[str] = []
    if os.path.isdir(module_dir):
        for ext in VIDEO_EXTENSIONS:
            candidates.extend(glob.glob(os.path.join(module_dir, "**", ext), recursive=True))
        logging.info(f"[VIDEO_DISCOVERY] found {len(candidates)} candidate files under module dir")
    if not candidates:
        logging.warning(
            f"[VIDEO_DISCOVERY] no files found under module={normalized_module}; falling back to root test_videos"
        )
        for ext in VIDEO_EXTENSIONS:
            candidates.extend(glob.glob(os.path.join(test_videos_dir, ext)))
    logging.info(f"[VIDEO_DISCOVERY] total candidates={len(candidates)}")

    for index, video_path in enumerate(sorted(candidates, key=lambda p: os.path.basename(p).lower())):
        abs_path = os.path.abspath(video_path)
        mapped_zone = _infer_zone_from_path(abs_path, index)
        camera_id = _camera_id_for_module(abs_path, normalized_module)
        logging.info(
            f"[VIDEO_DISCOVERY] file={abs_path} -> camera_id={camera_id} zone={mapped_zone} module={normalized_module}"
        )
        videos.append({
            "name": os.path.basename(abs_path),
            "path": abs_path,
            "camera_id": camera_id,
            "zone": mapped_zone,
            "module": normalized_module,
        })

    videos.sort(key=lambda item: item["name"].lower())
    return videos


def sync_camera_configs_from_test_videos(module: Optional[str] = None, force: bool = False) -> None:
    """Sync camera configs from test videos. Uses caching to avoid repeated discovery."""
    if not AUTO_DISCOVER_TEST_VIDEOS:
        return

    normalized_module = _normalize_module(module or selected_module)
    
    # Check cache - skip sync if recently done (unless forced)
    if not force:
        last_sync = _camera_sync_cache.get(normalized_module, 0)
        if time.time() - last_sync < _CAMERA_SYNC_CACHE_TTL:
            return  # Skip, cache is still valid
    
    videos = discover_test_videos(normalized_module)
    discovered_ids = set()
    logging.info(f"[CAMERA_SYNC] start module={normalized_module} videos={len(videos)}")

    for camera_id, config in list(camera_configs.items()):
        if config.get("source") == "test_video":
            del camera_configs[camera_id]

    for index, video in enumerate(videos):
        camera_id = video["camera_id"]
        discovered_ids.add(camera_id)

        existing = camera_configs.get(camera_id, {})
        zone = existing.get("zone") or video.get("zone") or _infer_zone_from_name(video["path"], index)
        active = existing.get("active", True)
        name = existing.get("name") or _friendly_name_from_video(video["path"])

        camera_configs[camera_id] = {
            **existing,
            "id": camera_id,
            "name": name,
            "zone": zone,
            "video_path": video["path"],
            "active": active,
            "source": "test_video",
            "video_name": video["name"],
            "module": normalized_module,
        }
        logging.info(
            f"[CAMERA_SYNC] mapped camera={camera_id} name={name} video={video['name']} zone={zone} module={normalized_module}"
        )

    logging.info(
        f"[CAMERA_SYNC] completed module={normalized_module} total_cameras={len(camera_configs)}"
    )
    
    # Update cache timestamp
    _camera_sync_cache[normalized_module] = time.time()


# ============================================================================
# STARTUP EVENT - Run discovery ONCE at startup
# ============================================================================
@app.on_event("startup")
async def startup_event():
    """Initialize camera configs on server startup."""
    logging.info("[STARTUP] Initializing camera configurations...")
    sync_camera_configs_from_test_videos(selected_module, force=True)
    logging.info(f"[STARTUP] Loaded {len(camera_configs)} cameras for module={selected_module}")


# Video capture instances for streaming
video_captures: Dict[str, cv2.VideoCapture] = {}
video_locks: Dict[str, threading.Lock] = {}

# ============================================================================
# HEALTH CHECK
# ============================================================================
@app.get("/health")
def health():
    return {"status": "ok", "cameras": len(camera_configs), "incidents": len(incidents)}


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================
@app.get("/auth/google")
async def google_auth_redirect():
    """Redirect to Google OAuth consent screen."""
    if not AUTH_ENABLED:
        return JSONResponse({"error": "Auth is disabled"}, status_code=400)
    auth_url = get_google_auth_url()
    return JSONResponse({"auth_url": auth_url})


@app.get("/auth/google/login")
async def google_login_redirect():
    """Direct redirect to Google OAuth (for browser navigation)."""
    if not AUTH_ENABLED:
        return JSONResponse({"error": "Auth is disabled"}, status_code=400)
    from fastapi.responses import RedirectResponse
    auth_url = get_google_auth_url()
    return RedirectResponse(url=auth_url)


@app.get("/auth/google/callback")
async def google_auth_callback(code: str = None, error: str = None):
    """Handle Google OAuth callback and issue JWT."""
    from fastapi.responses import RedirectResponse
    
    if not AUTH_ENABLED:
        return JSONResponse({"error": "Auth is disabled"}, status_code=400)
    
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_error={error}")
    
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=no_code")
    
    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        
        if not access_token:
            return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=no_access_token")
        
        # Get user info from Google
        google_user = await get_google_user_info(access_token)
        
        # Get or create user in our system
        user = get_or_create_user(google_user)
        
        # Create JWT token
        jwt_token = create_jwt_token(user)
        
        # Redirect to frontend with token
        return RedirectResponse(
            url=f"{FRONTEND_URL}?token={jwt_token}&user={user.name}"
        )
    except Exception as e:
        logging.error(f"OAuth callback error: {e}")
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=callback_failed")


@app.get("/auth/me")
async def get_me(user: User = Depends(require_auth)):
    """Get current authenticated user info."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "role": user.role,
    }


@app.get("/auth/verify")
async def verify_token(user: User = Depends(get_current_user)):
    """Verify if current token is valid. Returns user if valid, null if not."""
    if user:
        return {
            "valid": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "role": user.role,
            }
        }
    return {"valid": False, "user": None}


# ============================================================================
# ZONE CONFIGURATION ENDPOINTS
# ============================================================================
@app.get("/api/zones")
def get_zones():
    """Get all zone type definitions."""
    return {"zones": ZONE_TYPES}


@app.get("/api/modules")
def get_modules():
    """Get supported modules and current selection."""
    return {"modules": SUPPORTED_MODULES, "selected_module": selected_module}


@app.get("/api/module/current")
def get_current_module():
    """Get the current module used for test video discovery."""
    return {"module": selected_module}


@app.post("/api/module")
async def set_current_module(data: dict):
    """Set current module (home/school/office) for camera discovery."""
    global selected_module
    selected_module = _normalize_module(data.get("module"))
    sync_camera_configs_from_test_videos(selected_module)
    return {
        "success": True,
        "module": selected_module,
        "cameras": [c for c in camera_configs.values() if c.get("source") != "test_video" or c.get("module") == selected_module],
    }


@app.get("/api/cameras")
def get_cameras(request: Request):
    """Get all camera configurations."""
    requested_module = request.query_params.get("module")
    active_module = _normalize_module(requested_module or selected_module)
    sync_camera_configs_from_test_videos(active_module)
    visible_cameras = [
        cam for cam in camera_configs.values()
        if cam.get("source") != "test_video" or cam.get("module") == active_module
    ]
    return {"module": active_module, "cameras": visible_cameras}


@app.get("/api/camera/{camera_id}")
def get_camera(camera_id: str):
    """Get specific camera configuration."""
    sync_camera_configs_from_test_videos(selected_module)
    if camera_id not in camera_configs:
        return JSONResponse({"error": "Camera not found"}, status_code=404)
    return camera_configs[camera_id]


@app.post("/api/camera/{camera_id}")
async def update_camera(camera_id: str, config: dict):
    """Update camera configuration."""
    sync_camera_configs_from_test_videos(selected_module)
    if camera_id not in camera_configs:
        camera_configs[camera_id] = {"id": camera_id}
    
    camera_configs[camera_id].update(config)
    logging.info(f"Updated camera config: {camera_id} -> {camera_configs[camera_id]}")
    return {"success": True, "camera": camera_configs[camera_id]}


@app.post("/api/camera/{camera_id}/zone")
async def set_camera_zone(camera_id: str, data: dict):
    """Set zone for a camera."""
    zone = data.get("zone")
    if zone not in ZONE_TYPES:
        return JSONResponse({"error": f"Invalid zone: {zone}"}, status_code=400)
    
    if camera_id not in camera_configs:
        camera_configs[camera_id] = {"id": camera_id, "name": camera_id, "active": True}
    
    camera_configs[camera_id]["zone"] = zone
    logging.info(f"Camera {camera_id} zone set to: {zone}")
    return {"success": True, "camera": camera_configs[camera_id]}


# ============================================================================
# DYNAMIC CAMERA CREATION ENDPOINT
# ============================================================================
@app.post("/api/camera")
async def create_camera(data: dict):
    """
    Create a new camera dynamically from video path and zone.
    
    Input:
    {
        "video_path": "path/to/video.mp4",
        "zone": "corridor",
        "name": "Optional camera name"
    }
    
    Returns:
    {
        "success": true,
        "camera_id": "cam_xxx",
        "camera": { ... camera config ... }
    }
    """
    video_path = data.get("video_path")
    zone = data.get("zone")
    name = data.get("name")
    
    # Validate inputs
    if not video_path:
        return JSONResponse({"error": "video_path is required"}, status_code=400)
    
    if not zone:
        return JSONResponse({"error": "zone is required"}, status_code=400)
    
    if zone not in ZONE_TYPES:
        return JSONResponse({"error": f"Invalid zone: {zone}. Valid zones: {list(ZONE_TYPES.keys())}"}, status_code=400)
    
    # Check if video exists (if local path)
    abs_path = os.path.abspath(video_path)
    if not video_path.startswith(("rtsp://", "http://", "https://")) and not os.path.exists(abs_path):
        # Check in test_videos directory
        test_video_path = os.path.join(_get_test_videos_dir(), os.path.basename(video_path))
        if os.path.exists(test_video_path):
            abs_path = test_video_path
        else:
            return JSONResponse({"error": f"Video file not found: {video_path}"}, status_code=400)
    
    # Generate unique camera ID
    camera_id = _normalize_camera_id_from_video(abs_path)
    
    # Handle duplicate IDs
    base_id = camera_id
    counter = 1
    while camera_id in camera_configs:
        camera_id = f"{base_id}_{counter}"
        counter += 1
    
    # Generate name if not provided
    if not name:
        name = _friendly_name_from_video(abs_path)
    
    # Create camera config
    camera_config = {
        "id": camera_id,
        "name": name,
        "zone": zone,
        "video_path": abs_path,
        "active": True,
        "source": "dynamic",
        "video_name": os.path.basename(abs_path),
        "model": _get_zone_model(zone),
        "created_at": time.time(),
    }
    
    camera_configs[camera_id] = camera_config
    
    logging.info(f"🎥 Created new camera: {camera_id} -> zone={zone}, video={os.path.basename(abs_path)}")
    
    return {
        "success": True,
        "camera_id": camera_id,
        "camera": camera_config,
    }


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Upload a local test video to backend storage and return its absolute path."""
    if not file.filename:
        return JSONResponse({"error": "Invalid file name"}, status_code=400)

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return JSONResponse(
            {"error": f"Unsupported video format: {ext}. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}"},
            status_code=400,
        )

    upload_dir = _get_uploaded_videos_dir()
    safe_stem = "".join(ch if ch.isalnum() else "_" for ch in Path(file.filename).stem).strip("_") or "video"
    unique_name = f"{safe_stem}_{int(time.time() * 1000)}{ext}"
    target_path = os.path.join(upload_dir, unique_name)

    try:
        content = await file.read()
        with open(target_path, "wb") as out:
            out.write(content)
    except Exception as exc:
        logging.error(f"Video upload failed: {exc}")
        return JSONResponse({"error": "Failed to store uploaded video"}, status_code=500)

    return {
        "success": True,
        "filename": unique_name,
        "video_path": os.path.abspath(target_path),
    }


def _get_zone_model(zone: str) -> str:
    """Get the model file for a zone."""
    zone_models = {
        "outgate": "yolov8n.pt",
        "corridor": "yolov8s.pt",
        "school_ground": "yolov8s.pt",
        "classroom": "yolov8m.pt",
    }
    return zone_models.get(zone, "yolov8n.pt")


@app.delete("/api/camera/{camera_id}")
async def delete_camera(camera_id: str):
    """Delete a camera."""
    if camera_id not in camera_configs:
        return JSONResponse({"error": "Camera not found"}, status_code=404)
    
    config = camera_configs.pop(camera_id)
    logging.info(f"🗑️ Deleted camera: {camera_id}")
    
    # Clean up video capture if exists
    if camera_id in video_captures:
        try:
            video_captures[camera_id].release()
        except:
            pass
        del video_captures[camera_id]
    
    return {"success": True, "deleted": camera_id}


@app.get("/api/camera/{camera_id}/health")
async def camera_health(camera_id: str):
    """
    Check health status of a camera.
    Returns online if camera exists and has a working video source.
    """
    if camera_id not in camera_configs:
        return JSONResponse({"status": "offline", "error": "Camera not found"}, status_code=404)
    
    config = camera_configs[camera_id]
    
    # Check if camera has a video capture
    if camera_id in video_captures:
        cap = video_captures[camera_id]
        if cap is not None and cap.isOpened():
            return {
                "status": "online",
                "camera_id": camera_id,
                "zone": config.get("zone"),
                "active": config.get("active", True),
            }
    
    # Try to check if video source is accessible
    video_path = config.get("video_path") or config.get("source")
    if video_path in ("test_video", "rtsp"):
        video_path = None
    resolved_video_path = _resolve_video_path(video_path)
    if resolved_video_path:
        return {
            "status": "online",
            "camera_id": camera_id,
            "zone": config.get("zone"),
            "active": config.get("active", True),
            "source": "file",
        }
    
    return {
        "status": "offline",
        "camera_id": camera_id,
        "zone": config.get("zone"),
        "active": config.get("active", True),
        "reason": "No video source found",
    }


@app.get("/api/system/health")
async def system_health():
    """
    Get overall system health status.
    """
    online_cameras = 0
    total_cameras = len(camera_configs)
    
    for cam_id, config in camera_configs.items():
        if cam_id in video_captures:
            cap = video_captures[cam_id]
            if cap is not None and cap.isOpened():
                online_cameras += 1
        else:
            video_path = config.get("source") or config.get("video_path")
            if video_path and os.path.exists(video_path):
                online_cameras += 1
    
    ws_connected = len(active_alert_clients)
    
    return {
        "status": "healthy" if online_cameras > 0 or total_cameras == 0 else "degraded",
        "cameras": {
            "total": total_cameras,
            "online": online_cameras,
            "offline": total_cameras - online_cameras,
        },
        "websocket_clients": ws_connected,
        "incidents_count": len(incidents),
        "alerts_count": len(alerts_history),
        "module": selected_module,
    }


# ============================================================================
# TEST VIDEO DISCOVERY
# ============================================================================
@app.get("/api/test_videos")
def list_test_videos(request: Request):
    """List available test videos for a module from test_videos/<module> folder."""
    requested_module = request.query_params.get("module")
    active_module = _normalize_module(requested_module or selected_module)
    test_videos_dir = _module_test_videos_dir(active_module)
    videos = discover_test_videos(active_module)
    return {"module": active_module, "videos": videos, "directory": test_videos_dir}


# ============================================================================
# VIDEO STREAMING ENDPOINTS
# ============================================================================
def get_video_capture(camera_id: str) -> Optional[cv2.VideoCapture]:
    """Get or create video capture for a camera."""
    sync_camera_configs_from_test_videos(selected_module)
    config = camera_configs.get(camera_id)
    if not config:
        return None
    
    video_path = config.get("video_path", "")
    
    # Try configured video path
    resolved_video_path = _resolve_video_path(video_path)
    if resolved_video_path:
        cap = cv2.VideoCapture(resolved_video_path)
        if cap.isOpened():
            return cap
    
    # Try test_videos folder based on zone (only when auto-discovery is enabled)
    if not AUTO_DISCOVER_TEST_VIDEOS:
        return None

    # Try test_videos folder based on zone
    zone = config.get("zone", "")
    test_videos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../test_videos'))
    
    # Look for video matching zone name
    for ext in ['mp4', 'avi', 'mov', 'mkv']:
        zone_video = os.path.join(test_videos_dir, f"{zone}.{ext}")
        if os.path.exists(zone_video):
            cap = cv2.VideoCapture(zone_video)
            if cap.isOpened():
                return cap
    
    # Try any available video in test_videos
    for video in discover_test_videos():
        cap = cv2.VideoCapture(video["path"])
        if cap.isOpened():
            return cap
    
    # Fallback to webcam
    for idx in range(4):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            return cap
        cap.release()
    
    return None


def gen_video_frames(camera_id: str):
    """Generate MJPEG frames for a specific camera."""
    cap = get_video_capture(camera_id)
    if cap is None:
        # Return placeholder frame
        placeholder = create_placeholder_frame(camera_id)
        _, buffer = cv2.imencode('.jpg', placeholder)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        return
    
    config = camera_configs.get(camera_id, {})
    zone = config.get("zone", "unknown")
    
    while True:
        success, frame = cap.read()
        if not success:
            # Loop video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        # Add zone overlay
        frame = add_frame_overlay(frame, camera_id, zone)
        
        # Overlay latest detection boxes for this camera
        for alert_data in reversed(alerts_history[-10:]):
            event = alert_data.get("event", {})
            if event.get("camera_id") == camera_id or event.get("zone") == zone:
                boxes = event.get("bounding_boxes", [])
                for box in boxes:
                    if len(box) == 4:
                        x1, y1, x2, y2 = [int(v) for v in box]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                break
        
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.033)  # ~30 FPS
    
    cap.release()


def create_placeholder_frame(camera_id: str):
    """Create a placeholder frame when no video source is available."""
    # Create dark placeholder
    import numpy as np
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (30, 30, 30)  # Dark gray
    
    config = camera_configs.get(camera_id, {})
    
    # Add text
    cv2.putText(frame, "No Video Source", (180, 220), cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)
    cv2.putText(frame, f"Camera: {config.get('name', camera_id)}", (160, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 1)
    cv2.putText(frame, f"Zone: {config.get('zone', 'Not configured')}", (180, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 1)
    
    return frame


def add_frame_overlay(frame, camera_id: str, zone: str):
    """Add overlay information to frame."""
    h, w = frame.shape[:2]
    
    # Semi-transparent header bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)
    
    # Zone label
    zone_label = ZONE_TYPES.get(zone, {}).get("name", zone)
    cv2.putText(frame, zone_label, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Live indicator
    cv2.circle(frame, (w - 30, 20), 8, (0, 0, 255), -1)
    cv2.putText(frame, "LIVE", (w - 80, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    # Timestamp
    timestamp = time.strftime("%H:%M:%S")
    cv2.putText(frame, timestamp, (w - 100, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    
    return frame


@app.get("/video/{camera_id}")
def video_feed(camera_id: str):
    """MJPEG stream for a specific camera."""
    return StreamingResponse(
        gen_video_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# Legacy camera feed endpoint
@app.get("/camera_feed")
def camera_feed():
    """Legacy single camera feed endpoint."""
    return StreamingResponse(
        gen_video_frames("cam_outgate"),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ============================================================================
# EVENT INGEST
# ============================================================================
@app.post("/event")
async def receive_event(event: dict, request: Request = None):
    camera_id = event.get('camera_id', 'unknown')
    zone = event.get('zone', 'unknown')
    event_type = event.get('event_type', 'unknown')
    detected_by_zone = event.get('detected_by_zone', zone)
    confidence = event.get('confidence', 0.0)
    event_id = event.get('event_id', 'n/a')
    timestamp = event.get('timestamp', 'n/a')
    boxes_count = len(event.get('bounding_boxes', []) or [])

    # Validate event schema
    required_fields = ['event_id', 'camera_id', 'zone', 'event_type', 'confidence', 'timestamp']
    missing = [f for f in required_fields if f not in event]
    if missing:
        logging.warning(
            f"[EVENT_SCHEMA_INVALID] event_id={event_id} camera={camera_id} "
            f"missing_fields={missing}"
        )

    logging.info(
        "[EVENT_RX_ACCEPT] "
        f"event_id={event_id} camera={camera_id} zone={zone} detected_by_zone={detected_by_zone} "
        f"event_type={event_type} confidence={confidence:.2f} boxes={boxes_count} ts={timestamp}"
    )
    
    result = process_event(event)
    suspicion_score = float(result.get("suspicion_score", 0.0) or 0.0)
    priority = result.get("priority", "n/a")
    timeline = result.get("timeline", {}) or {}
    frames_considered = timeline.get("frames_considered", 0)

    if result.get("incident"):
        alert = trigger_alert(result)
        incident_id = event.get("event_id")
        incidents[incident_id] = {"event": event, "alert": alert}
        alerts_history.append({"event": event, "alert": alert})

        logging.warning(
            "[EVENT_INCIDENT_DETECTED] "
            f"event_id={event_id} type={event_type} camera={camera_id} zone={zone} "
            f"priority={priority} suspicion={suspicion_score:.2f} frames={frames_considered}"
        )
        logging.debug(f"[ALERT_PAYLOAD] {str(alert)[:200]}") 
        
        # Broadcast to all connected WebSocket clients
        # Queue with id for WebSocket delivery
        await alert_broadcast_queue.put({"event": event, "alert": alert})
        logging.info(
            f"[BROADCAST_QUEUED] event_id={event_id} type={event_type} "
            f"queue_size={alert_broadcast_queue.qsize()}"
        )
        return {"received": True, "alert": alert, "incident_id": incident_id}

    logging.debug(
        "[EVENT_NO_INCIDENT] "
        f"event_id={event_id} type={event_type} camera={camera_id} zone={zone} "
        f"confidence={confidence:.2f} suspicion={suspicion_score:.2f} priority={priority} "
        f"frames={frames_considered}"
    )
    return {"received": True, "alert": None}


# ============================================================================
# WEBSOCKET FOR REAL-TIME ALERTS
# ============================================================================
@app.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket):
    client_id = id(websocket)
    await websocket.accept()
    active_alert_clients.append(websocket)
    logging.info(f"[WS_CLIENT_CONNECTED] id={client_id} active_clients={len(active_alert_clients)}")
    
    try:
        # On connect, send the last alert if available
        if alerts_history:
            last_alert = alerts_history[-1]
            await websocket.send_json(last_alert)
            logging.debug(
                f"[WS_INITIAL_ALERT] client={client_id} "
                f"event_type={last_alert.get('event', {}).get('event_type', 'unknown')}"
            )
        else:
            await websocket.send_json({"msg": "No alerts yet."})
            logging.debug(f"[WS_INITIAL_EMPTY] client={client_id}")
        
        # Broadcast loop: listen for new alerts and send to all clients
        while True:
            alert = await alert_broadcast_queue.get()
            event_type = alert.get('event', {}).get('event_type', 'unknown')
            event_id = alert.get('event', {}).get('event_id', 'null')
            active_count = len(active_alert_clients)
            
            # STEP 1: LOG EXACT PAYLOAD BEFORE BROADCAST
            payload_to_send = {
                "id": event_id,  # ADD ID FOR FRONTEND
                "event": alert.get('event', {}),
                "alert": alert.get('alert', {})
            }
            logging.info(
                f"[WS_BROADCAST_START] event_id={event_id} type={event_type} "
                f"clients={active_count}"
            )
            logging.debug(
                f"[WS_PAYLOAD_DEBUG] Sending to {active_count} clients: "
                f"id={event_id} has_event={bool(payload_to_send['event'])} "
                f"has_alert={bool(payload_to_send['alert'])}"
            )
            
            # Broadcast to all connected clients
            failed_clients = []
            for idx, client in enumerate(active_alert_clients):
                try:
                    # Send payload WITH id field for frontend IncidentList
                    await client.send_json(payload_to_send)
                    logging.debug(
                        f"[WS_SEND_OK] event_id={event_id} client={idx} "
                        f"type={event_type}"
                    )
                except Exception as e:
                    logging.warning(
                        f"[WS_SEND_FAIL] event_id={event_id} client={idx} "
                        f"error={str(e)[:100]}"
                    )
                    failed_clients.append(client)
            
            # Remove dead clients
            for client in failed_clients:
                if client in active_alert_clients:
                    active_alert_clients.remove(client)
                    logging.info(
                        f"[WS_CLIENT_REMOVED] event_id={event_id} "
                        f"remaining={len(active_alert_clients)}"
                    )
            
            logging.info(
                f"[WS_BROADCAST_DONE] event_id={event_id} type={event_type} "
                f"success={active_count - len(failed_clients)}/{active_count}"
            )
    except Exception as e:
        logging.error(
            f"[WS_HANDLER_ERROR] client={client_id} error={e}",
            exc_info=True
        )
    finally:
        if websocket in active_alert_clients:
            active_alert_clients.remove(websocket)
        logging.info(
            f"[WS_CLIENT_DISCONNECTED] id={client_id} "
            f"remaining_clients={len(active_alert_clients)}"
        )


# ============================================================================
# INCIDENTS AND ANALYTICS
# ============================================================================
@app.get("/incidents")
def list_incidents():
    data = []
    for incident_id, payload in incidents.items():
        data.append({
            "id": incident_id,
            "event": payload.get("event", {}),
            "alert": payload.get("alert", {}),
        })

    totals = {
        "total_incidents": len(data),
        "critical_or_high": 0,
        "avg_suspicion_score": None,
    }
    by_type = {}
    by_zone = {}
    suspicion_scores = []

    for item in data:
        alert = item.get("alert") or {}
        event = item.get("event") or {}
        priority = (alert.get("priority") or "").lower()
        if priority in ("high", "critical"):
            totals["critical_or_high"] += 1
        if alert.get("suspicion_score") is not None:
            suspicion_scores.append(alert["suspicion_score"])
        
        etype = event.get("event_type") or "unknown"
        by_type[etype] = by_type.get(etype, 0) + 1
        
        zone = event.get("zone") or "unknown"
        by_zone[zone] = by_zone.get(zone, 0) + 1

    if suspicion_scores:
        totals["avg_suspicion_score"] = sum(suspicion_scores) / len(suspicion_scores)

    return {
        "incidents": data,
        "totals": totals,
        "by_type": by_type,
        "by_zone": by_zone,
    }


@app.get("/incident/{incident_id}/summary")
async def get_llm_summary(incident_id: str):
    incident = incidents.get(incident_id)
    if not incident:
        return {"error": "Incident not found"}
    return {"summary": incident["alert"].get("summary", "No summary available")}


@app.get("/incident/{incident_id}/pdf")
async def get_incident_pdf(incident_id: str):
    incident = incidents.get(incident_id)
    if not incident:
        return Response(content="Incident not found", status_code=404)
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "SentinelAI Incident Report")
    p.setFont("Helvetica", 12)
    p.drawString(100, 770, f"Incident ID: {incident_id}")
    p.drawString(100, 750, f"Event Type: {incident['event'].get('event_type', 'N/A')}")
    p.drawString(100, 730, f"Zone: {incident['event'].get('zone', 'N/A')}")
    p.drawString(100, 710, f"Camera: {incident['event'].get('camera_id', 'N/A')}")
    p.drawString(100, 690, f"Confidence: {incident['event'].get('confidence', 'N/A')}")
    p.drawString(100, 670, f"Priority: {incident['alert'].get('priority', 'N/A')}")
    
    ts = incident['event'].get('timestamp')
    if ts:
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
        p.drawString(100, 650, f"Timestamp: {time_str}")
    
    p.drawString(100, 620, "Summary:")
    summary = incident['alert'].get('summary', 'No summary available')
    # Word wrap summary
    y = 600
    words = summary.split()
    line = ""
    for word in words:
        if len(line + word) < 70:
            line += word + " "
        else:
            p.drawString(100, y, line)
            y -= 15
            line = word + " "
    if line:
        p.drawString(100, y, line)
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=incident_{incident_id}.pdf"}
    )


# ============================================================================
# STATS ENDPOINT
# ============================================================================
@app.get("/api/stats")
def get_stats():
    """Get real-time statistics for dashboard."""
    sync_camera_configs_from_test_videos(selected_module)
    return {
        "total_incidents": len(incidents),
        "active_cameras": sum(1 for c in camera_configs.values() if c.get("active")),
        "total_cameras": len(camera_configs),
        "alerts_count": len(alerts_history),
        "zones_monitored": len(set(c.get("zone") for c in camera_configs.values() if c.get("zone"))),
    }


# ============================================================================
# DEBUG ENDPOINT - Verify event flow and WebSocket connectivity
# ============================================================================
@app.get("/api/debug/ping")
async def debug_ping():
    """
    Send a debug ping through the WebSocket broadcast system.
    Useful for testing end-to-end event delivery without running workers.
    
    Usage: curl http://localhost:8000/api/debug/ping
    
    Monitor logs:
    - Backend: [DEBUG_PING] messages
    - Frontend: [WS_MESSAGE_RX] console logs
    """
    debug_event = {
        "event_id": f"debug_ping_{int(time.time() * 1000)}",
        "camera_id": "DEBUG_CAMERA",
        "zone": "debug",
        "event_type": "debug_ping",
        "confidence": 1.0,
        "timestamp": time.time(),
        "bounding_boxes": [],
        "metadata": {"source": "debug_endpoint"},
    }
    
    debug_alert = {
        "event": debug_event,
        "alert": {
            "priority": "low",
            "summary": "Debug ping received - event flow working correctly",
            "suspicion_score": 0.0,
            "recommended_actions": ["Monitor WebSocket logs in frontend console"],
        }
    }
    
    logging.info(
        f"[DEBUG_PING] event_id={debug_event['event_id']} "
        f"sending to {len(active_alert_clients)} WebSocket clients"
    )
    
    # Queue the debug alert for broadcast
    await alert_broadcast_queue.put(debug_alert)
    
    return {
        "msg": "Debug ping sent",
        "event_id": debug_event["event_id"],
        "ws_clients": len(active_alert_clients),
        "queue_depth": alert_broadcast_queue.qsize(),
    }


@app.on_event("startup")
async def startup_sync_cameras():
    logging.info("="*60)
    logging.info("🎬 SentinelAI Backend Starting...")
    logging.info("="*60)
    sync_camera_configs_from_test_videos(selected_module)
    logging.info(f"📦 Active module: {selected_module}")
    logging.info(f"📹 Discovered {len(camera_configs)} cameras from test videos")
    for cam_id, cam in camera_configs.items():
        logging.info(f"  • {cam.get('name')} [{cam_id}] - Zone: {cam.get('zone')} - Video: {cam.get('video_name')}")
    logging.info("="*60)
    logging.info("✓ Backend ready! Listening for events...")
    logging.info("="*60)
    logging.info(f"🔧 DEBUG: Test endpoint at http://localhost:8000/api/debug/ping")


if __name__ == "__main__":
    logging.info(f"Starting server on port {PORT}...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
