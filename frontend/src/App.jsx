import { useState, useEffect, useRef } from 'react'
import './App.css'
import AuthModal from './components/AuthModal'
import { authApi, questionsApi } from './services/api'

const initialTerritories = [
  { id: 'north', name: 'СЕВЕРНА СТРАЖА', short: 'СЕВЕР', icon: '⚔️', points: 180, owner: 'player', x: 26, y: 22 },
  { id: 'west', name: 'ЗАПАДЕН БАСТИОН', short: 'ЗАПАД', icon: '🛡️', points: 240, owner: 'enemy', x: 16, y: 52 },
  { id: 'capital', name: 'КРАЛСКА ЦИТАДЕЛА', short: 'СТОЛИЦА', icon: '🏰', points: 320, owner: 'neutral', x: 50, y: 46 },
  { id: 'east', name: 'ИЗТОЧНА КУЛА', short: 'ИЗТОК', icon: '🏹', points: 210, owner: 'player', x: 82, y: 36 },
  { id: 'south', name: 'ЮЖНА КРЕПОСТ', short: 'ЮГ', icon: '⚜️', points: 150, owner: 'neutral', x: 56, y: 78 },
]

const fallbackQuestion = {
  id: 1,
  category: 'История',
  text: 'През коя година е основана българската държава от хан Аспарух?',
  options: [
    { id: 1, text: '681 г.', is_correct: true },
    { id: 2, text: '865 г.', is_correct: false },
    { id: 3, text: '1018 г.', is_correct: false },
    { id: 4, text: '1185 г.', is_correct: false },
  ],
}

const avatarIcons = {
  'knight-1': '🛡️',
  'knight-2': '⚔️',
  'knight-3': '👑',
  'knight-4': '🏹',
}

const categoryIcons = {
  'История': '📜',
  'География': '🗺️',
  'Наука': '🧪',
  'Литература': '📖',
  'Изкуство': '🎨',
  'Спорт': '⚔️',
}

