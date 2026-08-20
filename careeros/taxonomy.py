from __future__ import annotations

from careeros.models import DeliveryRecord

_TAG_PREFIXES: dict[str, str] = {
    "impact": "[Impact]",
    "community": "[Community]",
    "delivery": "[Delivery]",
    "kudos": "[Kudos]",
}

_CONTEXT_BY_TAG: dict[str, str] = {
    "impact": "impact",
    "community": "community",
    "delivery": "delivery",
    "kudos": "kudos",
    "mentoring": "community",
}


def classify_context(record: DeliveryRecord) -> str:
    for tag in record.tags:
        normalized = tag.lower()
        if normalized in _CONTEXT_BY_TAG:
            return _CONTEXT_BY_TAG[normalized]
    if record.title.startswith("["):
        bracket = record.title.split("]", 1)[0].lower()
        for context, prefix in _TAG_PREFIXES.items():
            if prefix.lower() == f"{bracket}]":
                return context
    return "delivery"


def normalize_delivery_prefix(title: str, *, tags: tuple[str, ...]) -> str:
    if title.startswith("["):
        return title
    primary_tag = tags[0].lower() if tags else "delivery"
    prefix = _TAG_PREFIXES.get(primary_tag, "[Delivery]")
    return f"{prefix} {title}"


def apply_confidence_cap(record: DeliveryRecord) -> str:
    if record.confidence is None:
        return "partial"
    if record.confidence == "complete" and not record.evidence:
        return "partial"
    return record.confidence
