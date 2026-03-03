import { useState, useEffect, useRef } from 'react'
import { Moon, Sun, Settings as SettingsIcon, Menu } from 'lucide-react'
import ChatMessage from './components/ChatMessage'
import InputArea from './components/InputArea'
import Settings from './components/Settings'
import SessionPanel from './components/SessionPanel'
import { apiUrl } from './api'

function App() {
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : false
  })
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)

  const sessionIdRef = useRef(sessionId)
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  const [showSettings, setShowSettings] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)
  const [sessions, setSessions] = useState([])
  const [renamedSessions, setRenamedSessions] = useState(new Set())
  const [settings, setSettings] = useState(() => {
    const saved = localStorage.getItem('appSettings')
    return saved ? JSON.parse(saved) : { provider: 'groq' }
  })
  const messagesEndRef = useRef(null)
  const [backendWaking, setBackendWaking] = useState(false)
  const [wakingSecs, setWakingSecs] = useState(0)
  const [appInitializing, setAppInitializing] = useState(true)
  const wakeTimerRef = useRef(null)
  const wakeIntervalRef = useRef(null)

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
  }, [darkMode])

  useEffect(() => {
    localStorage.setItem('appSettings', JSON.stringify(settings))
  }, [settings])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startWakeDetector = () => {
    wakeTimerRef.current = setTimeout(() => {
      setBackendWaking(true)
      setWakingSecs(0)
      wakeIntervalRef.current = setInterval(() => {
        setWakingSecs(s => s + 1)
      }, 1000)
    }, 2000)
  }

  const stopWakeDetector = () => {
    clearTimeout(wakeTimerRef.current)
    clearInterval(wakeIntervalRef.current)
    setBackendWaking(false)
    setWakingSecs(0)
  }

  // Load sessions from backend on mount
  useEffect(() => {
    const initApp = async () => {
      // Check if backend is already awake via a timed health ping
      let backendAlive = false
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 3000)
      try {
        const healthRes = await fetch(apiUrl('/health'), { signal: controller.signal })
        if (healthRes.ok) backendAlive = true
      } catch (_) {
        // Health check timed out or failed — backend is likely cold-starting
      } finally {
        clearTimeout(timeout)
      }

      if (!backendAlive) {
        startWakeDetector()
      }

      try {
        const res = await fetch(apiUrl('/api/sessions'))
        stopWakeDetector()
        if (res.ok) {
          const data = await res.json()
          if (data.sessions && data.sessions.length > 0) {
            setSessions(data.sessions)
          }
        }
      } catch (e) {
        stopWakeDetector()
        // Backend might not be running yet, ignore
      } finally {
        setAppInitializing(false)
      }
    }
    initApp()
  }, [])

  const handleNewSession = () => {
    const newSession = {
      id: Date.now().toString(),
      title: 'New Conversation',
      created_at: new Date().toISOString()
    }
    setSessions(prev => [newSession, ...prev])
    setSessionId(newSession.id)
    setMessages([])
    setLoading(false)
  }

  const handleSelectSession = async (id) => {
    setSessionId(id)
    setLoading(false)
    // Load messages from backend
    try {
      const res = await fetch(apiUrl(`/api/sessions/${id}/history`))
      if (res.ok) {
        const data = await res.json()
        setMessages(data.messages || [])
      } else {
        setMessages([])
      }
    } catch (err) {
      console.error('[Sessions] Failed to load history:', err)
      setMessages([])
    }
  }

  const handleDeleteSession = async (id) => {
    // Delete from backend (removes folder)
    try {
      await fetch(apiUrl(`/api/sessions/${id}`), { method: 'DELETE' })
    } catch (err) {
      console.error('[Sessions] Failed to delete session:', err)
    }

    setSessions(prev => prev.filter(s => s.id !== id))
    if (sessionId === id) {
      const remaining = sessions.filter(s => s.id !== id)
      if (remaining.length > 0) {
        handleSelectSession(remaining[0].id)
      } else {
        handleNewSession()
      }
    }
  }

  const handleRenameSession = async (id, newTitle) => {
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title: newTitle } : s))
    setRenamedSessions(prev => new Set(prev).add(id))
    // Persist to backend
    try {
      await fetch(apiUrl(`/api/sessions/${id}/title`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      })
    } catch (err) {
      console.error('[Sessions] Failed to rename session:', err)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage = { role: 'user', content: input }
    const currentInput = input
    const startingSessionId = sessionId
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    // Auto-name session from first message (only if not manually renamed)
    if (messages.length === 0 && sessionId && !renamedSessions.has(sessionId)) {
      const title = currentInput.slice(0, 50) + (currentInput.length > 50 ? '...' : '')
      setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, title } : s))
      // Persist but don't mark as user-renamed
      try {
        await fetch(apiUrl(`/api/sessions/${sessionId}/title`), {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title })
        })
      } catch (err) {
        console.error('[Sessions] Failed to auto-name session:', err)
      }
    }

    try {
      const response = await fetch(apiUrl('/api/chat'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: currentInput,
          session_id: sessionId,
          provider: settings.provider
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      if (data.session_id) {
        // Add to session list if not present
        setSessions(prev => {
          const exists = prev.some(s => s.id === data.session_id)
          if (!exists) {
            return [{ id: data.session_id, title: currentInput.slice(0, 50), created_at: new Date().toISOString() }, ...prev]
          }
          return prev
        })

        if (sessionIdRef.current === startingSessionId) {
          setSessionId(data.session_id)
        }
      }

      if (sessionIdRef.current !== startingSessionId) {
        return;
      }

      // Trace is already built by the backend in frontend-friendly format
      const assistantMessage = {
        role: 'assistant',
        content: data.answer,
        visualizations: data.visualizations || [],
        visualization: data.visualization,
        error: data.error,
        trace: data.trace || []
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('[Chat] Request failed:', error)
      if (sessionIdRef.current !== startingSessionId) return

      const userFriendly = error.message?.includes('Failed to fetch')
        ? 'Could not connect to server. Is the backend running?'
        : error.message?.includes('API Key')
          ? 'API key issue — check your keys in Settings.'
          : `Failed to process query: ${error.message}`
      const errorMessage = {
        role: 'assistant',
        content: '',
        error: userFriendly
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      if (sessionIdRef.current === startingSessionId) {
        setLoading(false)
      }
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (appInitializing) {
    return (
      <div className="h-screen w-screen bg-gray-100 dark:bg-[#0f0f0f] flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center max-w-sm text-center">
          <img src="/clrinsights-logo.png" alt="CLRInsights" className="h-16 w-auto rounded-xl mb-8 animate-pulse shadow-sm" />

          <div className="flex gap-2 mb-6">
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce"></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
            <div className="w-3 h-3 bg-primary-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
          </div>

          <h2 className="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-2">
            Loading CLRInsights...
          </h2>

          {backendWaking && (
            <div className="mt-4 p-4 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg text-amber-800 dark:text-amber-300 w-full animate-in fade-in slide-in-from-bottom-4 transition-all duration-300">
              <div className="flex items-center gap-3 mb-2">
                <div className="relative flex-shrink-0">
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping absolute" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                </div>
                <span className="font-semibold text-sm">Waking up backend server</span>
                <span className="ml-auto font-mono text-xs font-bold">{wakingSecs}s</span>
              </div>
              <p className="text-xs text-amber-700/80 dark:text-amber-400/80 text-left">
                The free tier sleeps after 15 minutes of inactivity. Please wait ~1-2 mins for it to start.
              </p>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-100 dark:bg-[#0f0f0f] transition-colors flex flex-col overflow-hidden">
      {/* Render cold-start waking banner */}
      {backendWaking && (
        <div className="bg-amber-50 dark:bg-amber-950/40 border-b border-amber-300 dark:border-amber-700 px-4 py-2.5 flex items-center gap-3 z-30">
          <div className="relative flex-shrink-0">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping absolute" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold text-amber-800 dark:text-amber-300">Backend is waking up…</span>
            <span className="text-xs text-amber-700 dark:text-amber-400 ml-2">Free tier sleeps after 15 min of inactivity. Please wait 30–50s.</span>
          </div>
          <span className="text-sm font-mono font-bold text-amber-700 dark:text-amber-300 flex-shrink-0 bg-amber-100 dark:bg-amber-900/50 px-2 py-0.5 rounded">
            {wakingSecs}s
          </span>
        </div>
      )}
      {/* Header */}
      <header className="bg-white dark:bg-[#181818] border-b border-gray-200 dark:border-gray-900 z-20">
        <div className="px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src="/clrinsights-logo.png"
              alt="CLRInsights"
              className="h-10 w-auto rounded-lg"
            />
            {!showSidebar && (
              <button
                onClick={() => setShowSidebar(true)}
                className="btn-icon"
                title="Show sidebar"
              >
                <Menu className="w-5 h-5" />
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSettings(true)}
              className="btn-icon"
              title="Settings"
            >
              <SettingsIcon className="w-5 h-5" />
            </button>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="btn-icon"
              title="Toggle dark mode"
            >
              {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Session Sidebar */}
        {showSidebar && (
          <SessionPanel
            sessions={sessions}
            currentSessionId={sessionId}
            onSelectSession={handleSelectSession}
            onDeleteSession={handleDeleteSession}
            onRenameSession={handleRenameSession}
            onNewSession={handleNewSession}
            onClose={() => setShowSidebar(false)}
          />
        )}

        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0 relative">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto scrollbar-hidden p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full text-gray-500 dark:text-gray-400">
                <div className="text-center max-w-md">
                  <h2 className="text-2xl font-semibold mb-2">Start a conversation</h2>
                  <p>Ask questions about UPI transaction data</p>
                </div>
              </div>
            )}
            {messages.map((message, index) => (
              <ChatMessage key={index} message={message} />
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-800 flex items-center justify-center">
                  <div className="w-2 h-2 bg-primary-500 rounded-full animate-pulse"></div>
                </div>
                <div className="flex-1 px-4 py-3 rounded-lg bg-gray-50 dark:bg-[#181818]">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-gray-200 dark:border-gray-900">
            <InputArea
              input={input}
              setInput={setInput}
              loading={loading}
              onSend={sendMessage}
              onKeyDown={handleKeyDown}
            />
          </div>

        </div>
      </div>

      {/* Settings Modal */}
      <Settings
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        settings={settings}
        onSettingsChange={setSettings}
      />
    </div>
  )
}

export default App