function App() {
  const [territories, setTerritories] = useState(initialTerritories)
  const [activeTerritoryId, setActiveTerritoryId] = useState('capital')
  const [selectedOption, setSelectedOption] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [score, setScore] = useState(1240)
  const [round, setRound] = useState(1)
  const [log, setLog] = useState([
    'ВОЕНЕН СЪВЕТ: Изберете крепост на бойното поле, за да започнете щурм!',
  ])

  // Question State
  const [question, setQuestion] = useState(fallbackQuestion)
  const [loadingQuestion, setLoadingQuestion] = useState(false)

  // Auth State
  const [currentUser, setCurrentUser] = useState(null)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const [authTab, setAuthTab] = useState('login')

  const questionSectionRef = useRef(null)

  const activeTerritory = territories.find((t) => t.id === activeTerritoryId) || territories[2]

  const fetchRandomQuestion = async () => {
    setLoadingQuestion(true)
    const res = await questionsApi.getRandom()
    setLoadingQuestion(false)
    if (res.ok && res.data) {
      setQuestion(res.data)
      setSelectedOption(null)
      setSubmitted(false)
    }
  }

  // Load session & initial question on mount
  useEffect(() => {
    authApi.getMe().then((res) => {
      if (res.ok && res.data) {
        setCurrentUser(res.data)
      }
    })
    fetchRandomQuestion()
  }, [])

  // Handle territory selection
  const handleSelectTerritory = (t) => {
    setActiveTerritoryId(t.id)
    if (!submitted) {
      fetchRandomQuestion()
    }
    // Mobile/small screen scroll
    if (window.innerWidth <= 980 && questionSectionRef.current) {
      questionSectionRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }

  // Choose an answer option
  const handleChooseOption = (option) => {
    if (submitted) return
    setSelectedOption(option)
  }

  // Submit answer
  const handleSubmitAnswer = () => {
    if (!selectedOption || submitted) return
    const isCorrect = Boolean(selectedOption.is_correct)
    setSubmitted(true)

    if (isCorrect) {
      const addedPoints = activeTerritory.points || 300
      setScore((prev) => prev + addedPoints)

      // Capture territory for player
      setTerritories((prev) =>
        prev.map((t) =>
          t.id === activeTerritoryId ? { ...t, owner: 'player' } : t
        )
      )

      setLog((prev) => [
        `🏰 ПОБЕДА (+${addedPoints} т.): Крепостта "${activeTerritory.name}" бе превзета от вашия отряд!`,
        ...prev,
      ])
    } else {
      setLog((prev) => [
        `🛡️ ОТБЛЪСНАТ ЩУРМ: Защитниците на "${activeTerritory.name}" устояха на атаката. Опитайте отново!`,
        ...prev,
      ])
    }
  }

  // Next move / round
  const handleNextTurn = () => {
    setRound((r) => Math.min(r + 1, 12))
    setSelectedOption(null)
    setSubmitted(false)
    fetchRandomQuestion()
  }

  const controlledCount = territories.filter((t) => t.owner === 'player').length

  return (
    <main className="app-shell medieval-theme">
      {/* Top Medieval Banner Header */}
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">
            <span>QC</span>
          </div>
          <div className="brand-titles">
            <span className="eyebrow">РИЦАРСКА ТРИВИЯ ВОЙНА</span>
            <h1 className="game-title">
              QUIZ <span className="title-highlight">CONQUEST</span>
            </h1>
          </div>
        </div>

        {/* User Profile / Login Button */}
        <div className="auth-header-actions">
          {currentUser ? (
            <button
              type="button"
              className="user-pill-btn"
              onClick={() => {
                setAuthTab('profile')
                setIsAuthOpen(true)
              }}
              title="Преглед на рицарски профил"
            >
              <span className="user-pill-avatar">
                {avatarIcons[currentUser.profile?.avatar_key] || '🛡️'}
              </span>
              <span className="user-pill-name">
                {currentUser.profile?.nickname || currentUser.username}
              </span>
              <span className="pill-badge">ПРОФИЛ ⚜️</span>
            </button>
          ) : (
            <button
              type="button"
              className="login-trigger-btn"
              onClick={() => {
                setAuthTab('login')
                setIsAuthOpen(true)
              }}
            >
              ВХОД / РЕГИСТРАЦИЯ <span>⚔️</span>
            </button>
          )}
        </div>

        {/* Match / Round badge */}
        <div className="match-meta">
          <div className="match-badge">
            <span className="match-label">КАМПАНИЯ #01</span>
            <strong className="round-badge">РУНД {String(round).padStart(2, '0')} / 12</strong>
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label="Профил и настройки"
            onClick={() => {
              setAuthTab(currentUser ? 'profile' : 'login')
              setIsAuthOpen(true)
            }}
          >
            ≡
          </button>
        </div>
      </header>

      {/* Medieval War Council (Score Strip) */}
      <section className="score-strip" aria-label="Военен съвет">
        <div
          className="player-card player-active"
          onClick={() => {
            setAuthTab(currentUser ? 'profile' : 'login')
            setIsAuthOpen(true)
          }}
          title="Вашият рицар"
        >
          <div className="player-crest">
            {currentUser?.profile?.avatar_key
              ? avatarIcons[currentUser.profile.avatar_key]
              : '🛡️'}
          </div>
          <div className="player-info">
            <strong className="player-title">
              {currentUser?.profile?.nickname ? currentUser.profile.nickname : 'ТИ (ЧЕРВЕН ОРДЕН)'}
            </strong>
            <small className="player-subtitle">
              {currentUser ? `@${currentUser.username} • ${controlledCount} КРЕПОСТИ` : 'ЧЕРВЕНО КРАЛСТВО'}
            </small>
          </div>
          <div className="player-score-box">
            <b>{score.toLocaleString()}</b>
            <small>ТОЧКИ</small>
          </div>
        </div>

        <div className="player-card player-enemy">
          <div className="player-crest">⚔️</div>
          <div className="player-info">
            <strong className="player-title">ЛОРД КАЛОЯН</strong>
            <small className="player-subtitle">ЧЕРЕН ОРДЕН • 1 КРЕПОСТ</small>
          </div>
          <div className="player-score-box">
            <b>980</b>
            <small>ТОЧКИ</small>
          </div>
        </div>

        <div className="player-card player-neutral">
          <div className="player-crest">👑</div>
          <div className="player-info">
            <strong className="player-title">ЛЕЙДИ РАДА</strong>
            <small className="player-subtitle">ЗЛАТЕН ОРДЕН • 0 КРЕПОСТИ</small>
          </div>
          <div className="player-score-box">
            <b>760</b>
            <small>ТОЧКИ</small>
          </div>
        </div>

        <div className="turn-callout">
          <span className="pulse-dot" />
          <span>ТВОЙ РЕД ЗА ЩУРМ</span>
        </div>
      </section>

      {/* Guide Bar explaining how to play */}
      <div className="guide-ribbon">
        <span className="guide-step"><b>СТЪПКА 1:</b> Избери крепост на картата 🏰</span>
        <span className="guide-divider">➔</span>
        <span className="guide-step"><b>СТЪПКА 2:</b> Отговори на въпроса 📜</span>
        <span className="guide-divider">➔</span>
        <span className="guide-step"><b>СТЪПКА 3:</b> Превземи територията! ⚔️</span>
      </div>

      {/* Main Battle Grid: Map (Left) & Question (Right) */}
      <div className="game-layout">
        {/* Left: The Territory Map */}
        <section className="map-panel panel-frame">
          <div className="panel-heading">
            <div className="heading-title-group">
              <span className="section-label">КАРТА НА ЗЕМИТЕ</span>
              <h2>КРАЛСКО БОЙНО ПОЛЕ</h2>
            </div>
            <div className="active-target-badge">
              <span>ЦЕЛ:</span> <strong>{activeTerritory.name}</strong>
            </div>
          </div>

          <div className="territory-map" aria-label="Карта на крепостите">
            {/* SVG Campaign Road Connections */}
            <svg className="map-routes-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
              {/* North to Capital */}
              <line x1="26" y1="22" x2="50" y2="46" className="route-line" />
              {/* West to Capital */}
              <line x1="16" y1="52" x2="50" y2="46" className="route-line" />
              {/* East to Capital */}
              <line x1="82" y1="36" x2="50" y2="46" className="route-line" />
              {/* South to Capital */}
              <line x1="56" y1="78" x2="50" y2="46" className="route-line" />
              {/* North to East */}
              <line x1="26" y1="22" x2="82" y2="36" className="route-line secondary-route" />
              {/* West to South */}
              <line x1="16" y1="52" x2="56" y2="78" className="route-line secondary-route" />
            </svg>

            <div className="compass-rose" />

            {/* Fortress Territory Buttons */}
            {territories.map((t) => {
              const isSelected = activeTerritoryId === t.id
              let ownerClass = 'owner-neutral'
              let ownerLabel = 'СВОБОДНА'
              if (t.owner === 'player') {
                ownerClass = 'owner-player'
                ownerLabel = 'ТВОЯ'
              } else if (t.owner === 'enemy') {
                ownerClass = 'owner-enemy'
                ownerLabel = 'ВРАЖЕСКА'
              }

              return (
                <button
                  key={t.id}
                  type="button"
                  className={`territory-fortress ${ownerClass} ${isSelected ? 'fortress-selected' : ''}`}
                  style={{ left: `${t.x}%`, top: `${t.y}%` }}
                  onClick={() => handleSelectTerritory(t)}
                  title={`Кликнете за атака на ${t.name}`}
                >
                  <div className="fortress-crest">
                    <span className="fortress-icon">{t.icon}</span>
                    <span className="fortress-badge">{ownerLabel}</span>
                  </div>
                  <div className="fortress-details">
                    <span className="fortress-name">{t.short}</span>
                    <strong className="fortress-points">+{t.points} т.</strong>
                  </div>
                  {isSelected && <span className="selected-indicator">⚔️ АТАКА</span>}
                </button>
              )
            })}

            <div className="map-coordinates">⚜️ БАЛКАНСКИ ВОЕНЕН ТЕАТЪР • СЕКТОР ALFA</div>
          </div>

          <div className="map-footer">
            <div className="legend-item">
              <span className="legend-shield shield-player" /> <b>ТВОИ КРЕПОСТИ ({controlledCount})</b>
            </div>
            <div className="legend-item">
              <span className="legend-shield shield-enemy" /> <b>ВРАЖЕСКИ</b>
            </div>
            <div className="legend-item">
              <span className="legend-shield shield-neutral" /> <b>НЕУТРАЛНИ ЗА ЩУРМ</b>
            </div>
          </div>
        </section>

        {/* Right: The Question & Action Panel */}
        <section className="question-panel panel-frame" ref={questionSectionRef}>
          <div className="panel-heading question-heading">
            <div className="heading-title-group">
              <div className="category-tag">
                <span className="cat-icon">
                  {categoryIcons[question.category] || '📜'}
                </span>
                <span>КАТЕГОРИЯ: {question.category?.toUpperCase() || 'ОБЩА КУЛТУРА'}</span>
              </div>
              <h2 className="battle-title">
                АТАКА: <span>{activeTerritory.name}</span>
              </h2>
            </div>
            <div className="reward-badge">
              <span className="reward-label">НАГРАДА</span>
              <strong className="reward-pts">+{activeTerritory.points} т.</strong>
            </div>
          </div>

          {/* Question Text Box (Scroll style) */}
          <div className="question-scroll-box">
            <div className="scroll-corner-ornament top-left" />
            <div className="scroll-corner-ornament top-right" />
            <div className="question-meta-tag">
              ВЪПРОС #{question.id} • ИЗБЕРЕТЕ ВЕРЕН ОТГОВОР:
            </div>
            <p className="question-text">{question.text}</p>
          </div>

          {/* Multiple Choice Answers */}
          <div className="answer-grid" role="radiogroup" aria-label="Отговори на въпроса">
            {question.options?.map((option, index) => {
              const isSelected = selectedOption?.id === option.id
              let statusClass = ''
              if (submitted) {
                if (option.is_correct) {
                  statusClass = 'option-correct'
                } else if (isSelected && !option.is_correct) {
                  statusClass = 'option-wrong'
                }
              } else if (isSelected) {
                statusClass = 'option-selected'
              }

              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  disabled={submitted}
                  className={`medieval-answer-btn ${statusClass}`}
                  onClick={() => handleChooseOption(option)}
                >
                  <span className="seal-badge">{String.fromCharCode(65 + index)}</span>
                  <span className="answer-label">{option.text}</span>
                  <span className="feedback-icon">
                    {submitted && option.is_correct && '✓'}
                    {submitted && isSelected && !option.is_correct && '✗'}
                    {!submitted && isSelected && '•'}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Result Alert Banner */}
          {submitted && (
            <div className={`battle-result-banner ${selectedOption?.is_correct ? 'result-victory' : 'result-defeat'}`}>
              <div className="result-icon">
                {selectedOption?.is_correct ? '🏆' : '🛡️'}
              </div>
              <div>
                <strong>
                  {selectedOption?.is_correct
                    ? `СЛАВНА ПОБЕДА! Превзехте "${activeTerritory.name}" (+${activeTerritory.points} точки)!`
                    : `НЕУСПЕШЕН ЩУРМ! Крепостта "${activeTerritory.name}" устоя на атаката.`}
                </strong>
                <p>
                  {selectedOption?.is_correct
                    ? 'Територията вече се вее под вашия флаг! Продължете настъплението.'
                    : 'Правилният отговор е маркиран със зелен печат. Изберете следващ ход!'}
                </p>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="battle-actions">
            {!submitted ? (
              <button
                className="btn-primary-action confirm-btn"
                type="button"
                onClick={handleSubmitAnswer}
                disabled={!selectedOption || loadingQuestion}
              >
                <span>ПОТВЪРДИ ЩУРМА</span> <span>⚔️</span>
              </button>
            ) : (
              <button
                className="btn-primary-action next-btn"
                type="button"
                onClick={handleNextTurn}
              >
                <span>СЛЕДВАЩА БИТКА / ХОД</span> <span>➔</span>
              </button>
            )}

            <button
              className="btn-secondary-action skip-btn"
              type="button"
              onClick={handleNextTurn}
              title="Премини към друг въпрос"
            >
              СМЕНИ ВЪПРОС ⚜️
            </button>
          </div>
        </section>
      </div>

      {/* Bottom Grid: War Chronicles & Objectives */}
      <section className="bottom-grid">
        <div className="event-panel panel-frame">
          <div className="panel-heading">
            <div className="heading-title-group">
              <span className="section-label">ХРОНИКИ НА ВОЙНАТА</span>
              <h2>ДОКЛАДИ ОТ ФРОНТА</h2>
            </div>
            <span className="live-label">
              <i className="pulse-dot" /> АКТИВНО
            </span>
          </div>
          <div className="event-log">
            {log.slice(0, 3).map((entry, index) => (
              <p className={index === 0 ? 'event-newest' : ''} key={`${entry}-${index}`}>
                <span className="log-index">#{String(index + 1).padStart(2, '0')}</span>
                <span className="log-text">{entry}</span>
              </p>
            ))}
          </div>
        </div>

        <div className="objective-panel panel-frame">
          <span className="section-label">КРАЛСКА ЗАПОВЕД</span>
          <strong className="objective-title">ПРЕВЗЕМИ 3 КРЕПОСТИ</strong>
          <div className="progress-track">
            <span
              className="progress-fill"
              style={{ width: `${Math.min((controlledCount / 3) * 100, 100)}%` }}
            />
          </div>
          <small className="objective-status">
            {controlledCount >= 3 ? '🎉 ЦЕЛТА Е ПОСТИГНАТА!' : `${controlledCount} ОТ 3 КРЕПОСТИ ПОД ВАШ КОНТРОЛ`}
          </small>
        </div>

        <button
          className="leave-button"
          type="button"
          onClick={() => {
            if (window.confirm('Желаете ли да напуснете текущата битка?')) {
              window.location.reload()
            }
          }}
        >
          НАПУСНИ БИТКАТА <span>➔</span>
        </button>
      </section>

      {/* Auth & Profile Modal */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        user={currentUser}
        initialTab={authTab}
        onAuthSuccess={(userData) => setCurrentUser(userData)}
        onLogout={() => setCurrentUser(null)}
      />
    </main>
  )
}

export default App
