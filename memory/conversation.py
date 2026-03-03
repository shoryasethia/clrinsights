"""
Conversation history stored in MongoDB Atlas (Motor async driver).

Each session is a single document in the `sessions` collection:
{
  "session_id": str,
  "title": str,
  "created_at": str  (ISO),
  "updated_at": str  (ISO),
  "messages": [...],
  "traces": [...],
  "visualizations": [...]   # list of base64 PNG strings
}
"""
from datetime import datetime
from clrinsights.memory.db import db


def _col():
    return db["sessions"]


class ConversationHistory:
    """Async-backed conversation session stored in MongoDB."""

    def __init__(self, session_id: str, max_messages: int = 50):
        self.session_id = session_id
        self.max_messages = max_messages
        self.messages: list[dict] = []
        self.title: str = "New Conversation"
        self.created_at: str = datetime.now().isoformat()
        self.updated_at: str = self.created_at
        self._traces: list = []
        self._visualizations: list = []

    # ------------------------------------------------------------------
    # Factory – always use this instead of __init__ directly
    # ------------------------------------------------------------------
    @classmethod
    async def load(cls, session_id: str, max_messages: int = 50) -> "ConversationHistory":
        """Load from MongoDB or return a fresh session."""
        obj = cls(session_id, max_messages)
        doc = await _col().find_one({"session_id": session_id}, {"_id": 0})
        if doc:
            obj.title = doc.get("title", "New Conversation")
            obj.created_at = doc.get("created_at", obj.created_at)
            obj.updated_at = doc.get("updated_at", obj.updated_at)
            obj.messages = doc.get("messages", [])
            obj._traces = doc.get("traces", [])
            obj._visualizations = doc.get("visualizations", [])
        return obj

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def _save(self) -> None:
        """Upsert the full session document."""
        self.updated_at = datetime.now().isoformat()
        doc = {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": self.messages,
            "traces": self._traces,
            "visualizations": self._visualizations,
        }
        await _col().replace_one({"session_id": self.session_id}, doc, upsert=True)

    # ------------------------------------------------------------------
    # Public API (mirroring the old file-based interface)
    # ------------------------------------------------------------------
    async def add_message(self, role: str, content: str, **extra) -> None:
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if extra.get("visualizations"):
            msg["visualizations"] = extra["visualizations"]
        if extra.get("trace"):
            msg["trace"] = extra["trace"]
        if extra.get("error"):
            msg["error"] = extra["error"]
        if extra.get("sql_queries"):
            msg["sql_queries"] = extra["sql_queries"]

        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        await self._save()

    async def save_response(self, result: dict) -> None:
        """Persist trace + visualizations from an agent result dict."""
        trace = result.get("trace", [])
        if trace:
            self._traces.append(trace)
        for v in result.get("visualizations", []):
            if v:
                self._visualizations.append(v)
        await self._save()

    async def set_title(self, title: str) -> None:
        self.title = title
        await self._save()

    def get_messages(self) -> list[dict]:
        return self.messages

    def get_meta(self) -> dict:
        return {
            "id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
        }

    def get_context_string(self, max_chars: int = 2000) -> str:
        context: list[str] = []
        total = 0
        for msg in reversed(self.messages):
            s = f"{msg['role']}: {msg['content']}\n"
            if total + len(s) > max_chars:
                break
            context.insert(0, s)
            total += len(s)
        return "\n".join(context)

    async def delete(self) -> None:
        await _col().delete_one({"session_id": self.session_id})

    async def delete_message(self, index: int) -> bool:
        """Delete a message pair from the session history."""
        if 0 <= index < len(self.messages):
            num_to_delete = 1
            if self.messages[index]["role"] == "user":
                if index + 1 < len(self.messages) and self.messages[index + 1]["role"] == "assistant":
                    num_to_delete = 2
            elif self.messages[index]["role"] == "assistant":
                if index - 1 >= 0 and self.messages[index - 1]["role"] == "user":
                    index -= 1
                    num_to_delete = 2
            
            del self.messages[index:index + num_to_delete]
            await self._save()
            return True
        return False


# ---------------------------------------------------------------------------
# In-memory cache + module-level helpers (same names as the old file-based API)
# ---------------------------------------------------------------------------
_session_cache: dict[str, ConversationHistory] = {}


async def get_or_create_session(session_id: str) -> ConversationHistory:
    if session_id not in _session_cache:
        _session_cache[session_id] = await ConversationHistory.load(session_id)
    return _session_cache[session_id]


async def list_all_sessions() -> list[dict]:
    cursor = _col().find(
        {},
        {"session_id": 1, "title": 1, "created_at": 1, "updated_at": 1, "_id": 0},
    ).sort("updated_at", -1)
    sessions = []
    async for doc in cursor:
        sessions.append({
            "id": doc.get("session_id", ""),
            "title": doc.get("title", "Untitled"),
            "created_at": doc.get("created_at", ""),
            "updated_at": doc.get("updated_at", ""),
        })
    return sessions


async def delete_session(session_id: str) -> bool:
    session = await get_or_create_session(session_id)
    await session.delete()
    _session_cache.pop(session_id, None)
    return True
