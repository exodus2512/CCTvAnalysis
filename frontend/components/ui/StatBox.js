'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '../../lib/utils';

export function StatBox({ 
  label, 
  value, 
  icon,
  trend,
  trendValue,
  color = 'default',
  size = 'md',
  animate = true,
  className,
  ...props 
}) {
  const [displayValue, setDisplayValue] = useState(0);
  const prevValue = useRef(0);

  // Animated counter
  useEffect(() => {
    if (!animate || typeof value !== 'number') {
      setDisplayValue(value);
      return;
    }

    const start = prevValue.current;
    const end = value;
    const duration = 500;
    const startTime = Date.now();

    const animateCount = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      // Easing function
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(start + (end - start) * eased);
      
      setDisplayValue(current);
      
      if (progress < 1) {
        requestAnimationFrame(animateCount);
      }
    };

    requestAnimationFrame(animateCount);
    prevValue.current = value;
  }, [value, animate]);

  const colorClasses = {
    default: 'text-foreground',
    blue: 'text-blue-400',
    green: 'text-green-400',
    red: 'text-red-400',
    orange: 'text-orange-400',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
  };

  const sizeClasses = {
    sm: { value: 'text-xl', label: 'text-[10px]' },
    md: { value: 'text-2xl', label: 'text-xs' },
    lg: { value: 'text-3xl', label: 'text-sm' },
  };

  return (
    <div 
      className={cn(
        'bg-card border border-border rounded-xl p-4 flex flex-col',
        className
      )}
      {...props}
    >
      <div className="flex items-start justify-between mb-2">
        {icon && (
          <div className={cn('p-2 rounded-lg bg-muted', colorClasses[color])}>
            {icon}
          </div>
        )}
        {trend && (
          <div className={cn(
            'flex items-center gap-1 text-xs',
            trend === 'up' ? 'text-green-400' : 'text-red-400'
          )}>
            {trend === 'up' ? '↑' : '↓'}
            <span>{trendValue}</span>
          </div>
        )}
      </div>
      <div className={cn('font-bold tabular-nums', sizeClasses[size].value, colorClasses[color])}>
        {displayValue}
      </div>
      <div className={cn('text-muted-foreground uppercase tracking-wider mt-1', sizeClasses[size].label)}>
        {label}
      </div>
    </div>
  );
}
