import { useState } from 'react'
import { authApi } from '../services/api'

export default function AuthView({ onAuthSuccess }) {
  const [tab, setTab] = useState('login') // 'login' or 'register'
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})
  const [successMsg, setSuccessMsg] = useState(null)

  // Login form state
  const [loginForm, setLoginForm] = useState({ username: '', password: '' })

  // Register form state
  const [registerForm, setRegisterForm] = useState({
    username: '',
    email: '',
    nickname: '',
    password: '',
    password_confirm: '',
  })

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setErrorMsg(null)
    setFieldErrors({})

    const res = await authApi.login(loginForm)
    setLoading(false)

    if (res.ok) {
      onAuthSuccess(res.data)
    } else {
      if (res.errors) {
        if (typeof res.errors === 'string') {
          setErrorMsg(res.errors)
        } else if (res.errors.non_field_errors) {
          setErrorMsg(res.errors.non_field_errors.join(' '))
        } else if (res.errors.detail) {
          setErrorMsg(res.errors.detail)
        } else {
          setFieldErrors(res.errors)
        }
      } else {
        setErrorMsg('Грешно потребителско име или парола.')
      }
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    setLoading(true)
    setErrorMsg(null)
    setFieldErrors({})

    const res = await authApi.register(registerForm)
    setLoading(false)

    if (res.ok) {
      setSuccessMsg('Регистрацията бе успешна! Влизане...')
      const loginRes = await authApi.login({
        username: registerForm.username,
        password: registerForm.password,
      })
      if (loginRes.ok) {
        onAuthSuccess(loginRes.data)
      } else {
        setTab('login')
      }
    } else {
      if (res.errors) {
        if (typeof res.errors === 'string') {
          setErrorMsg(res.errors)
        } else {
          setFieldErrors(res.errors)
        }
      } else {
        setErrorMsg('Неуспешна регистрация. Проверете въведените данни.')
      }
    }
  }

  return (
    <div className="auth-view-container">
      <div className="auth-card-panel">
        {/* Brand Crest */}
        <div className="auth-header-crest">
          <div className="crest-emblem">QC</div>
          <span className="crest-subtitle">КРАЛСКА ТРИВИЯ ВОЙНА</span>
          <h1 className="crest-title">
            QUIZ <span>CONQUEST</span>
          </h1>
        </div>

        {/* Tab switchers */}
        <div className="auth-nav-tabs">
          <button
            type="button"
            className={`auth-tab-btn ${tab === 'login' ? 'active' : ''}`}
            onClick={() => {
              setTab('login')
              setErrorMsg(null)
              setFieldErrors({})
            }}
          >
            ⚔️ ВХОД
          </button>
          <button
            type="button"
            className={`auth-tab-btn ${tab === 'register' ? 'active' : ''}`}
            onClick={() => {
              setTab('register')
              setErrorMsg(null)
              setFieldErrors({})
            }}
          >
            📜 РЕГИСТРАЦИЯ
          </button>
        </div>

        {/* Alerts */}
        {errorMsg && <div className="medieval-alert alert-error">{errorMsg}</div>}
        {successMsg && <div className="medieval-alert alert-success">{successMsg}</div>}

        {/* Login Form */}
        {tab === 'login' ? (
          <form onSubmit={handleLogin} className="medieval-form">
            <div className="input-group">
              <label>ПОТРЕБИТЕЛСКО ИМЕ</label>
              <input
                type="text"
                required
                value={loginForm.username}
                onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                placeholder="Въведете потребителско име"
                className={fieldErrors.username ? 'input-err' : ''}
              />
              {fieldErrors.username && (
                <span className="field-err-msg">{fieldErrors.username.join(' ')}</span>
              )}
            </div>

            <div className="input-group">
              <label>ПАРОЛА</label>
              <input
                type="password"
                required
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                placeholder="Въведете парола"
                className={fieldErrors.password ? 'input-err' : ''}
              />
              {fieldErrors.password && (
                <span className="field-err-msg">{fieldErrors.password.join(' ')}</span>
              )}
            </div>

            <button className="medieval-btn btn-primary" type="submit" disabled={loading}>
              <span>{loading ? 'ПРОВЕРКА...' : 'ВЛЕЗ В КРАЛСТВОТО'}</span>
              <span>➔</span>
            </button>

            <p className="auth-switch-text">
              Все още нямате профил?{' '}
              <button
                type="button"
                className="link-switch"
                onClick={() => {
                  setTab('register')
                  setErrorMsg(null)
                }}
              >
                Създайте рицар тук
              </button>
            </p>
          </form>
        ) : (
          /* Register Form */
          <form onSubmit={handleRegister} className="medieval-form">
            <div className="input-group">
              <label>ПОТРЕБИТЕЛСКО ИМЕ (USERNAME)</label>
              <input
                type="text"
                required
                value={registerForm.username}
                onChange={(e) => setRegisterForm({ ...registerForm, username: e.target.value })}
                placeholder="напр. knight_marko"
                className={fieldErrors.username ? 'input-err' : ''}
              />
              {fieldErrors.username && (
                <span className="field-err-msg">{fieldErrors.username.join(' ')}</span>
              )}
            </div>

            <div className="input-group">
              <label>ЕЛЕКТРОННА ПОЩА (EMAIL)</label>
              <input
                type="email"
                required
                value={registerForm.email}
                onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                placeholder="knight@example.com"
                className={fieldErrors.email ? 'input-err' : ''}
              />
              {fieldErrors.email && (
                <span className="field-err-msg">{fieldErrors.email.join(' ')}</span>
              )}
            </div>

            <div className="input-group">
              <label>РИЦАРСКИ ПРЯКОР (NICKNAME В ИГРАТА)</label>
              <input
                type="text"
                required
                maxLength={30}
                value={registerForm.nickname}
                onChange={(e) => setRegisterForm({ ...registerForm, nickname: e.target.value })}
                placeholder="напр. Марко Кралевити"
                className={fieldErrors.nickname ? 'input-err' : ''}
              />
              {fieldErrors.nickname && (
                <span className="field-err-msg">{fieldErrors.nickname.join(' ')}</span>
              )}
            </div>

            <div className="input-row">
              <div className="input-group">
                <label>ПАРОЛА</label>
                <input
                  type="password"
                  required
                  value={registerForm.password}
                  onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                  placeholder="Парола"
                  className={fieldErrors.password ? 'input-err' : ''}
                />
                {fieldErrors.password && (
                  <span className="field-err-msg">{fieldErrors.password.join(' ')}</span>
                )}
              </div>

              <div className="input-group">
                <label>ПОВТОРИ ПАРОЛА</label>
                <input
                  type="password"
                  required
                  value={registerForm.password_confirm}
                  onChange={(e) => setRegisterForm({ ...registerForm, password_confirm: e.target.value })}
                  placeholder="Потвърди"
                  className={fieldErrors.password_confirm ? 'input-err' : ''}
                />
                {fieldErrors.password_confirm && (
                  <span className="field-err-msg">{fieldErrors.password_confirm.join(' ')}</span>
                )}
              </div>
            </div>

            <button className="medieval-btn btn-primary" type="submit" disabled={loading}>
              <span>{loading ? 'СЪЗДАВАНЕ...' : 'СЪЗДАЙ РИЦАРСКИ ПРОФИЛ'}</span>
              <span>➔</span>
            </button>

            <p className="auth-switch-text">
              Вече сте рицар?{' '}
              <button
                type="button"
                className="link-switch"
                onClick={() => {
                  setTab('login')
                  setErrorMsg(null)
                }}
              >
                Влезте оттук
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
