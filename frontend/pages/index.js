'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { motion } from 'framer-motion';
import { 
  Camera, 
  Play, 
  Plus, 
  Trash2, 
  Edit2, 
  CheckCircle,
  Home,
  GraduationCap,
  Building,
  Car,
  Users,
  MapPin,
  BookOpen,
  Search,
  ChevronRight,
  Shield,
  Zap,
  Eye,
  Loader2
} from 'lucide-react';

import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Input, Select, Checkbox } from '../components/ui/Input';
import { StatusIndicator } from '../components/ui/StatusIndicator';
import { EmptyState } from '../components/ui/EmptyState';
import SetupWizard from '../components/SetupWizard';
import GoogleLoginButton, { AuthStatus, useAuth } from '../components/GoogleLogin';

import { BACKEND_URL, ZONES, MODULES, DEFAULT_CAMERAS } from '../lib/constants';
import { cn } from '../lib/utils';

// Zone icons mapping
const ZONE_ICONS = {
  all: Search,
  outgate: Car,
  corridor: Users,
  school_ground: MapPin,
  classroom: BookOpen,
};

// Module icons mapping
const MODULE_ICONS = {
  home: Home,
  school: GraduationCap,
  office: Building,
};

export default function LandingPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [cameras, setCameras] = useState([]);
  const [selectedModule, setSelectedModule] = useState('school');
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [showSetupWizard, setShowSetupWizard] = useState(false);
  const [wizardCamera, setWizardCamera] = useState(null);

  const handleWizardComplete = (cameraData) => {
    if (wizardCamera) {
      // Editing existing camera
      setCameras(prev => prev.map(c => c.id === cameraData.id ? cameraData : c));
    } else {
      // Adding new camera
      setCameras(prev => [...prev, cameraData]);
    }
    setShowSetupWizard(false);
    setWizardCamera(null);
  };

  const openWizardForNew = () => {
    setWizardCamera(null);
    setShowSetupWizard(true);
  };

  const openWizardForEdit = (camera) => {
    setWizardCamera(camera);
    setShowSetupWizard(true);
  };
  const [cameraHealth, setCameraHealth] = useState({});

  // Load current module
  useEffect(() => {
    async function loadCurrentModule() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/module/current`);
        if (res.ok) {
          const data = await res.json();
          if (data?.module) setSelectedModule(data.module);
        }
      } catch {}
    }
    loadCurrentModule();
  }, []);

  // Load cameras for selected module
  useEffect(() => {
    async function loadCameras() {
      try {
        const res = await fetch(`${BACKEND_URL}/api/cameras?module=${selectedModule}`);
        if (res.ok) {
          const data = await res.json();
          setCameras(Array.isArray(data.cameras) ? data.cameras : []);
        }
      } catch {
        setCameras([]);
      }
    }
    loadCameras();
  }, [selectedModule]);

  // Check camera health
  useEffect(() => {
    async function checkHealth() {
      const healthMap = {};
      for (const cam of cameras) {
        try {
          const res = await fetch(`${BACKEND_URL}/api/camera/${cam.id}/health`, {
            method: 'GET',
          });
          healthMap[cam.id] = res.ok ? 'online' : 'offline';
        } catch {
          healthMap[cam.id] = 'offline';
        }
      }
      setCameraHealth(healthMap);
    }
    if (cameras.length > 0) {
      checkHealth();
      const interval = setInterval(checkHealth, 30000);
      return () => clearInterval(interval);
    }
  }, [cameras]);

  const handleModuleSelect = (moduleId) => {
    setSelectedModule(moduleId);
  };

  const handleAddCamera = async (cameraData) => {
    const newCamera = {
      id: `cam_${Date.now()}`,
      ...cameraData,
      active: true,
      status: 'online',
    };
    
    try {
      await fetch(`${BACKEND_URL}/api/camera/${newCamera.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCamera),
      });
    } catch (e) {
      console.error('Failed to add camera:', e);
    }
    
    setCameras(prev => [...prev, newCamera]);
    setShowAddModal(false);
  };

  const handleEditCamera = async (cameraData) => {
    const updatedCamera = { ...editingCamera, ...cameraData };
    
    try {
      await fetch(`${BACKEND_URL}/api/camera/${updatedCamera.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedCamera),
      });
    } catch (e) {
      console.error('Failed to update camera:', e);
    }
    
    setCameras(prev => prev.map(c => c.id === updatedCamera.id ? updatedCamera : c));
    setEditingCamera(null);
  };

  const handleDeleteCamera = async (cameraId) => {
    try {
      await fetch(`${BACKEND_URL}/api/camera/${cameraId}`, { method: 'DELETE' });
    } catch (e) {
      console.error('Failed to delete camera:', e);
    }
    setCameras(prev => prev.filter(c => c.id !== cameraId));
  };

  const handleToggleActive = (cameraId) => {
    setCameras(prev => prev.map(c => 
      c.id === cameraId ? { ...c, active: !c.active } : c
    ));
  };

  const handleStartMonitoring = async () => {
    setLoading(true);
    
    // Save config
    const config = { module: selectedModule, cameras };
    window.localStorage.setItem('sentinel_config', JSON.stringify(config));

    // Set module
    try {
      await fetch(`${BACKEND_URL}/api/module`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module: selectedModule }),
      });
    } catch (e) {
      console.error('Failed to set module:', selectedModule);
    }
    
    // Sync cameras
    for (const cam of cameras) {
      try {
        await fetch(`${BACKEND_URL}/api/camera/${cam.id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cam),
        });
      } catch (e) {
        console.error('Failed to sync camera:', cam.id);
      }
    }
    
    router.push('/monitor');
  };

  const activeCount = cameras.filter(c => c.active).length;
  const onlineCount = Object.values(cameraHealth).filter(s => s === 'online').length;

  // Loading state
  if (authLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/5 to-transparent" />
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/25">
            <Eye className="w-8 h-8 text-white" />
          </div>
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Auth Gate - Show login page if not authenticated
  if (!user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/5 to-transparent" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 max-w-md w-full mx-6 p-8 bg-card border border-border rounded-3xl shadow-2xl"
        >
          <div className="flex flex-col items-center text-center mb-8">
            <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-3xl flex items-center justify-center shadow-lg shadow-blue-500/25 mb-6">
              <Eye className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-foreground mb-2">SentinelAI</h1>
            <p className="text-muted-foreground">AI-Powered School Safety System</p>
          </div>

          <div className="space-y-4">
            <GoogleLoginButton fullWidth size="lg" />
            
            <p className="text-xs text-center text-muted-foreground">
              Sign in with your Google account to access the dashboard
            </p>
          </div>

          <div className="mt-8 pt-6 border-t border-border">
            <div className="flex justify-center gap-6 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Shield className="w-3 h-3" /> Secure
              </span>
              <span className="flex items-center gap-1">
                <Zap className="w-3 h-3" /> Real-time
              </span>
              <span className="flex items-center gap-1">
                <Camera className="w-3 h-3" /> Multi-Zone
              </span>
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-purple-500/5 to-transparent" />
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        
        <div className="relative max-w-7xl mx-auto px-6 pt-12 pb-8">
          {/* Logo & Header */}
          <div className="flex items-center justify-between mb-12">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/25">
                <Eye className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-foreground">SentinelAI</h1>
                <p className="text-muted-foreground">AI-Powered School Safety System</p>
              </div>
            </div>
            
            {/* Auth, Stats & Setup Wizard */}
            <div className="hidden md:flex items-center gap-6">
              {/* Quick Stats */}
              <div className="flex items-center gap-6 border-r border-border pr-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-foreground">{cameras.length}</div>
                  <div className="text-xs text-muted-foreground">Cameras</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">{activeCount}</div>
                  <div className="text-xs text-muted-foreground">Active</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">{onlineCount}</div>
                  <div className="text-xs text-muted-foreground">Online</div>
                </div>
              </div>
              
              {/* Setup Wizard Button */}
              <Button onClick={openWizardForNew} size="sm" className="gap-2">
                <Plus className="w-4 h-4" />
                Setup Camera
              </Button>
              
              {/* User Auth */}
              <AuthStatus />
            </div>
          </div>

          {/* Feature Pills */}
          <div className="flex flex-wrap gap-3 mb-8">
            <FeaturePill icon={Zap} text="Real-time Detection" />
            <FeaturePill icon={Shield} text="YOLOv8 AI Models" />
            <FeaturePill icon={Camera} text="Multi-Zone Monitoring" />
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pb-12 space-y-8">
        {/* Module Selection */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">Select Environment</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {MODULES.map((module) => {
              const Icon = MODULE_ICONS[module.id];
              const isSelected = selectedModule === module.id;
              
              return (
                <motion.button
                  key={module.id}
                  onClick={() => handleModuleSelect(module.id)}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className={cn(
                    'relative p-6 rounded-2xl border-2 transition-all text-left',
                    isSelected
                      ? 'bg-blue-500/10 border-blue-500 shadow-lg shadow-blue-500/10'
                      : 'bg-card border-border hover:border-border-hover'
                  )}
                >
                  {isSelected && (
                    <div className="absolute top-3 right-3">
                      <CheckCircle className="w-5 h-5 text-blue-400" />
                    </div>
                  )}
                  
                  <div className={cn(
                    'w-12 h-12 rounded-xl flex items-center justify-center mb-3',
                    isSelected ? 'bg-blue-500/20' : 'bg-muted'
                  )}>
                    <Icon className={cn('w-6 h-6', isSelected ? 'text-blue-400' : 'text-muted-foreground')} />
                  </div>
                  
                  <h3 className={cn(
                    'text-lg font-semibold mb-1',
                    isSelected ? 'text-blue-400' : 'text-foreground'
                  )}>
                    {module.label}
                  </h3>
                  <p className="text-sm text-muted-foreground">{module.description}</p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Videos from: test_videos/{module.id}
                  </p>
                </motion.button>
              );
            })}
          </div>
        </section>

        {/* Zone Capabilities */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">Detection Zones</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {ZONES.filter(z => z.id !== 'all').map((zone) => {
              const Icon = ZONE_ICONS[zone.id];
              
              return (
                <Card key={zone.id} className="p-4">
                  <div className="flex items-center gap-3 mb-2">
                    <div className={cn(
                      'w-10 h-10 rounded-lg flex items-center justify-center',
                      zone.color === 'blue' && 'bg-blue-500/20 text-blue-400',
                      zone.color === 'green' && 'bg-green-500/20 text-green-400',
                      zone.color === 'orange' && 'bg-orange-500/20 text-orange-400',
                      zone.color === 'cyan' && 'bg-cyan-500/20 text-cyan-400',
                    )}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-medium text-foreground text-sm">{zone.label}</h3>
                      <p className="text-[10px] text-muted-foreground">{zone.description}</p>
                    </div>
                  </div>
                  <Badge variant="outline" size="sm" className="mt-2">
                    {zone.model}
                  </Badge>
                </Card>
              );
            })}
          </div>
        </section>

        {/* Camera Configuration */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-foreground">Camera Configuration</h2>
            <Button onClick={openWizardForNew} size="sm">
              <Plus className="w-4 h-4" />
              Add Camera
            </Button>
          </div>

          {cameras.length === 0 ? (
            <Card>
              <CardContent>
                <EmptyState
                  icon="camera"
                  title="No cameras configured"
                  description="Add your first camera to start monitoring"
                  action={openWizardForNew}
                  actionLabel="Add Camera"
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Camera Name</th>
                      <th>Zone</th>
                      <th>Status</th>
                      <th>Active</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cameras.map((camera) => {
                      const zone = ZONES.find(z => z.id === camera.zone);
                      const health = cameraHealth[camera.id] || 'offline';
                      
                      return (
                        <tr key={camera.id}>
                          <td>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
                                <Camera className="w-4 h-4 text-muted-foreground" />
                              </div>
                              <span className="font-medium">{camera.name}</span>
                            </div>
                          </td>
                          <td>
                            <Badge variant="outline" size="sm">
                              {zone?.label || camera.zone}
                            </Badge>
                          </td>
                          <td>
                            <StatusIndicator status={health} size="sm" />
                          </td>
                          <td>
                            <Checkbox
                              checked={camera.active}
                              onChange={() => handleToggleActive(camera.id)}
                            />
                          </td>
                          <td>
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => openWizardForEdit(camera)}
                                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                              >
                                <Edit2 className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => handleDeleteCamera(camera.id)}
                                className="p-1.5 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </section>

        {/* Start Monitoring CTA */}
        <div className="flex items-center justify-between p-6 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-blue-500/10 rounded-2xl border border-blue-500/20">
          <div>
            <h3 className="text-lg font-semibold text-foreground mb-1">Ready to Start?</h3>
            <p className="text-sm text-muted-foreground">
              {activeCount} camera{activeCount !== 1 ? 's' : ''} configured and ready for monitoring
            </p>
          </div>
          <Button 
            onClick={handleStartMonitoring} 
            loading={loading}
            size="lg"
            className="gap-2"
          >
            <Play className="w-5 h-5" />
            Start Monitoring
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Add Camera Modal (Legacy - keep for backward compat) */}
      <CameraFormModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSubmit={handleAddCamera}
        title="Add New Camera"
      />

      {/* Edit Camera Modal (Legacy - keep for backward compat) */}
      <CameraFormModal
        isOpen={!!editingCamera}
        onClose={() => setEditingCamera(null)}
        onSubmit={handleEditCamera}
        camera={editingCamera}
        title="Edit Camera"
      />

      {/* Setup Wizard */}
      <SetupWizard
        isOpen={showSetupWizard}
        onClose={() => {
          setShowSetupWizard(false);
          setWizardCamera(null);
        }}
        onComplete={handleWizardComplete}
        existingCamera={wizardCamera}
      />

      {/* Footer */}
      <footer className="text-center py-6 border-t border-border">
        <p className="text-sm text-muted-foreground">
          SentinelAI School Safety System v1.0 — Powered by YOLOv8
        </p>
      </footer>
    </div>
  );
}

// Feature Pill Component
function FeaturePill({ icon: Icon, text }) {
  return (
    <div className="inline-flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-full">
      <Icon className="w-4 h-4 text-blue-400" />
      <span className="text-sm text-foreground">{text}</span>
    </div>
  );
}

// Camera Form Modal
function CameraFormModal({ isOpen, onClose, onSubmit, camera, title }) {
  const [name, setName] = useState('');
  const [zone, setZone] = useState('outgate');

  useEffect(() => {
    if (camera) {
      setName(camera.name || '');
      setZone(camera.zone || 'outgate');
    } else {
      setName('');
      setZone('outgate');
    }
  }, [camera, isOpen]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit({ name: name.trim(), zone });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Camera Name"
          placeholder="Enter camera name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        
        <Select
          label="Zone Assignment"
          value={zone}
          onChange={(e) => setZone(e.target.value)}
          options={ZONES.filter(z => z.id !== 'all').map(z => ({
            value: z.id,
            label: z.label
          }))}
        />

        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit">
            {camera ? 'Save Changes' : 'Add Camera'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}


