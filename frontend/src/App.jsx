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
  const [showSettings, setShowSettings] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)
  const [sessions, setSessions] = useState([])
  const [renamedSessions, setRenamedSessions] = useState(new Set())
  const [settings, setSettings] = useState(() => {
    const saved = localStorage.getItem('appSettings')
    return saved ? JSON.parse(saved) : { provider: 'groq' }
  })
  const messagesEndRef = useRef(null)

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

  // Load sessions from backend on mount
  useEffect(() => {
    const loadSessions = async () => {
      try {
        const res = await fetch(apiUrl('/api/sessions'))
        if (res.ok) {
          const data = await res.json()
          if (data.sessions && data.sessions.length > 0) {
            setSessions(data.sessions)
          }
        }
      } catch (e) {
        // Backend might not be running yet, ignore
      }
    }
    loadSessions()
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
  }

  const handleSelectSession = async (id) => {
    setSessionId(id)
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
        setSessionId(data.session_id)
        // Add to session list if not present
        setSessions(prev => {
          const exists = prev.some(s => s.id === data.session_id)
          if (!exists) {
            return [{ id: data.session_id, title: currentInput.slice(0, 50), created_at: new Date().toISOString() }, ...prev]
          }
          return prev
        })
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
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="h-screen bg-gray-100 dark:bg-[#0f0f0f] transition-colors flex flex-col overflow-hidden">
      {/* Header */}
      <header className="bg-white dark:bg-[#181818] border-b border-gray-200 dark:border-gray-900 z-20">
        <div className="px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src="/assets/clrinsights-logo.png"
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
