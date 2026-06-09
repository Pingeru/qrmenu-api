import os
from dotenv import load_dotenv
import pytest

load_dotenv()

_mongo_client = None
_db = None


@pytest.fixture(scope="session")
def mongo_setup():
    """Set up MongoDB connection for the entire test session."""
    global _mongo_client, _db

    try:
        from src.utils.database_helper import client, db
        _mongo_client = client
        _db = db

        _mongo_client.admin.command("ping")
    except Exception as exc:
        pytest.skip(f"Mongo unavailable: {exc}")

    yield



def pytest_configure(config):
    """Pytest hook to initialize MongoDB before tests."""
    global _mongo_client, _db

    try:
        from src.utils.database_helper import client, db
        _mongo_client = client
        _db = db

        _mongo_client.admin.command("ping")
    except Exception as exc:
        pass


@pytest.fixture(autouse=True)
def ensure_mongo_client():
    """Ensure MongoDB client is available for each test."""
    if _mongo_client is None:
        pytest.skip("MongoDB client not initialized")
    yield

