import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_dir=str(tmp_path / "storage"),
        max_recipients=50,
    )
    # TestClient runs FastAPI background tasks before returning the response,
    # so by the time .post() returns, generation has finished.
    with TestClient(create_app(settings)) as c:
        yield c


def make_payload(recipients):
    return {
        "certificate": {
            "title": "Certificate of Completion",
            "event_name": "Python Bootcamp 2026",
            "issuer": "Acme Academy",
            "issue_date": "2026-10-01",
        },
        "recipients": recipients,
    }
