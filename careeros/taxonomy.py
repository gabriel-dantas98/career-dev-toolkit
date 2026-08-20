from __future__ import annotations

from careeros.models import DeliveryRecord

TAG_PREFIXES: dict[str, str] = {
    "impact": "[Impact]",
    "community": "[Community]",
    "delivery": "[Delivery]",
    "kudos": "[Kudos]",
}

CONTEXT_BY_TAG: dict[str, str] = {
    "impact": "impact",
    "community": "community",
    "delivery": "delivery",
    "kudos": "kudos",
    "mentoring": "community",
}


def prefix_for_tag(tag: str) -> str:
    return TAG_PREFIXES.get(tag.lower(), "[Delivery]")


def context_for_prefix(prefix: str) -> str | None:
    for context, expected_prefix in TAG_PREFIXES.items():
        if prefix == expected_prefix:
            return context
    return None


def classify_context(record: DeliveryRecord) -> str:
    for tag in record.tags:
        normalized = tag.lower()
        if normalized in CONTEXT_BY_TAG:
            return CONTEXT_BY_TAG[normalized]
    if record.title.startswith("["):
        closing = record.title.find("]")
        if closing != -1:
            context = context_for_prefix(record.title[: closing + 1])
            if context is not None:
                return context
    return "delivery"


def normalize_delivery_prefix(title: str, *, tags: tuple[str, ...]) -> str:
    if title.startswith("["):
        return title
    primary_tag = tags[0].lower() if tags else "delivery"
    return f"{prefix_for_tag(primary_tag)} {title}"


def apply_confidence_cap(record: DeliveryRecord) -> str:
    if record.confidence is None:
        return "partial"
    if record.confidence == "complete" and not record.evidence:
        return "partial"
    return record.confidence
