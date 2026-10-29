import re
from datetime import date, timedelta

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from config import settings
from src.generation.prompts import (
    ABSTAIN,
    REWRITE_PROMPT,
    SYSTEM_PROMPT,
    user_message,
)
from src.providers import build_config, get_llm
from src.retrieval.citation_formatter import location_label, source_name
from src.vector.vector_retriever import retrieve_documents


HISTORY_MESSAGES = 4

HISTORY_MESSAGE_CHARS = 600

SNIPPET_CHARS = 400

# Words that usually mean the question depends on earlier turns.
FOLLOW_UP = re.compile(
    r"\b(it|its|it's|they|them|their|theirs|this|that|these|those|he|she|"
    r"him|her|his|hers|there|same|above|previous|former|latter|else)\b"
    r"|^\s*(and|also|what about|how about|why|more|then)\b",
    re.IGNORECASE,
)


RELATIVE_DAYS = {
    "day before yesterday": -2,
    "yesterday": -1,
    "today": 0,
    "tomorrow": 1,
}

RELATIVE_DAY = re.compile(
    r"\b(" + "|".join(RELATIVE_DAYS) + r")\b",
    re.IGNORECASE,
)


def with_absolute_dates(query: str, today: date | None = None) -> str:
    """
    Sources store dates (2026-10-28), not "yesterday". Append the date the
    word means so keyword search can match it.
    """

    match = RELATIVE_DAY.search(query)

    if not match:
        return query

    today = today or date.today()
    day = today + timedelta(days=RELATIVE_DAYS[match.group(1).lower()])

    return f"{query} {day.isoformat()}"


def needs_rewrite(question: str) -> bool:
    return bool(FOLLOW_UP.search(question)) or len(question.split()) <= 3


def rewrite_query(config, question: str, history: list[dict]) -> str:
    """Turn a follow-up ("what about its budget?") into a standalone query."""

    if not settings.QUERY_REWRITE or not history or not needs_rewrite(question):
        return question

    transcript = "\n".join(
        f"{message['role'].upper()}: {message['content'][:500]}"
        for message in history[-4:]
    )

    try:
        response = get_llm(config).invoke(
            REWRITE_PROMPT.format(history=transcript, question=question)
        )
    except Exception:
        return question

    rewritten = str(response.content).strip().strip('"').splitlines()

    if not rewritten or not rewritten[0].strip() or len(rewritten[0]) > 300:
        return question

    return rewritten[0].strip()


def limit_context(documents, max_chars: int):
    """Best-first documents until the evidence budget is used (always >= 1)."""

    kept = []
    used = 0

    for document in documents:

        size = len(document.page_content)

        if kept and used + size > max_chars:
            break

        kept.append(document)
        used += size

    return kept


def to_sources(documents) -> list[dict]:
    """Numbered evidence entries; numbers match the [n] citations."""

    sources = []

    for number, document in enumerate(documents, start=1):

        metadata = document.metadata

        sources.append(
            {
                "n": number,
                "source_id": metadata.get("source_id"),
                "name": source_name(metadata),
                "location": location_label(metadata),
                "file_type": metadata.get("file_type"),
                "page": metadata.get("page"),
                "start_time": metadata.get("start_time"),
                "url": metadata.get("url"),
                "youtube_id": metadata.get("youtube_id"),
                "score": round(
                    float(
                        metadata.get(
                            "rerank_score",
                            metadata.get("rrf_score", 0.0),
                        )
                    ),
                    4,
                ),
                "snippet": document.page_content[:SNIPPET_CHARS],
                "text": document.page_content,
            }
        )

    return sources


def build_messages(question: str, sources: list[dict], history: list[dict]):

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    for message in history[-HISTORY_MESSAGES:]:

        content = message["content"][:HISTORY_MESSAGE_CHARS]

        if message["role"] == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message(question, sources)))

    return messages


def public_sources(sources: list[dict]) -> list[dict]:
    """Sources without the full chunk text (sent to the browser / stored)."""

    return [
        {key: value for key, value in source.items() if key != "text"}
        for source in sources
    ]


def stream_answer(config, search, question: str, history: list[dict] | None = None):
    """
    search(query) -> relevant Documents, best first.

    Yields events:
      {"type": "sources", "sources": [...]}
      {"type": "token", "text": "..."}
      {"type": "done", "answer": "..."}
    """

    history = history or []

    query = rewrite_query(config, question, history)

    documents = limit_context(
        search(with_absolute_dates(query), question),
        settings.MAX_CONTEXT_CHARS,
    )

    sources = to_sources(documents)

    yield {"type": "sources", "sources": public_sources(sources), "query": query}

    if not sources:
        yield {"type": "token", "text": ABSTAIN}
        yield {"type": "done", "answer": ABSTAIN}
        return

    # Earlier turns only help follow-ups; for standalone questions they
    # cost prompt time and distract small local models.
    context_history = history if needs_rewrite(question) else []

    answer = []

    for chunk in get_llm(config).stream(build_messages(question, sources, context_history)):

        text = chunk.content if isinstance(chunk.content, str) else ""

        if text:
            answer.append(text)
            yield {"type": "token", "text": text}

    text = "".join(answer).strip()

    done = {"type": "done", "answer": text}

    # The model looked at the evidence and found nothing relevant:
    # don't present those passages as sources.
    if text.startswith(ABSTAIN[:30]):
        done["sources"] = []

    yield done


def generate_answer(
    vector_store,
    question: str,
    k: int = 5,
    chunks=None,
    chat_history=None,
    bm25_retriever=None,
    config=None,
):
    """Non-streaming answer (used by app.py)."""

    config = config or build_config()

    def search(query, original):
        return retrieve_documents(
            vector_store,
            query,
            k=k,
            expanded_queries=[original],
            bm25_retriever=bm25_retriever,
        )

    sources = []
    documents = []
    answer = ""

    for event in stream_answer(config, search, question, chat_history):

        if event["type"] == "sources":
            sources = event["sources"]

        if event["type"] == "done":
            answer = event["answer"]

    return {
        "answer": answer,
        "sources": sources,
        "documents": documents,
    }
