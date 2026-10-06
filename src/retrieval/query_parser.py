import re


DATE_PATTERN = re.compile(r"(?<!\d)(20\d{6})(?!\d)")

ENVIRONMENT_ALIASES = {
    "continuous integration": "ci",
    "ci": "ci",
    "axqa": "axqa",
    "tpqa": "tpqa",
}

NEGATIVE_STATUS = (
    "not executed",
    "not run",
    "failed",
    "pending",
    "not deployed",
)

POSITIVE_STATUS = (
    "executed",
    "execute",
    "deployed",
    "successful",
    "success",
    "ran",
    "run",
)

COUNT_TERMS = (
    "how many",
    "count",
    "number of",
)

LIST_TERMS = (
    "which",
    "what",
    "list",
    "show",
    "files",
    "scripts",
)


def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def extract_date(query: str) -> str | None:
    match = DATE_PATTERN.search(query)
    return match.group(1) if match else None


def extract_environment(query: str) -> str | None:
    normalized = normalize_query(query)

    for alias in sorted(
        ENVIRONMENT_ALIASES,
        key=len,
        reverse=True,
    ):
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return ENVIRONMENT_ALIASES[alias]

    return None


def extract_status(query: str) -> str | None:
    normalized = normalize_query(query)

    for term in NEGATIVE_STATUS:
        if term in normalized:
            return "not_executed"

    for term in POSITIVE_STATUS:
        if re.search(rf"\b{re.escape(term)}\b", normalized):
            return "executed"

    return None


def extract_intent(query: str) -> str:
    normalized = normalize_query(query)

    if any(term in normalized for term in COUNT_TERMS):
        return "count"

    if any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in LIST_TERMS
    ):
        return "list"

    return "lookup"


def parse_structured_query(query: str) -> dict:
    parsed = {
        "original_query": query,
        "normalized_query": normalize_query(query),
        "date": extract_date(query),
        "environment": extract_environment(query),
        "status": extract_status(query),
        "intent": extract_intent(query),
    }

    parsed["is_structured"] = any(
        [
            parsed["date"],
            parsed["environment"],
            parsed["status"],
        ]
    )

    return parsed
