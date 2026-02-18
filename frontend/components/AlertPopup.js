const ZONE_LABELS = {
  all: { name: 'All Zones (Multi-Detection)', icon: '🔍' },
  outgate: { name: 'Outgate / Gate Area', icon: '🚗' },
  corridor: { name: 'Corridor / Hallway', icon: '🚶' },
  school_ground: { name: 'School Ground', icon: '🏃' },
  classroom: { name: 'Classroom', icon: '📚' },
};

const EVENT_LABELS = {
  vehicle_detected: { name: 'Vehicle Detected', icon: '🚗' },
  gate_accident: { name: 'Gate Accident', icon: '⚠️' },
  crowd_formation: { name: 'Crowd Formation', icon: '👥' },
  fight: { name: 'Fight Detected', icon: '🥊' },
  mobile_usage: { name: 'Mobile Usage', icon: '📱' },
  weapon_detected: { name: 'Weapon Detected', icon: '🔪' },
};

const PRIORITY_STYLES = {
  critical: {
    border: 'border-red-500',
    bg: 'bg-red-500/10',
    badge: 'bg-red-500 text-white',
    text: 'text-red-400',
  },
  high: {
    border: 'border-orange-500',
    bg: 'bg-orange-500/10',
    badge: 'bg-orange-500 text-white',
    text: 'text-orange-400',
  },
  medium: {
    border: 'border-yellow-500',
    bg: 'bg-yellow-500/10',
    badge: 'bg-yellow-500 text-black',
    text: 'text-yellow-400',
  },
  low: {
    border: 'border-green-500',
    bg: 'bg-green-500/10',
    badge: 'bg-green-500 text-white',
    text: 'text-green-400',
  },
};

export default function AlertPopup({ alert, onDismiss }) {
  if (!alert) return null;

  // Handle simple message alerts
  if (alert.msg) {
    return (
      <div className="bg-[#242b3d] border border-[#2f3542] rounded-lg p-4">
        <p className="text-sm text-gray-300">{alert.msg}</p>
      </div>
    );
  }

  const event = alert.event || {};
  const actions = alert.actions || [];
  const priority = (alert.priority || 'medium').toLowerCase();
  const styles = PRIORITY_STYLES[priority] || PRIORITY_STYLES.medium;
  
  const eventInfo = EVENT_LABELS[event.event_type] || { 
    name: event.event_type?.replace(/_/g, ' ') || 'Unknown Event', 
    icon: '⚠️' 
  };
  
  const zoneInfo = ZONE_LABELS[event.zone] || { 
    name: event.zone || 'Unknown Zone', 
    icon: '📍' 
  };

  const timestamp = event.timestamp 
    ? new Date(event.timestamp < 1e12 ? event.timestamp * 1000 : event.timestamp).toLocaleString()
    : new Date().toLocaleString();

  return (
    <div className={`rounded-lg border-l-4 ${styles.border} ${styles.bg} overflow-hidden`}>
      {/* Header */}
      <div className="p-4 border-b border-[#2f3542]/50">
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{eventInfo.icon}</span>
            <div>
              <div className="text-lg font-semibold text-white">
                {eventInfo.name}
              </div>
              <div className="text-xs text-gray-400 flex items-center gap-2">
                <span>{zoneInfo.icon} {zoneInfo.name}</span>
                <span>•</span>
                <span>{event.camera_id || 'Unknown Camera'}</span>
              </div>
            </div>
          </div>
          <span className={`px-2 py-1 text-xs font-semibold rounded ${styles.badge}`}>
            {priority.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Stats */}
      <div className="p-4 grid grid-cols-3 gap-4 border-b border-[#2f3542]/50">
        <div>
          <div className="text-[10px] text-gray-500 uppercase">Confidence</div>
          <div className={`text-lg font-semibold ${styles.text}`}>
            {typeof event.confidence === 'number' 
              ? `${(event.confidence * 100).toFixed(0)}%` 
              : 'N/A'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase">Suspicion</div>
          <div className={`text-lg font-semibold ${styles.text}`}>
            {typeof alert.suspicion_score === 'number' 
              ? `${(alert.suspicion_score * 100).toFixed(0)}%` 
              : 'N/A'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase">Time</div>
          <div className="text-sm font-medium text-gray-300">
            {new Date(event.timestamp < 1e12 ? event.timestamp * 1000 : event.timestamp).toLocaleTimeString()}
          </div>
        </div>
      </div>

      {/* LLM Explanation */}
      {alert.llm_explanation && (
        <div className="p-4 border-b border-[#2f3542]/50">
          <div className="text-[10px] text-gray-500 uppercase mb-2">AI Analysis</div>
          <p className="text-sm text-gray-300 italic">
            {alert.llm_explanation}
          </p>
        </div>
      )}

      {/* Summary if no LLM explanation */}
      {!alert.llm_explanation && alert.summary && (
        <div className="p-4 border-b border-[#2f3542]/50">
          <div className="text-[10px] text-gray-500 uppercase mb-2">Summary</div>
          <p className="text-sm text-gray-300">
            {alert.summary}
          </p>
        </div>
      )}

      {/* Recommended Actions */}
      {actions.length > 0 && (
        <div className="p-4 border-b border-[#2f3542]/50">
          <div className="text-[10px] text-gray-500 uppercase mb-2">Recommended Actions</div>
          <ul className="space-y-1">
            {actions.map((action, idx) => (
              <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                <span className="text-green-400">✓</span>
                {action}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions */}
      <div className="p-4 flex items-center gap-3">
        <button className="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          View Camera
        </button>
        <button
          onClick={onDismiss}
          className="px-4 py-2 bg-[#242b3d] hover:bg-[#2f3542] text-gray-300 text-sm font-medium rounded-lg transition-colors"
        >
          Dismiss
        </button>
      </div>

      {/* Timestamp footer */}
      <div className="px-4 py-2 bg-[#1a1f2e]/50 text-[10px] text-gray-500">
        Alert received: {timestamp}
      </div>
    </div>
  );
}
