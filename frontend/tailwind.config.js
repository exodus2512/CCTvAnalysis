module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./contexts/**/*.{js,ts,jsx,tsx}",
    "./hooks/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Dynamic theme colors using CSS variables
        background: 'var(--bg-primary)',
        foreground: 'var(--text-primary)',
        card: 'var(--bg-secondary)',
        'card-hover': 'var(--bg-tertiary)',
        muted: 'var(--bg-tertiary)',
        'muted-foreground': 'var(--text-secondary)',
        border: 'var(--border-color)',
        'border-hover': 'var(--border-hover)',
        
        // Priority colors
        critical: '#f4212e',
        high: '#ff7a00',
        medium: '#ffd400',
        low: '#1d9bf0',
        
        // Status colors
        success: '#00ba7c',
        warning: '#ffd400',
        danger: '#f4212e',
        info: '#1d9bf0',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'slide-out': 'slideOut 0.3s ease-in',
        'fade-in': 'fadeIn 0.2s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'counter': 'counter 0.5s ease-out',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        slideOut: {
          '0%': { transform: 'translateX(0)', opacity: '1' },
          '100%': { transform: 'translateX(100%)', opacity: '0' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      boxShadow: {
        'glow-red': '0 0 20px rgba(244, 33, 46, 0.3)',
        'glow-blue': '0 0 20px rgba(29, 155, 240, 0.3)',
        'glow-green': '0 0 20px rgba(0, 186, 124, 0.3)',
      },
    },
  },
  plugins: [],
};
