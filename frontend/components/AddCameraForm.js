import { useState, useEffect } from 'react';

// ─── API Configuration ───────────────────────────────────────────────────────
// For local development, uncomment: const BACKEND_URL = 'http://localhost:8000';
const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

const ZONE_OPTIONS = [
  { value: 'all', label: 'All Zones', icon: '🔍', model: 'ALL', description: 'Run all detectors simultaneously (recommended)' },
  { value: 'outgate', label: 'Outgate', icon: '🚗', model: 'yolov8n.pt', description: 'Vehicle detection, gate accidents' },
  { value: 'corridor', label: 'Corridor', icon: '🚶', model: 'yolov8s.pt', description: 'Crowd formation, fights' },
  { value: 'school_ground', label: 'School Ground', icon: '🏫', model: 'yolov8s.pt', description: 'Crowd formation, fights' },
  { value: 'classroom', label: 'Classroom', icon: '📱', model: 'yolov8m.pt', description: 'Mobile phone detection' },
];

export default function AddCameraForm({ onCameraAdded, onCancel }) {
  const [videoPath, setVideoPath] = useState('');
  const [zone, setZone] = useState('all');
  const [name, setName] = useState('');
  const [testVideos, setTestVideos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Fetch available test videos
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/test_videos`)
      .then(res => res.json())
      .then(data => setTestVideos(data.videos || []))
      .catch(() => setTestVideos([]));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch(`${BACKEND_URL}/api/camera`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_path: videoPath,
          zone: zone,
          name: name || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to create camera');
      }

      setSuccess(`Camera "${data.camera.name}" created successfully!`);
      setVideoPath('');
      setName('');

      if (onCameraAdded) {
        onCameraAdded(data.camera);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const selectedZoneInfo = ZONE_OPTIONS.find(z => z.value === zone);

  return (
    <div className="bg-[#1a1f2e] border border-gray-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="bg-[#242b3d] px-4 py-3 flex items-center justify-between">
        <h3 className="text-white font-medium">Add New Camera</h3>
        {onCancel && (
          <button onClick={onCancel} className="text-gray-400 hover:text-white">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="p-4 space-y-4">
        {/* Video Source Selection */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">Video Source</label>
          
          {/* Quick select from test videos */}
          {testVideos.length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] text-gray-500 mb-2">Quick select from test videos:</div>
              <div className="flex flex-wrap gap-2">
                {testVideos.slice(0, 6).map((video) => (
                  <button
                    key={video.path}
                    type="button"
                    onClick={() => setVideoPath(video.path)}
                    className={`px-2 py-1 text-[10px] rounded border transition-all ${
                      videoPath === video.path
                        ? 'border-cyan-500 bg-cyan-500/20 text-cyan-400'
                        : 'border-gray-700 bg-[#242b3d] text-gray-400 hover:border-gray-600'
                    }`}
                  >
                    {video.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Manual path input */}
          <input
            type="text"
            value={videoPath}
            onChange={(e) => setVideoPath(e.target.value)}
            placeholder="Video file path or RTSP URL"
            className="w-full bg-[#242b3d] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            required
          />
        </div>

        {/* Zone Selection */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">Detection Zone</label>
          <div className="grid grid-cols-2 gap-2">
            {ZONE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setZone(opt.value)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  zone === opt.value
                    ? 'border-cyan-500 bg-cyan-500/10'
                    : 'border-gray-700 bg-[#242b3d] hover:border-gray-600'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{opt.icon}</span>
                  <div>
                    <div className={`text-sm font-medium ${zone === opt.value ? 'text-cyan-400' : 'text-white'}`}>
                      {opt.label}
                    </div>
                    <div className="text-[10px] text-gray-500">{opt.description}</div>
                    <div className="text-[9px] text-gray-600">Model: {opt.model}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Optional Name */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-2">
            Camera Name <span className="text-gray-600">(optional)</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Auto-generated from video filename"
            className="w-full bg-[#242b3d] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        {/* Selected Zone Info */}
        {selectedZoneInfo && (
          <div className="p-3 bg-[#242b3d] rounded-lg border border-gray-700">
            <div className="flex items-center gap-2 text-sm">
              <span>{selectedZoneInfo.icon}</span>
              <span className="text-white font-medium">{selectedZoneInfo.label}</span>
              <span className="text-gray-500">→</span>
              <span className="text-purple-400 text-xs">{selectedZoneInfo.model}</span>
            </div>
            <div className="text-xs text-gray-500 mt-1">{selectedZoneInfo.description}</div>
          </div>
        )}

        {/* Error/Success Messages */}
        {error && (
          <div className="p-3 bg-red-900/30 border border-red-800 rounded-lg text-sm text-red-400">
            {error}
          </div>
        )}
        {success && (
          <div className="p-3 bg-green-900/30 border border-green-800 rounded-lg text-sm text-green-400">
            {success}
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end gap-3 pt-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-400 hover:text-white text-sm transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={loading || !videoPath}
            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Creating...' : 'Add Camera'}
          </button>
        </div>
      </form>
    </div>
  );
}
