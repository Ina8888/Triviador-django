import { useState, useEffect } from 'react'
import { questionsApi } from '../services/api'

const categoryIcons = {
  'История': '📜',
  'География': '🗺️',
  'Наука': '🧪',
  'Литература': '📖',
  'Изкуство': '🎨',
  'Спорт': '⚔️',
}

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

export default function GameView({
  matchData,
  user,
  onSaveMatch,
  onBackToLobby,
}) {
  const [territories, setTerritories] = useState(matchData.territories)
  const [score, setScore] = useState(matchData.score)
  const [round, setRound] = useState(matchData.round)
  const [activeTerritoryId, setActiveTerritoryId] = useState('capital')

  const [question, setQuestion] = useState(fallbackQuestion)
  const [selectedOption, setSelectedOption] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [loadingQuestion, setLoadingQuestion] = useState(false)
  const [battleFeedback, setBattleFeedback] = useState(null)

  const activeTerritory = territories.find((t) => t.id === activeTerritoryId) || territories[0]
  const controlledCount = territories.filter((t) => t.owner === 'player').length

  // Fetch question from Question Bank
  const loadQuestion = async () => {
    setLoadingQuestion(true)
    const res = await questionsApi.getRandom()
    setLoadingQuestion(false)
    if (res.ok && res.data) {
      setQuestion(res.data)
      setSelectedOption(null)
      setSubmitted(false)
      setBattleFeedback(null)
    }
  }

  // Load question on mount
  useEffect(() => {
    loadQuestion()
  }, [])

  // Sync state back to parent & storage
  useEffect(() => {
    onSaveMatch({
      round,
      score,
      territories,
    })
  }, [round, score, territories])

  // Select territory
  const handleSelectTerritory = (t) => {
    setActiveTerritoryId(t.id)
    if (!submitted) {
      loadQuestion()
    }
  }

  // Select answer
  const handleSelectOption = (opt) => {
    if (submitted) return
    setSelectedOption(opt)
  }

  // Submit answer
  const handleSubmit = () => {
    if (!selectedOption || submitted) return
    const isCorrect = Boolean(selectedOption.is_correct)
    setSubmitted(true)

    if (isCorrect) {
      const addedPoints = activeTerritory.points || 200
      const newScore = score + addedPoints
      setScore(newScore)

      // Capture territory
      const updatedTerritories = territories.map((t) =>
        t.id === activeTerritoryId ? { ...t, owner: 'player' } : t
      )
      setTerritories(updatedTerritories)

      setBattleFeedback({
        type: 'victory',
        title: `СЛАВНА ПОБЕДА! (+${addedPoints} т.)`,
        text: `Крепостта "${activeTerritory.name}" бе превзета от вашето знаме!`,
      })
    } else {
      setBattleFeedback({
        type: 'defeat',
        title: 'ЩУРМЪТ БЕ ОТБЛЪСНАТ!',
        text: `Защитниците на "${activeTerritory.name}" устояха на атаката. Верният отговор е маркиран със зелено.`,
      })
    }
  }

  // Next move / round
  const handleNextBattle = () => {
    setRound((r) => Math.min(r + 1, 12))
    loadQuestion()
  }

  return (
    <div className="game-screen-container">
      {/* Top Simple Battle Header */}
      <header className="game-topbar">
        <button
          type="button"
          className="medieval-btn btn-back-lobby"
          onClick={onBackToLobby}
        >
          <span>←</span> <span>МЕНЮ / ПРОФИЛ</span>
        </button>

        <div className="battle-brand-mini">
          <h2>QUIZ <span>CONQUEST</span></h2>
          <small>БОЙНО ПОЛЕ ЗА ЗЕМИТЕ</small>
        </div>

        <div className="battle-quick-stats">
          <div className="quick-stat-badge">
            <span className="badge-lbl">РУНД</span>
            <strong className="badge-val">{round} / 12</strong>
          </div>
          <div className="quick-stat-badge score-badge">
            <span className="badge-lbl">ТОЧКИ</span>
            <strong className="badge-val">{score.toLocaleString()}</strong>
          </div>
          <div className="quick-stat-badge territories-badge">
            <span className="badge-lbl">ТВОИ КРЕПОСТИ</span>
            <strong className="badge-val">{controlledCount} / 5</strong>
          </div>
        </div>
      </header>

      {/* Main Board: Map on Left, Question on Right */}
      <div className="battle-arena-grid">
        {/* LEFT: SIMPLIFIED MAP */}
        <section className="battle-card map-card">
          <div className="battle-card-header">
            <div>
              <span className="section-tag">КАРТА НА ЗЕМИТЕ</span>
              <h3>КРЕПОСТИ И ТЕРИТОРИИ</h3>
            </div>
            <div className="target-pill">
              <span>АТАКА:</span> <strong>{activeTerritory.name}</strong>
            </div>
          </div>

          <div className="arena-map">
            {/* SVG Connecting Roads */}
            <svg className="arena-routes-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
              <line x1="26" y1="22" x2="50" y2="46" className="arena-route" />
              <line x1="16" y1="52" x2="50" y2="46" className="arena-route" />
              <line x1="82" y1="36" x2="50" y2="46" className="arena-route" />
              <line x1="56" y1="78" x2="50" y2="46" className="arena-route" />
              <line x1="26" y1="22" x2="82" y2="36" className="arena-route secondary" />
              <line x1="16" y1="52" x2="56" y2="78" className="arena-route secondary" />
            </svg>

            {/* Fortresses */}
            {territories.map((t) => {
              const isSelected = activeTerritoryId === t.id
              let ownerBadge = 'СВОБОДНА'
              let ownerClass = 'neutral'
              if (t.owner === 'player') {
                ownerBadge = 'ТВОЯ'
                ownerClass = 'player'
              } else if (t.owner === 'enemy') {
                ownerBadge = 'ВРАЖЕСКА'
                ownerClass = 'enemy'
              }

              return (
                <button
                  key={t.id}
                  type="button"
                  className={`fortress-node ${ownerClass} ${isSelected ? 'active-target' : ''}`}
                  style={{ left: `${t.x}%`, top: `${t.y}%` }}
                  onClick={() => handleSelectTerritory(t)}
                  title={`Кликнете за да атакувате ${t.name}`}
                >
                  <div className="node-crest">
                    <span>{t.icon}</span>
                    <small>{ownerBadge}</small>
                  </div>
                  <strong className="node-title">{t.short}</strong>
                  <span className="node-pts">+{t.points} т.</span>
                  {isSelected && <span className="node-pulse-arrow">⚔️ ЦЕЛ</span>}
                </button>
              )
            })}
          </div>

          <div className="arena-map-legend">
            <span className="legend-entry">
              <i className="dot dot-player" /> Твои крепости ({controlledCount})
            </span>
            <span className="legend-entry">
              <i className="dot dot-enemy" /> Вражески крепости
            </span>
            <span className="legend-entry">
              <i className="dot dot-neutral" /> Свободни крепости
            </span>
          </div>
        </section>

        {/* RIGHT: SIMPLIFIED QUESTION & ANSWERS */}
        <section className="battle-card question-card">
          <div className="battle-card-header">
            <div className="cat-header-group">
              <span className="cat-badge">
                {categoryIcons[question.category] || '📜'} {question.category?.toUpperCase() || 'ОБЩА КУЛТУРА'}
              </span>
              <h3>БИТКА ЗА {activeTerritory.name}</h3>
            </div>
            <div className="pts-reward-tag">
              <span>НАГРАДА:</span> <strong>+{activeTerritory.points} т.</strong>
            </div>
          </div>

          {/* Question Text in clear scroll */}
          <div className="battle-question-box">
            <div className="q-tag">ВЪПРОС #{question.id} • ИЗБЕРЕТЕ ВЕРЕН ОТГОВОР:</div>
            <p className="q-body">{question.text}</p>
          </div>

          {/* 4 Clickable Answer Buttons */}
          <div className="battle-answers-list">
            {question.options?.map((opt, idx) => {
              const isSelected = selectedOption?.id === opt.id
              let btnClass = ''
              if (submitted) {
                if (opt.is_correct) btnClass = 'correct'
                else if (isSelected) btnClass = 'wrong'
              } else if (isSelected) {
                btnClass = 'selected'
              }

              return (
                <button
                  key={opt.id}
                  type="button"
                  disabled={submitted}
                  className={`answer-choice-btn ${btnClass}`}
                  onClick={() => handleSelectOption(opt)}
                >
                  <span className="seal-circle">{String.fromCharCode(65 + idx)}</span>
                  <span className="choice-text">{opt.text}</span>
                  <span className="status-mark">
                    {submitted && opt.is_correct && '✓'}
                    {submitted && isSelected && !opt.is_correct && '✗'}
                    {!submitted && isSelected && '•'}
                  </span>
                </button>
              )
            })}
          </div>

          {/* Feedback banner */}
          {battleFeedback && (
            <div className={`feedback-alert ${battleFeedback.type}`}>
              <div className="alert-icon">
                {battleFeedback.type === 'victory' ? '🏆' : '🛡️'}
              </div>
              <div>
                <strong>{battleFeedback.title}</strong>
                <p>{battleFeedback.text}</p>
              </div>
            </div>
          )}

          {/* Action Button */}
          <div className="arena-actions">
            {!submitted ? (
              <button
                type="button"
                className="medieval-btn btn-confirm-action"
                disabled={!selectedOption || loadingQuestion}
                onClick={handleSubmit}
              >
                <span>ПОТВЪРДИ ЩУРМА</span> <span>⚔️</span>
              </button>
            ) : (
              <button
                type="button"
                className="medieval-btn btn-next-action"
                onClick={handleNextBattle}
              >
                <span>СЛЕДВАЩА БИТКА</span> <span>➔</span>
              </button>
            )}

            <button
              type="button"
              className="medieval-btn btn-change-q"
              onClick={handleNextBattle}
              title="Зареди друг въпрос"
            >
              СМЕНИ ВЪПРОС ⚜️
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
