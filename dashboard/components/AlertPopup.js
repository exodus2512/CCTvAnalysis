export default function AlertPopup({ alert }) {
  if (!alert) return null;

  if (alert.msg) {
    return (
      <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-700 p-4 mb-4">
        <p>{alert.msg}</p>
      </div>
    );
  }

  const event = alert.event || {};
  const actions = alert.actions || [];

  return (
    <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-4 shadow-lg">
      <div className="font-bold text-lg">
        ALERT: {alert.summary || 'Incident detected'}
      </div>

      <div className="mt-1 text-sm flex flex-wrap gap-2">
        {event.event_type && (
          <span className="px-2 py-0.5 bg-red-200 rounded text-xs uppercase">
            {event.event_type.replace('_', ' ')}
          </span>
        )}
        {alert.priority && (
          <span className="px-2 py-0.5 bg-gray-200 rounded text-xs">
            Priority: {alert.priority}
          </span>
        )}
        {typeof event.confidence === 'number' && (
          <span className="px-2 py-0.5 bg-gray-200 rounded text-xs">
            Confidence: {event.confidence.toFixed(2)}
          </span>
        )}
        {typeof alert.suspicion_score === 'number' && (
          <span className="px-2 py-0.5 bg-gray-200 rounded text-xs">
            Suspicion: {alert.suspicion_score.toFixed(2)}
          </span>
        )}
      </div>

      <div className="text-sm mt-2">
        {event.zone && <div>Zone: {event.zone}</div>}
        {event.timestamp && (
          <div>
            Time:{' '}
            {new Date(
              (event.timestamp * 1000) < 1e12
                ? event.timestamp * 1000
                : event.timestamp
            ).toLocaleString()}
          </div>
        )}
      </div>

      {alert.llm_explanation && (
        <div className="text-xs mt-3 italic">
          {alert.llm_explanation}
        </div>
      )}

      {actions.length > 0 && (
        <div className="text-xs mt-3">
          <div className="font-semibold mb-1">Playbook actions:</div>
          <ul className="list-disc list-inside space-y-0.5">
            {actions.map((a, idx) => (
              <li key={idx}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
