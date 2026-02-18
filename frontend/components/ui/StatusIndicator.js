'use client';

import { cn } from '../../lib/utils';

const STATUS_CONFIGS = {
  connected: { color: 'bg-green-500', label: 'Connected', pulse: false },
  connecting: { color: 'bg-yellow-500', label: 'Connecting', pulse: true },
  disconnected: { color: 'bg-red-500', label: 'Disconnected', pulse: false },
  error: { color: 'bg-red-500', label: 'Error', pulse: false },
  online: { color: 'bg-green-500', label: 'Online', pulse: false },
  offline: { color: 'bg-gray-500', label: 'Offline', pulse: false },
  live: { color: 'bg-red-500', label: 'LIVE', pulse: true },
};

export function StatusIndicator({ 
  status = 'offline', 
  showLabel = true,
  size = 'md',
  className,
  ...props 
}) {
  const config = STATUS_CONFIGS[status] || STATUS_CONFIGS.offline;
  
  const sizeClasses = {
    sm: { dot: 'w-1.5 h-1.5', text: 'text-[10px]' },
    md: { dot: 'w-2 h-2', text: 'text-xs' },
    lg: { dot: 'w-3 h-3', text: 'text-sm' },
  };

  return (
    <div className={cn('flex items-center gap-2', className)} {...props}>
      <span 
        className={cn(
          'rounded-full',
          config.color,
          sizeClasses[size].dot,
          config.pulse && 'animate-pulse'
        )} 
      />
      {showLabel && (
        <span className={cn('text-muted-foreground capitalize', sizeClasses[size].text)}>
          {config.label}
        </span>
      )}
    </div>
  );
}

export function LiveIndicator({ className, ...props }) {
  return (
    <div className={cn('flex items-center gap-1.5', className)} {...props}>
      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
      <span className="text-[10px] font-bold text-red-400 uppercase tracking-wider">LIVE</span>
    </div>
  );
}
