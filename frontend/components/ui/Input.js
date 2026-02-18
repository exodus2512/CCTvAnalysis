'use client';

import { cn } from '../../lib/utils';

export function Input({ 
  label,
  error,
  className,
  ...props 
}) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-xs font-medium text-muted-foreground">
          {label}
        </label>
      )}
      <input
        className={cn(
          'w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground',
          'placeholder:text-muted-foreground/50',
          'focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500',
          'transition-colors',
          error && 'border-red-500 focus:ring-red-500/50',
          className
        )}
        {...props}
      />
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  );
}

export function Select({ 
  label,
  options = [],
  error,
  className,
  ...props 
}) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-xs font-medium text-muted-foreground">
          {label}
        </label>
      )}
      <select
        className={cn(
          'w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-foreground',
          'focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500',
          'transition-colors appearance-none cursor-pointer',
          error && 'border-red-500',
          className
        )}
        {...props}
      >
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="text-xs text-red-400">{error}</p>
      )}
    </div>
  );
}

export function Checkbox({ 
  label,
  className,
  ...props 
}) {
  return (
    <label className={cn('flex items-center gap-2 cursor-pointer', className)}>
      <input
        type="checkbox"
        className={cn(
          'w-4 h-4 rounded border-border bg-background text-blue-500',
          'focus:ring-blue-500/50 focus:ring-2'
        )}
        {...props}
      />
      {label && (
        <span className="text-sm text-foreground">{label}</span>
      )}
    </label>
  );
}
