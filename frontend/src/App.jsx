import { useState } from 'react'
import './App.css'

const territories = [
  { id: 'north', name: 'NORTH', points: '180 PTS', color: 'coral', x: 22, y: 17 },
  { id: 'west', name: 'WESTLAND', points: '240 PTS', color: 'black', x: 10, y: 47 },
  { id: 'capital', name: 'CAPITAL', points: '320 PTS', color: 'yellow', x: 43, y: 43 },
  { id: 'east', name: 'EAST MARCH', points: '210 PTS', color: 'coral', x: 74, y: 34 },
  { id: 'south', name: 'SOUTH', points: '150 PTS', color: 'yellow', x: 52, y: 74 },
]

const answers = [
  'The printing press',
  'The steam engine',
  'The compass',
  'The telephone',
]

function App() {
  const [selectedAnswer, setSelectedAnswer] = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const [activeTerritory, setActiveTerritory] = useState('capital')
  const [log, setLog] = useState(['YOUR TURN: choose an answer to attack CAPITAL.'])
  const [round, setRound] = useState(4)

  const chooseAnswer = (answer) => {
    setSelectedAnswer(answer)
    setSubmitted(false)
  }

  const submitAnswer = () => {
    if (!selectedAnswer) return
    const isCorrect = selectedAnswer === answers[0]
    setSubmitted(true)
    setLog((currentLog) => [
      isCorrect ? 'CORRECT: CAPITAL is now contested.' : 'WRONG: the territory holds its ground.',
      ...currentLog,
    ])
  }

  const endTurn = () => {
    setRound((currentRound) => Math.min(currentRound + 1, 12))
    setSelectedAnswer(null)
    setSubmitted(false)
    setLog((currentLog) => ['TURN PASSED: waiting for the next move.', ...currentLog])
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <span className="brand-mark">QC</span>
          <div>
            <p className="eyebrow">MULTIPLAYER TRIVIA WAR</p>
            <h1>QUIZ<span>CONQUEST</span></h1>
          </div>
        </div>
        <div className="match-meta">
          <span>MATCH 08—A</span>
          <strong>ROUND {String(round).padStart(2, '0')} / 12</strong>
          <button className="icon-button" type="button" aria-label="Open game menu">≡</button>
        </div>
      </header>

      <section className="score-strip" aria-label="Player scores">
        <div className="player-card player-active">
          <span className="player-number">01</span>
          <div><strong>YOU</strong><small>RED COMMAND</small></div>
          <b>1,240</b>
        </div>
        <div className="player-card">
          <span className="player-number">02</span>
          <div><strong>NOAH</strong><small>BLACK COMMAND</small></div>
          <b>980</b>
        </div>
        <div className="player-card">
          <span className="player-number">03</span>
          <div><strong>MILA</strong><small>YELLOW COMMAND</small></div>
          <b>760</b>
        </div>
        <div className="turn-callout"><span className="pulse-dot" /> YOUR TURN</div>
      </section>

      <div className="game-layout">
        <section className="map-panel panel-frame">
          <div className="panel-heading">
            <div><span className="section-label">01 / TERRITORY MAP</span><h2>THE BOARD</h2></div>
            <span className="map-status">5 LIVE ZONES</span>
          </div>
          <div className="territory-map" aria-label="Territory map">
            <div className="map-grid" />
            <div className="route route-one" /><div className="route route-two" /><div className="route route-three" />
            {territories.map((territory) => (
              <button
                className={`territory territory-${territory.color} ${activeTerritory === territory.id ? 'territory-active' : ''}`}
                key={territory.id}
                type="button"
                style={{ left: `${territory.x}%`, top: `${territory.y}%` }}
                onClick={() => setActiveTerritory(territory.id)}
              >
                <span className="territory-pin" />
                <span>{territory.name}</span>
                <small>{territory.points}</small>
              </button>
            ))}
            <div className="map-coordinates">N 42° 18' / E 19° 51'</div>
          </div>
          <div className="map-footer"><span><i className="legend-dot red" /> YOUR ZONES</span><span><i className="legend-dot black" /> ENEMY ZONES</span><span><i className="legend-dot yellow" /> OPEN ZONES</span></div>
        </section>

        <section className="question-panel panel-frame">
          <div className="panel-heading question-heading">
            <div><span className="section-label">02 / ATTACK {activeTerritory.toUpperCase()}</span><h2>MAKE YOUR MOVE</h2></div>
            <div className="timer"><span>TIME</span><strong>00:18</strong></div>
          </div>
          <div className="question-card">
            <span className="question-index">QUESTION 04</span>
            <p>Which invention most directly changed the spread of knowledge in 15th-century Europe?</p>
          </div>
          <div className="answer-list" role="radiogroup" aria-label="Answers">
            {answers.map((answer, index) => (
              <button
                className={`answer-button ${selectedAnswer === answer ? 'answer-selected' : ''}`}
                key={answer}
                type="button"
                role="radio"
                aria-checked={selectedAnswer === answer}
                onClick={() => chooseAnswer(answer)}
              >
                <span className="answer-key">{String.fromCharCode(65 + index)}</span>
                <span>{answer}</span>
                <span className="answer-check">{selectedAnswer === answer ? '×' : ''}</span>
              </button>
            ))}
          </div>
          {submitted && <div className={`result-message ${selectedAnswer === answers[0] ? 'result-correct' : 'result-wrong'}`}>{selectedAnswer === answers[0] ? 'CORRECT / +320 POINTS' : 'INCORRECT / 0 POINTS'}</div>}
          <div className="question-actions">
            <button className="primary-button" type="button" onClick={submitAnswer} disabled={!selectedAnswer || submitted}>CONFIRM ANSWER <span>↗</span></button>
            <button className="secondary-button" type="button" onClick={endTurn}>END TURN</button>
          </div>
        </section>
      </div>

      <section className="bottom-grid">
        <div className="event-panel panel-frame">
          <div className="panel-heading"><div><span className="section-label">03 / LIVE FEED</span><h2>FIELD REPORT</h2></div><span className="live-label"><i className="pulse-dot" /> LIVE</span></div>
          <div className="event-log">{log.slice(0, 3).map((entry, index) => <p className={index === 0 ? 'event-new' : ''} key={`${entry}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span>{entry}</p>)}</div>
        </div>
        <div className="objective-panel panel-frame"><span className="section-label">CURRENT OBJECTIVE</span><strong>CONTROL 3 ZONES</strong><div className="progress-track"><span /></div><small>2 OF 3 CONTROLLED</small></div>
        <button className="leave-button" type="button" onClick={() => window.alert('Leave match?')}>LEAVE MATCH <span>→</span></button>
      </section>
    </main>
  )
}

export default App
