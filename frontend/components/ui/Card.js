'use client';

import { cn } from '../../lib/utils';

export function Card({ children, className, hover = false, highlight = false, ...props }) {
  return (
    <div
      className={cn(
        'bg-card border border-border rounded-xl shadow-sm',
        hover && 'transition-all hover:shadow-lg hover:border-border-hover hover:-translate-y-0.5',
        highlight && 'ring-2 ring-red-500/50 animate-pulse',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className, ...props }) {
  return (
    <div
      className={cn(
        'px-4 py-3 border-b border-border flex items-center justify-between',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, className, icon, ...props }) {
  return (
    <h3 className={cn('text-sm font-semibold text-foreground flex items-center gap-2', className)} {...props}>
      {icon && <span className="text-muted">{icon}</span>}
      {children}
    </h3>
  );
}

export function CardContent({ children, className, ...props }) {
  return (
    <div className={cn('p-4', className)} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className, ...props }) {
  return (
    <div className={cn('px-4 py-3 border-t border-border', className)} {...props}>
      {children}
    </div>
  );
}
