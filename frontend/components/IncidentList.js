// ─── API Configuration ───────────────────────────────────────────────────────
// For local development, uncomment: const BACKEND_URL = 'http://localhost:8000';
const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

const PRIORITY_STYLES = {
  critical: { bg: 'bg-red-500/20', text: 'text-red-400', dot: 'bg-red-500' },
  high: { bg: 'bg-orange-500/20', text: 'text-orange-400', dot: 'bg-orange-500' },
  medium: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', dot: 'bg-yellow-500' },
  low: { bg: 'bg-green-500/20', text: 'text-green-400', dot: 'bg-green-500' },
};

const ZONE_LABELS = {
  outgate: 'Outgate',
  corridor: 'Corridor',
  school_ground: 'School Ground',
  classroom: 'Classroom',
};

const EVENT_LABELS = {
  vehicle_detected: 'Vehicle Detected',
  gate_accident: 'Gate Accident',
  crowd_formation: 'Crowd Formation',
  fight: 'Fight Detected',
  mobile_usage: 'Mobile Usage',
};

export default function IncidentList({ incidents }) {
  const list = incidents || [];

  return (
    <div className="panel h-full flex flex-col">
      <div className="panel-header">
        <span className="panel-title">Recent Incidents</span>
        <span className="text-xs text-gray-500">{list.length} total</span>
      </div>
      
      <div className="panel-body flex-1 overflow-y-auto">
        {list.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 text-gray-500">
            <svg className="w-8 h-8 mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} 
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs">No incidents recorded</span>
          </div>
        ) : (
          <div className="space-y-2">
            {list.map((item) => {
              const { id, event, alert } = item;
              const ts = event?.timestamp;
              const tsMs = ts && ts < 1e12 ? ts * 1000 : ts;
              const priority = alert?.priority?.toLowerCase() || 'low';
              const styles = PRIORITY_STYLES[priority] || PRIORITY_STYLES.low;
              
              // Use event_id for stable key, fallback to id
              const itemKey = event?.event_id || id;
              
              return (
                <div 
                  key={itemKey} 
                  className="bg-[#242b3d] rounded-lg p-3 hover:bg-[#2a3347] transition-colors cursor-pointer"
                >
                  <div className="flex items-start gap-3">
                    {/* Priority indicator */}
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${styles.dot}`} />
                    
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="text-sm font-medium text-white truncate">
                          {alert?.summary || EVENT_LABELS[event?.event_type] || 'Incident'}
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${styles.bg} ${styles.text} shrink-0`}>
                          {priority.toUpperCase()}
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-2 mt-1">
                        {event?.event_type && (
                          <span className="text-[11px] text-gray-400">
                            {EVENT_LABELS[event.event_type] || event.event_type.replace(/_/g, ' ')}
                          </span>
                        )}
                        {event?.zone && (
                          <>
                            <span className="text-gray-600">•</span>
                            <span className="text-[11px] text-cyan-400">
                              {ZONE_LABELS[event.zone] || event.zone}
                            </span>
                          </>
                        )}
                      </div>
                      
                      <div className="flex items-center justify-between mt-2">
                        {ts && (
                          <span className="text-[10px] text-gray-500">
                            {new Date(tsMs).toLocaleString()}
                          </span>
                        )}
                        <a
                          href={`${BACKEND_URL}/incident/${encodeURIComponent(id)}/pdf`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[10px] text-cyan-400 hover:text-cyan-300 font-medium"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Export PDF →
                        </a>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

