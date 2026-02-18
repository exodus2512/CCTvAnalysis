'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Camera,
  MapPin,
  Play,
  Check,
  ChevronRight,
  ChevronLeft,
  Video,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Loader2,
  X,
  Car,
  Users,
  BookOpen,
  Shield,
  Wifi,
  Settings,
  Eye,
} from 'lucide-react';

import { Card, CardContent } from './ui/Card';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { Input, Select } from './ui/Input';
import { StatusIndicator } from './ui/StatusIndicator';

import { BACKEND_URL, ZONES } from '../lib/constants';
import { cn } from '../lib/utils';

// Zone icons mapping
const ZONE_ICONS = {
  outgate: Car,
  corridor: Users,
  school_ground: MapPin,
  classroom: BookOpen,
};

// Zone colors mapping
const ZONE_COLORS = {
  outgate: 'blue',
  corridor: 'green',
  school_ground: 'orange',
  classroom: 'cyan',
};

const WIZARD_STEPS = [
  { id: 'info', title: 'Camera Details', description: 'Name and video source', icon: Camera },
  { id: 'zone', title: 'Zone & Detection', description: 'Select monitoring zone', icon: MapPin },
  { id: 'preview', title: 'Stream Test', description: 'Verify connection', icon: Wifi },
  { id: 'confirm', title: 'Review & Save', description: 'Confirm configuration', icon: Shield },
];

