import { useState } from 'react'
import { authApi } from '../services/api'

const AVATAR_LIST = [
  { key: 'knight-1', label: 'Щит на защитника', icon: '🛡️' },
  { key: 'knight-2', label: 'Меч на завоевателя', icon: '⚔️' },
  { key: 'knight-3', label: 'Кралска корона', icon: '👑' },
  { key: 'knight-4', label: 'Стрелец на стражата', icon: '🏹' },
]

export default function LobbyView({
  user,
  savedMatch,
  onStartNewMatch,
  onResumeMatch,
  onUserUpdate,
  onLogout,
}) {
  const [nickname, setNickname] = useState(user?.profile?.nickname || user?.username || '')
  const [avatarKey, setAvatarKey] = useState(user?.profile?.avatar_key || 'knight-1')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [err, setErr] = useState(null)

  const handleSaveProfile = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMsg(null)
    setErr(null)

    const res = await authApi.updateProfile({ nickname, avatar_key: avatarKey })
    setSaving(false)

    if (res.ok) {
      setMsg('Рицарският профил бе обновен успешно!')
      onUserUpdate(res.data)
    } else {
      setErr(res.errors?.nickname ? res.errors.nickname.join(' ') : 'Грешка при обновяване.')
    }
  }

  const currentAvatarIcon =
    AVATAR_LIST.find((a) => a.key === (user?.profile?.avatar_key || 'knight-1'))?.icon || '🛡️'

  return (
    <div className="lobby-container">
      {/* Top Profile Banner Bar */}
      <header className="lobby-topbar">
        <div className="lobby-brand">
          <span className="brand-shield">QC</span>
          <div>
            <span className="lobby-eyebrow">РИЦАРСКО ЛОБИ</span>
            <h1 className="lobby-title">QUIZ <span>CONQUEST</span></h1>
          </div>
        </div>

        <div className="lobby-user-bar">
          <div className="lobby-user-pill">
            <span className="user-icon">{currentAvatarIcon}</span>
            <span className="user-name">{user?.profile?.nickname || user?.username}</span>
            <span className="user-role">РИЦАР</span>
          </div>

          <button
            type="button"
            className="medieval-btn btn-logout"
            onClick={onLogout}
            title="Изход от системата"
          >
            ИЗХОД 🚪
          </button>
        </div>
      </header>

      {/* Main Dual Panels: 1) Match Selection & 2) Profile Config */}
      <div className="lobby-grid">
        {/* PANEL 1: MATCH SELECTION (NEW OR RESUME) */}
        <section className="lobby-card match-choice-panel">
          <div className="card-header">
            <span className="card-tag">БОЙНИ КАМПАНИИ</span>
            <h2>ИЗБЕРЕТЕ БИТКА</h2>
            <p className="card-desc">Продължете старата си война за земите или поведете нов поход.</p>
          </div>

          <div className="match-options-list">
            {/* OPTION A: RESUME OLD MATCH */}
            <div className={`match-option-box ${savedMatch ? 'active-save' : 'disabled-save'}`}>
              <div className="option-crest">🏰</div>
              <div className="option-body">
                <div className="option-header-row">
                  <h3>ДОВЪРШИ СТАРА БИТКА</h3>
                  {savedMatch ? (
                    <span className="badge-active">АКТИВНА ИГРА</span>
                  ) : (
                    <span className="badge-none">НЯМА ЗАПИС</span>
                  )}
                </div>

                {savedMatch ? (
                  <div className="save-stats-row">
                    <div className="stat-pill">
                      <span>РУНД:</span> <b>{savedMatch.round || 1} / 12</b>
                    </div>
                    <div className="stat-pill">
                      <span>ТОЧКИ:</span> <b>{(savedMatch.score || 0).toLocaleString()}</b>
                    </div>
                    <div className="stat-pill">
                      <span>КРЕПОСТИ:</span>{' '}
                      <b>
                        {savedMatch.territories?.filter((t) => t.owner === 'player')?.length || 0} / 5
                      </b>
                    </div>
                  </div>
                ) : (
                  <p className="no-save-text">
                    Все още нямате незавършена битка. Започнете нова от бутона по-долу!
                  </p>
                )}

                <button
                  type="button"
                  className="medieval-btn btn-action-large btn-resume"
                  disabled={!savedMatch}
                  onClick={onResumeMatch}
                >
                  <span>ПРОДЪЛЖИ ТЕКУЩИЯ МАЧ</span>
                  <span>➔</span>
                </button>
              </div>
            </div>

            {/* OPTION B: START NEW MATCH */}
            <div className="match-option-box new-match-box">
              <div className="option-crest">⚔️</div>
              <div className="option-body">
                <div className="option-header-row">
                  <h3>ЗАПОЧНИ НОВ МАЧ</h3>
                  <span className="badge-new">ЧИСТО ПОЛЕ</span>
                </div>
                <p className="option-desc">
                  Стартира нова битка от Рунд 01 с първоначалните 5 крепости и пресни въпроси от кралската банка.
                </p>

                <button
                  type="button"
                  className="medieval-btn btn-action-large btn-new"
                  onClick={onStartNewMatch}
                >
                  <span>ЗАПОЧНИ НОВА БИТКА</span>
                  <span>⚔️</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* PANEL 2: PROFILE MANAGEMENT */}
        <section className="lobby-card profile-settings-panel">
          <div className="card-header">
            <span className="card-tag">РИЦАРСКА САМОЛИЧНОСТ</span>
            <h2>ТВОЯТ ПРОФИЛ</h2>
            <p className="card-desc">Персонализирайте своя прякор и боен герб.</p>
          </div>

          {msg && <div className="medieval-alert alert-success">{msg}</div>}
          {err && <div className="medieval-alert alert-error">{err}</div>}

          <form onSubmit={handleSaveProfile} className="profile-form">
            <div className="profile-badge-preview">
              <div className="preview-avatar">
                {AVATAR_LIST.find((a) => a.key === avatarKey)?.icon || '🛡️'}
              </div>
              <div className="preview-meta">
                <strong>{nickname || user?.username}</strong>
                <span>@{user?.username}</span>
                <small className="user-id-badge">ID #{user?.id}</small>
              </div>
            </div>

            <div className="input-group">
              <label>РИЦАРСКИ ПРЯКОР (NICKNAME)</label>
              <input
                type="text"
                required
                maxLength={30}
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="Въведете прякор"
              />
            </div>

            <div className="input-group">
              <label>ИЗБЕРЕТЕ БОЕН ГЕРБ (АВАТАР)</label>
              <div className="avatar-selection-grid">
                {AVATAR_LIST.map((av) => (
                  <button
                    key={av.key}
                    type="button"
                    className={`avatar-pick-btn ${avatarKey === av.key ? 'selected' : ''}`}
                    onClick={() => setAvatarKey(av.key)}
                  >
                    <span className="avatar-pick-icon">{av.icon}</span>
                    <span className="avatar-pick-label">{av.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <button className="medieval-btn btn-save" type="submit" disabled={saving}>
              {saving ? 'ЗАПАЗВАНЕ...' : 'ЗАПАЗИ ПРОМЕНИТЕ ⚜️'}
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
