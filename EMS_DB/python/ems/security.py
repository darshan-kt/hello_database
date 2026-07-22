import hashlib


def hash_password(raw: str) -> str:
    """SHA-256 for demo simplicity, shared by the API and the seed data
    generator so demo accounts actually log in. A real system would use
    bcrypt/argon2 with a per-user salt -- see the README's design notes."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
