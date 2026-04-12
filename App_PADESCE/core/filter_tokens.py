from __future__ import annotations

from django.core import signing

FILTER_TOKEN_SALT = "padesce-filter-choice"


def build_filter_token(scope: str, value: str) -> str:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    return signing.dumps(
        {"scope": str(scope or "").strip(), "value": normalized_value},
        salt=FILTER_TOKEN_SALT,
        compress=True,
    )


def resolve_filter_token(scope: str, token_or_value: str) -> str:
    normalized_input = str(token_or_value or "").strip()
    if not normalized_input:
        return ""
    try:
        payload = signing.loads(normalized_input, salt=FILTER_TOKEN_SALT)
    except signing.BadSignature:
        return normalized_input
    if str(payload.get("scope") or "").strip() != str(scope or "").strip():
        return normalized_input
    resolved_value = str(payload.get("value") or "").strip()
    return resolved_value or normalized_input


def build_tokenized_filter_choices(scope: str, values) -> list[dict[str, str]]:
    return [
        {"label": normalized_value, "value": build_filter_token(scope, normalized_value)}
        for normalized_value in [str(value or "").strip() for value in values]
        if normalized_value
    ]
