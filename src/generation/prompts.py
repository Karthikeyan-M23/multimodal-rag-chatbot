from langchain_core.prompts import ChatPromptTemplate


ABSTAIN = "The information is not available in the uploaded sources."


SYSTEM_PROMPT = f"""You are a precise assistant that answers questions using ONLY the numbered sources provided by the user's knowledge base.

Rules:
- Use only facts stated in the sources. Never use outside knowledge or guess.
- Cite every factual sentence with the source number in square brackets, e.g. [1] or [2][3].
- If the sources do not contain the answer, reply exactly: "{ABSTAIN}"
- If the sources only partly answer the question, answer that part and say what is missing.
- Be direct and concise. Use short paragraphs or bullet lists; use a table only for comparisons.
- Answer in the same language as the question."""


def format_evidence(sources: list[dict]) -> str:

    blocks = []

    for source in sources:
        heading = f"[{source['n']}] {source['name']}"

        if source.get("location"):
            heading += f" — {source['location']}"

        blocks.append(f"{heading}\n{source['text']}")

    return "\n\n---\n\n".join(blocks)


def user_message(question: str, sources: list[dict]) -> str:

    return (
        f"Sources:\n\n{format_evidence(sources)}\n\n"
        f"Question: {question}\n\n"
        "Answer using only the sources above, with [n] citations."
    )


REWRITE_PROMPT = """Rewrite the latest question so it can be understood without the conversation.

Rules:
- Only replace pronouns or vague references (it, its, they, that, he, she...) with what they refer to in the conversation.
- If the question already makes sense on its own, or is about a new topic, return it unchanged.
- Never add topics, names or details that the question does not refer to.
- Output ONLY the rewritten question.

Conversation:
{history}

Latest question: {question}

Rewritten question:"""


# Kept for app.py (Streamlit) compatibility.
RAG_PROMPT = ChatPromptTemplate.from_template(
    SYSTEM_PROMPT + "\n\nEvidence:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"
)
