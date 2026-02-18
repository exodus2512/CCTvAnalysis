const EVENT_COLORS = {
  vehicle_detected: { bg: 'bg-blue-500/20', text: 'text-blue-400', bar: 'bg-blue-500' },
  gate_accident: { bg: 'bg-red-500/20', text: 'text-red-400', bar: 'bg-red-500' },
  crowd_formation: { bg: 'bg-orange-500/20', text: 'text-orange-400', bar: 'bg-orange-500' },
  fight: { bg: 'bg-purple-500/20', text: 'text-purple-400', bar: 'bg-purple-500' },
  mobile_usage: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', bar: 'bg-yellow-500' },
};

const ZONE_COLORS = {
  outgate: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  corridor: { bg: 'bg-green-500/20', text: 'text-green-400' },
  school_ground: { bg: 'bg-orange-500/20', text: 'text-orange-400' },
  classroom: { bg: 'bg-purple-500/20', text: 'text-purple-400' },
};

export default function AnalyticsPanel({ analytics, expanded = false }) {
  const totals = analytics?.totals || {};
  const byType = analytics?.by_type || {};
  const byZone = analytics?.by_zone || {};
  
  const totalIncidents = totals.total_incidents || 0;
  const maxTypeCount = Math.max(...Object.values(byType), 1);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Analytics</span>
        <span className="text-xs text-gray-500">Real-time</span>
      </div>
      <div className="panel-body space-y-4">
        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-[#242b3d] rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-white">{totals.total_incidents ?? 0}</div>
            <div className="text-[10px] text-gray-400 uppercase">Total</div>
          </div>
          <div className="bg-[#242b3d] rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-red-400">{totals.critical_or_high ?? 0}</div>
            <div className="text-[10px] text-gray-400 uppercase">Critical</div>
          </div>
          <div className="bg-[#242b3d] rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-orange-400">
              {totals.avg_suspicion_score != null 
                ? `${(totals.avg_suspicion_score * 100).toFixed(0)}%` 
                : '--'}
            </div>
            <div className="text-[10px] text-gray-400 uppercase">Avg Susp.</div>
          </div>
        </div>

        {/* Incidents by Type */}
        <div>
          <div className="text-xs font-medium text-gray-400 mb-3">By Event Type</div>
          {Object.keys(byType).length === 0 ? (
            <div className="text-xs text-gray-500 text-center py-4">No incidents yet</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(byType).map(([type, count]) => {
                const colors = EVENT_COLORS[type] || { bg: 'bg-gray-500/20', text: 'text-gray-400', bar: 'bg-gray-500' };
                const percentage = (count / maxTypeCount) * 100;
                
                return (
                  <div key={type} className="relative">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs capitalize ${colors.text}`}>
                        {type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs font-semibold text-white">{count}</span>
                    </div>
                    <div className="h-1.5 bg-[#242b3d] rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${colors.bar} rounded-full transition-all duration-500`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Incidents by Zone (only show in expanded mode) */}
        {expanded && Object.keys(byZone).length > 0 && (
          <div>
            <div className="text-xs font-medium text-gray-400 mb-3">By Zone</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(byZone).map(([zone, count]) => {
                const colors = ZONE_COLORS[zone] || { bg: 'bg-gray-500/20', text: 'text-gray-400' };
                return (
                  <div key={zone} className={`px-3 py-1.5 rounded-lg ${colors.bg}`}>
                    <span className={`text-xs capitalize ${colors.text}`}>
                      {zone.replace(/_/g, ' ')}: <span className="font-semibold">{count}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

