from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Department:
    department_id: Optional[int]
    name: str
    code: str
    created_at: Optional[datetime] = None


@dataclass
class User:
    user_id: Optional[int]
    name: str
    email: str
    password_hash: str
    department_id: Optional[int] = None
    role: str = "staff"
    created_at: Optional[datetime] = None


@dataclass
class HospitalDocument:
    document_id: Optional[int]
    title: str
    source_type: str
    original_filename: str
    file_hash: str
    department_id: Optional[int] = None
    uploaded_by: Optional[int] = None
    status: str = "pending"
    error_message: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None


@dataclass
class DocumentChunk:
    chunk_id: Optional[int]
    document_id: int
    chunk_index: int
    content: str
    content_hash: str
    token_count: int
    embedding_model: str
    created_at: Optional[datetime] = None


@dataclass
class Conversation:
    conversation_id: Optional[int]
    user_id: int
    title: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class Message:
    message_id: Optional[int]
    conversation_id: int
    role: str
    content: str
    created_at: Optional[datetime] = None
