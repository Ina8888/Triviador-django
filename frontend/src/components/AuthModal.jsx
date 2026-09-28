import { useState, useEffect } from 'react';
import { authApi } from '../services/api';

const AVATAR_OPTIONS = [
  { key: 'knight-1', label: 'Knight 1 (Shield)', icon: '🛡️' },
  { key: 'knight-2', label: 'Knight 2 (Sword)', icon: '⚔️' },
  { key: 'knight-3', label: 'Knight 3 (Crown)', icon: '👑' },
  { key: 'knight-4', label: 'Knight 4 (Archer)', icon: '🏹' },
];

export default function AuthModal({ isOpen, onClose, user, onAuthSuccess, onLogout, initialTab = 'login' }) {
  const [tab, setTab] = useState(initialTab); // 'login', 'register', 'profile'
  const [errorMsg, setErrorMsg] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [successMsg, setSuccessMsg] = useState(null);
  const [loading, setLoading] = useState(false);

  // Login form state
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });

  // Register form state
  const [registerForm, setRegisterForm] = useState({
    username: '',
    email: '',
    nickname: '',
    password: '',
    password_confirm: '',
  });

  // Profile form state
  const [profileForm, setProfileForm] = useState({
    nickname: '',
    avatar_key: 'knight-1',
  });

  useEffect(() => {
    setTab(initialTab);
    setErrorMsg(null);
    setFieldErrors({});
    setSuccessMsg(null);
  }, [initialTab, isOpen]);

  useEffect(() => {
    if (user?.profile) {
      setProfileForm({
        nickname: user.profile.nickname || '',
        avatar_key: user.profile.avatar_key || 'knight-1',
      });
    }
  }, [user]);

  if (!isOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setFieldErrors({});
    setSuccessMsg(null);

    const res = await authApi.login(loginForm);
    setLoading(false);

    if (res.ok) {
      onAuthSuccess(res.data);
      onClose();
    } else {
      if (res.errors) {
        if (typeof res.errors === 'string') {
          setErrorMsg(res.errors);
        } else if (res.errors.non_field_errors) {
          setErrorMsg(res.errors.non_field_errors.join(' '));
        } else if (res.errors.detail) {
          setErrorMsg(res.errors.detail);
        } else {
          setFieldErrors(res.errors);
        }
      } else {
        setErrorMsg('Login failed. Please check your credentials.');
      }
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setFieldErrors({});
    setSuccessMsg(null);

    const res = await authApi.register(registerForm);
    setLoading(false);

    if (res.ok) {
      // Automatic login or notification
      setSuccessMsg('Registration successful! Logging in...');
      const loginRes = await authApi.login({
        username: registerForm.username,
        password: registerForm.password,
      });
      if (loginRes.ok) {
        onAuthSuccess(loginRes.data);
        setTimeout(() => onClose(), 800);
      } else {
        setTab('login');
      }
    } else {
      if (res.errors) {
        if (typeof res.errors === 'string') {
          setErrorMsg(res.errors);
        } else {
          setFieldErrors(res.errors);
        }
      } else {
        setErrorMsg('Registration failed. Please check your input.');
      }
    }
  };

  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setFieldErrors({});
    setSuccessMsg(null);

    const res = await authApi.updateProfile(profileForm);
    setLoading(false);

    if (res.ok) {
      setSuccessMsg('Profile updated successfully!');
      onAuthSuccess(res.data);
    } else {
      if (res.errors) {
        if (typeof res.errors === 'string') {
          setErrorMsg(res.errors);
        } else {
          setFieldErrors(res.errors);
        }
      } else {
        setErrorMsg('Failed to update profile.');
      }
    }
  };

  const handleLogout = async () => {
    setLoading(true);
    await authApi.logout();
    setLoading(false);
    onLogout();
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-window panel-frame" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-tabs">
            {!user ? (
              <>
                <button
                  type="button"
                  className={`modal-tab ${tab === 'login' ? 'tab-active' : ''}`}
                  onClick={() => { setTab('login'); setErrorMsg(null); setFieldErrors({}); }}
                >
                  LOGIN
                </button>
                <button
                  type="button"
                  className={`modal-tab ${tab === 'register' ? 'tab-active' : ''}`}
                  onClick={() => { setTab('register'); setErrorMsg(null); setFieldErrors({}); }}
                >
                  REGISTER
                </button>
              </>
            ) : (
              <button
                type="button"
                className="modal-tab tab-active"
                onClick={() => setTab('profile')}
              >
                USER PROFILE
              </button>
            )}
          </div>
          <button className="modal-close" type="button" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {errorMsg && <div className="auth-alert error-alert">{errorMsg}</div>}
          {successMsg && <div className="auth-alert success-alert">{successMsg}</div>}

          {/* LOGIN FORM */}
          {tab === 'login' && !user && (
            <form onSubmit={handleLogin} className="auth-form">
              <div className="form-group">
                <label>USERNAME</label>
                <input
                  type="text"
                  required
                  value={loginForm.username}
                  onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                  placeholder="Enter username"
                  className={fieldErrors.username ? 'input-error' : ''}
                />
                {fieldErrors.username && <small className="field-err">{fieldErrors.username.join(' ')}</small>}
              </div>

              <div className="form-group">
                <label>PASSWORD</label>
                <input
                  type="password"
                  required
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  placeholder="Enter password"
                  className={fieldErrors.password ? 'input-error' : ''}
                />
                {fieldErrors.password && <small className="field-err">{fieldErrors.password.join(' ')}</small>}
              </div>

              <div className="auth-actions">
                <button className="primary-button" type="submit" disabled={loading}>
                  {loading ? 'LOGGING IN...' : 'LOGIN TO CONQUEST'} <span>↗</span>
                </button>
              </div>

              <p className="tab-switch-hint">
                Don't have an account?{' '}
                <button type="button" className="link-button" onClick={() => setTab('register')}>
                  Register here
                </button>
              </p>
            </form>
          )}

          {/* REGISTER FORM */}
          {tab === 'register' && !user && (
            <form onSubmit={handleRegister} className="auth-form">
              <div className="form-group">
                <label>USERNAME</label>
                <input
                  type="text"
                  required
                  value={registerForm.username}
                  onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                  placeholder="e.g. player_one"
                  className={fieldErrors.username ? 'input-error' : ''}
                />
                {fieldErrors.username && <small className="field-err">{fieldErrors.username.join(' ')}</small>}
              </div>

              <div className="form-group">
                <label>EMAIL</label>
                <input
                  type="email"
                  required
                  value={registerForm.email}
                  onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                  placeholder="e.g. player@example.com"
                  className={fieldErrors.email ? 'input-error' : ''}
                />
                {fieldErrors.email && <small className="field-err">{fieldErrors.email.join(' ')}</small>}
              </div>

              <div className="form-group">
                <label>NICKNAME (IN-GAME NAME)</label>
                <input
                  type="text"
                  required
                  maxLength={30}
                  value={registerForm.nickname}
                  onChange={(e) => setRegisterForm({ ...registerForm, nickname: e.target.value })}
                  placeholder="e.g. MountainKnight"
                  className={fieldErrors.nickname ? 'input-error' : ''}
                />
                {fieldErrors.nickname && <small className="field-err">{fieldErrors.nickname.join(' ')}</small>}
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>PASSWORD</label>
                  <input
                    type="password"
                    required
                    value={registerForm.password}
                    onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                    placeholder="Enter password"
                    className={fieldErrors.password ? 'input-error' : ''}
                  />
                  {fieldErrors.password && <small className="field-err">{fieldErrors.password.join(' ')}</small>}
                </div>

                <div className="form-group">
                  <label>CONFIRM PASSWORD</label>
                  <input
                    type="password"
                    required
                    value={registerForm.password_confirm}
                    onChange={(e) => setRegisterForm({ ...registerForm, password_confirm: e.target.value })}
                    placeholder="Confirm password"
                    className={fieldErrors.password_confirm ? 'input-error' : ''}
                  />
                  {fieldErrors.password_confirm && (
                    <small className="field-err">{fieldErrors.password_confirm.join(' ')}</small>
                  )}
                </div>
              </div>

              <div className="auth-actions">
                <button className="primary-button" type="submit" disabled={loading}>
                  {loading ? 'REGISTERING...' : 'CREATE ACCOUNT'} <span>↗</span>
                </button>
              </div>

              <p className="tab-switch-hint">
                Already registered?{' '}
                <button type="button" className="link-button" onClick={() => setTab('login')}>
                  Login here
                </button>
              </p>
            </form>
          )}

          {/* PROFILE VIEW (PROTECTED) */}
          {user ? (
            <form onSubmit={handleUpdateProfile} className="auth-form profile-form">
              <div className="profile-identity-card">
                <div className="avatar-badge">
                  {AVATAR_OPTIONS.find((a) => a.key === profileForm.avatar_key)?.icon || '🛡️'}
                </div>
                <div>
                  <h3>{user.username}</h3>
                  <p className="user-email">{user.email}</p>
                  <span className="user-id-tag">PLAYER ID #{user.id}</span>
                </div>
              </div>

              <div className="form-group">
                <label>EDIT NICKNAME</label>
                <input
                  type="text"
                  required
                  maxLength={30}
                  value={profileForm.nickname}
                  onChange={(e) => setProfileForm({ ...profileForm, nickname: e.target.value })}
                  placeholder="Enter nickname"
                  className={fieldErrors.nickname ? 'input-error' : ''}
                />
                {fieldErrors.nickname && <small className="field-err">{fieldErrors.nickname.join(' ')}</small>}
              </div>

              <div className="form-group">
                <label>CHOOSE AVATAR</label>
                <div className="avatar-grid">
                  {AVATAR_OPTIONS.map((av) => (
                    <button
                      key={av.key}
                      type="button"
                      className={`avatar-option ${profileForm.avatar_key === av.key ? 'avatar-selected' : ''}`}
                      onClick={() => setProfileForm({ ...profileForm, avatar_key: av.key })}
                    >
                      <span className="avatar-icon">{av.icon}</span>
                      <span className="avatar-title">{av.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="profile-actions">
                <button className="primary-button" type="submit" disabled={loading}>
                  {loading ? 'SAVING...' : 'SAVE CHANGES'} <span>✓</span>
                </button>
                <button className="secondary-button" type="button" onClick={handleLogout} disabled={loading}>
                  LOGOUT
                </button>
              </div>
            </form>
          ) : tab === 'profile' && (
            <div className="protected-alert">
              <h3>🔒 PROTECTED PROFILE</h3>
              <p>You must be logged in to view and edit your profile.</p>
              <button className="primary-button" type="button" onClick={() => setTab('login')}>
                GO TO LOGIN
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
