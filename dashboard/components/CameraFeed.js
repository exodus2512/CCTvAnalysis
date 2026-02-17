export default function CameraFeed() {
  return (
    <div className="w-full flex flex-col items-center">
      {/* Directly hit the FastAPI MJPEG stream. Browsers allow
          cross-origin <img> sources on localhost, and this avoids
          any Next.js streaming proxy issues. */}
      <img
        src="http://localhost:8000/camera_feed"
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
