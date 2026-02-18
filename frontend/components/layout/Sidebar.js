'use client';

import { useRouter } from 'next/router';
import Link from 'next/link';
import { 
  LayoutDashboard, 
  Camera, 
  AlertTriangle, 
  BarChart3, 
  Settings,
  Home,
  ChevronLeft,
  Moon,
  Sun 
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useTheme } from '../../contexts/ThemeContext';
import { StatusIndicator } from '../ui/StatusIndicator';

const NAV_ITEMS = [
  { id: 'monitoring', href: '/monitor', icon: LayoutDashboard, label: 'Dashboard' },
  { id: 'cameras', href: '/monitor?tab=cameras', icon: Camera, label: 'Cameras' },
  { id: 'incidents', href: '/monitor?tab=incidents', icon: AlertTriangle, label: 'Incidents' },
  { id: 'analytics', href: '/monitor?tab=analytics', icon: BarChart3, label: 'Analytics' },
  { id: 'settings', href: '/monitor?tab=settings', icon: Settings, label: 'Settings' },
];

export function Sidebar({ 
  activeTab, 
  onTabChange,
  wsStatus = 'disconnected',
  collapsed = false,
  onToggleCollapse,
}) {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className={cn(
      'fixed left-0 top-0 bottom-0 z-40',
      'bg-card border-r border-border',
      'flex flex-col transition-all duration-300',
      collapsed ? 'w-16' : 'w-64'
    )}>
      {/* Logo */}
      <div className="h-16 px-4 flex items-center justify-between border-b border-border">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center flex-shrink-0">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <div className="text-foreground font-bold text-lg">SentinelAI</div>
              <div className="text-muted-foreground text-xs">School Safety</div>
            </div>
          )}
        </Link>
        
        {!collapsed && onToggleCollapse && (
          <button 
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all',
                'text-sm font-medium',
                isActive 
                  ? 'bg-blue-500/10 text-blue-400 border-l-2 border-blue-500' 
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                collapsed && 'justify-center px-2'
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={cn('w-5 h-5 flex-shrink-0', isActive && 'text-blue-400')} />
              {!collapsed && <span>{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-4 space-y-3 border-t border-border">
        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg',
            'text-muted-foreground hover:bg-muted hover:text-foreground transition-all',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode` : undefined}
        >
          {theme === 'dark' ? (
            <Sun className="w-5 h-5" />
          ) : (
            <Moon className="w-5 h-5" />
          )}
          {!collapsed && (
            <span className="text-sm">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
          )}
        </button>

        {/* Connection Status */}
        <div className={cn(
          'flex items-center gap-3 px-3 py-2',
          collapsed && 'justify-center px-2'
        )}>
          <StatusIndicator status={wsStatus} showLabel={!collapsed} size="md" />
        </div>

        {/* Back to Config */}
        <Link
          href="/"
          className={cn(
            'flex items-center gap-3 px-3 py-2 rounded-lg',
            'text-muted-foreground hover:bg-muted hover:text-foreground transition-all',
            collapsed && 'justify-center px-2'
          )}
          title={collapsed ? 'Back to Config' : undefined}
        >
          <Home className="w-5 h-5" />
          {!collapsed && <span className="text-sm">Back to Config</span>}
        </Link>
      </div>
    </aside>
  );
}
