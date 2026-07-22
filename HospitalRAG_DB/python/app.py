"""
FastAPI app + static UI host for the Hospital AI Knowledge Assistant.

Thin HTTP layer over the repository/service classes in `rag/` -- routes
translate requests into service calls and domain exceptions into HTTP
status codes; no RAG logic lives here. Two roles: staff (ask questions,
own conversation history) and admin (manage departments/documents, run
the evaluation harness, view the audit log). Login is demo-mode
permissive, same as mini_EcommerceDB and EMS_DB -- see
docs/01_requirements.md.
"""
import dataclasses
import hashlib
import os
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from rag.exceptions import (
    DuplicateDocumentError,
    DuplicateEmailError,
    EmptyDocumentError,
    LLMGenerationError,
    NotFoundError,
    RAGError,
    UnsupportedDocumentTypeError,
)
from rag.repositories.audit_repository import AuditRepository
from rag.repositories.chunk_repository import ChunkRepository
from rag.repositories.conversation_repository import ConversationRepository
from rag.repositories.department_repository import DepartmentRepository
from rag.repositories.document_repository import DocumentRepository
from rag.repositories.message_repository import MessageRepository
from rag.repositories.user_repository import UserRepository
from rag.security import hash_password
from rag.services.chat_service import ChatService
from rag.services.evaluation_service import EvalCase, EvaluationService
from rag.services.ingestion_service import IngestionService

load_dotenv()

app = FastAPI(title="Hospital AI Knowledge Assistant")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "dev-secret-change-me"))

departments = DepartmentRepository()
users = UserRepository()
documents = DocumentRepository()
chunks = ChunkRepository()
conversations = ConversationRepository()
messages = MessageRepository()
audit = AuditRepository()

ingestion_service = IngestionService()
chat_service = ChatService()
evaluation_service = EvaluationService()

EXTENSION_TO_SOURCE_TYPE = {".pdf": "pdf", ".txt": "txt", ".md": "markdown", ".markdown": "markdown"}


