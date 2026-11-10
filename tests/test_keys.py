import hashlib
import re

import pytest

from url_shortener.services.keys import generate_key, key_matches, parse_prefix

KEY_FORMAT = re.compile(r"sk_[0-9A-Za-z]{8}_[0-9A-Za-z]{32}")
VALID_SECRET = "a" * 32


def test_generated_key_has_expected_format() -> None:
    key = generate_key()

    assert KEY_FORMAT.fullmatch(key.full_key)
    assert len(key.prefix) == 11
    assert key.full_key.startswith(key.prefix + "_")


def test_generated_keys_are_unique() -> None:
    keys = {generate_key().full_key for _ in range(100)}

    assert len(keys) == 100


def test_hash_is_sha256_hex_of_full_key() -> None:
    key = generate_key()

    assert key.key_hash == hashlib.sha256(key.full_key.encode()).hexdigest()
    assert len(key.key_hash) == 64


def test_parse_prefix_returns_prefix_of_valid_key() -> None:
    key = generate_key()

    assert parse_prefix(key.full_key) == key.prefix


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "sk_abcdefgh",
        f"pk_abcdefgh_{VALID_SECRET}",
        f"sk_abcdefg_{VALID_SECRET}",
        f"sk_abcdefgh-{VALID_SECRET}",
        f"sk_abcdefgh_{VALID_SECRET[:-1]}",
        f"sk_abcdefgh_{VALID_SECRET}a",
        f"sk_abcdefgh_{VALID_SECRET[:-1]}!",
        f"sk_abcdefgh_{VALID_SECRET}\n",
        f"sk_abcdefgh_{VALID_SECRET[:-1]}٣",
    ],
)
def test_parse_prefix_rejects_malformed_keys(candidate: str) -> None:
    assert parse_prefix(candidate) is None


def test_key_matches_its_own_hash() -> None:
    key = generate_key()

    assert key_matches(key.full_key, key.key_hash)


def test_key_does_not_match_another_keys_hash() -> None:
    key, other = generate_key(), generate_key()

    assert not key_matches(key.full_key, other.key_hash)