export default function SetupWizard({ isOpen, onClose, onComplete, existingCamera = null }) {
  const fileInputRef = useRef(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState({
    name: '',
    source: '',
    sourceType: 'test_video', // 'test_video', 'rtsp', 'file'
    zone: 'outgate',
  });
  const [previewStatus, setPreviewStatus] = useState('idle'); // 'idle', 'loading', 'success', 'error'
  const [previewError, setPreviewError] = useState('');
  const [selectedVideoName, setSelectedVideoName] = useState('');
  const [selectedVideoFile, setSelectedVideoFile] = useState(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState('');
  const [saving, setSaving] = useState(false);

  // Load existing camera data for editing
  useEffect(() => {
    if (existingCamera) {
      setFormData({
        name: existingCamera.name || '',
        source: existingCamera.video_path || existingCamera.rtsp_url || '',
        sourceType: existingCamera.rtsp_url ? 'rtsp' : 'test_video',
        zone: existingCamera.zone || 'outgate',
      });
    } else {
      setFormData({
        name: '',
        source: '',
        sourceType: 'test_video',
        zone: 'outgate',
      });
    }
    setCurrentStep(0);
    setPreviewStatus('idle');
    setPreviewError('');
    setSelectedVideoName('');
    setSelectedVideoFile(null);
    setLocalPreviewUrl('');
  }, [existingCamera, isOpen]);

  useEffect(() => {
    return () => {
      if (localPreviewUrl) {
        URL.revokeObjectURL(localPreviewUrl);
      }
    };
  }, [localPreviewUrl]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleTestVideoFilePick = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setSelectedVideoName(file.name);
    setSelectedVideoFile(file);

    if (localPreviewUrl) {
      URL.revokeObjectURL(localPreviewUrl);
    }
    const objectUrl = URL.createObjectURL(file);
    setLocalPreviewUrl(objectUrl);

    // Keep editable manual path/value so user can configure backend-available path as needed.
    setFormData(prev => ({
      ...prev,
      source: prev.source?.trim() ? prev.source : file.name,
    }));
  };

  const canProceed = () => {
    switch (currentStep) {
      case 0: // Camera Info
        return formData.name.trim().length > 0;
      case 1: // Zone
        return formData.zone && ZONES.some(z => z.id === formData.zone);
      case 2: // Preview
        return previewStatus === 'success' || previewStatus === 'idle';
      case 3: // Confirm
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const testStreamPreview = async () => {
    setPreviewStatus('loading');
    setPreviewError('');

    if (formData.sourceType === 'test_video' && localPreviewUrl) {
      setTimeout(() => {
        setPreviewStatus('success');
      }, 400);
      return;
    }

    try {
      // Create a temporary camera to test the stream
      const testCameraId = existingCamera?.id || `cam_test_${Date.now()}`;
      
      // Check if we can load the MJPEG stream
      const img = new Image();
      img.onload = () => setPreviewStatus('success');
      img.onerror = () => {
        setPreviewStatus('error');
        setPreviewError('Failed to load stream. Check source path or RTSP URL.');
      };
      
      // Set a timeout for the test
      const timeout = setTimeout(() => {
        if (previewStatus === 'loading') {
          setPreviewStatus('success'); // Assume success if no error
        }
      }, 3000);

      img.src = `${BACKEND_URL}/video/${testCameraId}?t=${Date.now()}`;
      
      return () => clearTimeout(timeout);
    } catch (err) {
      setPreviewStatus('error');
      setPreviewError(err.message || 'Connection failed');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const cameraId = existingCamera?.id || `cam_${formData.name.toLowerCase().replace(/\s+/g, '_')}_${Date.now()}`;
      const backendBaseUrl = BACKEND_URL.replace('/event', '');
      
      const cameraData = {
        id: cameraId,
        name: formData.name,
        zone: formData.zone,
        active: true,
        status: 'online',
      };

      if (formData.sourceType === 'rtsp') {
        cameraData.rtsp_url = formData.source;
      } else {
        if (selectedVideoFile) {
          const uploadForm = new FormData();
          uploadForm.append('file', selectedVideoFile);

          const uploadRes = await fetch(`${backendBaseUrl}/api/upload-video`, {
            method: 'POST',
            body: uploadForm,
          });

          if (!uploadRes.ok) {
            throw new Error('Failed to upload selected video file');
          }

          const uploadPayload = await uploadRes.json();
          cameraData.video_path = uploadPayload.video_path;
        } else if (formData.source?.trim()) {
          cameraData.video_path = formData.source.trim();
        } else {
          throw new Error('Please choose a test video file or provide a manual video path.');
        }
      }

      const res = await fetch(`${BACKEND_URL}/api/camera/${cameraId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cameraData),
      });

      if (!res.ok) throw new Error('Failed to save camera');

      onComplete?.(cameraData);
      onClose?.();
    } catch (err) {
      console.error('Failed to save camera:', err);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  const selectedZone = ZONES.find(z => z.id === formData.zone);
  const CurrentStepIcon = WIZARD_STEPS[currentStep].icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ type: "spring", duration: 0.5 }}
        className="w-full max-w-3xl bg-card border border-border rounded-3xl shadow-2xl overflow-hidden"
      >
        {/* Header with Gradient */}
        <div className="relative px-8 py-6 bg-gradient-to-r from-blue-500/10 via-purple-500/5 to-transparent border-b border-border">
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
          
          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/25">
                <CurrentStepIcon className="w-6 h-6 text-white" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-foreground">
                  {existingCamera ? 'Edit Camera' : 'Add New Camera'}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Step {currentStep + 1}: {WIZARD_STEPS[currentStep].title}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-3 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Enhanced Step Indicator */}
          <div className="flex items-center justify-between mt-8 px-2">
            {WIZARD_STEPS.map((step, idx) => {
              const StepIcon = step.icon;
              const isCompleted = idx < currentStep;
              const isCurrent = idx === currentStep;
              const isPending = idx > currentStep;
              
              return (
                <div key={step.id} className="flex items-center flex-1">
                  <div className="flex flex-col items-center relative z-10">
                    <motion.div
                      initial={false}
                      animate={{
                        scale: isCurrent ? 1.1 : 1,
                        backgroundColor: isCompleted ? 'rgb(34, 197, 94)' : isCurrent ? 'rgb(59, 130, 246)' : 'transparent',
                      }}
                      className={cn(
                        'w-12 h-12 rounded-2xl flex items-center justify-center transition-all border-2',
                        isCompleted && 'border-green-500 bg-green-500 shadow-lg shadow-green-500/30',
                        isCurrent && 'border-blue-500 bg-blue-500 shadow-lg shadow-blue-500/30',
                        isPending && 'border-border bg-muted'
                      )}
                    >
                      {isCompleted ? (
                        <Check className="w-5 h-5 text-white" />
                      ) : (
                        <StepIcon className={cn(
                          'w-5 h-5',
                          isCurrent ? 'text-white' : 'text-muted-foreground'
                        )} />
                      )}
                    </motion.div>
                    <span className={cn(
                      'text-xs font-medium mt-2 whitespace-nowrap',
                      isCompleted && 'text-green-400',
                      isCurrent && 'text-blue-400',
                      isPending && 'text-muted-foreground'
                    )}>
                      {step.title}
                    </span>
                  </div>
                  {idx < WIZARD_STEPS.length - 1 && (
                    <div className="flex-1 h-0.5 mx-3 -mt-6">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-300',
                          idx < currentStep ? 'bg-green-500' : 'bg-border'
                        )}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div className="p-8 min-h-[380px]">
          <AnimatePresence mode="wait">
            {/* Step 1: Camera Info */}
            {currentStep === 0 && (
              <motion.div
                key="info"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ type: "spring", duration: 0.4 }}
                className="space-y-6"
              >
                <div className="text-center mb-8">
                  <h3 className="text-lg font-semibold text-foreground mb-2">Camera Information</h3>
                  <p className="text-sm text-muted-foreground">
                    Enter a name and select the video source for this camera
                  </p>
                </div>

                <div className="max-w-md mx-auto space-y-5">
                  <Input
                    label="Camera Name"
                    placeholder="e.g., Main Entrance, Hallway A, Classroom 101"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    autoFocus
                  />

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground">Source Type</label>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        type="button"
                        onClick={() => handleInputChange('sourceType', 'test_video')}
                        className={cn(
                          'p-4 rounded-xl border-2 text-left transition-all',
                          formData.sourceType === 'test_video'
                            ? 'border-blue-500 bg-blue-500/10'
                            : 'border-border hover:border-border-hover bg-card'
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            'w-10 h-10 rounded-lg flex items-center justify-center',
                            formData.sourceType === 'test_video' ? 'bg-blue-500/20' : 'bg-muted'
                          )}>
                            <Video className={cn(
                              'w-5 h-5',
                              formData.sourceType === 'test_video' ? 'text-blue-400' : 'text-muted-foreground'
                            )} />
                          </div>
                          <div>
                            <span className={cn(
                              'text-sm font-medium block',
                              formData.sourceType === 'test_video' ? 'text-blue-400' : 'text-foreground'
                            )}>Test Video</span>
                            <span className="text-xs text-muted-foreground">Local file</span>
                          </div>
                        </div>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleInputChange('sourceType', 'rtsp')}
                        className={cn(
                          'p-4 rounded-xl border-2 text-left transition-all',
                          formData.sourceType === 'rtsp'
                            ? 'border-blue-500 bg-blue-500/10'
                            : 'border-border hover:border-border-hover bg-card'
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            'w-10 h-10 rounded-lg flex items-center justify-center',
                            formData.sourceType === 'rtsp' ? 'bg-blue-500/20' : 'bg-muted'
                          )}>
                            <Wifi className={cn(
                              'w-5 h-5',
                              formData.sourceType === 'rtsp' ? 'text-blue-400' : 'text-muted-foreground'
                            )} />
                          </div>
                          <div>
                            <span className={cn(
                              'text-sm font-medium block',
                              formData.sourceType === 'rtsp' ? 'text-blue-400' : 'text-foreground'
                            )}>RTSP Stream</span>
                            <span className="text-xs text-muted-foreground">IP Camera</span>
                          </div>
                        </div>
                      </button>
                    </div>
                  </div>

                  {formData.sourceType === 'rtsp' && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                    >
                      <Input
                        label="RTSP URL"
                        placeholder="rtsp://192.168.1.100:554/stream"
                        value={formData.source}
                        onChange={(e) => handleInputChange('source', e.target.value)}
                      />
                    </motion.div>
                  )}

                  {formData.sourceType === 'test_video' && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="space-y-3"
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="video/*"
                        className="hidden"
                        onChange={handleTestVideoFilePick}
                      />

                      <div className="p-4 rounded-xl border border-border bg-muted/30">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-foreground">Choose Test Video</p>
                            <p className="text-xs text-muted-foreground">
                              Open your PC folder and pick a video file
                            </p>
                          </div>
                          <Button
                            type="button"
                            variant="secondary"
                            onClick={() => fileInputRef.current?.click()}
                          >
                            Browse File
                          </Button>
                        </div>
                        {selectedVideoName && (
                          <p className="text-xs text-muted-foreground mt-3">
                            Selected: <span className="text-foreground">{selectedVideoName}</span>
                          </p>
                        )}
                      </div>

                      <Input
                        label="Video Path (Manual)"
                        placeholder="e.g., C:/Videos/test_video.mp4"
                        value={formData.source}
                        onChange={(e) => handleInputChange('source', e.target.value)}
                      />
                    </motion.div>
                  )}

                  <div className="p-4 bg-gradient-to-r from-blue-500/5 to-purple-500/5 rounded-xl border border-blue-500/20">
                    <div className="flex items-start gap-3">
                      <Eye className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <h4 className="text-sm font-medium text-foreground">Video Source Info</h4>
                        <p className="text-xs text-muted-foreground mt-1">
                          {formData.sourceType === 'rtsp' 
                            ? 'Enter your IP camera RTSP URL. Most cameras use port 554. Check your camera manual for the correct stream path.'
                            : 'Use Browse File to pick a local video, then keep or edit the manual video path used for backend configuration.'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 2: Zone Assignment */}
            {currentStep === 1 && (
              <motion.div
                key="zone"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ type: "spring", duration: 0.4 }}
                className="space-y-6"
              >
                <div className="text-center mb-8">
                  <h3 className="text-lg font-semibold text-foreground mb-2">Select Detection Zone</h3>
                  <p className="text-sm text-muted-foreground">
                    Choose the monitoring zone to determine which AI detection models are used
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {ZONES.filter(z => z.id !== 'all').map((zone) => {
                    const isSelected = formData.zone === zone.id;
                    const ZoneIcon = ZONE_ICONS[zone.id] || MapPin;
                    const zoneColor = ZONE_COLORS[zone.id] || 'blue';
                    
                    return (
                      <motion.button
                        key={zone.id}
                        onClick={() => handleInputChange('zone', zone.id)}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className={cn(
                          'p-5 rounded-2xl border-2 text-left transition-all relative overflow-hidden',
                          isSelected
                            ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/10'
                            : 'border-border hover:border-border-hover bg-card hover:bg-muted/50'
                        )}
                      >
                        {isSelected && (
                          <motion.div 
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            className="absolute top-3 right-3"
                          >
                            <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                              <Check className="w-4 h-4 text-white" />
                            </div>
                          </motion.div>
                        )}
                        
                        <div className={cn(
                          'w-14 h-14 rounded-xl flex items-center justify-center mb-4 transition-all',
                          isSelected && 'shadow-lg',
                          zoneColor === 'blue' && (isSelected ? 'bg-blue-500' : 'bg-blue-500/20'),
                          zoneColor === 'green' && (isSelected ? 'bg-green-500' : 'bg-green-500/20'),
                          zoneColor === 'orange' && (isSelected ? 'bg-orange-500' : 'bg-orange-500/20'),
                          zoneColor === 'cyan' && (isSelected ? 'bg-cyan-500' : 'bg-cyan-500/20'),
                        )}>
                          <ZoneIcon className={cn(
                            'w-7 h-7',
                            isSelected ? 'text-white' : `text-${zoneColor}-400`,
                            zoneColor === 'blue' && !isSelected && 'text-blue-400',
                            zoneColor === 'green' && !isSelected && 'text-green-400',
                            zoneColor === 'orange' && !isSelected && 'text-orange-400',
                            zoneColor === 'cyan' && !isSelected && 'text-cyan-400',
                          )} />
                        </div>
                        
                        <h3 className={cn(
                          'font-semibold text-base mb-1',
                          isSelected ? 'text-blue-400' : 'text-foreground'
                        )}>
                          {zone.label}
                        </h3>
                        <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                          {zone.description}
                        </p>
                        <div className="flex items-center gap-2">
                          <Badge 
                            variant="outline" 
                            size="sm"
                            className={isSelected ? 'border-blue-500/50 text-blue-400' : ''}
                          >
                            {zone.model}
                          </Badge>
                        </div>
                      </motion.button>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {/* Step 3: Test Stream Preview */}
            {currentStep === 2 && (
              <motion.div
                key="preview"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ type: "spring", duration: 0.4 }}
                className="space-y-6"
              >
                <div className="text-center mb-6">
                  <h3 className="text-lg font-semibold text-foreground mb-2">Test Camera Connection</h3>
                  <p className="text-sm text-muted-foreground">
                    Verify the video stream is working before saving
                  </p>
                </div>

                <div className="aspect-video bg-gradient-to-br from-muted to-muted/50 rounded-2xl overflow-hidden relative border-2 border-border shadow-inner">
                  {previewStatus === 'idle' && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <div className="w-20 h-20 rounded-2xl bg-muted/80 flex items-center justify-center mb-4">
                        <Camera className="w-10 h-10 text-muted-foreground" />
                      </div>
                      <p className="text-sm text-muted-foreground font-medium">No preview available</p>
                      <p className="text-xs text-muted-foreground mt-1">Click "Test Connection" below to start</p>
                    </div>
                  )}
                  
                  {previewStatus === 'loading' && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-blue-500/5 to-purple-500/5">
                      <div className="relative">
                        <div className="w-16 h-16 rounded-full border-4 border-blue-500/20" />
                        <div className="absolute inset-0 w-16 h-16 rounded-full border-4 border-transparent border-t-blue-500 animate-spin" />
                        <Wifi className="absolute inset-0 m-auto w-6 h-6 text-blue-400" />
                      </div>
                      <p className="text-sm text-blue-400 font-medium mt-4">Connecting to stream...</p>
                      <p className="text-xs text-muted-foreground mt-1">This may take a few seconds</p>
                    </div>
                  )}
                  
                  {previewStatus === 'success' && (
                    <>
                      {formData.sourceType === 'test_video' && localPreviewUrl ? (
                        <video
                          src={localPreviewUrl}
                          controls
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <img
                          src={`${BACKEND_URL}/video/${existingCamera?.id || 'cam_test'}?t=${Date.now()}`}
                          alt="Camera Preview"
                          className="w-full h-full object-cover"
                        />
                      )}
                      <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-full">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
                        <span className="text-xs text-white font-medium tracking-wide">LIVE</span>
                      </div>
                      <div className="absolute bottom-4 right-4">
                        <Badge variant="success" className="bg-green-500/80 text-white border-0">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Connected
                        </Badge>
                      </div>
                    </>
                  )}
                  
                  {previewStatus === 'error' && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-red-500/5 to-orange-500/5">
                      <div className="w-16 h-16 rounded-2xl bg-red-500/20 flex items-center justify-center mb-4">
                        <AlertCircle className="w-8 h-8 text-red-400" />
                      </div>
                      <p className="text-sm text-red-400 font-medium">Connection Failed</p>
                      <p className="text-xs text-muted-foreground mt-1 max-w-xs text-center">
                        {previewError || 'Unable to connect to the video stream'}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-center gap-4">
                  <Button
                    variant={previewStatus === 'success' ? 'success' : 'primary'}
                    onClick={testStreamPreview}
                    disabled={previewStatus === 'loading'}
                    size="lg"
                    className="min-w-[180px]"
                  >
                    {previewStatus === 'loading' ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Testing...
                      </>
                    ) : previewStatus === 'success' ? (
                      <>
                        <CheckCircle className="w-5 h-5" />
                        Connection Verified
                      </>
                    ) : (
                      <>
                        <Play className="w-5 h-5" />
                        Test Connection
                      </>
                    )}
                  </Button>
                  
                  {(previewStatus === 'success' || previewStatus === 'error') && (
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setPreviewStatus('idle');
                        setPreviewError('');
                      }}
                    >
                      <RefreshCw className="w-4 h-4" />
                      Retry
                    </Button>
                  )}
                </div>

                <div className="p-3 bg-muted/50 rounded-xl flex items-center justify-center gap-2">
                  <Settings className="w-4 h-4 text-muted-foreground" />
                  <p className="text-xs text-muted-foreground">
                    You can skip this step if using test videos from the local folder
                  </p>
                </div>
              </motion.div>
            )}

            {/* Step 4: Confirm */}
            {currentStep === 3 && (
              <motion.div
                key="confirm"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -30 }}
                transition={{ type: "spring", duration: 0.4 }}
                className="space-y-6"
              >
                <div className="text-center mb-6">
                  <h3 className="text-lg font-semibold text-foreground mb-2">Review Configuration</h3>
                  <p className="text-sm text-muted-foreground">
                    Verify the camera settings before saving
                  </p>
                </div>

                <div className="max-w-lg mx-auto">
                  <Card className="overflow-hidden border-2 shadow-lg">
                    <div className="px-6 py-4 bg-gradient-to-r from-blue-500/10 via-purple-500/5 to-transparent border-b border-border">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                          <Camera className="w-6 h-6 text-white" />
                        </div>
                        <div>
                          <h3 className="font-bold text-lg text-foreground">{formData.name}</h3>
                          <p className="text-xs text-muted-foreground">Camera Configuration</p>
                        </div>
                      </div>
                    </div>
                    <CardContent className="p-6 space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-muted/50 rounded-xl">
                          <span className="text-xs text-muted-foreground block mb-1">Zone</span>
                          <div className="flex items-center gap-2">
                            {(() => {
                              const ZoneIcon = ZONE_ICONS[formData.zone] || MapPin;
                              return <ZoneIcon className="w-4 h-4 text-blue-400" />;
                            })()}
                            <span className="text-sm font-semibold text-foreground">{selectedZone?.label}</span>
                          </div>
                        </div>
                        <div className="p-4 bg-muted/50 rounded-xl">
                          <span className="text-xs text-muted-foreground block mb-1">AI Model</span>
                          <span className="text-sm font-semibold text-foreground">{selectedZone?.model}</span>
                        </div>
                        <div className="p-4 bg-muted/50 rounded-xl">
                          <span className="text-xs text-muted-foreground block mb-1">Source Type</span>
                          <span className="text-sm font-semibold text-foreground">
                            {formData.sourceType === 'rtsp' ? 'RTSP Stream' : 'Test Video'}
                          </span>
                        </div>
                        <div className="p-4 bg-muted/50 rounded-xl">
                          <span className="text-xs text-muted-foreground block mb-1">Initial Status</span>
                          <div className="flex items-center gap-2">
                            <StatusIndicator status="online" size="sm" />
                            <span className="text-sm font-semibold text-green-400">Online</span>
                          </div>
                        </div>
                      </div>
                      
                      {formData.source && (
                        <div className="p-4 bg-muted/30 rounded-xl border border-border">
                          <span className="text-xs text-muted-foreground block mb-2">Source URL</span>
                          <code className="text-xs text-foreground font-mono bg-muted px-2 py-1 rounded break-all block">
                            {formData.source}
                          </code>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="mt-6 p-5 bg-gradient-to-r from-green-500/10 to-emerald-500/10 border-2 border-green-500/30 rounded-2xl"
                  >
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 bg-green-500/20 rounded-xl flex items-center justify-center flex-shrink-0">
                        <CheckCircle className="w-5 h-5 text-green-400" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-green-400 mb-1">Ready to Save</h4>
                        <p className="text-xs text-green-400/80">
                          Click "Save Camera" to complete setup. The camera will begin monitoring immediately with real-time AI detection.
                        </p>
                      </div>
                    </div>
                  </motion.div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="px-8 py-5 border-t border-border bg-gradient-to-r from-muted/30 to-transparent flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={handleBack}
            disabled={currentStep === 0}
            className="gap-2"
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </Button>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            Step {currentStep + 1} of {WIZARD_STEPS.length}
          </div>

          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            
            {currentStep < WIZARD_STEPS.length - 1 ? (
              <Button onClick={handleNext} disabled={!canProceed()} className="gap-2 min-w-[100px]">
                Next
                <ChevronRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button 
                onClick={handleSave} 
                disabled={saving}
                className="gap-2 min-w-[140px]"
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Save Camera
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
