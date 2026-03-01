import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from clrinsights.config import settings
from clrinsights.agent import run_agent
from clrinsights.memory import get_or_create_session, list_all_sessions, delete_session


app = FastAPI(title="CLRInsights API", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Chat request model."""
    query: str
    session_id: Optional[str] = None
    provider: Optional[str] = "groq"


class ChatResponse(BaseModel):
    """Chat response model."""
    answer: str
    visualizations: Optional[List[str]] = None
    sql_queries: Optional[List[str]] = None
    visualization: Optional[str] = None  # backward compat (first viz)
    sql_query: Optional[str] = None  # backward compat (first query)
    session_id: str
    error: Optional[str] = None
    trace: Optional[List[Dict]] = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process chat query and return answer.
    
    Args:
        request: Chat request with query and optional session_id
        
    Returns:
        Chat response with answer and metadata
    """
    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())
    history = await get_or_create_session(session_id)
    
    # Add user message to history
    await history.add_message("user", request.query)
    
    try:
        # Run agent
        result = await run_agent(
            query=request.query,
            conversation_history=history.get_messages(),
            provider=request.provider
        )
        
        # Build frontend-friendly trace
        raw_trace = result.get('trace', [])
        frontend_trace = []
        for t in raw_trace:
            frontend_trace.append({
                'text': t.get('step', ''),
                'type': t.get('type'),
                'prompt': t.get('prompt'),
                'response': t.get('response'),
            })
        
        sql_queries = result.get('sql_queries', [])
        if sql_queries:
            for i, sq in enumerate(sql_queries):
                frontend_trace.append({
                    'text': f"SQL Query{f' (Step {i+1})' if len(sql_queries) > 1 else ''}: {sq}",
                    'type': 'sql',
                    'prompt': sq,
                })
        
        vizs = result.get('visualizations', [])
        frontend_trace.append({
            'text': f"Response generated ({len(vizs)} chart{'s' if len(vizs) != 1 else ''})",
            'type': 'response',
        })
        
        # Add assistant response to history (with visualizations + trace)
        if result['answer']:
            await history.add_message(
                "assistant",
                result['answer'],
                visualizations=result.get('visualizations', []),
                trace=frontend_trace,
                error=result.get('error'),
                sql_queries=sql_queries
            )
        
        # Auto-save trace, visualizations, and response to session folder
        await history.save_response(result)
        
        return ChatResponse(
            answer=result['answer'],
            visualizations=result.get('visualizations', []),
            sql_queries=sql_queries,
            visualization=result.get('visualization'),
            sql_query=result.get('sql_query'),
            session_id=session_id,
            error=result.get('error'),
            trace=frontend_trace
        )
    
    except Exception as e:
        error_msg = str(e)
        status_code = 500
        
        # Categorize errors for user-friendly messages
        if "API key" in error_msg or "INVALID_ARGUMENT" in error_msg or "API_KEY_INVALID" in error_msg:
            error_msg = "Invalid API key. Please update your key in Settings."
            status_code = 401
        elif "rate" in error_msg.lower() and "limit" in error_msg.lower():
            error_msg = "Rate limit reached. Please wait a moment and try again."
            status_code = 429
        elif "quota" in error_msg.lower():
            error_msg = "API quota exceeded. Check your plan or try a different provider in Settings."
            status_code = 429
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            error_msg = "Request timed out. Try a simpler query or try again."
            status_code = 504
        elif "Could not parse" in error_msg or "JSONDecodeError" in error_msg:
            error_msg = "The AI returned an unexpected response. Please try rephrasing your question."
            status_code = 500
        elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
            error_msg = "Could not connect to the AI provider. Check your internet connection."
            status_code = 502
        
        raise HTTPException(status_code=status_code, detail=error_msg)


@app.get("/sessions")
async def get_sessions():
    """List all saved sessions."""
    return {"sessions": await list_all_sessions()}


@app.get("/sessions/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for session."""
    history = await get_or_create_session(session_id)
    return {"messages": history.get_messages()}


@app.put("/sessions/{session_id}/title")
async def rename_session(session_id: str, body: dict):
    """Rename a session."""
    title = body.get("title", "Untitled")
    history = await get_or_create_session(session_id)
    await history.set_title(title)
    return {"status": "renamed", "title": title}


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Delete session and its folder entirely."""
    await delete_session(session_id)
    return {"status": "deleted"}


@app.put("/settings/keys")
async def update_keys(body: dict):
    """Update API keys at runtime and persist to .env."""
    from clrinsights.llm import update_api_key
    from pathlib import Path
    import re

    provider = body.get("provider")
    key = body.get("key", "").strip()
    if not provider or not key:
        raise HTTPException(status_code=400, detail="provider and key required")

    # Update live client
    try:
        update_api_key(provider, key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Persist to .env
    env_path = Path(__file__).parent / ".env"
    env_var = "GEMINI_API_KEY" if provider == "gemini" else "GROQ_API_KEY"
    if env_path.exists():
        content = env_path.read_text()
        pattern = rf'^{env_var}\s*=.*$'
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f'{env_var}={key}', content, flags=re.MULTILINE)
        else:
            content += f'\n{env_var}={key}\n'
        env_path.write_text(content)
    else:
        env_path.write_text(f'{env_var}={key}\n')

    return {"status": "updated", "provider": provider}


@app.get("/settings/keys")
async def get_keys():
    """Return masked API keys so the frontend can show status."""
    def mask(k: str) -> str:
        if not k or len(k) < 8:
            return ""
        return k[:4] + "•" * (len(k) - 8) + k[-4:]

    return {
        "gemini": mask(settings.gemini_api_key),
        "groq": mask(settings.groq_api_key),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info"
    )