def _json_safe(value):
    if dataclasses.is_dataclass(value):
        return {k: _json_safe(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def ok(value):
    return JSONResponse(content=_json_safe(value))


# ---------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------
def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"user_id": user_id, "role": request.session.get("role", "staff")}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------
# Domain error -> HTTP status mapping
# ---------------------------------------------------------------------
@app.exception_handler(RAGError)
async def handle_domain_error(request: Request, exc: RAGError):
    status = 400
    if isinstance(exc, (DuplicateEmailError, DuplicateDocumentError)):
        status = 409
    elif isinstance(exc, NotFoundError):
        status = 404
    elif isinstance(exc, (UnsupportedDocumentTypeError, EmptyDocumentError)):
        status = 400
    elif isinstance(exc, LLMGenerationError):
        status = 502
    return JSONResponse(status_code=status, content={"error": str(exc), "type": type(exc).__name__})


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
@app.post("/api/auth/register")
def register(request: Request, body: dict):
    name, email, password = body.get("name"), body.get("email"), body.get("password")
    department_id = body.get("department_id")
    if not all([name, email, password]):
        raise HTTPException(status_code=400, detail="name, email and password are required")
    user_id = users.create(name, email, hash_password(password), department_id=department_id)
    request.session["user_id"] = user_id
    request.session["role"] = "staff"
    return ok({"user_id": user_id, "name": name, "email": email})


def _display_name_from_email(email: str) -> str:
    return email.split("@")[0].replace(".", " ").replace("_", " ").title() or "Guest"


@app.post("/api/auth/login")
def login(request: Request, body: dict):
    """Demo mode: any email/password logs you in. If the email doesn't
    belong to an existing account, one is created on the spot -- see
    docs/01_requirements.md."""
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    user = users.get_by_email(email)
    if user is None:
        try:
            users.create(_display_name_from_email(email), email, hash_password(password))
        except DuplicateEmailError:
            pass
        user = users.get_by_email(email)

    request.session["user_id"] = user.user_id
    request.session["role"] = user.role
    return ok({"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role})


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return ok({"ok": True})


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    record = users.get_by_id(user["user_id"])
    if record is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return ok(
        {
            "user_id": record.user_id,
            "name": record.name,
            "email": record.email,
            "role": record.role,
            "department_id": record.department_id,
        }
    )


# ---------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------
@app.get("/api/departments")
def list_departments():
    return ok([dataclasses.asdict(d) for d in departments.list_all()])


@app.post("/api/departments")
def create_department(body: dict, _admin: dict = Depends(require_admin)):
    department_id = departments.create(body.get("name"), body.get("code"))
    return ok({"department_id": department_id})


# ---------------------------------------------------------------------
# Documents (Module 4-5: ingestion)
# ---------------------------------------------------------------------
@app.get("/api/documents")
def list_documents(department_id: Optional[int] = None, _admin: dict = Depends(require_admin)):
    items = documents.list_by_department(department_id) if department_id else documents.list_all()
    return ok([dataclasses.asdict(d) for d in items])


@app.post("/api/documents")
async def upload_document(
    file: UploadFile = File(...),
    department_id: Optional[int] = Form(None),
    admin: dict = Depends(require_admin),
):
    extension = Path(file.filename).suffix.lower()
    source_type = EXTENSION_TO_SOURCE_TYPE.get(extension)
    if source_type is None:
        raise UnsupportedDocumentTypeError(
            f"Unsupported file extension '{extension}'. Supported: .pdf, .txt, .md"
        )

    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    document_id = documents.create(
        title=file.filename,
        source_type=source_type,
        original_filename=file.filename,
        file_hash=file_hash,
        department_id=department_id,
        uploaded_by=admin["user_id"],
    )
    result = ingestion_service.ingest(document_id, file_bytes, source_type)
    audit.record(
        admin["user_id"],
        "upload_document",
        {"document_id": document_id, "filename": file.filename, **result},
    )
    return ok({"document_id": document_id, **result})


@app.get("/api/documents/{document_id}")
def get_document(document_id: int, _admin: dict = Depends(require_admin)):
    document = documents.get_by_id(document_id)
    if document is None:
        raise NotFoundError("Document", document_id)
    return ok(dataclasses.asdict(document))


@app.get("/api/documents/{document_id}/chunks")
def get_document_chunks(document_id: int, _admin: dict = Depends(require_admin)):
    return ok(chunks.list_by_document(document_id))


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int, admin: dict = Depends(require_admin)):
    documents.delete(document_id)
    audit.record(admin["user_id"], "delete_document", {"document_id": document_id})
    return ok({"ok": True})


# ---------------------------------------------------------------------
# Chat (Module 6-9: retrieve -> prompt -> generate -> remember)
# ---------------------------------------------------------------------
@app.post("/api/chat/ask")
def ask(body: dict, user: dict = Depends(get_current_user)):
    question = body.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    result = chat_service.ask(
        user_id=user["user_id"],
        question=question,
        conversation_id=body.get("conversation_id"),
        department_id=body.get("department_id"),
    )
    return ok(result)


@app.post("/api/chat/ask/stream")
def ask_stream(body: dict, user: dict = Depends(get_current_user)):
    """Server-Sent Events variant. The local provider simulates
    streaming (see LocalLLMProvider.stream); the OpenAI provider streams
    real tokens -- same endpoint, same wire format, different provider
    underneath."""
    question = body.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    conversation_id = chat_service.get_or_create_conversation(
        user["user_id"], body.get("conversation_id")
    )
    recent_turns = messages.list_recent_turns(conversation_id)
    is_first_question = not recent_turns
    chunk_results = chat_service.retriever.retrieve(
        question, department_id=body.get("department_id")
    )
    from rag.services.prompt_service import build_messages

    prompt_messages = build_messages(question, chunk_results, recent_turns=recent_turns)
    messages.create(conversation_id, "user", question)

    def event_source():
        # Same deterministic short-circuit as ChatService.ask() -- see
        # its comment for why this doesn't rely on the system prompt's
        # instruction alone. Streamed as a single SSE chunk so the UI
        # doesn't need a separate code path for the no-context case.
        if not chunk_results:
            from rag.services.chat_service import NO_CONTEXT_ANSWER

            yield f"data: {NO_CONTEXT_ANSWER}\n\n"
            full_answer = NO_CONTEXT_ANSWER
        else:
            collected = []
            for piece in chat_service.llm_provider.stream(prompt_messages):
                collected.append(piece)
                yield f"data: {piece}\n\n"
            full_answer = "".join(collected)
        assistant_message_id = messages.create(conversation_id, "assistant", full_answer)
        citations = [
            {"chunk_id": c["chunk_id"], "rank": i + 1, "similarity_score": round(float(c["similarity"]), 5)}
            for i, c in enumerate(chunk_results)
        ]
        messages.add_citations(assistant_message_id, citations)
        audit.record(
            user["user_id"],
            "ask_question",
            {"conversation_id": conversation_id, "question": question, "chunks_retrieved": len(chunk_results)},
        )
        if is_first_question:
            title = question[:80] + ("..." if len(question) > 80 else "")
            conversations.set_title(conversation_id, title)
        yield f"event: done\ndata: {conversation_id}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.get("/api/conversations")
def list_conversations(user: dict = Depends(get_current_user)):
    return ok(conversations.list_by_user(user["user_id"]))


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: int, user: dict = Depends(get_current_user)):
    conversation = conversations.get_by_id(conversation_id)
    if conversation is None or conversation["user_id"] != user["user_id"]:
        raise NotFoundError("Conversation", conversation_id)
    return ok(messages.list_by_conversation(conversation_id))


# ---------------------------------------------------------------------
# Evaluation (Module 10) & Audit
# ---------------------------------------------------------------------
@app.get("/api/evaluation/run")
def run_evaluation(_admin: dict = Depends(require_admin)):
    from scripts.eval_dataset import EVAL_CASES

    cases = [EvalCase(**c) for c in EVAL_CASES]
    return ok(evaluation_service.evaluate(cases))


@app.get("/api/audit")
def list_audit_log(_admin: dict = Depends(require_admin)):
    return ok(audit.list_recent())


# ---------------------------------------------------------------------
# Static UI (mounted last so it never shadows an /api/* route)
# ---------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
