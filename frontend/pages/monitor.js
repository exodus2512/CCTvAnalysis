'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/router';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Maximize2,
  Minimize2,
  Camera,
  AlertTriangle,
  Activity,
  Clock,
  Filter,
  Search,
  Download,
  RefreshCw,
  X,
} from 'lucide-react';

import { DashboardLayout } from '../components/layout';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { StatBox } from '../components/ui/StatBox';
import { StatusIndicator, LiveIndicator } from '../components/ui/StatusIndicator';
import { Input, Select } from '../components/ui/Input';
import { SkeletonCameraGrid, SkeletonTable } from '../components/ui/Skeleton';
import { NoIncidents, NoAlerts, NoCameras, NoSearchResults } from '../components/ui/EmptyState';

import { useWebSocket } from '../hooks/useWebSocket';
import { BACKEND_URL, ZONES, PRIORITY_COLORS, EVENT_LABELS } from '../lib/constants';
import { cn, formatTimestamp, formatRelativeTime, formatEventType, getAlertKey, getCameraId, getEventType } from '../lib/utils';

// Import chart components
import AnalyticsCharts from '../components/AnalyticsCharts';
import AlertPopupNew from '../components/AlertPopupNew';
import IncidentTimeline from '../components/IncidentTimeline';

const TAB_TITLES = {
  monitoring: { title: 'Live Monitoring', subtitle: 'Real-time surveillance and threat detection' },
  cameras: { title: 'Camera Management', subtitle: 'Configure and monitor camera feeds' },
  incidents: { title: 'Incident History', subtitle: 'View and filter past security events' },
  analytics: { title: 'Analytics Dashboard', subtitle: 'Insights and trends analysis' },
  settings: { title: 'System Settings', subtitle: 'Configure system preferences' },
};

