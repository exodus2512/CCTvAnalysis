'use client';

import { cn } from '../../lib/utils';
import { 
  AlertTriangle, 
  Camera, 
  Activity, 
  CheckCircle,
  Search,
  Inbox 
} from 'lucide-react';
import { Button } from './Button';

const ICONS = {
  alert: AlertTriangle,
  camera: Camera,
  activity: Activity,
  success: CheckCircle,
  search: Search,
  inbox: Inbox,
};

export function EmptyState({ 
  icon = 'inbox',
  title = 'No data',
  description,
  action,
  actionLabel,
  className,
}) {
  const IconComponent = ICONS[icon] || Inbox;

  return (
    <div className={cn(
      'flex flex-col items-center justify-center py-12 px-4 text-center',
      className
    )}>
      <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4">
        <IconComponent className="w-8 h-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm">{description}</p>
      )}
      {action && actionLabel && (
        <Button onClick={action} variant="secondary" className="mt-4">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export function NoIncidents({ className }) {
  return (
    <EmptyState
      icon="success"
      title="No incidents yet"
      description="The system is monitoring. Incidents will appear here when detected."
      className={className}
    />
  );
}

export function NoAlerts({ className }) {
  return (
    <div className={cn('text-center py-8', className)}>
      <div className="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center mx-auto mb-3">
        <CheckCircle className="w-6 h-6 text-green-400" />
      </div>
      <div className="text-sm font-medium text-foreground">No active alerts</div>
      <div className="text-xs text-muted-foreground mt-1">System is monitoring</div>
    </div>
  );
}

export function NoCameras({ onAdd, className }) {
  return (
    <EmptyState
      icon="camera"
      title="No cameras configured"
      description="Add cameras to start monitoring your facility."
      action={onAdd}
      actionLabel="Add Camera"
      className={className}
    />
  );
}

export function NoSearchResults({ query, className }) {
  return (
    <EmptyState
      icon="search"
      title="No results found"
      description={query ? `No results for "${query}"` : 'Try adjusting your search or filters.'}
      className={className}
    />
  );
}
