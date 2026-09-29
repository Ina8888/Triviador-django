import { useState, useEffect } from 'react'
import './App.css'
import { authApi } from './services/api'
import AuthView from './components/AuthView'
import LobbyView from './components/LobbyView'
import GameView from './components/GameView'

const DEFAULT_TERRITORIES = [
  { id: 'north', name: 'СЕВЕРНА СТРАЖА', short: 'СЕВЕР', icon: '⚔️', points: 180, owner: 'player', x: 26, y: 22 },
  { id: 'west', name: 'ЗАПАДЕН БАСТИОН', short: 'ЗАПАД', icon: '🛡️', points: 240, owner: 'enemy', x: 16, y: 52 },
  { id: 'capital', name: 'КРАЛСКА ЦИТАДЕЛА', short: 'СТОЛИЦА', icon: '🏰', points: 320, owner: 'neutral', x: 50, y: 46 },
  { id: 'east', name: 'ИЗТОЧНА КУЛА', short: 'ИЗТОК', icon: '🏹', points: 210, owner: 'player', x: 82, y: 36 },
  { id: 'south', name: 'ЮЖНА КРЕПОСТ', short: 'ЮГ', icon: '⚜️', points: 150, owner: 'neutral', x: 56, y: 78 },
]

const MATCH_STORAGE_KEY = 'quiz_conquest_saved_match'

function createInitialMatch() {
  return {
    round: 1,
    score: 1240,
    territories: DEFAULT_TERRITORIES,
  }
}

export default function App() {
  const [currentUser, setCurrentUser] = useState(null)
  const [initializing, setInitializing] = useState(true)
  const [currentView, setCurrentView] = useState('auth') // 'auth' | 'lobby' | 'game'
  const [savedMatch, setSavedMatch] = useState(null)
  const [matchData, setMatchData] = useState(null)

  // Load saved match from localStorage and check active session
  useEffect(() => {
    // 1. Read existing saved match if any
    try {
      const stored = localStorage.getItem(MATCH_STORAGE_KEY)
      if (stored) {
        setSavedMatch(JSON.parse(stored))
      }
    } catch {
      console.warn('Could not read saved match from localStorage')
    }

    // 2. Check session with Django backend
    authApi
      .getMe()
      .then((res) => {
        if (res.ok && res.data) {
          setCurrentUser(res.data)
          setCurrentView('lobby')
        } else {
          setCurrentUser(null)
          setCurrentView('auth')
        }
      })
      .catch(() => {
        setCurrentView('auth')
      })
      .finally(() => {
        setInitializing(false)
      })
  }, [])

  // User logged in / registered successfully
  const handleAuthSuccess = (userData) => {
    setCurrentUser(userData)
    setCurrentView('lobby')
  }

  // Logout
  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore
    }
    setCurrentUser(null)
    setCurrentView('auth')
  }

  // Update profile in memory
  const handleUserUpdate = (updatedUser) => {
    setCurrentUser(updatedUser)
  }

  // Start fresh match
  const handleStartNewMatch = () => {
    const fresh = createInitialMatch()
    setMatchData(fresh)
    setSavedMatch(fresh)
    localStorage.setItem(MATCH_STORAGE_KEY, JSON.stringify(fresh))
    setCurrentView('game')
  }

  // Resume old match
  const handleResumeMatch = () => {
    if (savedMatch) {
      setMatchData(savedMatch)
      setCurrentView('game')
    } else {
      handleStartNewMatch()
    }
  }

  // Save current progress during gameplay
  const handleSaveMatch = (updated) => {
    setMatchData(updated)
    setSavedMatch(updated)
    try {
      localStorage.setItem(MATCH_STORAGE_KEY, JSON.stringify(updated))
    } catch {
      // ignore
    }
  }

  // Return to Lobby/Profile from Battle
  const handleBackToLobby = () => {
    setCurrentView('lobby')
  }

  if (initializing) {
    return (
      <main className="app-shell loading-shell">
        <div className="init-spinner-box">
          <div className="crest-spin">⚜️</div>
          <h2>QUIZ CONQUEST</h2>
          <p>Зареждане на кралските архиви...</p>
        </div>
      </main>
    )
  }

  return (
    <main className="app-shell medieval-theme">
      {currentView === 'auth' && (
        <AuthView onAuthSuccess={handleAuthSuccess} />
      )}

      {currentView === 'lobby' && (
        <LobbyView
          user={currentUser}
          savedMatch={savedMatch}
          onStartNewMatch={handleStartNewMatch}
          onResumeMatch={handleResumeMatch}
          onUserUpdate={handleUserUpdate}
          onLogout={handleLogout}
        />
      )}

      {currentView === 'game' && matchData && (
        <GameView
          matchData={matchData}
          user={currentUser}
          onSaveMatch={handleSaveMatch}
          onBackToLobby={handleBackToLobby}
        />
      )}
    </main>
  )
}
