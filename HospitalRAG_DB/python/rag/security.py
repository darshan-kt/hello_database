import hashlib


def hash_password(raw: str) -> str:
    """SHA-256 for demo simplicity, matching mini_EcommerceDB and
    EMS_DB. Login in this project is demo-mode-permissive (see
    docs/01_requirements.md) so this hash is barely load-bearing, but
    the field exists because a real system's would be."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
