import mongoengine
from src.core.config import settings

def init_db():
    mongoengine.connect(
        db=settings.DB_NAME,
        host=settings.MONGODB_URI
    )

def close_db():
    mongoengine.disconnect()
