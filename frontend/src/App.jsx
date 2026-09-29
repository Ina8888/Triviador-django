import { useState, useEffect } from 'react'
import './App.css'
import AuthModal from './components/AuthModal'
import { authApi, questionsApi } from './services/api'

const territories = [
  { id: 'north', name: 'СЕВЕР', points: '180 Т.', color: 'coral', x: 22, y: 17 },
  { id: 'west', name: 'ЗАПАД', points: '240 Т.', color: 'black', x: 10, y: 47 },
  { id: 'capital', name: 'СТОЛИЦА', points: '320 Т.', color: 'yellow', x: 43, y: 43 },
  { id: 'east', name: 'ИЗТОК', points: '210 Т.', color: 'coral', x: 74, y: 34 },
  { id: 'south', name: 'ЮГ', points: '150 Т.', color: 'yellow', x: 52, y: 74 },
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

function App() {
  const [selectedOption, setSelectedOption] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [activeTerritory, setActiveTerritory] = useState('capital')
  const [log, setLog] = useState(['ВАШ РЕД: Изберете територия и отговорете на въпроса.'])
  const [round, setRound] = useState(1)
  const [score, setScore] = useState(1240)

  // Dynamic question state
  const [question, setQuestion] = useState(fallbackQuestion)
  const [loadingQuestion, setLoadingQuestion] = useState(false)

  // Authentication state
  const [currentUser, setCurrentUser] = useState(null)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const [authTab, setAuthTab] = useState('login')

  // Fetch question from question bank
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

  // Check existing session and fetch initial question on mount
  useEffect(() => {
    authApi.getMe().then((res) => {
      if (res.ok && res.data) {
        setCurrentUser(res.data)
      }
    })
    fetchRandomQuestion()
  }, [])

  const chooseOption = (option) => {
    if (submitted) return
    setSelectedOption(option)
  }

  const submitAnswer = () => {
    if (!selectedOption || submitted) return
    const isCorrect = Boolean(selectedOption.is_correct)
    setSubmitted(true)

    if (isCorrect) {
      setScore((s) => s + 320)
      setLog((currentLog) => [
        `ВЕРЕН ОТГОВОР (+320 т.): Атаката към ${territories.find((t) => t.id === activeTerritory)?.name || 'територията'} бе успешна!`,
        ...currentLog,
      ])
    } else {
      setLog((currentLog) => [
        `ГРЕШЕН ОТГОВОР: Територията устоя на щурма.`,
        ...currentLog,
      ])
    }
  }

  const endTurn = () => {
    setRound((currentRound) => Math.min(currentRound + 1, 12))
    setSelectedOption(null)
    setSubmitted(false)
    setLog((currentLog) => ['НОВ РУНД: Зареждане на ново бойно поле...', ...currentLog])
    fetchRandomQuestion()
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <span className="brand-mark">QC</span>
          <div>
            <p className="eyebrow">ИНТЕРАКТИВНА ТРИВИА ВОЙНА</p>
            <h1>QUIZ<span>CONQUEST</span></h1>
          </div>
        </div>

        <div className="auth-header-actions">
          {currentUser ? (
            <button
              type="button"
              className="user-pill-btn"
              onClick={() => {
                setAuthTab('profile')
                setIsAuthOpen(true)
              }}
            >
              <span className="user-pill-avatar">
                {avatarIcons[currentUser.profile?.avatar_key] || '🛡️'}
              </span>
              <span className="user-pill-name">
                {currentUser.profile?.nickname || currentUser.username}
              </span>
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
              ВХОД / РЕГИСТРАЦИЯ <span>↗</span>
            </button>
          )}
        </div>

        <div className="match-meta">
          <span>БИТКА #01</span>
          <strong>РУНД {String(round).padStart(2, '0')} / 12</strong>
          <button
            className="icon-button"
            type="button"
            aria-label="Отвори профил"
            onClick={() => {
              setAuthTab(currentUser ? 'profile' : 'login')
              setIsAuthOpen(true)
            }}
          >
            ≡
          </button>
        </div>
      </header>

      <section className="score-strip" aria-label="Точки на играчите">
        <div
          className="player-card player-active"
          style={{ cursor: 'pointer' }}
          onClick={() => {
            setAuthTab(currentUser ? 'profile' : 'login')
            setIsAuthOpen(true)
          }}
        >
          <span className="player-number">
            {currentUser?.profile?.avatar_key
              ? avatarIcons[currentUser.profile.avatar_key]
              : '01'}
          </span>
          <div>
            <strong>
              {currentUser?.profile?.nickname ? currentUser.profile.nickname : 'ТИ (YOU)'}
            </strong>
            <small>
              {currentUser ? `@${currentUser.username}` : 'ЧЕРВЕНО КОМАНДВАНЕ'}
            </small>
          </div>
          <b>{score.toLocaleString()}</b>
        </div>
        <div className="player-card">
          <span className="player-number">02</span>
          <div><strong>КАЛОЯН</strong><small>ЧЕРНО КОМАНДВАНЕ</small></div>
          <b>980</b>
        </div>
        <div className="player-card">
          <span className="player-number">03</span>
          <div><strong>РАДА</strong><small>ЖЪЛТО КОМАНДВАНЕ</small></div>
          <b>760</b>
        </div>
        <div className="turn-callout"><span className="pulse-dot" /> ТВОЙ РЕД</div>
      </section>

      <div className="game-layout">
        <section className="map-panel panel-frame">
          <div className="panel-heading">
            <div><span className="section-label">01 / КАРТА НА ТЕРИТОРИИТЕ</span><h2>БОЙНОТО ПОЛЕ</h2></div>
            <span className="map-status">5 АКТИВНИ ЗОНИ</span>
          </div>
          <div className="territory-map" aria-label="Карта">
            <div className="map-grid" />
            <div className="route route-one" /><div className="route route-two" /><div className="route route-three" />
            {territories.map((territory) => (
              <button
                className={`territory territory-${territory.color} ${activeTerritory === territory.id ? 'territory-active' : ''}`}
                key={territory.id}
                type="button"
                style={{ left: `${territory.x}%`, top: `${territory.y}%` }}
                onClick={() => {
                  setActiveTerritory(territory.id)
                  fetchRandomQuestion()
                }}
              >
                <span className="territory-pin" />
                <span>{territory.name}</span>
                <small>{territory.points}</small>
              </button>
            ))}
            <div className="map-coordinates">N 42° 18' / E 19° 51'</div>
          </div>
          <div className="map-footer">
            <span><i className="legend-dot red" /> ТВОИ ЗОНИ</span>
            <span><i className="legend-dot black" /> ВРАЖЕСКИ ЗОНИ</span>
            <span><i className="legend-dot yellow" /> СВОБОДНИ ЗОНИ</span>
          </div>
        </section>

        <section className="question-panel panel-frame">
          <div className="panel-heading question-heading">
            <div>
              <span className="section-label">
                02 / АТАКА: {territories.find((t) => t.id === activeTerritory)?.name || 'ТЕРИТОРИЯ'} | КАТЕГОРИЯ: {question.category?.toUpperCase()}
              </span>
              <h2>НАПРАВИ ХОД</h2>
            </div>
            <div className="timer">
              <span>ВРЕМЕ</span>
              <strong>00:25</strong>
            </div>
          </div>

          <div className="question-card">
            <span className="question-index">
              ВЪПРОС #{question.id} [{question.category}]
            </span>
            <p>{question.text}</p>
          </div>

          <div className="answer-list" role="radiogroup" aria-label="Отговори">
            {question.options?.map((option, index) => (
              <button
                className={`answer-button ${selectedOption?.id === option.id ? 'answer-selected' : ''}`}
                key={option.id}
                type="button"
                role="radio"
                aria-checked={selectedOption?.id === option.id}
                onClick={() => chooseOption(option)}
              >
                <span className="answer-key">{String.fromCharCode(65 + index)}</span>
                <span>{option.text}</span>
                <span className="answer-check">{selectedOption?.id === option.id ? '✓' : ''}</span>
              </button>
            ))}
          </div>

          {submitted && (
            <div className={`result-message ${selectedOption?.is_correct ? 'result-correct' : 'result-wrong'}`}>
              {selectedOption?.is_correct ? 'ПРАВИЛЕН ОТГОВОР / +320 ТОЧКИ' : 'ГРЕШЕН ОТГОВОР / 0 ТОЧКИ'}
            </div>
          )}

          <div className="question-actions">
            {!submitted ? (
              <button
                className="primary-button"
                type="button"
                onClick={submitAnswer}
                disabled={!selectedOption || loadingQuestion}
              >
                ПОТВЪРДИ ОТГОВОРА <span>↗</span>
              </button>
            ) : (
              <button
                className="primary-button"
                type="button"
                onClick={endTurn}
              >
                СЛЕДВАЩ ВЪПРОС / ХОД <span>→</span>
              </button>
            )}
            <button className="secondary-button" type="button" onClick={endTurn}>
              ПРЕМИНИ РУНД
            </button>
          </div>
        </section>
      </div>

      <section className="bottom-grid">
        <div className="event-panel panel-frame">
          <div className="panel-heading">
            <div><span className="section-label">03 / БОЙНИ ДЕЙСТВИЯ</span><h2>ДОКЛАД ОТ ФРОНТА</h2></div>
            <span className="live-label"><i className="pulse-dot" /> НА ЖИВО</span>
          </div>
          <div className="event-log">
            {log.slice(0, 3).map((entry, index) => (
              <p className={index === 0 ? 'event-new' : ''} key={`${entry}-${index}`}>
                <span>{String(index + 1).padStart(2, '0')}</span>{entry}
              </p>
            ))}
          </div>
        </div>
        <div className="objective-panel panel-frame">
          <span className="section-label">ТЕКУЩА ЦЕЛ</span>
          <strong>КОНТРОЛИРАЙ 3 ЗОНИ</strong>
          <div className="progress-track"><span /></div>
          <small>2 ОТ 3 ОВЛАДЕНИ</small>
        </div>
        <button className="leave-button" type="button" onClick={() => window.alert('Напускане на битката?')}>
          ИЗХОД ОТ ИГРАТА <span>→</span>
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
