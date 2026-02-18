// ─── API Configuration ───────────────────────────────────────────────────────
// For local development, uncomment: const BACKEND_URL = 'http://localhost:8000';
const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export default function CameraFeed() {
  return (
    <div className="w-full flex flex-col items-center">
      {/* Directly hit the FastAPI MJPEG stream. Browsers allow
          cross-origin <img> sources on localhost, and this avoids
          any Next.js streaming proxy issues. */}
      <img
        src={`${BACKEND_URL}/camera_feed`}
        alt="Camera Feed"
        className="rounded shadow max-w-full"
        style={{ minHeight: 320 }}
      />
      <div className="text-xs text-gray-500 mt-2">
        Live camera feed with detection overlay
      </div>
    </div>
  );
}
