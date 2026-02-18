import { useEffect, useState } from 'react';

// ─── API Configuration ───────────────────────────────────────────────────────
// For local development, uncomment: const BACKEND_URL = 'http://localhost:8000';
const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

const ZONE_LABELS = {
  all: { name: 'All Zones', icon: '🔍', color: 'cyan', model: 'ALL' },
  outgate: { name: 'Outgate', icon: '🚗', color: 'blue', model: 'yolov8n.pt' },
  corridor: { name: 'Corridor', icon: '🚶', color: 'green', model: 'yolov8s.pt' },
  school_ground: { name: 'School Ground', icon: '🏃', color: 'orange', model: 'yolov8s.pt' },
  classroom: { name: 'Classroom', icon: '📚', color: 'purple', model: 'yolov8m.pt' },
};

export default function MultiCameraGrid() {
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [selectedModule, setSelectedModule] = useState('school');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const sameCameraSet = (prev, next) => {
    if (prev.length !== next.length) {
      return false;
    }
    for (let i = 0; i < prev.length; i += 1) {
      const a = prev[i];
      const b = next[i];
      if (!b) {
        return false;
      }
      if (a.id !== b.id || a.zone !== b.zone || a.active !== b.active || a.video_path !== b.video_path) {
        return false;
      }
    }
    return true;
  };

  useEffect(() => {
    try {
      const saved = window.localStorage?.getItem('sentinel_config');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed?.module) {
          setSelectedModule(parsed.module);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    const fallbackCameras = () => {
      try {
        const saved = window.localStorage?.getItem('sentinel_config');
        if (!saved) {
          return [];
        }
        const parsed = JSON.parse(saved);
        return parsed?.cameras || [];
      } catch {
        return [];
      }
    };

    const fetchCameras = async () => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);
      try {
        const res = await fetch(`${BACKEND_URL}/api/cameras?module=${encodeURIComponent(selectedModule)}`, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(`Camera API returned ${res.status}`);
        }
        const data = await res.json();
        if (!mounted) {
          return;
        }

        const nextCameras = data.cameras || [];
        setLoadError('');
        setCameras((prev) => (sameCameraSet(prev, nextCameras) ? prev : nextCameras));
        setSelectedCamera((current) => {
          if (!current) {
            return null;
          }
          return nextCameras.find((cam) => cam.id === current.id) || null;
        });
      } catch (err) {
        console.error('Failed to fetch cameras:', err);
        if (!mounted) {
          return;
        }
        const fallback = fallbackCameras();
        if (fallback.length > 0) {
          setCameras(fallback);
          setLoadError(`Backend camera API unavailable. Showing local config (${selectedModule}).`);
        } else {
          setCameras([]);
          setLoadError(`Cannot load camera feeds from backend for module: ${selectedModule}.`);
        }
      } finally {
        clearTimeout(timeoutId);
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchCameras();
    const intervalId = setInterval(fetchCameras, 15000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, [selectedModule]);

  const activeCameras = cameras.filter(c => c.active !== false);

  if (loading) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Camera Feeds</span>
        </div>
        <div className="panel-body text-center py-12 text-gray-400">
          Loading camera feeds...
        </div>
      </div>
    );
  }

  if (!activeCameras.length) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Camera Feeds</span>
        </div>
        <div className="panel-body text-center py-12">
          <div className="text-4xl mb-4">📹</div>
          <div className="text-gray-400">No cameras configured</div>
          {loadError && <div className="text-xs text-red-400 mt-2">{loadError}</div>}
          <div className="text-sm text-gray-500 mt-2">
            Configure cameras on the landing page
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Full view of selected camera */}
      {selectedCamera && (
        <div className="panel">
          <div className="panel-header">
            <div className="flex items-center gap-3">
              <span className="panel-title">{selectedCamera.name}</span>
              <span className="text-xs px-2 py-1 rounded bg-[#242b3d] text-gray-300">
                {ZONE_LABELS[selectedCamera.zone]?.name || selectedCamera.zone}
              </span>
            </div>
            <button
              onClick={() => setSelectedCamera(null)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="relative bg-black aspect-video">
            <img
              src={`${BACKEND_URL}/video/${selectedCamera.id}`}
              alt={selectedCamera.name}
              className="w-full h-full object-contain"
            />
            <CameraOverlay camera={selectedCamera} />
          </div>
        </div>
      )}

      {/* Camera Grid */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Camera Grid</span>
          <span className="text-xs text-gray-500">{activeCameras.length} active feeds</span>
        </div>
        <div className="panel-body p-4">
          {loadError && (
            <div className="mb-3 text-xs text-yellow-400">{loadError}</div>
          )}
          <div className="grid grid-cols-2 gap-4">
            {activeCameras.map((cam) => (
              <CameraFeed
                key={cam.id}
                camera={cam}
                onClick={() => setSelectedCamera(cam)}
                isSelected={selectedCamera?.id === cam.id}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function CameraFeed({ camera, onClick, isSelected }) {
  const [error, setError] = useState(false);
  const zoneInfo = ZONE_LABELS[camera.zone] || { name: camera.zone, icon: '📷', color: 'gray' };

  return (
    <div
      onClick={onClick}
      className={`relative bg-[#0f1419] rounded-lg overflow-hidden cursor-pointer transition-all hover:ring-2 hover:ring-blue-500 ${
        isSelected ? 'ring-2 ring-blue-500' : 'ring-1 ring-[#2f3542]'
      }`}
    >
      {/* Video Feed */}
      <div className="aspect-video bg-black">
        {!error ? (
          <img
            src={`${BACKEND_URL}/video/${camera.id}`}
            alt={camera.name}
            className="w-full h-full object-cover"
            onError={() => setError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <div className="text-3xl mb-2">📷</div>
              <div className="text-xs text-gray-500">No feed available</div>
            </div>
          </div>
        )}
      </div>

      {/* Overlay */}
      <CameraOverlay camera={camera} compact />
    </div>
  );
}

function CameraOverlay({ camera, compact = false }) {
  const zoneInfo = ZONE_LABELS[camera.zone] || { name: camera.zone, icon: '📷', color: 'gray', model: 'yolov8n.pt' };
  const modelName = camera.model || zoneInfo.model || 'yolov8n.pt';
  
  return (
    <>
      {/* Top overlay with gradient */}
      <div className="absolute top-0 left-0 right-0 p-2 bg-gradient-to-b from-black/70 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">{zoneInfo.icon}</span>
            <div>
              <div className={`${compact ? 'text-xs' : 'text-sm'} font-medium text-white`}>
                {camera.name}
              </div>
              <div className={`${compact ? 'text-[10px]' : 'text-xs'} text-gray-300`}>
                {zoneInfo.name}
              </div>
            </div>
          </div>
          {/* Live indicator */}
          <div className="flex items-center gap-1 px-2 py-1 bg-red-600/80 rounded text-[10px] text-white font-medium">
            <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            LIVE
          </div>
        </div>
      </div>

      {/* Bottom overlay with timestamp and model */}
      <div className="absolute bottom-0 left-0 right-0 p-2 bg-gradient-to-t from-black/70 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`${compact ? 'text-[10px]' : 'text-xs'} text-gray-300`}>
              {new Date().toLocaleTimeString()}
            </div>
            {/* Model badge (debug info) */}
            <div className={`${compact ? 'text-[9px]' : 'text-[10px]'} px-1.5 py-0.5 rounded bg-purple-600/50 text-purple-200`}>
              {modelName}
            </div>
          </div>
          <div className={`${compact ? 'text-[10px]' : 'text-xs'} px-2 py-0.5 rounded bg-white/20 text-white`}>
            {camera.id}
          </div>
        </div>
      </div>
    </>
  );
}

