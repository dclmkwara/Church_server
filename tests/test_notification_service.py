import inspect
import os
from pathlib import Path
import sys

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.notification_service import NotificationService


def test_notification_polling_has_bounded_bucket_limit():
    signature = inspect.signature(NotificationService.poll_new_data)

    assert "per_bucket_limit" in signature.parameters
    assert signature.parameters["per_bucket_limit"].default == 100


def test_notification_polling_avoids_concurrent_session_queries():
    source = inspect.getsource(NotificationService.poll_new_data)

    assert "asyncio.gather" not in source
    assert ".limit(per_bucket_limit)" in source
