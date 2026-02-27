import { useState } from 'react'
import { User, Bot, AlertCircle, Maximize2, Terminal, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react'
import ImageViewer from './ImageViewer'

function TraceCopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { }
  }
  return (
    <button onClick={copy} className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors" title={copied ? 'Copied!' : 'Copy'}>
      {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
    </button>
  )
}

function TraceSection({ steps }) {
  const [expandedSteps, setExpandedSteps] = useState(new Set())

  const toggleStep = (i) => {
    const s = new Set(expandedSteps)
    s.has(i) ? s.delete(i) : s.add(i)
    setExpandedSteps(s)
  }

  return (
    <div className="space-y-1.5">
      {steps.map((step, i) => (
        <div key={i} className="bg-gray-100 dark:bg-[#0f0f0f] rounded border border-gray-200 dark:border-gray-800 overflow-hidden">
          <div
            onClick={() => step.prompt && toggleStep(i)}
            className={`px-3 py-2 flex items-start gap-2 ${step.prompt ? 'cursor-pointer hover:bg-gray-200 dark:hover:bg-[#181818]' : ''}`}
          >
            {step.prompt && (
              expandedSteps.has(i)
                ? <ChevronDown className="w-3.5 h-3.5 text-gray-500 mt-0.5 flex-shrink-0" />
                : <ChevronRight className="w-3.5 h-3.5 text-gray-500 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <div className="text-xs text-gray-600 dark:text-gray-400 leading-snug">{step.text || step.step}</div>
              {step.type && (
                <span className={`inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] leading-none ${step.type === 'prompt' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' :
                  step.type === 'response' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                    step.type === 'sql' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400' :
                      step.type === 'error' ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' :
                        'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                  }`}>
                  {step.type}
                </span>
              )}
            </div>
          </div>
          {expandedSteps.has(i) && step.prompt && (
            <div className="border-t border-gray-200 dark:border-gray-700 px-3 py-2 space-y-2">
              <div>
                <div className="flex items-center justify-between mb-0.5">
                  <div className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">
                    {step.type === 'sql' ? 'SQL Query' : 'Prompt'}
                  </div>
                  <TraceCopyBtn text={step.prompt} />
                </div>
                <pre className="text-xs font-mono bg-white dark:bg-gray-950 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-96 overflow-auto text-gray-800 dark:text-gray-300 whitespace-pre-wrap break-words">
                  <code>{step.prompt}</code>
                </pre>
              </div>
              {step.response && (
                <div>
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="text-[10px] font-semibold text-gray-500 dark:text-gray-400 uppercase">Response</div>
                    <TraceCopyBtn text={step.response} />
                  </div>
                  <pre className="text-xs font-mono bg-white dark:bg-gray-950 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-96 overflow-auto text-gray-800 dark:text-gray-300 whitespace-pre-wrap break-words">
                    <code>{step.response}</code>
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

export default function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const [viewerIndex, setViewerIndex] = useState(null)
  const [showTrace, setShowTrace] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('Copy failed', e)
    }
  }

  // Support both single visualization and array of visualizations
  const visualizations = message.visualizations && message.visualizations.length > 0
    ? message.visualizations
    : message.visualization
      ? [message.visualization]
      : []

  return (
    <div className={`flex gap-3 ${isUser ? 'message-user' : 'message-assistant'}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${isUser
        ? 'bg-primary-700 text-white'
        : 'bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
        }`}>
        {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
      </div>

      {/* Message Content */}
      <div className="flex-1 min-w-0 group/msg">
        <div className={`message-content relative ${isUser ? 'bg-primary-50 dark:bg-[#1a1a2e]' : 'bg-gray-50 dark:bg-[#141414]'}`}>
          {/* Copy button — visible on hover */}
          {message.content && (
            <button
              onClick={handleCopy}
              className="absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover/msg:opacity-100 transition-opacity bg-gray-200/80 dark:bg-gray-700/80 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300"
              title={copied ? 'Copied!' : 'Copy message'}
            >
              {copied
                ? <Check className="w-3.5 h-3.5 text-green-500" />
                : <Copy className="w-3.5 h-3.5" />
              }
            </button>
          )}

          {/* Per-message trace toggle — above response */}
          {!isUser && message.trace && message.trace.length > 0 && (
            <div className="mb-2">
              <button
                onClick={() => setShowTrace(!showTrace)}
                className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>{showTrace ? 'Hide' : 'Show'} trace ({message.trace.length} steps)</span>
                {showTrace ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
              {showTrace && (
                <div className="mt-2">
                  <TraceSection steps={message.trace} />
                </div>
              )}
            </div>
          )}

          {message.content && (
            <div className="prose dark:prose-invert max-w-none">
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          )}

          {/* Visualizations as tiles */}
          {visualizations.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-3">
              {visualizations.map((viz, idx) => {
                const imgSrc = `data:image/png;base64,${viz}`
                return (
                  <div
                    key={idx}
                    className="group relative rounded-lg overflow-hidden bg-white border border-gray-200 dark:border-gray-700 cursor-pointer hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
                    style={{ width: visualizations.length === 1 ? 'clamp(160px, 50%, 360px)' : 'clamp(140px, 45%, 280px)' }}
                    onClick={() => setViewerIndex(idx)}
                  >
                    <img
                      src={imgSrc}
                      alt={`Chart ${idx + 1}`}
                      className="w-full h-auto block"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 rounded-full p-2">
                        <Maximize2 className="w-5 h-5 text-white" />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Error */}
          {message.error && (
            <div className="mt-3 flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <span className="text-sm">{message.error}</span>
            </div>
          )}

        </div>
      </div>

      {/* Full-screen image viewer */}
      {viewerIndex !== null && (
        <ImageViewer
          images={visualizations.map(v => `data:image/png;base64,${v}`)}
          currentIndex={viewerIndex}
          onNavigate={setViewerIndex}
          alt="Chart"
          onClose={() => setViewerIndex(null)}
        />
      )}
    </div>
  )
}
