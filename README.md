<div align="center">
  <img src="frontend/assets/clrinsights-logo-bw.png" alt="CLRInsights Logo" width="200" height="auto" />
  <p><strong>Conversational Leadership Reports & Insights</strong></p>
  <p>An agentic approach for querying and analyzing UPI transaction data using natural language</p>
</div>

---

## Architecture

CLRInsights uses an agentic approach powered by LangGraph, enabling intelligent data analysis through natural language conversations. The system features:

- **Agentic Workflow**: LangGraph-based agent that plans queries, executes SQL, generates visualizations, and provides insights
- **Dual LLM Support**: Google Gemini (primary) and Groq (fallback) with automatic retry logic
- **Sandboxed Execution**: Safe code execution using RestrictedPython
- **Schema-Driven**: Comprehensive schema file prevents hallucination and ensures accurate queries
- **Conversation Memory**: Full context retention across chat sessions
- **Modern React UI**: Professional chat interface with React + Vite + Tailwind CSS, featuring light/dark mode, real-time execution traces, and responsive design

### Agentic Workflow

```mermaid
graph TD
    A[User Query] --> B[analyze]
    B --> C{Has SQL steps?}
    C -->|No - conversational| H[answer]
    C -->|Yes| D[prepare_step]
    D --> E[execute_sql]
    E --> F{SQL OK?}
    F -->|Error| G[fix_sql]
    G -->|retry ≤3| E
    F -->|Success| I{More steps?}
    I -->|Yes| J[advance_step]
    J --> D
    I -->|No| K[generate_viz]
    K --> H[answer]
    H --> L[END]
```

## Project Structure

```
clrinsights/
├── frontend/          # React + Vite + Tailwind chat interface
│   ├── src/
│   │   ├── components/    # React components (ChatMessage, InputArea, ExecutionTrace)
│   │   ├── App.jsx        # Main application component
│   │   ├── main.jsx       # React entry point
│   │   └── index.css      # Tailwind CSS styles
│   ├── assets/            # Static assets (logo — served as public dir)
│   ├── package.json       # Node.js dependencies
│   ├── vite.config.js     # Vite configuration
│   └── tailwind.config.js # Tailwind CSS configuration
├── agent/             # LangGraph workflow
├── tools/             # SQL, visualization, Python execution tools
├── llm/               # Gemini and Groq clients
├── data/              # DuckDB manager
├── memory/            # Conversation history
├── sandbox/           # Code execution
├── schema.json        # CSV schema definition
├── config.py          # Configuration management
└── main.py            # FastAPI backend
```

## Setup

1. Navigate to clrinsights directory and create virtual environment:
```bash
cd clrinsights
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
copy .env.example .env  # Windows
# or
cp .env.example .env  # Linux/Mac
```

Edit `.env` (copy from `.env.example`) and configure:
- **API keys** (`GEMINI_API_KEY` and `GROQ_API_KEY`) — Required
- **MongoDB** (`MONGODB_URI`) — Required (MongoDB Atlas free tier M0)
- **Model names** — All model configurations
- **CSV_PATH** — Set to `data/upi_transactions_2024.csv` (bundled in repo)
- **SCHEMA_PATH** — Path to schema.json (default: `schema.json`)
- All other settings (ports, timeouts, etc.)

## Usage

**Terminal 1 - Start Backend:**

Navigate to `clrinsights` directory and run:

```powershell
# Windows PowerShell
.venv\Scripts\activate
cd ..
uvicorn clrinsights.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
# Linux/Mac
source .venv/bin/activate
cd .. 
uvicorn clrinsights.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Start Frontend:**

From `clrinsights/frontend` directory:
```bash
npm run dev
```

**Access the application:**
- Backend API: `http://localhost:8000`
- Frontend UI: `http://localhost:3000`


### MongoDB

https://github.com/shoryasethia/clrinsights/blob/196c809873f3eb115fea9a603ba7eaf56ccfd90e/.env.example#L5-L6

### LLM Models

https://github.com/shoryasethia/clrinsights/blob/196c809873f3eb115fea9a603ba7eaf56ccfd90e/.env.example#L8-L13

### Data Paths

https://github.com/shoryasethia/clrinsights/blob/196c809873f3eb115fea9a603ba7eaf56ccfd90e/.env.example#L15-L18

### API Settings

https://github.com/shoryasethia/clrinsights/blob/196c809873f3eb115fea9a603ba7eaf56ccfd90e/.env.example#L24-L27

### Additional Settings
See `.env.example` for all available configuration options including:
- Sandbox configuration (timeouts, memory limits)
- Memory configuration (conversation history, context window)
- LLM configuration (temperature, retries, timeouts)

## How It Works

1. **User Query**: User asks question in natural language
2. **Query Analysis**: Agent analyzes intent and creates execution plan
3. **SQL Generation**: Agent generates SQL query using schema context
4. **Data Retrieval**: DuckDB executes query on CSV data
5. **Visualization**: If applicable, matplotlib generates charts
6. **Answer Generation**: LLM creates leadership-friendly response
7. **Response**: Answer with optional visualization returned to user

## Schema File

The `schema.json` file is critical for preventing hallucination. It contains:
- Complete column definitions with types and descriptions
- Valid values for categorical columns
- NULL conditions and constraints
- Query guidelines for common patterns

The agent receives this schema context with every query to ensure accurate SQL generation.

## LISCENSE

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details.

---
<p align="center">
  Built for Techfest IIT Bombay x NPCI Competition (InsightX) by team ClrInsights
</p>
