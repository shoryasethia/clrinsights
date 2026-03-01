import { X, Settings as SettingsIcon, Check, Eye, EyeOff, Key } from 'lucide-react'
import { useState, useEffect } from 'react'
import { apiUrl } from '../api'

function ApiKeyInput({ provider, label, maskedKey, onSaved }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState('')
  const [show, setShow] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    if (!value.trim()) return
    setSaving(true)
    try {
      const res = await fetch(apiUrl('/api/settings/keys'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, key: value.trim() })
      })
      if (res.ok) {
        setSaved(true)
        setTimeout(() => { setSaved(false); setEditing(false); setValue('') }, 1500)
        onSaved?.()
      }
    } catch { }
    setSaving(false)
  }

  if (!editing) {
    return (
      <div className="mt-2 flex items-center gap-2">
        <Key className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
        <span className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate flex-1">
          {maskedKey || 'Not configured'}
        </span>
        <button
          onClick={() => setEditing(true)}
          className="text-xs text-primary-600 dark:text-primary-400 hover:underline flex-shrink-0"
        >
          {maskedKey ? 'Change' : 'Add key'}
        </button>
      </div>
    )
  }

  return (
    <div className="mt-2 space-y-2" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <input
            type={show ? 'text' : 'password'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={`Enter ${label} API key`}
            className="w-full px-3 py-1.5 pr-8 text-sm bg-white dark:bg-[#0f0f0f] border border-gray-300 dark:border-gray-700 rounded-md text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-1 focus:ring-primary-500"
            autoFocus
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); if (e.key === 'Escape') { setEditing(false); setValue('') } }}
          />
          <button
            onClick={() => setShow(!show)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !value.trim()}
          className="px-3 py-1.5 text-sm rounded-md bg-primary-600 hover:bg-primary-700 text-white disabled:opacity-50 transition-colors flex-shrink-0"
        >
          {saved ? <Check className="w-4 h-4" /> : saving ? '...' : 'Save'}
        </button>
        <button
          onClick={() => { setEditing(false); setValue('') }}
          className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

export default function Settings({ isOpen, onClose, settings, onSettingsChange }) {
  const [maskedKeys, setMaskedKeys] = useState({ gemini: '', groq: '' })

  const loadKeys = async () => {
    try {
      const res = await fetch(apiUrl('/api/settings/keys'))
      if (res.ok) {
        const data = await res.json()
        setMaskedKeys(data)
      } else {
        console.error('[Settings] Failed to load keys:', res.status, res.statusText)
      }
    } catch (err) {
      console.error('[Settings] Error fetching keys:', err)
    }
  }

  // Eagerly load keys on mount so they are ready when dialog opens
  useEffect(() => { loadKeys() }, [])

  // Reload keys every time the dialog is opened (in case they were changed)
  useEffect(() => {
    if (isOpen) loadKeys()
  }, [isOpen])

  if (!isOpen) return null

  const handleProviderChange = (provider) => {
    onSettingsChange({ ...settings, provider })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-[#181818] rounded-lg shadow-xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-900">
          <div className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Settings</h2>
          </div>
          <button onClick={onClose} className="btn-icon p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-6">
          {/* Model Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Model Provider
            </label>
            <div className="space-y-2">
              {/* Gemini Option */}
              <div
                onClick={() => handleProviderChange('gemini')}
                className={`w-full p-3 rounded-lg border-2 transition-colors cursor-pointer ${settings.provider === 'gemini'
                    ? 'border-primary-600 bg-primary-50 dark:bg-[#222]'
                    : 'border-gray-200 dark:border-gray-900 hover:border-gray-300 dark:hover:border-gray-800'
                  }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                      <span className="text-lg font-bold text-blue-600 dark:text-blue-400">G</span>
                    </div>
                    <div className="text-left">
                      <div className="font-medium text-gray-900 dark:text-white">Google Gemini</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">Fast & accurate</div>
                    </div>
                  </div>
                  {settings.provider === 'gemini' && (
                    <Check className="w-5 h-5 text-primary-500" />
                  )}
                </div>
                <ApiKeyInput provider="gemini" label="Gemini" maskedKey={maskedKeys.gemini} onSaved={loadKeys} />
              </div>

              {/* Groq Option */}
              <div
                onClick={() => handleProviderChange('groq')}
                className={`w-full p-3 rounded-lg border-2 transition-colors cursor-pointer ${settings.provider === 'groq'
                    ? 'border-primary-600 bg-primary-50 dark:bg-[#222]'
                    : 'border-gray-200 dark:border-gray-900 hover:border-gray-300 dark:hover:border-gray-800'
                  }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                      <span className="text-lg font-bold text-purple-600 dark:text-purple-400">G</span>
                    </div>
                    <div className="text-left">
                      <div className="font-medium text-gray-900 dark:text-white">Groq</div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">Ultra-fast inference</div>
                    </div>
                  </div>
                  {settings.provider === 'groq' && (
                    <Check className="w-5 h-5 text-primary-500" />
                  )}
                </div>
                <ApiKeyInput provider="groq" label="Groq" maskedKey={maskedKeys.groq} onSaved={loadKeys} />
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-900 flex justify-end">
          <button onClick={onClose} className="btn-primary">
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
