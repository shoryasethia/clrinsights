# Quick Start Guide

## 1. Setup Environment

```bash
cd clrinsights
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configure API Keys

Edit `clrinsights/.env`:
```
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

## 3. Start Backend

```bash
cd clrinsights
python -m main
```

Backend runs at: http://localhost:8000

## 4. Open Frontend

Open `clrinsights/frontend/index.html` in browser

Or serve it:
```bash
cd clrinsights/frontend
npm run dev
```

Then visit: http://localhost:3000

## 5. Test Queries

Try asking:
- "What is the failure rate for each transaction type?"
- "Show me transaction trends by hour of day"
- "Which state has the most transactions?"

## Project Structure

```
InsightX-tf/
├── data/                    # CSV data only
├── problem-statement/       # PDF only
├── round1ques/             # Question files
└── clrinsights/            # Main project (with git)
    ├── agent/              # LangGraph workflow
    ├── tools/              # SQL, viz, Python tools
    ├── llm/                # Gemini & Groq clients
    ├── data/               # DuckDB manager
    ├── memory/             # Conversation history
    ├── sandbox/            # Code execution
    ├── frontend/           # Chat UI
    ├── schema.json         # CSV schema
    ├── config.py           # Settings
    └── main.py             # FastAPI app
```

## Key Features

- **Schema-driven**: No hallucination, accurate queries
- **Agentic workflow**: LangGraph plans & executes
- **Dual LLM**: Gemini primary, Groq fallback
- **Sandboxed**: Safe code execution
- **Memory**: Full conversation context
- **Clean UI**: Claude-like interface
