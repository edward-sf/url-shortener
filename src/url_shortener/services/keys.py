import hashlib
import hmac
import re
import secrets
import string
from dataclasses import dataclass

KEY_PREFIX = "sk_"
PUBLIC_LENGTH = 8
SECRET_LENGTH = 32

_BASE62 = string.digits + string.ascii_letters
_KEY_PATTERN = re.compile(r"(?P<prefix>sk_[0-9A-Za-z]{8})_[0-9A-Za-z]{32}")


@dataclass(frozen=True, slots=True)
class GeneratedKey:
    """A newly generated API key and the values to store for it."""

    full_key: str
    prefix: str
    key_hash: str


def _random_base62(length: int) -> str:
    return "".join(secrets.choice(_BASE62) for _ in range(length))


def hash_key(full_key: str) -> str:
    """Return the SHA-256 hex digest stored in place of the key."""
    return hashlib.sha256(full_key.encode()).hexdigest()


def generate_key() -> GeneratedKey:
    """Generate a key shaped like ``sk_<8 public chars>_<32 secret chars>``."""
    prefix = KEY_PREFIX + _random_base62(PUBLIC_LENGTH)
    full_key = f"{prefix}_{_random_base62(SECRET_LENGTH)}"
    return GeneratedKey(full_key=full_key, prefix=prefix, key_hash=hash_key(full_key))


def parse_prefix(candidate: str) -> str | None:
    """Return the lookup prefix of a well-formed key, or None if it is malformed."""
    match = _KEY_PATTERN.fullmatch(candidate)
    return match["prefix"] if match else None


def key_matches(full_key: str, stored_hash: str) -> bool:
    """Check a presented key against a stored hash in constant time."""
    return hmac.compare_digest(hash_key(full_key), stored_hash)
