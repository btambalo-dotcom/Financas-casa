
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"sslmode": "require"} if DATABASE_URL and DATABASE_URL.startswith("postgres") else {}
)

SessionLocal = scoped_session(sessionmaker(bind=engine))

def get_session():
    return SessionLocal()

def safe_execute(fn):
    def wrapper(*args, **kwargs):
        session = get_session()
        try:
            return fn(session, *args, **kwargs)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    return wrapper