export default function MonitorPage() {
  const router = useRouter();
  const { tab } = router.query;
  
  const [activeTab, setActiveTab] = useState('monitoring');
  const [cameras, setCameras] = useState([]);
  const [stats, setStats] = useState({ active_cameras: 0, total_incidents: 0 });
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedCamera, setExpandedCamera] = useState(null);
  const [highlightedCamera, setHighlightedCamera] = useState(null);

  // WebSocket hook for real-time alerts
  const { 
    status: wsStatus, 
    alerts, 
    incidents, 
    alertCount,
    dismissAlert, 
    markResolved,
    setIncidents,
  } = useWebSocket();

  // Update active tab from URL
  useEffect(() => {
    if (tab && TAB_TITLES[tab]) {
      setActiveTab(tab);
    }
  }, [tab]);

  // Handle tab change
  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    router.push(`/monitor?tab=${newTab}`, undefined, { shallow: true });
  };

  // Load initial data
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [camerasRes, statsRes, incidentsRes] = await Promise.all([
          fetch(`${BACKEND_URL}/api/cameras`),
          fetch(`${BACKEND_URL}/api/stats`),
          fetch(`${BACKEND_URL}/incidents`),
        ]);

        if (camerasRes.ok) {
          const data = await camerasRes.json();
          setCameras(data.cameras || []);
        }

        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data);
        }

        if (incidentsRes.ok) {
          const data = await incidentsRes.json();
          setAnalytics({ 
            totals: data.totals, 
            by_type: data.by_type, 
            by_zone: data.by_zone 
          });
          
          // Set initial incidents sorted by timestamp
          const sortedIncidents = (data.incidents || []).sort((a, b) => {
            const aTs = a.event?.timestamp || 0;
            const bTs = b.event?.timestamp || 0;
            return bTs - aTs;
          });
          setIncidents(sortedIncidents);
        }
      } catch (e) {
        console.error('Failed to load data:', e);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [setIncidents]);

  // Periodic stats refresh
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/stats`);
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch {}
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  // Highlight camera when alert received
  useEffect(() => {
    Object.keys(alerts).forEach(cameraId => {
      setHighlightedCamera(cameraId);
      setTimeout(() => setHighlightedCamera(null), 3000);
    });
  }, [alerts]);

  const tabConfig = TAB_TITLES[activeTab] || TAB_TITLES.monitoring;
  const activeAlertCount = Object.keys(alerts).length;
  const criticalCount = Object.values(alerts).filter(a => a?.priority === 'critical').length;

  return (
    <DashboardLayout
      activeTab={activeTab}
      onTabChange={handleTabChange}
      title={tabConfig.title}
      subtitle={tabConfig.subtitle}
      stats={{
        activeCameras: stats.active_cameras || cameras.length,
        totalIncidents: stats.total_incidents || incidents.length,
        criticalAlerts: criticalCount,
      }}
      alertCount={activeAlertCount}
      wsStatus={wsStatus}
    >
      <AnimatePresence mode="wait">
        {activeTab === 'monitoring' && (
          <MonitoringView
            key="monitoring"
            cameras={cameras}
            alerts={alerts}
            incidents={incidents}
            analytics={analytics}
            loading={loading}
            wsStatus={wsStatus}
            expandedCamera={expandedCamera}
            setExpandedCamera={setExpandedCamera}
            highlightedCamera={highlightedCamera}
            dismissAlert={dismissAlert}
          />
        )}

        {activeTab === 'cameras' && (
          <CamerasView
            key="cameras"
            cameras={cameras}
            loading={loading}
            expandedCamera={expandedCamera}
            setExpandedCamera={setExpandedCamera}
          />
        )}

        {activeTab === 'incidents' && (
          <IncidentsView
            key="incidents"
            incidents={incidents}
            loading={loading}
            markResolved={markResolved}
          />
        )}

        {activeTab === 'analytics' && (
          <AnalyticsView
            key="analytics"
            analytics={analytics}
            incidents={incidents}
            loading={loading}
          />
        )}

        {activeTab === 'settings' && (
          <SettingsView
            key="settings"
            wsStatus={wsStatus}
          />
        )}
      </AnimatePresence>
    </DashboardLayout>
  );
}

// ─── Monitoring View ─────────────────────────────────────────────────────────
function MonitoringView({ 
  cameras, 
  alerts, 
  incidents, 
  analytics,
  loading, 
  wsStatus,
  expandedCamera,
  setExpandedCamera,
  highlightedCamera,
  dismissAlert
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <SkeletonCameraGrid count={4} />
        </div>
        <div className="space-y-4">
          <Card className="h-64" />
          <Card className="h-48" />
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="grid grid-cols-1 xl:grid-cols-3 gap-6"
    >
      {/* Camera Grid */}
      <div className="xl:col-span-2">
        <CameraGrid
          cameras={cameras}
          alerts={alerts}
          expandedCamera={expandedCamera}
          setExpandedCamera={setExpandedCamera}
          highlightedCamera={highlightedCamera}
        />
      </div>

      {/* Right Panel - Alerts & Quick Analytics */}
      <div className="space-y-6">
        {/* Active Alerts Panel */}
        <Card>
          <CardHeader>
            <CardTitle icon={<span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}>
              Active Alerts
            </CardTitle>
            <Badge variant="outline" size="sm">
              {Object.keys(alerts).length} live
            </Badge>
          </CardHeader>
          <CardContent className="max-h-[50vh] overflow-y-auto">
            {Object.keys(alerts).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(alerts).map(([cameraId, alert]) => (
                  <AlertPopupNew
                    key={getAlertKey(alert)}
                    alert={alert}
                    onDismiss={() => dismissAlert(cameraId)}
                  />
                ))}
              </div>
            ) : (
              <NoAlerts />
            )}
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 gap-3">
          <StatBox
            label="Active Cameras"
            value={cameras.filter(c => c.active).length}
            icon={<Camera className="w-5 h-5" />}
            color="blue"
            size="sm"
          />
          <StatBox
            label="Incidents Today"
            value={incidents.length}
            icon={<AlertTriangle className="w-5 h-5" />}
            color="orange"
            size="sm"
          />
        </div>

        {/* Mini Analytics */}
        {analytics && (
          <Card>
            <CardHeader>
              <CardTitle icon={<Activity className="w-4 h-4" />}>
                Quick Stats
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {Object.entries(analytics.by_type || {}).slice(0, 4).map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {formatEventType(type)}
                    </span>
                    <Badge variant="outline" size="sm">{count}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Fullscreen Camera Modal */}
      <AnimatePresence>
        {expandedCamera && (
          <FullscreenCamera
            camera={cameras.find(c => c.id === expandedCamera)}
            onClose={() => setExpandedCamera(null)}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Camera Grid ─────────────────────────────────────────────────────────────
function CameraGrid({ cameras, alerts, expandedCamera, setExpandedCamera, highlightedCamera }) {
  if (cameras.length === 0) {
    return (
      <Card>
        <CardContent>
          <NoCameras onAdd={() => window.location.href = '/'} />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {cameras.map((camera) => {
        const hasAlert = !!alerts[camera.id];
        const isHighlighted = highlightedCamera === camera.id;
        const zone = ZONES.find(z => z.id === camera.zone);
        
        return (
          <motion.div
            key={camera.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
              'camera-feed group relative aspect-video rounded-xl overflow-hidden',
              'border border-border bg-card',
              hasAlert && 'camera-feed alert border-red-500',
              isHighlighted && 'ring-2 ring-red-500 ring-offset-2 ring-offset-background'
            )}
          >
            {/* Video Feed */}
            <img
              src={`${BACKEND_URL}/video/${camera.id}`}
              alt={camera.name}
              className="w-full h-full object-cover"
              onError={(e) => {
                e.target.src = '/placeholder-camera.svg';
              }}
            />

            {/* Top Overlay */}
            <div className="camera-overlay">
              <div className="flex items-center gap-2">
                <LiveIndicator />
                <Badge variant={camera.active ? 'online' : 'offline'} size="sm" dot>
                  {camera.active ? 'Online' : 'Offline'}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" size="sm">
                  {zone?.label || camera.zone}
                </Badge>
                <button
                  onClick={() => setExpandedCamera(camera.id)}
                  className="p-1.5 rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Bottom Overlay */}
            <div className="camera-overlay-bottom">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-white">{camera.name}</span>
                {zone?.model && (
                  <span className="text-[10px] text-white/70">Model: {zone.model}</span>
                )}
              </div>
            </div>

            {/* Alert Badge */}
            {hasAlert && (
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                <div className="px-4 py-2 bg-red-500/90 rounded-lg text-white font-medium text-sm animate-pulse">
                  {formatEventType(getEventType(alerts[camera.id]))}
                </div>
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

// ─── Fullscreen Camera ───────────────────────────────────────────────────────
function FullscreenCamera({ camera, onClose }) {
  if (!camera) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.9 }}
        className="relative max-w-6xl w-full aspect-video rounded-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <img
          src={`${BACKEND_URL}/video/${camera.id}`}
          alt={camera.name}
          className="w-full h-full object-contain bg-black"
        />
        
        <div className="absolute top-4 left-4 flex items-center gap-3">
          <LiveIndicator />
          <span className="text-white font-medium">{camera.name}</span>
        </div>
        
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-colors"
        >
          <Minimize2 className="w-5 h-5" />
        </button>
      </motion.div>
    </motion.div>
  );
}

// ─── Cameras View ────────────────────────────────────────────────────────────
function CamerasView({ cameras, loading, expandedCamera, setExpandedCamera }) {
  if (loading) {
    return <SkeletonCameraGrid count={6} />;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {cameras.map((camera) => {
          const zone = ZONES.find(z => z.id === camera.zone);
          
          return (
            <Card key={camera.id} hover className="overflow-hidden">
              <div className="aspect-video relative">
                <img
                  src={`${BACKEND_URL}/video/${camera.id}`}
                  alt={camera.name}
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-2 right-2">
                  <Badge variant={camera.active ? 'online' : 'offline'} size="sm" dot>
                    {camera.active ? 'Online' : 'Offline'}
                  </Badge>
                </div>
              </div>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-foreground">{camera.name}</h3>
                    <p className="text-sm text-muted-foreground">{zone?.label || camera.zone}</p>
                  </div>
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={() => setExpandedCamera(camera.id)}
                  >
                    <Maximize2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <AnimatePresence>
        {expandedCamera && (
          <FullscreenCamera
            camera={cameras.find(c => c.id === expandedCamera)}
            onClose={() => setExpandedCamera(null)}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─── Incidents View ──────────────────────────────────────────────────────────
function IncidentsView({ incidents, loading, markResolved }) {
  if (loading) {
    return <SkeletonTable rows={10} cols={5} />;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <Card>
        <CardHeader>
          <CardTitle>Incident Timeline</CardTitle>
          <Badge variant="outline">{incidents.length} total</Badge>
        </CardHeader>
        <CardContent>
          <IncidentTimeline 
            incidents={incidents} 
            onResolve={markResolved}
          />
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ─── Analytics View ──────────────────────────────────────────────────────────
function AnalyticsView({ analytics, incidents, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="h-80" />
        <Card className="h-80" />
        <Card className="h-64 lg:col-span-2" />
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
    >
      <AnalyticsCharts 
        analytics={analytics} 
        incidents={incidents}
      />
    </motion.div>
  );
}

// ─── Settings View ───────────────────────────────────────────────────────────
function SettingsView({ wsStatus }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="max-w-2xl"
    >
      <Card>
        <CardHeader>
          <CardTitle>System Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SettingRow
            label="Backend URL"
            description="API endpoint for data"
            value={<code className="text-xs bg-muted px-2 py-1 rounded">{BACKEND_URL}</code>}
          />
          <SettingRow
            label="WebSocket Status"
            description="Real-time connection"
            value={<StatusIndicator status={wsStatus} />}
          />
          <SettingRow
            label="Refresh Rate"
            description="Data polling interval"
            value={<span className="text-sm text-muted-foreground">10 seconds</span>}
          />
          <SettingRow
            label="Theme"
            description="Appearance settings"
            value={<span className="text-sm text-muted-foreground">System (Dark)</span>}
          />
        </CardContent>
      </Card>
    </motion.div>
  );
}

function SettingRow({ label, description, value }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <div>
        <div className="text-sm font-medium text-foreground">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      {value}
    </div>
  );
}

