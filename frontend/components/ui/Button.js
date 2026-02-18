'use client';

import { cn } from '../../lib/utils';

const VARIANTS = {
  primary: 'bg-gradient-to-r from-blue-500 to-purple-600 text-white hover:opacity-90',
  secondary: 'bg-card border border-border text-foreground hover:bg-muted',
  ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
  danger: 'bg-red-500/20 border border-red-500/50 text-red-400 hover:bg-red-500/30',
  success: 'bg-green-500/20 border border-green-500/50 text-green-400 hover:bg-green-500/30',
  outline: 'border-2 border-dashed border-border text-muted-foreground hover:border-blue-500 hover:text-blue-400',
};

const SIZES = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
  icon: 'p-2',
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  className,
  ...props
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all',
        'focus:outline-none focus:ring-2 focus:ring-blue-500/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANTS[variant],
        SIZES[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
          <circle 
            className="opacity-25" 
            cx="12" cy="12" r="10" 
            stroke="currentColor" 
            strokeWidth="4" 
            fill="none" 
          />
          <path 
            className="opacity-75" 
            fill="currentColor" 
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" 
          />
        </svg>
      )}
      {children}
    </button>
  );
}
