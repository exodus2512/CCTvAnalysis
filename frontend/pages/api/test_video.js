import fs from 'fs';
import path from 'path';

// Streams a test video from the shared ../test_videos directory.
// Usage from the frontend:
//   <video src={`/api/test_video?name=${encodeURIComponent(fileName)}`} ... />
//
// This is intended for local/demo use only. In production, map module-specific
// footage into a storage bucket or CDN and expose signed URLs per tenant.

export default function handler(req, res) {
  const { name } = req.query;

  if (!name || Array.isArray(name)) {
    res.status(400).send('Missing video name');
    return;
  }

  const safeName = path.basename(name);
  const filePath = path.join(process.cwd(), '..', 'test_videos', safeName);

  if (!fs.existsSync(filePath)) {
    res.status(404).send('Test video not found');
    return;
  }

  const stat = fs.statSync(filePath);
  const fileSize = stat.size;
  const range = req.headers.range;

  if (range) {
    const parts = range.replace(/bytes=/, '').split('-');
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
    const chunkSize = end - start + 1;
    const file = fs.createReadStream(filePath, { start, end });
    const head = {
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunkSize,
      'Content-Type': 'video/mp4',
    };
    res.writeHead(206, head);
    file.pipe(res);
  } else {
    const head = {
      'Content-Length': fileSize,
      'Content-Type': 'video/mp4',
    };
    res.writeHead(200, head);
    fs.createReadStream(filePath).pipe(res);
  }
}

