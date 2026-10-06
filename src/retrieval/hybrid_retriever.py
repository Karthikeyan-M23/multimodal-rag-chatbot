import re


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_./-]+", text.lower()))


def lexical_score(query: str, text: str) -> float:
    q = _tokens(query)
    t = _tokens(text)

    if not q or not t:
        return 0.0

    overlap = len(q & t) / len(q)
    return min(overlap, 1.0)


def rank_chunks(query: str, chunks: list[dict], limit: int = 10):
    scored = []

    for chunk in chunks:
        score = lexical_score(
            query,
            chunk.get("text", ""),
        )

        metadata = chunk.get("metadata", {})
        script = str(metadata.get("git_script", "")).lower()

        if script and script in query.lower():
            score += 1.0

        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [chunk for score, chunk in scored[:limit] if score > 0]
