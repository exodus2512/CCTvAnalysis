'use client';

import { createContext, useContext, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertTriangle, Info, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils';

const ToastContext = createContext({
  showToast: () => {},
  showSuccess: () => {},
  showError: () => {},
  showWarning: () => {},
  showInfo: () => {},
});

const TOAST_TYPES = {
  success: { icon: CheckCircle, bg: 'bg-green-500/20', border: 'border-green-500/50', text: 'text-green-400' },
  error: { icon: AlertCircle, bg: 'bg-red-500/20', border: 'border-red-500/50', text: 'text-red-400' },
  warning: { icon: AlertTriangle, bg: 'bg-orange-500/20', border: 'border-orange-500/50', text: 'text-orange-400' },
  info: { icon: Info, bg: 'bg-blue-500/20', border: 'border-blue-500/50', text: 'text-blue-400' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info', duration = 5000) => {
    const id = Date.now().toString();
    
    setToasts(prev => [...prev, { id, message, type }]);
    
    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, duration);
    }
    
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const value = {
    showToast,
    showSuccess: (message, duration) => showToast(message, 'success', duration),
    showError: (message, duration) => showToast(message, 'error', duration),
    showWarning: (message, duration) => showToast(message, 'warning', duration),
    showInfo: (message, duration) => showToast(message, 'info', duration),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      
      {/* Toast Container */}
      <div className="fixed top-4 right-4 z-50 space-y-3 max-w-md">
        <AnimatePresence>
          {toasts.map(toast => {
            const config = TOAST_TYPES[toast.type] || TOAST_TYPES.info;
            const Icon = config.icon;
            
            return (
              <motion.div
                key={toast.id}
                initial={{ opacity: 0, x: 100, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 100, scale: 0.95 }}
                className={cn(
                  'relative p-4 rounded-xl border backdrop-blur-sm shadow-lg',
                  'bg-card',
                  config.border
                )}
              >
                <div className="flex items-start gap-3">
                  <div className={cn('p-1 rounded-lg', config.bg)}>
                    <Icon className={cn('w-4 h-4', config.text)} />
                  </div>
                  <p className="text-sm text-foreground flex-1 pr-6">{toast.message}</p>
                  <button
                    onClick={() => removeToast(toast.id)}
                    className="absolute top-3 right-3 p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
