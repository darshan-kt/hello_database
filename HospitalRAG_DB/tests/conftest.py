import pytest

from rag.db.connection import get_pool
from rag.repositories.chunk_repository import ChunkRepository
from rag.repositories.conversation_repository import ConversationRepository
from rag.repositories.department_repository import DepartmentRepository
from rag.repositories.document_repository import DocumentRepository
from rag.repositories.message_repository import MessageRepository
from rag.repositories.user_repository import UserRepository
from rag.security import hash_password

TABLES_IN_FK_ORDER = [
    "message_citations", "messages", "conversations", "audit_logs",
    "document_chunks", "hospital_documents", "users", "departments",
]


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate every table before each test so tests are independent of
    seed data and of each other."""
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {', '.join(TABLES_IN_FK_ORDER)} RESTART IDENTITY CASCADE")
        conn.commit()
    yield


class FakeLLMProvider:
    """A stand-in for the local/OpenAI providers -- instant and
    deterministic, so tests don't pay for a real (slow, CPU-bound)
    model call just to check that the orchestration around it is
    correct. Real generation is exercised manually / in the demo, not
    the automated suite -- see docs/04_interactive_learning.md."""

    model_name = "fake-model"

    def __init__(self, response: str = "This is a fake grounded answer [1]."):
        self.response = response
        self.calls: list[list[dict]] = []

    def generate(self, messages: list[dict], max_tokens: int = 300) -> dict:
        self.calls.append(messages)
        return {"content": self.response, "tokens_used": 42, "model": self.model_name}

    def stream(self, messages: list[dict], max_tokens: int = 300):
        self.calls.append(messages)
        for word in self.response.split(" "):
            yield word + " "


@pytest.fixture
def department_repo():
    return DepartmentRepository()


@pytest.fixture
def user_repo():
    return UserRepository()


@pytest.fixture
def document_repo():
    return DocumentRepository()


@pytest.fixture
def chunk_repo():
    return ChunkRepository()


@pytest.fixture
def conversation_repo():
    return ConversationRepository()


@pytest.fixture
def message_repo():
    return MessageRepository()


@pytest.fixture
def fake_llm():
    return FakeLLMProvider()


@pytest.fixture
def sample_department_id(department_repo):
    return department_repo.create("Test Department", "TESTDEPT")


@pytest.fixture
def sample_staff_id(user_repo, sample_department_id):
    return user_repo.create(
        "Test Staff", "staff@example.com", hash_password("x"),
        department_id=sample_department_id, role="staff",
    )


@pytest.fixture
def sample_admin_id(user_repo):
    return user_repo.create("Test Admin", "admin@example.com", hash_password("x"), role="admin")
