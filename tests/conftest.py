import os
from dotenv import load_dotenv
import pytest

load_dotenv()

# Global MongoDB client to be shared across all test sessions
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

        # Test connection
        _mongo_client.admin.command("ping")
    except Exception as exc:
        pytest.skip(f"Mongo unavailable: {exc}")

    yield

    # Don't close the client here - let it persist for all tests


def pytest_configure(config):
    """Pytest hook to initialize MongoDB before tests."""
    global _mongo_client, _db

    try:
        from src.utils.database_helper import client, db
        _mongo_client = client
        _db = db

        # Verify connection
        _mongo_client.admin.command("ping")
    except Exception as exc:
        pass  # Will be skipped in individual tests


@pytest.fixture(autouse=True)
def ensure_mongo_client():
    """Ensure MongoDB client is available for each test."""
    if _mongo_client is None:
        pytest.skip("MongoDB client not initialized")
    yield

