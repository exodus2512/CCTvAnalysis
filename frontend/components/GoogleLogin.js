'use client';

import { useState, useEffect, createContext, useContext } from 'react';
import { motion } from 'framer-motion';
import { Loader2, LogOut } from 'lucide-react';
import { cn } from '../lib/utils';
import { BACKEND_URL } from '../lib/constants';

// ============================================================================
// AUTH CONTEXT
// ============================================================================
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(null);

  // Check for token on mount and URL params
  useEffect(() => {
    // Check URL for token (from OAuth callback)
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get('token');
    const authError = params.get('auth_error');
    
    if (authError) {
      console.error('Auth error:', authError);
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
      setLoading(false);
      return;
    }
    
    if (urlToken) {
      // Save token from URL
      localStorage.setItem('sentinelai_token', urlToken);
      setToken(urlToken);
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    } else {
      // Check localStorage
      const storedToken = localStorage.getItem('sentinelai_token');
      if (storedToken) {
        setToken(storedToken);
      }
    }
    
    setLoading(false);
  }, []);

  // Verify token and load user
  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }

    const verifyToken = async () => {
      try {
        const backendUrl = BACKEND_URL.replace('/event', '');
        const res = await fetch(`${backendUrl}/auth/verify`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        
        if (res.ok) {
          const data = await res.json();
          if (data.valid && data.user) {
            setUser(data.user);
          } else {
            // Token invalid, clear it
            localStorage.removeItem('sentinelai_token');
            setToken(null);
            setUser(null);
          }
        } else {
          localStorage.removeItem('sentinelai_token');
          setToken(null);
          setUser(null);
        }
      } catch (err) {
        console.error('Token verification failed:', err);
        // Don't clear token on network errors
      }
    };

    verifyToken();
  }, [token]);

  const signIn = () => {
    const backendUrl = BACKEND_URL.replace('/event', '');
    window.location.href = `${backendUrl}/auth/google/login`;
  };

  const signOut = () => {
    localStorage.removeItem('sentinelai_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

// ============================================================================
// GOOGLE LOGIN BUTTON
// ============================================================================
export default function GoogleLoginButton({ 
  className,
  size = 'default',
  fullWidth = false,
}) {
  const { signIn } = useAuth();
  const [loading, setLoading] = useState(false);

  const handleClick = () => {
    setLoading(true);
    signIn();
  };

  const sizeClasses = {
    sm: 'py-2 px-4 text-sm',
    default: 'py-3 px-6 text-base',
    lg: 'py-4 px-8 text-lg',
  };

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={handleClick}
      disabled={loading}
      className={cn(
        'relative flex items-center justify-center gap-3',
        'bg-white text-gray-700 font-medium rounded-xl',
        'border border-gray-200 shadow-sm',
        'hover:bg-gray-50 hover:border-gray-300',
        'disabled:opacity-70 disabled:cursor-not-allowed',
        'transition-all duration-200',
        sizeClasses[size],
        fullWidth && 'w-full',
        className
      )}
    >
      {loading ? (
        <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
      ) : (
        <GoogleIcon className="w-5 h-5" />
      )}
      <span>{loading ? 'Signing in...' : 'Continue with Google'}</span>
    </motion.button>
  );
}

function GoogleIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

/**
 * Auth Status Component
 * Shows current user or login prompt
 */
export function AuthStatus() {
  const { user, loading, signOut } = useAuth();
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = () => {
    setSigningOut(true);
    signOut();
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading...</span>
      </div>
    );
  }

  if (user) {
    return (
      <div className="flex items-center gap-3">
        {user.picture ? (
          <img 
            src={user.picture} 
            alt={user.name || 'User'}
            className="w-9 h-9 rounded-full border-2 border-border"
          />
        ) : (
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-sm font-semibold shadow-lg">
            {user.name?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || 'U'}
          </div>
        )}
        <div className="text-left hidden lg:block">
          <p className="text-sm font-medium text-foreground leading-tight">{user.name}</p>
          <p className="text-xs text-muted-foreground">{user.email}</p>
        </div>
        <button
          onClick={handleSignOut}
          disabled={signingOut}
          className="ml-1 p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-all disabled:opacity-50"
          title="Sign out"
        >
          {signingOut ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <LogOut className="w-4 h-4" />
          )}
        </button>
      </div>
    );
  }

  return <GoogleLoginButton size="sm" />;
}
