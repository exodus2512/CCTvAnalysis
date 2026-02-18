import { useState, useEffect } from 'react';

// ─── API Configuration ───────────────────────────────────────────────────────
// For local development, uncomment: const BACKEND_URL = 'http://localhost:8000';
const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

const ZONE_TYPES = {
  all: {
    name: 'All Zones',
    description: 'Run all detectors simultaneously',
    icon: '🔍',
    color: 'cyan',
    model: 'ALL',
  },
  outgate: {
    name: 'Outgate',
    description: 'Vehicle detection, gate accidents',
    icon: '🚗',
    color: 'cyan',
    model: 'yolov8n.pt',
  },
  corridor: {
    name: 'Corridor',
    description: 'Crowd formation, fights',
    icon: '🚶',
    color: 'green',
    model: 'yolov8s.pt',
  },
  school_ground: {
    name: 'School Ground',
    description: 'Crowd formation, fights',
    icon: '🏫',
    color: 'orange',
    model: 'yolov8s.pt',
  },
  classroom: {
    name: 'Classroom',
    description: 'Mobile phone detection',
    icon: '📱',
    color: 'purple',
    model: 'yolov8m.pt',
  },
};

const INPUT_MODES = {
  webcam: { label: 'Webcam', icon: '📹' },
  rtsp: { label: 'RTSP/IP', icon: '🌐' },
  file: { label: 'Video File', icon: '🎬' },
};

export default function CameraConfig({ camera, onSave, onDelete }) {
  const [config, setConfig] = useState({
    id: camera?.id || `cam_${Date.now()}`,
    name: camera?.name || 'Camera 1',
    zone: camera?.zone || 'corridor',
    mode: camera?.mode || 'file',
    url: camera?.url || '',
    enabled: camera?.enabled ?? true,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (camera) {
      setConfig({
        id: camera.id,
        name: camera.name || 'Camera',
        zone: camera.zone || 'corridor',
        mode: camera.mode || 'file',
        url: camera.url || '',
        enabled: camera.enabled ?? true,
      });
    }
  }, [camera]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/camera/${config.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (response.ok && onSave) {
        onSave(config);
      }
    } catch (err) {
      console.error('Failed to save camera:', err);
    }
    setSaving(false);
  };

  const zoneInfo = ZONE_TYPES[config.zone] || ZONE_TYPES.corridor;

  return (
    <div className="bg-[#1a1f2e] border border-gray-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="bg-[#242b3d] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${config.enabled ? 'bg-green-500' : 'bg-gray-500'}`} />
          <input
            type="text"
            value={config.name}
            onChange={(e) => setConfig({ ...config, name: e.target.value })}
            className="bg-transparent text-white font-medium text-sm border-none outline-none focus:ring-0"
            placeholder="Camera name"
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-xs text-gray-400">Enabled</span>
            <div 
              className={`w-8 h-4 rounded-full transition-colors cursor-pointer ${config.enabled ? 'bg-cyan-500' : 'bg-gray-600'}`}
              onClick={() => setConfig({ ...config, enabled: !config.enabled })}
            >
              <div className={`w-3 h-3 mt-0.5 rounded-full bg-white transition-transform ${config.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </div>
          </label>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Zone Selection */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">Detection Zone</label>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(ZONE_TYPES).map(([key, zone]) => (
              <button
                key={key}
                onClick={() => setConfig({ ...config, zone: key })}
                className={`p-3 rounded-lg border text-left transition-all ${
                  config.zone === key
                    ? 'border-cyan-500 bg-cyan-500/10'
                    : 'border-gray-700 bg-[#242b3d] hover:border-gray-600'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{zone.icon}</span>
                  <div>
                    <div className={`text-sm font-medium ${config.zone === key ? 'text-cyan-400' : 'text-white'}`}>
                      {zone.name}
                    </div>
                    <div className="text-[10px] text-gray-500">{zone.description}</div>
                    <div className="text-[9px] text-gray-600 mt-0.5">Model: {zone.model}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Input Mode */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">Input Source</label>
          <div className="flex gap-2">
            {Object.entries(INPUT_MODES).map(([key, mode]) => (
              <button
                key={key}
                onClick={() => setConfig({ ...config, mode: key })}
                className={`flex-1 py-2 px-3 rounded-lg border text-xs font-medium transition-all ${
                  config.mode === key
                    ? 'border-cyan-500 bg-cyan-500/10 text-cyan-400'
                    : 'border-gray-700 bg-[#242b3d] text-gray-400 hover:border-gray-600'
                }`}
              >
                <span className="mr-1">{mode.icon}</span> {mode.label}
              </button>
            ))}
          </div>
        </div>

        {/* URL Input */}
        {config.mode !== 'webcam' && (
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-2">
              {config.mode === 'rtsp' ? 'RTSP URL' : 'Video File Path'}
            </label>
            <input
              type="text"
              value={config.url}
              onChange={(e) => setConfig({ ...config, url: e.target.value })}
              placeholder={
                config.mode === 'rtsp'
                  ? 'rtsp://user:pass@ip:554/stream'
                  : 'C:\\path\\to\\video.mp4'
              }
              className="w-full bg-[#242b3d] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2">
          {onDelete && (
            <button
              onClick={() => onDelete(config.id)}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Remove Camera
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="ml-auto px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </div>
    </div>
  );
}

