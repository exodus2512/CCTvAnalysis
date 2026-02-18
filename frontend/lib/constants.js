// ─── API Configuration ───────────────────────────────────────────────────────
export const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export const getWsUrl = () => {
  const base = BACKEND_URL;
  if (base.startsWith('https://')) {
    return base.replace('https://', 'wss://') + '/ws/alerts';
  }
  return base.replace('http://', 'ws://') + '/ws/alerts';
};

// ─── Color System ────────────────────────────────────────────────────────────
export const PRIORITY_COLORS = {
  critical: {
    bg: 'bg-red-500/20',
    border: 'border-red-500',
    text: 'text-red-400',
    dot: 'bg-red-500',
    gradient: 'from-red-500/20 to-transparent',
  },
  high: {
    bg: 'bg-orange-500/20',
    border: 'border-orange-500',
    text: 'text-orange-400',
    dot: 'bg-orange-500',
    gradient: 'from-orange-500/20 to-transparent',
  },
  medium: {
    bg: 'bg-yellow-500/20',
    border: 'border-yellow-500',
    text: 'text-yellow-400',
    dot: 'bg-yellow-500',
    gradient: 'from-yellow-500/20 to-transparent',
  },
  low: {
    bg: 'bg-blue-500/20',
    border: 'border-blue-500',
    text: 'text-blue-400',
    dot: 'bg-blue-500',
    gradient: 'from-blue-500/20 to-transparent',
  },
};

export const STATUS_COLORS = {
  online: { bg: 'bg-green-500', text: 'text-green-400' },
  offline: { bg: 'bg-red-500', text: 'text-red-400' },
  connecting: { bg: 'bg-yellow-500', text: 'text-yellow-400' },
  error: { bg: 'bg-red-500', text: 'text-red-400' },
};

// ─── Zone Definitions ────────────────────────────────────────────────────────
export const ZONES = [
  { 
    id: 'all', 
    label: 'All Zones', 
    description: 'Multi-Detection',
    icon: 'Search',
    model: 'ALL',
    color: 'purple'
  },
  { 
    id: 'outgate', 
    label: 'Outgate', 
    description: 'Vehicle & accident detection',
    icon: 'Car',
    model: 'yolov8n.pt',
    color: 'blue'
  },
  { 
    id: 'corridor', 
    label: 'Corridor', 
    description: 'Crowd & fight detection',
    icon: 'Users',
    model: 'yolov8s.pt',
    color: 'green'
  },
  { 
    id: 'school_ground', 
    label: 'School Ground', 
    description: 'Violence & weapon detection',
    icon: 'MapPin',
    model: 'yolov8s.pt',
    color: 'orange'
  },
  { 
    id: 'classroom', 
    label: 'Classroom', 
    description: 'Mobile phone detection',
    icon: 'BookOpen',
    model: 'yolov8m.pt',
    color: 'cyan'
  },
];

export const DEFAULT_CAMERAS = [
  { id: 'cam_outgate', name: 'Outgate Camera', zone: 'outgate', active: true, status: 'online' },
  { id: 'cam_corridor', name: 'Corridor Camera', zone: 'corridor', active: true, status: 'online' },
  { id: 'cam_ground', name: 'School Ground Camera', zone: 'school_ground', active: true, status: 'online' },
  { id: 'cam_classroom', name: 'Classroom Camera', zone: 'classroom', active: true, status: 'online' },
];

// ─── Event Type Labels ───────────────────────────────────────────────────────
export const EVENT_LABELS = {
  vehicle_detected: 'Vehicle Detected',
  gate_accident: 'Gate Accident',
  crowd_formation: 'Crowd Formation',
  fight: 'Fight Detected',
  weapon_detected: 'Weapon Detected',
  fire_smoke_detected: 'Fire/Smoke Detected',
  mobile_usage: 'Mobile Phone Usage',
  fall_detected: 'Fall Detected',
  after_hours_intrusion: 'After Hours Intrusion',
};

// ─── Module Definitions ──────────────────────────────────────────────────────
export const MODULES = [
  { id: 'home', label: 'Home', icon: 'Home', description: 'Home surveillance' },
  { id: 'school', label: 'School', icon: 'GraduationCap', description: 'School monitoring' },
  { id: 'office', label: 'Office', icon: 'Building', description: 'Office security' },
];
