import '../styles/styles.css';
import { ThemeProvider } from '../contexts/ThemeContext';
import { ToastProvider } from '../components/ui/Toast';
import { AuthProvider } from '../components/GoogleLogin';

export default function App({ Component, pageProps }) {
  return (
    <AuthProvider>
      <ThemeProvider>
        <ToastProvider>
          <Component {...pageProps} />
        </ToastProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}
