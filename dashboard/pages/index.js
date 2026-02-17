
import { useEffect, useState } from 'react';
import AlertPopup from '../components/AlertPopup';
import CameraFeed from '../components/CameraFeed';

export default function Home() {
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/alerts');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setAlert(data.alert || data);
      } catch (e) {
        setAlert({ msg: 'Invalid alert data' });
      }
    };
    ws.onerror = () => setAlert({ msg: 'WebSocket error' });
    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold mb-6">SentinelAI School Security Dashboard</h1>
      <div className="w-full max-w-xl mb-6">
        <CameraFeed />
      </div>
      <div className="w-full max-w-xl">
        {alert && <AlertPopup alert={alert} />}
      </div>
      <div className="mt-8 text-gray-500">Incident timeline coming soon.</div>
    </div>
  );
}
