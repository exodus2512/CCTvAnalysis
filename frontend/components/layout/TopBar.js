'use client';

import { Bell, Search, Menu } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Badge } from '../ui/Badge';
import { StatusIndicator } from '../ui/StatusIndicator';

export function TopBar({ 
  title,
  subtitle,
  stats = {},
  alertCount = 0,
  wsStatus = 'disconnected',
  onMenuClick,
  children,
  className,
}) {
  return (
    <header className={cn(
      'h-16 bg-card border-b border-border px-6',
      'flex items-center justify-between',
      'sticky top-0 z-30',
      className
    )}>
      {/* Left Section */}
      <div className="flex items-center gap-4">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        
        <div>
          <h1 className="text-lg font-semibold text-foreground">{title}</h1>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>

      {/* Center Section - Stats */}
      <div className="hidden md:flex items-center gap-6">
        <StatItem 
          value={stats.activeCameras || 0} 
          label="Active Cameras" 
          color="blue"
        />
        <Divider />
        <StatItem 
          value={stats.totalIncidents || 0} 
          label="Total Incidents" 
          color="default"
        />
        <Divider />
        <StatItem 
          value={stats.criticalAlerts || 0} 
          label="Critical" 
          color="red"
        />
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-4">
        {/* WebSocket Status */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-muted rounded-lg">
          <StatusIndicator status={wsStatus} size="sm" />
          {wsStatus === 'connected' && (
            <span className="text-xs text-green-400 font-medium">LIVE</span>
          )}
        </div>

        {/* Alert Bell */}
        <button className="relative p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <Bell className="w-5 h-5" />
          {alertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-white text-[10px] font-bold flex items-center justify-center animate-pulse">
              {alertCount > 99 ? '99+' : alertCount}
            </span>
          )}
        </button>

        {/* Custom Actions */}
        {children}
      </div>
    </header>
  );
}

function StatItem({ value, label, color = 'default' }) {
  const colorClasses = {
    default: 'text-foreground',
    blue: 'text-blue-400',
    red: 'text-red-400',
    green: 'text-green-400',
    orange: 'text-orange-400',
  };

  return (
    <div className="text-center">
      <div className={cn('text-xl font-bold tabular-nums', colorClasses[color])}>
        {value}
      </div>
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
        {label}
      </div>
    </div>
  );
}

function Divider() {
  return <div className="w-px h-8 bg-border" />;
}
