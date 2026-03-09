/**
 * LoginScreen — shown when no valid session token exists.
 *
 * Two modes:
 *   1. Setup mode (first run) — user creates a password
 *   2. Login mode — user enters their password
 *
 * Props:
 *   onAuthenticated {function} - Called with the JWT token after successful auth
 */

import { useState, useEffect } from 'react';
import { api } from '../api';
import './LoginScreen.css';

function LoginScreen({ onAuthenticated }) {
  const [mode, setMode] = useState(null); // 'login' | 'setup' | null (loading)
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const status = await api.getAuthStatus();
      setMode(status.password_set ? 'login' : 'setup');
    } catch {
      // Backend not reachable — default to login
      setMode('login');
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const result = await api.login(password);
      onAuthenticated(result.token, { passwordTooShort: result.password_too_short });
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSetup = async (e) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await api.setupPassword(password);
      onAuthenticated(result.token);
    } catch (err) {
      setError(err.message || 'Setup failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (mode === null) {
    return (
      <div className="login-screen">
        <div className="login-card">
          <p>Connecting to server...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="login-title">C-Suite AI</h1>

        {mode === 'setup' ? (
          <>
            <p className="login-subtitle">
              Welcome! Set a password to protect your instance.
              This password encrypts your API keys and controls access.
            </p>
            <form onSubmit={handleSetup} className="login-form">
              <label className="login-label">
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Choose a password"
                  autoFocus
                  className="login-input"
                />
              </label>
              <label className="login-label">
                Confirm Password
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  className="login-input"
                />
              </label>
              {error && <div className="login-error">{error}</div>}
              <button
                type="submit"
                disabled={isSubmitting || !password}
                className="login-button"
              >
                {isSubmitting ? 'Setting up...' : 'Set Password & Continue'}
              </button>
            </form>
          </>
        ) : (
          <>
            <p className="login-subtitle">Enter your password to continue.</p>
            <form onSubmit={handleLogin} className="login-form">
              <label className="login-label">
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  autoFocus
                  className="login-input"
                />
              </label>
              {error && <div className="login-error">{error}</div>}
              <button
                type="submit"
                disabled={isSubmitting || !password}
                className="login-button"
              >
                {isSubmitting ? 'Logging in...' : 'Log In'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default LoginScreen;
