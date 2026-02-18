import { format, formatDistanceToNow } from 'date-fns';

// ─── Class Name Utilities ────────────────────────────────────────────────────
export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}

// ─── Date Formatting ─────────────────────────────────────────────────────────
export function formatTimestamp(timestamp) {
  if (!timestamp) return 'Unknown';
  const date = new Date(timestamp > 1e12 ? timestamp : timestamp * 1000);
  return format(date, 'MMM d, yyyy HH:mm:ss');
}

export function formatRelativeTime(timestamp) {
  if (!timestamp) return 'Unknown';
  const date = new Date(timestamp > 1e12 ? timestamp : timestamp * 1000);
  return formatDistanceToNow(date, { addSuffix: true });
}

// ─── Alert Helpers ───────────────────────────────────────────────────────────
export function getAlertKey(alertObj) {
  const event = alertObj?.event || alertObj || {};
  return event.event_id || `${event.camera_id || 'cam'}_${event.event_type || 'event'}_${event.timestamp || Date.now()}`;
}

export function getCameraId(alertObj) {
  const event = alertObj?.event || alertObj || {};
  return event.camera_id || alertObj?.camera_id || 'unknown_camera';
}

export function getEventType(alertObj) {
  const event = alertObj?.event || alertObj || {};
  return event.event_type || alertObj?.event_type || 'unknown_event';
}

// ─── Event Type Formatting ───────────────────────────────────────────────────
export function formatEventType(eventType) {
  if (!eventType) return 'Unknown Event';
  return eventType
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

// ─── Priority Helpers ────────────────────────────────────────────────────────
export function getPriorityLevel(priority) {
  const levels = { critical: 4, high: 3, medium: 2, low: 1 };
  return levels[priority?.toLowerCase()] || 0;
}

export function sortByPriority(items, key = 'priority') {
  return [...items].sort((a, b) => {
    const aPriority = getPriorityLevel(a.alert?.[key] || a[key]);
    const bPriority = getPriorityLevel(b.alert?.[key] || b[key]);
    return bPriority - aPriority;
  });
}

// ─── Number Formatting ───────────────────────────────────────────────────────
export function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num?.toString() || '0';
}
