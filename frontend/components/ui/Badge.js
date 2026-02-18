'use client';

import { cn } from '../../lib/utils';
import { PRIORITY_COLORS } from '../../lib/constants';

const VARIANTS = {
  default: 'bg-muted text-muted-foreground',
  outline: 'border border-border text-muted-foreground',
  critical: `${PRIORITY_COLORS.critical.bg} ${PRIORITY_COLORS.critical.text} border border-red-500/50`,
  high: `${PRIORITY_COLORS.high.bg} ${PRIORITY_COLORS.high.text} border border-orange-500/50`,
  medium: `${PRIORITY_COLORS.medium.bg} ${PRIORITY_COLORS.medium.text} border border-yellow-500/50`,
  low: `${PRIORITY_COLORS.low.bg} ${PRIORITY_COLORS.low.text} border border-blue-500/50`,
  success: 'bg-green-500/20 text-green-400 border border-green-500/50',
  online: 'bg-green-500/20 text-green-400',
  offline: 'bg-red-500/20 text-red-400',
};

const SIZES = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export function Badge({ 
  children, 
  variant = 'default', 
  size = 'md',
  dot = false,
  pulse = false,
  className,
  ...props 
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full whitespace-nowrap',
        VARIANTS[variant] || VARIANTS.default,
        SIZES[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span 
          className={cn(
            'w-1.5 h-1.5 rounded-full',
            variant === 'online' || variant === 'success' ? 'bg-green-500' :
            variant === 'offline' || variant === 'critical' ? 'bg-red-500' :
            variant === 'high' ? 'bg-orange-500' :
            variant === 'medium' ? 'bg-yellow-500' :
            variant === 'low' ? 'bg-blue-500' : 'bg-current',
            pulse && 'animate-pulse'
          )}
        />
      )}
      {children}
    </span>
  );
}
