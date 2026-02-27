import { Send } from 'lucide-react'

export default function InputArea({ input, setInput, loading, onSend, onKeyDown }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="bg-white dark:bg-[#181818] rounded-lg border border-gray-200 dark:border-gray-900 p-3 flex gap-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question about your data..."
          rows="2"
          disabled={loading}
          className="flex-1 bg-transparent border-none focus:outline-none resize-none text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
        />
        <button
          onClick={onSend}
          disabled={loading || !input.trim()}
          className="btn-primary h-10 px-4 self-end"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
      <p className="flex items-center justify-center gap-1.5 text-xs text-gray-400 dark:text-gray-500 select-none">
        <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        clrInsights is an AI. AI can make mistakes, so double-check outputs.
      </p>
    </div>
  )
}
