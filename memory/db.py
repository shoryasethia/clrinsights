"""
MongoDB client initialisation (Motor async driver).
Import `db` anywhere in the app to get a handle to the clrinsights database.
"""
import certifi
import motor.motor_asyncio
from clrinsights.config import settings

_client = motor.motor_asyncio.AsyncIOMotorClient(
    settings.mongodb_uri,
    tlsCAFile=certifi.where()
)
db = _client["clrinsights"]
