from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


def make_session_factory(database_url: str) -> sessionmaker:
    kwargs = {}
    if database_url.startswith("sqlite"):
        # Background tasks run in worker threads, so allow cross-thread use.
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
